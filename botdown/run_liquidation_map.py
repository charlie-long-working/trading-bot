#!/usr/bin/env python3
"""
Crawl vị thế long/short theo khoảng giá thanh lý (BTC mặc định).

  python -m botdown.run_liquidation_map
  python -m botdown.run_liquidation_map --symbol XAUUSDT
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT.parent / "stock" / ".env")
except ImportError:
    pass

from data_loaders.liquidation_map import fetch_liquidation_map, save_liquidation_reports  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Liquidation map: long/short theo khoảng giá thanh lý")
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--hours", type=int, default=72, help="Lookback hours for reconstruction")
    args = ap.parse_args()

    snap = fetch_liquidation_map(args.symbol, lookback_hours=args.hours)
    paths = save_liquidation_reports(snap)
    s = snap.summary()
    print(json.dumps({k: s[k] for k in s if k != "top_clusters"}, indent=2, ensure_ascii=False))
    print("\nTop clusters:")
    for row in s.get("top_clusters") or []:
        print(
            f"  {row['price_lo']:.0f}-{row['price_hi']:.0f}  {row['dominant']:5}  "
            f"L ${row['long_usd']:,.0f}  S ${row['short_usd']:,.0f}  ({row['pct_from_mark']:+.2f}%)"
        )
    print(f"\nWrote {paths['json']}")
    print(f"Wrote {paths['csv']}")
    return 0 if snap.mark > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
