#!/usr/bin/env python3
"""
CLI to download Binance spot and futures UM daily/monthly klines from data.binance.vision.

Example:
  python crawl_binance_klines.py --market-type spot,um --symbols BTCUSDT,ETHUSDT \\
    --interval 1h --start 2020-01-01 --end 2025-03-15 --frequency monthly --out-dir data
"""

import argparse
from datetime import date, datetime
from pathlib import Path

from crawler.config import CrawlConfig, VALID_INTERVALS, MARKET_TYPES, FREQUENCIES
from crawler.downloader import download_all, unzip_and_merge_to_csv


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Download Binance spot/futures klines from data.binance.vision",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument(
        "--market-type",
        type=str,
        default="spot,um",
        help="Comma-separated: spot and/or um (USD-M futures)",
    )
    ap.add_argument(
        "--symbols",
        type=str,
        default="BTCUSDT,ETHUSDT",
        help="Comma-separated symbols, e.g. BTCUSDT,ETHUSDT",
    )
    ap.add_argument(
        "--interval",
        type=str,
        default=None,
        help=f"Single interval (used if --intervals not set). Choices: {', '.join(VALID_INTERVALS)}",
    )
    ap.add_argument(
        "--intervals",
        type=str,
        default=None,
        help="Comma-separated intervals, e.g. 1h,1d (overrides --interval; fetches all at once)",
    )
    ap.add_argument(
        "--start",
        type=str,
        default="2020-01-01",
        help="Start date YYYY-MM-DD",
    )
    ap.add_argument(
        "--end",
        type=str,
        default=None,
        help="End date YYYY-MM-DD (default: today)",
    )
    ap.add_argument(
        "--frequency",
        type=str,
        choices=FREQUENCIES,
        default="monthly",
        help="daily or monthly",
    )
    ap.add_argument(
        "--out-dir",
        type=str,
        default="data",
        help="Output directory for ZIPs (and merged CSVs if --merge-csv)",
    )
    ap.add_argument(
        "--workers",
        type=int,
        default=2,
        help="Parallel download workers (1-4)",
    )
    ap.add_argument(
        "--merge-csv",
        action="store_true",
        help="After download, unzip and merge into one CSV per (market, symbol, interval)",
    )
    ap.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Re-download even if file already exists",
    )
    args = ap.parse_args()

    end = _parse_date(args.end) if args.end else date.today()
    if args.intervals:
        intervals = [i.strip() for i in args.intervals.split(",") if i.strip()]
    else:
        intervals = [args.interval or "1h"]
    config = CrawlConfig(
        symbols=[s.strip() for s in args.symbols.split(",") if s.strip()],
        intervals=intervals,
        start_date=_parse_date(args.start),
        end_date=end,
        market_types=[m.strip() for m in args.market_type.split(",") if m.strip()],
        frequency=args.frequency,
        out_dir=args.out_dir,
        workers=max(1, min(args.workers, 4)),
        merge_csv=args.merge_csv,
        skip_existing=not args.no_skip_existing,
    )

    download_all(config)
    if config.merge_csv:
        unzip_and_merge_to_csv(config)


if __name__ == "__main__":
    main()
