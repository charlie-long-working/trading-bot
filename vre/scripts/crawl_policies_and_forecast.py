#!/usr/bin/env python3
"""
Crawl chính sách BĐS 6 tháng gần nhất + chạy dự báo vĩ mô có điều chỉnh chính sách.

Chạy từ thư mục Trading-bot:
  python vre/scripts/crawl_policies_and_forecast.py
  python vre/scripts/crawl_policies_and_forecast.py --months 6 --refresh-fred
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from vre.data_loaders.fred import get_merged_monthly
from vre.data_loaders.vietnam_econ import load_interest_rates, build_property_index
from vre.data_loaders.policy_crawler import crawl_policies, filter_recent, POLICIES_CSV
from vre.models.trend_predictor import run_full_analysis
from vre.models.policy_scenarios import compute_policy_net_impact, apply_policy_adjustment

REPORT_DIR = ROOT / "vre" / "data" / "reports"


def main():
    parser = argparse.ArgumentParser(description="Crawl chính sách BĐS + dự báo")
    parser.add_argument("--months", type=int, default=6, help="Số tháng crawl/lọc (mặc định 6)")
    parser.add_argument("--refresh-fred", action="store_true", help="Fetch lại FRED (cần FRED_API_KEY)")
    args = parser.parse_args()

    print(f"[1/4] Crawl chính sách {args.months} tháng gần nhất...")
    policies = crawl_policies(months=args.months)
    if policies is None or len(policies) == 0:
        print("  Không có chính sách. Kiểm tra mạng hoặc file CSV.")
        return 1

    recent = filter_recent(policies, months=args.months)
    print(f"  Tổng {len(policies)} mục trong {POLICIES_CSV.name}, {len(recent)} mục trong {args.months} tháng.")

    print("[2/4] Load dữ liệu vĩ mô + giá BĐS...")
    fred = get_merged_monthly(force_refresh=args.refresh_fred)
    prop_index = build_property_index()
    vn_rates = load_interest_rates()

    print("[3/4] Chạy mô hình dự báo...")
    analysis = run_full_analysis(fred, prop_index, vn_rates)
    forecast = analysis.get("forecast")
    merged = analysis.get("merged_data")
    model_res = analysis.get("model_result")

    if forecast is None or model_res is None:
        print("  Không dự báo được (thiếu dữ liệu vĩ mô hoặc giá BĐS).")
        return 1

    current_idx = None
    if merged is not None and "property_index" in merged.columns:
        current_idx = float(merged["property_index"].iloc[-1])

    print("[4/4] Điều chỉnh theo chính sách...")
    impact = compute_policy_net_impact(policies, months=args.months)
    adjusted = apply_policy_adjustment(forecast, impact, current_index=current_idx)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    report_path = REPORT_DIR / f"policy_forecast_{stamp}.json"

    base_pred = float(forecast["predicted_index"].iloc[0])
    adj_pred = float(adjusted["predicted_index"].iloc[0]) if adjusted is not None else base_pred

    report = {
        "generated_at": datetime.now().isoformat(),
        "months_window": args.months,
        "n_policies_recent": impact["n_policies"],
        "policy_net_impact": impact["net_impact"],
        "policy_adjustment_pct": impact["adjustment_pct"],
        "current_property_index": current_idx,
        "forecast_base_index": base_pred,
        "forecast_adjusted_index": adj_pred,
        "model_r2": model_res.get("r2_train"),
        "model_mae": model_res.get("mae_train"),
        "direction_accuracy_backtest": (
            analysis.get("backtest", {}) or {}
        ).get("direction_accuracy"),
        "recent_policies": recent[
            ["date", "source", "title", "impact_score", "impact_direction", "url"]
        ].astype({"date": str}).to_dict(orient="records"),
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== KẾT QUẢ DỰ BÁO (tham khảo, không phải tư vấn đầu tư) ===")
    print(f"Chính sách {args.months} tháng: {impact['n_policies']} mục "
          f"(+{impact['positive_count']} / -{impact['negative_count']} / ={impact['neutral_count']})")
    print(f"Net impact: {impact['net_impact']:+.3f} → điều chỉnh {impact['adjustment_pct']:+.2f}%")
    if current_idx:
        print(f"Chỉ số hiện tại: {current_idx:.1f} (mốc 2015=100)")
    print(f"Dự báo vĩ mô (base):     {base_pred:.1f}")
    print(f"Dự báo + chính sách:     {adj_pred:.1f}")
    if current_idx and current_idx != 0:
        chg = (adj_pred - current_idx) / current_idx * 100
        print(f"Hướng 1 quý tới:         {chg:+.1f}%")
    print(f"\nBáo cáo JSON: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
