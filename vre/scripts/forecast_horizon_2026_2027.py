#!/usr/bin/env python3
"""In dự báo giá nhà 08/2026 → 12/2027 ra JSON + CSV."""

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vre.data_loaders.fred import get_merged_monthly
from vre.data_loaders.vietnam_econ import load_interest_rates, build_property_index, load_property_prices
from vre.data_loaders.policy_crawler import load_policies
from vre.models.trend_predictor import run_full_analysis
from vre.models.policy_scenarios import compute_policy_net_impact

REPORT_DIR = ROOT / "vre" / "data" / "reports"


def main():
    fred = get_merged_monthly()
    prop_index = build_property_index()
    vn_rates = load_interest_rates()
    policies = load_policies()
    analysis = run_full_analysis(
        fred, prop_index, vn_rates,
        policies=policies, policy_months=6,
    )
    horizon = analysis.get("horizon_forecast")
    if not horizon or horizon.get("national") is None:
        print("Không tạo được dự báo horizon.")
        return 1

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    nat = horizon["national"]
    reg = horizon["regional"]

    nat.to_csv(REPORT_DIR / f"horizon_forecast_national_{stamp}.csv", index=False)
    reg.to_csv(REPORT_DIR / f"horizon_forecast_regional_{stamp}.csv", index=False)

    pi = analysis.get("policy_impact")
    if pi and isinstance(pi, dict):
        pi = {k: v for k, v in pi.items() if k != "recent_policies"}

    out = {
        "generated_at": datetime.now().isoformat(),
        "period": "2026-08 → 2027-12",
        "summary": horizon.get("summary"),
        "policy_impact": pi,
    }
    path = REPORT_DIR / f"horizon_forecast_{stamp}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    s = horizon["summary"]
    print("\n=== DỰ BÁO GIÁ NHÀ 08/2026 → 12/2027 (tham khảo) ===")
    print(f"Giá BQ cả nước 08/2026: {s['price_start_vnd']:,} VND/m²")
    print(f"Giá BQ cả nước 12/2027: {s['price_end_vnd']:,} VND/m² (base)")
    print(f"                        {s['price_end_policy_vnd']:,} VND/m² (+ chính sách)")
    print(f"Tăng cả giai đoạn:      {s['change_pct']:+.1f}% (base) / {s['change_pct_policy']:+.1f}% (+ CS)")
    print(f"\nCSV: {REPORT_DIR}/horizon_forecast_*_{stamp}.csv")
    print(f"JSON: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
