#!/usr/bin/env python3
"""
Run DCA optimization: best hour ($10/day), best day+hour ($100/week), best BTC/ETH ratio.

Run from project root: python -m botv2.run_dca
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from botv2.config import END_DATE, START_DATE
from botv2.dca.optimize import optimize_daily_hour, optimize_weekly_day_hour, optimize_btc_ratio


def main():
    start = START_DATE.strftime("%Y-%m-%d")
    end = END_DATE.strftime("%Y-%m-%d")
    print("botv2 DCA Optimizer (2017 – now)")
    print(f"  Period: {start} → {end}\n")

    # 1. $10/day – best hour
    print("--- $10/day: Best hour (UTC) ---")
    best_h, daily_val, top5 = optimize_daily_hour(10.0, start, end, 0.7)
    print(f"  Best hour: {best_h}:00 UTC → Portfolio ${daily_val:,.0f}")
    print("  Top 5 hours:")
    for h, v in top5:
        print(f"    {h}:00 UTC → ${v:,.0f}")

    # 2. $100/week – best day + hour
    print("\n--- $100/week: Best day + hour (UTC) ---")
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    best_d, best_h_wk, weekly_val, top10 = optimize_weekly_day_hour(100.0, start, end, 0.7)
    print(f"  Best: {days[best_d]} {best_h_wk}:00 UTC → Portfolio ${weekly_val:,.0f}")
    print("  Top 10:")
    for d, h, v in top10:
        print(f"    {days[d]} {h}:00 UTC → ${v:,.0f}")

    # 3. Best BTC/ETH ratio (using best hour from step 1)
    print("\n--- Best BTC/ETH ratio (daily $10 at best hour) ---")
    best_ratio, ratio_val, top5 = optimize_btc_ratio(10.0, start, end, best_h, 0.1)
    eth_ratio = 1 - best_ratio
    print(f"  Best: BTC {best_ratio*100:.0f}% / ETH {eth_ratio*100:.0f}% → Portfolio ${ratio_val:,.0f}")
    print("  Top 5 ratios:")
    for r, v in top5:
        print(f"    BTC {r*100:.0f}% / ETH {(1-r)*100:.0f}% → ${v:,.0f}")

    # Write report
    report_path = ROOT / "botv2" / "reports" / "dca_results.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        f.write("# botv2 DCA Optimization Results\n\n")
        f.write(f"Period: {start} → {end}\n\n")
        f.write("## $10/day – Best hour (UTC)\n")
        f.write(f"- **Best hour**: {best_h}:00 UTC\n")
        f.write(f"- **Portfolio value**: ${daily_val:,.0f}\n\n")
        f.write("## $100/week – Best day + hour (UTC)\n")
        f.write(f"- **Best**: {days[best_d]} {best_h_wk}:00 UTC\n")
        f.write(f"- **Portfolio value**: ${weekly_val:,.0f}\n\n")
        f.write("## Best BTC/ETH ratio\n")
        f.write(f"- **BTC**: {best_ratio*100:.0f}% | **ETH**: {eth_ratio*100:.0f}%\n")
        f.write(f"- **Portfolio value**: ${ratio_val:,.0f}\n\n")
        f.write("## Điểm mua tốt (DCA)\n")
        f.write(f"- **Daily $10**: Mua vào lúc **{best_h}:00 UTC** mỗi ngày\n")
        f.write(f"- **Weekly $100**: Mua vào **{days[best_d]} {best_h_wk}:00 UTC** mỗi tuần\n")
        f.write(f"- **Tỷ lệ**: BTC {best_ratio*100:.0f}% / ETH {eth_ratio*100:.0f}%\n")
    print(f"\nReport saved to {report_path}")
    print("\nDone.")


if __name__ == "__main__":
    main()
