"""
Điều chỉnh dự báo giá BĐS theo chính sách gần đây.

Cách làm:
  1. Lấy các chính sách N tháng gần nhất (CSV + RSS crawl).
  2. Tính điểm tác động có trọng số theo thời gian (gần hơn = nặng hơn).
  3. Điều chỉnh chỉ số dự báo từ mô hình vĩ mô: adjusted = base * (1 + net_impact * scale).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

try:
    import pandas as pd
    import numpy as np
except ImportError:
    pd = None
    np = None

# Mỗi điểm impact_score (±1) tương ứng ~0.8% điều chỉnh chỉ số 1 quý
IMPACT_SCALE = 0.008
MAX_ADJUSTMENT_PCT = 3.0


def compute_policy_net_impact(
    policies: "pd.DataFrame",
    months: int = 6,
    as_of: Optional[datetime] = None,
) -> dict:
    """
    Trả về net_impact (-1..+1), breakdown theo hướng, danh sách chính sách gần đây.
    """
    if pd is None or policies is None or len(policies) == 0:
        return {
            "net_impact": 0.0,
            "n_policies": 0,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 0,
            "recent_policies": policies,
            "adjustment_pct": 0.0,
        }

    as_of = as_of or datetime.now()
    p = policies.copy()
    p["date"] = pd.to_datetime(p["date"])
    cutoff = as_of - pd.Timedelta(days=months * 30)
    recent = p[p["date"] >= cutoff].copy()

    if len(recent) == 0:
        return {
            "net_impact": 0.0,
            "n_policies": 0,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 0,
            "recent_policies": recent,
            "adjustment_pct": 0.0,
        }

    days_ago = (as_of - recent["date"]).dt.days.clip(lower=1)
    weight = 1.0 / (1.0 + days_ago / 90.0)
    scores = recent["impact_score"].astype(float) * weight
    net = float(scores.sum() / weight.sum()) if weight.sum() > 0 else 0.0
    net = max(-1.0, min(1.0, net))

    adj_pct = net * IMPACT_SCALE * 100
    adj_pct = max(-MAX_ADJUSTMENT_PCT, min(MAX_ADJUSTMENT_PCT, adj_pct))

    return {
        "net_impact": round(net, 4),
        "n_policies": len(recent),
        "positive_count": int((recent["impact_direction"] == "positive").sum()),
        "negative_count": int((recent["impact_direction"] == "negative").sum()),
        "neutral_count": int((recent["impact_direction"] == "neutral").sum()),
        "recent_policies": recent.sort_values("date", ascending=False),
        "adjustment_pct": round(adj_pct, 2),
    }


def apply_policy_adjustment(
    base_forecast: "pd.DataFrame",
    policy_impact: dict,
    current_index: Optional[float] = None,
) -> Optional["pd.DataFrame"]:
    """
    Nhân chỉ số dự báo với hệ số điều chỉnh từ chính sách.
    """
    if pd is None or base_forecast is None or len(base_forecast) == 0:
        return None

    adj_pct = policy_impact.get("adjustment_pct", 0.0) / 100.0
    out = base_forecast.copy()
    factor = 1.0 + adj_pct

    if "predicted_index" in out.columns:
        out["predicted_index_base"] = out["predicted_index"]
        out["predicted_index"] = (out["predicted_index"] * factor).round(2)
        out["policy_adjustment_pct"] = round(adj_pct * 100, 2)

    if current_index is not None and current_index != 0 and "predicted_index" in out.columns:
        out["vs_current_pct"] = (
            (out["predicted_index"] - current_index) / current_index * 100
        ).round(2)

    return out
