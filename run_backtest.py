#!/usr/bin/env python3
"""
Run backtest for all data from 2017 to latest (plan: through 2026 when available).

Uses merged klines: spot + um, BTCUSDT + ETHUSDT, 1d + 1h.
"""

from backtest import run_backtest


def main() -> None:
    data_dir = "data"
    configs = [
        ("spot", "BTCUSDT", "1d"),
        ("spot", "BTCUSDT", "1h"),
        ("spot", "ETHUSDT", "1d"),
        ("spot", "ETHUSDT", "1h"),
        ("um", "BTCUSDT", "1d"),
        ("um", "BTCUSDT", "1h"),
        ("um", "ETHUSDT", "1d"),
        ("um", "ETHUSDT", "1h"),
    ]
    print("Backtest (regime + technical) on all data 2017 to latest\n")
    for market_type, symbol, interval in configs:
        r = run_backtest(data_dir, market_type, symbol, interval, lookback=100)
        if r is None:
            print(f"  {market_type} {symbol} {interval}: no data")
            continue
        print(
            f"  {market_type} {symbol} {interval}: {r.num_trades} trades | "
            f"return {r.total_return_pct:.1f}% | maxDD {r.max_drawdown_pct:.1f}% | "
            f"win rate {r.win_rate:.1f}% | PF {r.profit_factor:.2f}"
        )
    print("\nDone.")


if __name__ == "__main__":
    main()
