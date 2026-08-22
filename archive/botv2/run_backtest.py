#!/usr/bin/env python3
"""
Run backtest for spot + future, 1h + 1d, BTC & ETH.

Uses botv2 cache (or fallback to parent data/). Compares strategy vs buy-and-hold.
Run from project root: python -m botv2.run_backtest
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from botv2.backtest.engine import run_backtest
from botv2.config import CACHE_DIR, SYMBOLS, TIMEFRAMES


def main():
    configs = []
    for market in ("spot", "future"):
        for symbol in SYMBOLS:
            for tf in TIMEFRAMES:
                configs.append((market, symbol, tf))

    print("botv2 Backtest: Regime + OB/FVG/Supply-Demand")
    print(f"  Cache: {CACHE_DIR}\n")

    results = []
    for market_type, symbol, interval in configs:
        r = run_backtest(market_type, symbol, interval, cache_dir=CACHE_DIR)
        if r is None:
            print(f"  {market_type} {symbol} {interval}: no data")
            continue
        results.append((f"{market_type} {symbol} {interval}", r))
        vs = r.total_return_pct - r.hold_return_pct
        line = (
            f"  {market_type} {symbol} {interval}: {r.num_trades} trades | "
            f"Strategy {r.total_return_pct:+.1f}% | Hold {r.hold_return_pct:+.1f}% | "
            f"Vs hold {vs:+.1f}% | Max DD {r.max_drawdown_pct:.1f}% | "
            f"Win {r.win_rate:.1f}% | PF {r.profit_factor:.2f} | Sharpe {r.sharpe_ratio:.2f}"
        )
        if r.num_trades:
            line += f" | Avg win {r.avg_win_pct:+.1f}% | Avg loss {r.avg_loss_pct:.1f}%"
        print(line)

    if results:
        print("\n--- Strategy vs Hold ---")
        for label, r in results:
            vs = r.total_return_pct - r.hold_return_pct
            print(f"  {label}: Strategy {r.total_return_pct:+.1f}% | Hold {r.hold_return_pct:+.1f}% | Vs hold {vs:+.1f}%")
    print("\nDone.")


if __name__ == "__main__":
    main()
