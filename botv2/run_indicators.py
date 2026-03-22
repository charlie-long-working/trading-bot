#!/usr/bin/env python3
"""
Export backtest signals to CSV/JSON with entry, SL, TP.

Run from project root: python -m botv2.run_indicators
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from botv2.backtest.engine import run_backtest
from botv2.config import CACHE_DIR, SYMBOLS, TIMEFRAMES
from botv2.indicators.export_signals import export_all_configs


def main():
    configs = []
    for market in ("spot", "future"):
        for symbol in SYMBOLS:
            for tf in TIMEFRAMES:
                configs.append((market, symbol, tf))

    results = []
    for market_type, symbol, interval in configs:
        r = run_backtest(market_type, symbol, interval, cache_dir=CACHE_DIR)
        if r is not None and r.num_trades > 0:
            label = f"{market_type}_{symbol}_{interval}"
            results.append((label, r))

    out_dir = str(ROOT / "botv2" / "reports" / "indicators")
    export_all_configs(results, out_dir=out_dir)
    print("\nDone.")


if __name__ == "__main__":
    main()
