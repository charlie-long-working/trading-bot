#!/usr/bin/env python3
"""
Run full botv2 pipeline: data (optional), backtest, indicators, DCA.

Run from project root: python -m botv2.run_all
Use --skip-data to skip CCXT fetch (use existing data/).
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description="botv2 full pipeline")
    parser.add_argument("--skip-data", action="store_true", help="Skip CCXT fetch, use existing data")
    args = parser.parse_args()

    if not args.skip_data:
        print("=== 1. Fetch data ---")
        from botv2.run_data import main as run_data
        run_data()

    print("\n=== 2. Backtest ---")
    from botv2.run_backtest import main as run_backtest
    run_backtest()

    print("\n=== 3. Export indicators ---")
    from botv2.run_indicators import main as run_indicators
    run_indicators()

    print("\n=== 4. DCA optimize ---")
    from botv2.run_dca import main as run_dca
    run_dca()

    print("\n=== Done. See botv2/reports/ ===")


if __name__ == "__main__":
    main()
