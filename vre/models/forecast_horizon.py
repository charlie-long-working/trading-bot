"""
Dự báo giá nhà theo tháng — horizon dài (vd. 08/2026 → 12/2027).

Phương pháp (tham khảo):
  1. Neo giá tại điểm quan sát gần nhất (property_prices.csv).
  2. Nội suy tới tháng bắt đầu bằng YoY gần nhất của từng vùng.
  3. Từ tháng bắt đầu: tăng trưởng tháng = momentum YoY (suy giảm dần) + điều chỉnh vĩ mô + chính sách.
  4. Kịch bản «+ chính sách»: cộng drift hàng tháng từ net impact chính sách 6 tháng.
"""

from __future__ import annotations

from typing import Optional

try:
    import pandas as pd
    import numpy as np
except ImportError:
    pd = None
    np = None

# YoY giảm 0.2 điểm % mỗi quý khi thị trường tăng (mean reversion)
YOY_DECAY_PER_QUARTER = 0.2
# Khi YoY âm: hồi phục +2 điểm % mỗi quý (điều chỉnh dần, không sụt mãi)
BEAR_RECOVERY_PP_PER_QUARTER = 2.0
# Trọng số điều chỉnh vĩ mô vào tốc độ tăng tháng
MACRO_GROWTH_WEIGHT = 0.25


def _yoy_to_monthly(yoy_pct: float) -> float:
    """Chuyển YoY % sang tăng trưởng tháng (compound)."""
    yoy = max(-30.0, min(40.0, float(yoy_pct)))
    return (1.0 + yoy / 100.0) ** (1.0 / 12.0) - 1.0


def _macro_monthly_growth(merged: Optional["pd.DataFrame"]) -> float:
    """Tốc độ tăng trung bình 12 tháng gần nhất của chỉ số giá (nếu có)."""
    if merged is None or pd is None or "property_index" not in merged.columns:
        return 0.0
    s = merged["property_index"].dropna()
    if len(s) < 6:
        return 0.0
    tail = s.iloc[-12:] if len(s) >= 12 else s
    if tail.iloc[0] == 0:
        return 0.0
    total = tail.iloc[-1] / tail.iloc[0] - 1.0
    months = max(1, len(tail) - 1)
    annual = (1.0 + total) ** (12.0 / months) - 1.0
    return annual / 12.0


def _policy_monthly_drift(policy_impact: Optional[dict]) -> float:
    if not policy_impact:
        return 0.0
    adj = float(policy_impact.get("adjustment_pct", 0.0)) / 100.0
    return adj / 12.0


def _bridge_to_date(
    price: float,
    yoy_pct: float,
    from_date: "pd.Timestamp",
    to_date: "pd.Timestamp",
) -> float:
    months = max(0, (to_date.year - from_date.year) * 12 + (to_date.month - from_date.month))
    g = _yoy_to_monthly(yoy_pct)
    return price * ((1.0 + g) ** months)


def forecast_regional_prices(
    property_df: Optional["pd.DataFrame"],
    merged: Optional["pd.DataFrame"] = None,
    model_result: Optional[dict] = None,
    policy_impact: Optional[dict] = None,
    start: str = "2026-08-01",
    end: str = "2027-12-01",
    base_year: int = 2015,
) -> Optional["pd.DataFrame"]:
    """
    Dự báo giá/m² theo vùng, tần suất tháng.

    Returns DataFrame:
      date, region, price_per_m2, price_per_m2_policy, yoy_implied,
      index_base, index_policy, is_forecast
    """
    if pd is None or np is None or property_df is None or len(property_df) == 0:
        return None

    start_dt = pd.Timestamp(start).replace(day=1)
    end_dt = pd.Timestamp(end).replace(day=1)
    if end_dt < start_dt:
        return None

    hist = property_df.copy()
    hist["date"] = pd.to_datetime(hist["date"])

    # Mốc 2015 cho chỉ số
    base_prices = hist[hist["date"].dt.year == base_year].groupby("region")["price_per_m2"].first()
    macro_g = _macro_monthly_growth(merged) * MACRO_GROWTH_WEIGHT
    policy_g = _policy_monthly_drift(policy_impact)

    # Điều chỉnh vĩ mô từ mô hình hồi quy (gap level → drift nhỏ hàng tháng)
    model_drift = 0.0
    if model_result is not None and merged is not None and "property_index" in merged.columns:
        try:
            from vre.models.trend_predictor import forecast_next_quarters
            latest = merged.iloc[[-1]]
            fc = forecast_next_quarters(model_result, latest, n_quarters=1)
            if fc is not None and len(fc) > 0:
                pred_idx = float(fc["predicted_index"].iloc[0])
                cur_idx = float(merged["property_index"].iloc[-1])
                if cur_idx > 0:
                    gap = (pred_idx - cur_idx) / cur_idx
                    model_drift = gap / 24.0  # hội tụ chậm ~2 năm
        except Exception:
            pass

    months = pd.date_range(start_dt, end_dt, freq="MS")
    rows = []

    for region in sorted(hist["region"].unique()):
        reg = hist[hist["region"] == region].sort_values("date")
        if len(reg) == 0:
            continue

        last = reg.iloc[-1]
        anchor_date = pd.Timestamp(last["date"]).replace(day=1)
        anchor_price = float(last["price_per_m2"])
        yoy = float(last.get("yoy_change", 10.0) or 10.0)

        # Sau đợt sụt mạnh (2 mốc gần nhất giảm >15% annualized): dự báo tiếp ở vùng đi ngang
        if len(reg) >= 2:
            prev = reg.iloc[-2]
            mspan = max(
                1,
                (anchor_date.year - pd.Timestamp(prev["date"]).year) * 12
                + anchor_date.month - pd.Timestamp(prev["date"]).month,
            )
            p0, p1 = float(prev["price_per_m2"]), anchor_price
            if p0 > 0:
                ann = ((p1 / p0) ** (12.0 / mspan) - 1.0) * 100.0
                if ann < -15.0:
                    yoy = max(-8.0, ann * 0.35)

        base_2015 = float(base_prices.get(region, anchor_price) or anchor_price)

        price = _bridge_to_date(anchor_price, yoy, anchor_date, start_dt)
        price_pol = price
        quarter_idx = 0

        for i, dt in enumerate(months):
            if i > 0:
                if yoy < 0:
                    yoy_eff = min(0.0, yoy + BEAR_RECOVERY_PP_PER_QUARTER * quarter_idx)
                else:
                    yoy_eff = max(0.0, yoy - YOY_DECAY_PER_QUARTER * quarter_idx)
                g = _yoy_to_monthly(yoy_eff) + macro_g + model_drift
                g_pol = g + policy_g
                price *= 1.0 + g
                price_pol *= 1.0 + g_pol
            if (i + 1) % 3 == 0:
                quarter_idx += 1

            rows.append({
                "date": dt,
                "region": region,
                "price_per_m2": round(price, 0),
                "price_per_m2_policy": round(price_pol, 0),
                "yoy_implied": round(
                    ((1.0 + _yoy_to_monthly(
                        min(0.0, yoy + BEAR_RECOVERY_PP_PER_QUARTER * quarter_idx) if yoy < 0
                        else max(0.0, yoy - YOY_DECAY_PER_QUARTER * quarter_idx)
                    )) ** 12 - 1) * 100,
                    1,
                ),
                "index_base": round(price / base_2015 * 100, 1),
                "index_policy": round(price_pol / base_2015 * 100, 1),
                "is_forecast": True,
            })

    if not rows:
        return None

    out = pd.DataFrame(rows)
    return out.sort_values(["date", "region"]).reset_index(drop=True)


def forecast_national_average(forecast_df: Optional["pd.DataFrame"]) -> Optional["pd.DataFrame"]:
    """Gộp dự báo vùng → bình quân cả nước."""
    if forecast_df is None or len(forecast_df) == 0:
        return None
    agg = forecast_df.groupby("date").agg({
        "price_per_m2": "mean",
        "price_per_m2_policy": "mean",
        "yoy_implied": "mean",
        "index_base": "mean",
        "index_policy": "mean",
    }).reset_index()
    agg["region"] = "National Avg"
    agg["is_forecast"] = True
    return agg


def build_horizon_forecast(
    property_df: Optional["pd.DataFrame"],
    merged: Optional["pd.DataFrame"] = None,
    model_result: Optional[dict] = None,
    policy_impact: Optional[dict] = None,
    start: str = "2026-08-01",
    end: str = "2027-12-01",
) -> dict:
    """
    Pipeline đầy đủ: regional + national + tóm tắt đầu/cuối kỳ.
    """
    regional = forecast_regional_prices(
        property_df, merged, model_result, policy_impact, start, end,
    )
    national = forecast_national_average(regional)

    summary = {}
    if national is not None and len(national) > 0:
        first = national.iloc[0]
        last = national.iloc[-1]
        summary = {
            "start": str(first["date"].date()),
            "end": str(last["date"].date()),
            "price_start_vnd": int(first["price_per_m2"]),
            "price_end_vnd": int(last["price_per_m2"]),
            "price_end_policy_vnd": int(last["price_per_m2_policy"]),
            "change_pct": round((last["price_per_m2"] / first["price_per_m2"] - 1) * 100, 1),
            "change_pct_policy": round((last["price_per_m2_policy"] / first["price_per_m2"] - 1) * 100, 1),
            "index_start": round(first["index_base"], 1),
            "index_end": round(last["index_base"], 1),
        }

    return {
        "regional": regional,
        "national": national,
        "summary": summary,
        "start": start,
        "end": end,
    }
