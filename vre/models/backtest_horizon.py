"""
Backtest walk-forward: so sánh dự báo giá nhà vs thực tế theo tháng.

Cửa sổ mặc định: 11/2025 → 08/2026.
- Thực tế quan sát: các mốc 6 tháng trong property_prices.csv.
- Thực tế nội suy: linear giữa các mốc quan sát.
- Thực tế ngoại suy: từ 01/2026 trở đi theo tốc độ implied Jul/2025→01/2026 (để so sánh khi chưa có mốc 07/2026).
"""

from __future__ import annotations

from typing import Optional

try:
    import pandas as pd
    import numpy as np
except ImportError:
    pd = None
    np = None

from vre.models.trend_predictor import (
    prepare_analysis_dataframe,
    build_regression_model,
)
from vre.models.forecast_horizon import forecast_regional_prices, forecast_national_average


def _build_property_index_from_hist(avg_df: "pd.DataFrame") -> Optional["pd.DataFrame"]:
    """Wrapper — build index từ national avg đã truncate."""
    if avg_df is None or len(avg_df) == 0:
        return None
    tmp = avg_df.copy()
    tmp = tmp.rename(columns={"price_per_m2": "price_per_m2"})
    tmp = tmp.set_index("date").resample("6MS").last().reset_index()
    base_rows = tmp[tmp["date"].dt.year == 2015]
    base_val = float(base_rows["price_per_m2"].iloc[0]) if len(base_rows) else float(tmp["price_per_m2"].iloc[0])
    if base_val == 0:
        base_val = 1.0
    tmp["value"] = tmp["price_per_m2"] / base_val * 100.0
    return tmp[["date", "value"]]


def build_monthly_actual(
    property_df: "pd.DataFrame",
    extend_through: Optional[str] = None,
) -> Optional["pd.DataFrame"]:
    """
    Chuỗi giá/m² hàng tháng từ quan sát + nội suy linear giữa các mốc 6 tháng.
    Columns: date, region, price_actual, actual_kind (observed|interpolated|extrapolated)
    """
    if pd is None or property_df is None or len(property_df) == 0:
        return None

    hist = property_df.copy()
    hist["date"] = pd.to_datetime(hist["date"])
    rows = []

    for region in sorted(hist["region"].unique()):
        reg = hist[hist["region"] == region].sort_values("date")
        if len(reg) < 2:
            continue

        observed_dates = set(pd.to_datetime(reg["date"]).dt.normalize())

        s = reg.set_index("date")["price_per_m2"].sort_index()
        end_cap = s.index.max() + pd.DateOffset(months=6)
        if extend_through:
            ext = pd.Timestamp(extend_through).replace(day=1)
            if ext > end_cap:
                end_cap = ext
        monthly_idx = pd.date_range(s.index.min(), end_cap, freq="MS")
        monthly = s.reindex(monthly_idx).interpolate(method="linear")

        # Ngoại suy sau mốc cuối (tốc độ implied 6 tháng cuối)
        last_obs = s.index.max()
        if len(s) >= 2:
            prev_obs = s.index[-2]
            months_span = max(1, (last_obs.year - prev_obs.year) * 12 + last_obs.month - prev_obs.month)
            g = (s.iloc[-1] / s.iloc[-2]) ** (1.0 / months_span) - 1.0
        else:
            g = 0.0

        for dt in monthly_idx:
            if pd.isna(monthly.get(dt)):
                continue
            price = float(monthly.loc[dt])
            dt_norm = pd.Timestamp(dt).normalize()
            if dt_norm in observed_dates or dt == s.index.max():
                kind = "observed"
            elif dt <= last_obs:
                kind = "interpolated"
            else:
                months_ahead = (dt.year - last_obs.year) * 12 + dt.month - last_obs.month
                price = float(s.iloc[-1]) * ((1.0 + g) ** months_ahead)
                kind = "extrapolated"

            rows.append({
                "date": pd.Timestamp(dt).replace(day=1),
                "region": region,
                "price_actual": round(price, 0),
                "actual_kind": kind,
            })

    if not rows:
        return None
    return pd.DataFrame(rows).sort_values(["date", "region"]).reset_index(drop=True)


def _truncate_fred(fred_monthly: "pd.DataFrame", before: "pd.Timestamp") -> "pd.DataFrame":
    f = fred_monthly.copy()
    f["date"] = pd.to_datetime(f["date"])
    return f[f["date"] < before].copy()


def _truncate_rates(rates: "pd.DataFrame", before: "pd.Timestamp") -> "pd.DataFrame":
    r = rates.copy()
    r["date"] = pd.to_datetime(r["date"])
    return r[r["date"] < before].copy()


def run_walk_forward_backtest(
    property_df: "pd.DataFrame",
    fred_monthly: "pd.DataFrame",
    vn_rates: Optional["pd.DataFrame"],
    start: str = "2025-11-01",
    end: str = "2026-08-01",
) -> Optional[dict]:
    """
    Mỗi tháng T trong [start, end]:
      - Chỉ dùng dữ liệu giá có date < T và macro date < T.
      - Dự báo giá tại tháng T (momentum + vĩ mô).
      - So với price_actual tại T.
    """
    if pd is None or np is None:
        return None

    start_dt = pd.Timestamp(start).replace(day=1)
    end_dt = pd.Timestamp(end).replace(day=1)
    actual_all = build_monthly_actual(property_df, extend_through=str(end_dt.date()))
    if actual_all is None:
        return None

    months = pd.date_range(start_dt, end_dt, freq="MS")

    rows = []
    for origin in months:
        hist = property_df.copy()
        hist["date"] = pd.to_datetime(hist["date"])
        hist = hist[hist["date"] < origin]
        if len(hist) < 5:
            continue

        fred_cut = _truncate_fred(fred_monthly, origin)
        rates_cut = _truncate_rates(vn_rates, origin) if vn_rates is not None else None

        nat_hist = hist.groupby("date")["price_per_m2"].mean().reset_index()
        prop_index = _build_property_index_from_hist(nat_hist)
        merged = prepare_analysis_dataframe(fred_cut, prop_index, rates_cut)
        model = build_regression_model(merged) if merged is not None else None

        pred_reg = forecast_regional_prices(
            hist, merged, model, policy_impact=None,
            start=str(origin.date()), end=str(origin.date()),
        )
        if pred_reg is None or len(pred_reg) == 0:
            continue

        pred_nat = forecast_national_average(pred_reg)
        act = actual_all[actual_all["date"] == origin]
        if len(act) == 0:
            continue

        act_nat = act["price_actual"].mean()
        pred_nat_val = float(pred_nat["price_per_m2"].iloc[0]) if pred_nat is not None else np.nan

        act_merge = act.merge(
            pred_reg[["region", "price_per_m2"]],
            on="region", how="inner",
        )
        for _, r in act_merge.iterrows():
            err = r["price_per_m2"] - r["price_actual"]
            err_pct = err / r["price_actual"] * 100 if r["price_actual"] else np.nan
            rows.append({
                "date": origin,
                "region": r["region"],
                "price_actual": r["price_actual"],
                "price_predicted": r["price_per_m2"],
                "actual_kind": act[act["region"] == r["region"]]["actual_kind"].iloc[0],
                "error_vnd": round(err, 0),
                "error_pct": round(err_pct, 2),
                "abs_error_pct": round(abs(err_pct), 2),
            })

        if not np.isnan(pred_nat_val):
            err_n = pred_nat_val - act_nat
            rows.append({
                "date": origin,
                "region": "National Avg",
                "price_actual": round(act_nat, 0),
                "price_predicted": round(pred_nat_val, 0),
                "actual_kind": "mixed",
                "error_vnd": round(err_n, 0),
                "error_pct": round(err_n / act_nat * 100, 2) if act_nat else np.nan,
                "abs_error_pct": round(abs(err_n / act_nat * 100), 2) if act_nat else np.nan,
            })

    if not rows:
        return None

    bt = pd.DataFrame(rows)
    nat = bt[bt["region"] == "National Avg"].copy()

    def _metrics(sub: "pd.DataFrame") -> dict:
        if len(sub) == 0:
            return {}
        return {
            "n": len(sub),
            "mae_vnd": round(sub["error_vnd"].abs().mean(), 0),
            "mape_pct": round(sub["abs_error_pct"].mean(), 2),
            "rmse_pct": round(np.sqrt((sub["error_pct"] ** 2).mean()), 2),
            "direction_accuracy_pct": None,
        }

    # Độ chính xác hướng (national): so với tháng trước
    if len(nat) >= 2:
        nat = nat.sort_values("date")
        prev_act = nat["price_actual"].shift(1)
        prev_pred = nat["price_predicted"].shift(1)
        act_dir = nat["price_actual"] > prev_act
        pred_dir = nat["price_predicted"] > prev_pred
        valid = prev_act.notna()
        dir_acc = float((act_dir[valid] == pred_dir[valid]).mean()) * 100
    else:
        dir_acc = None

    nat_metrics = _metrics(nat)
    nat_metrics["direction_accuracy_pct"] = round(dir_acc, 1) if dir_acc is not None else None

    reg_metrics = _metrics(bt[bt["region"] != "National Avg"])

    return {
        "detail": bt.sort_values(["date", "region"]).reset_index(drop=True),
        "national": nat.sort_values("date").reset_index(drop=True),
        "metrics": {
            "national": nat_metrics,
            "regional": reg_metrics,
        },
        "start": start,
        "end": end,
        "actual_monthly": actual_all,
        "note": (
            "actual_kind=observed: mốc CSV (01/2026, 07/2026); "
            "interpolated: nội suy linear giữa các mốc; "
            "extrapolated: ngoại suy sau mốc cuối. "
            "Mốc 07/2026 cập nhật theo khảo sát thị trường (giảm ~25–30%)."
        ),
    }


def run_fixed_origin_path(
    property_df: "pd.DataFrame",
    fred_monthly: "pd.DataFrame",
    vn_rates: Optional["pd.DataFrame"],
    origin: str = "2025-11-01",
    end: str = "2026-08-01",
) -> Optional["pd.DataFrame"]:
    """
    Dự báo cả đường đi từ một mốc origin (dùng dữ liệu trước origin) — như forecast «ngày 11/2025».
    """
    if pd is None:
        return None

    o = pd.Timestamp(origin).replace(day=1)
    hist = property_df.copy()
    hist["date"] = pd.to_datetime(hist["date"])
    hist = hist[hist["date"] < o]
    fred_cut = _truncate_fred(fred_monthly, o)
    rates_cut = _truncate_rates(vn_rates, o) if vn_rates is not None else None
    nat_hist = hist.groupby("date")["price_per_m2"].mean().reset_index()
    prop_index = _build_property_index_from_hist(nat_hist)
    merged = prepare_analysis_dataframe(fred_cut, prop_index, rates_cut)
    model = build_regression_model(merged) if merged is not None else None

    pred = forecast_regional_prices(
        hist, merged, model, policy_impact=None,
        start=str(o.date()), end=end,
    )
    if pred is None:
        return None
    pred["origin"] = origin
    return pred
