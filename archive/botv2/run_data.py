#!/usr/bin/env python3
"""
Fetch klines 2017–now via CCXT and save to botv2/data/cache.

Run from project root: python -m botv2.run_data
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from botv2.config import (
    CACHE_DIR,
    END_DATE,
    EXCHANGE_FUTURE,
    EXCHANGE_SPOT,
    START_DATE,
    SYMBOLS,
    TIMEFRAMES,
)
from botv2.data.fetcher import fetch_and_save_klines


def main():
    start_str = START_DATE.strftime("%Y-%m-%d")
    end_str = END_DATE.strftime("%Y-%m-%d")

    print("botv2: Fetching klines 2017–now via CCXT")
    print(f"  Start: {start_str} | End: {end_str}")
    print(f"  Cache: {CACHE_DIR}\n")

    # Binance USD-M futures launched ~Sep 2019; use later start for futures
    futures_start = "2019-09-01"

    for symbol in SYMBOLS:
        for tf in TIMEFRAMES:
            print(f"Spot {symbol} {tf}")
            fetch_and_save_klines(
                EXCHANGE_SPOT,
                "spot",
                symbol,
                tf,
                start_str,
                end_str,
                cache_dir=CACHE_DIR,
            )
            print(f"Future {symbol} {tf}")
            fetch_and_save_klines(
                EXCHANGE_FUTURE,
                "future",
                symbol,
                tf,
                futures_start,
                end_str,
                cache_dir=CACHE_DIR,
            )

    print("\nDone.")


if __name__ == "__main__":
    main()
