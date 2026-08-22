#!/usr/bin/env python3
"""Backtest Nov/2025 → Aug/2026: thực tế vs model."""

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vre.data_loaders.fred import get_merged_monthly
from vre.data_loaders.vietnam_econ import load_interest_rates, load_property_prices
from vre.models.backtest_horizon import (
    run_walk_forward_backtest,
    run_fixed_origin_path,
    build_monthly_actual,
)

REPORT_DIR = ROOT / "vre" / "data" / "reports"


def main():
    prices = load_property_prices()
    fred = get_merged_monthly()
    rates = load_interest_rates()
    if prices is None or fred is None:
        print("Thiếu dữ liệu giá hoặc FRED.")
        return 1

    result = run_walk_forward_backtest(
        prices, fred, rates,
        start="2025-11-01",
        end="2026-08-01",
    )
    if result is None:
        print("Backtest không chạy được.")
        return 1

    fixed = run_fixed_origin_path(
        prices, fred, rates,
        origin="2025-11-01",
        end="2026-08-01",
    )

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    detail = result["detail"]
    national = result["national"]
    detail.to_csv(REPORT_DIR / f"backtest_horizon_detail_{stamp}.csv", index=False)
    national.to_csv(REPORT_DIR / f"backtest_horizon_national_{stamp}.csv", index=False)
    if fixed is not None:
        fixed.to_csv(REPORT_DIR / f"backtest_horizon_fixed_origin_{stamp}.csv", index=False)

    meta = {
        "generated_at": datetime.now().isoformat(),
        "window": "2025-11 → 2026-08",
        "metrics": result["metrics"],
        "note": result["note"],
    }
    meta_path = REPORT_DIR / f"backtest_horizon_{stamp}.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    m = result["metrics"]["national"]
    print("\n=== BACKTEST 11/2025 → 08/2026 (National Avg) ===")
    print(f"Số tháng:        {m.get('n', 0)}")
    print(f"MAE:             {m.get('mae_vnd', 0):,.0f} VND/m²")
    print(f"MAPE:            {m.get('mape_pct', 0):.2f}%")
    print(f"RMSE (%):        {m.get('rmse_pct', 0):.2f}%")
    print(f"Đúng hướng:      {m.get('direction_accuracy_pct', 'N/A')}%")
    print(f"\n{result['note']}")
    print("\n--- Chi tiết từng tháng (National) ---")
    show = national.copy()
    show["date"] = show["date"].astype(str).str[:7]
    show["price_actual"] = show["price_actual"].apply(lambda x: f"{x:,.0f}")
    show["price_predicted"] = show["price_predicted"].apply(lambda x: f"{x:,.0f}")
    print(show[["date", "price_actual", "price_predicted", "error_pct", "actual_kind"]].to_string(index=False))
    print(f"\nCSV: {REPORT_DIR}/backtest_horizon_*_{stamp}.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
