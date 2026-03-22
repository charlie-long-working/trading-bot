#!/usr/bin/env python3
"""
Chỉ in tín hiệu giao dịch OKX (Long/Short + SL/TP + timeline), không đặt lệnh.

Dùng candles public OKX (không cần API key). Hữu ích để xem tín hiệu trước khi chạy bot thật.

Ví dụ:
  python run_okx_signal_only.py --symbols BTCUSDT,ETHUSDT --market swap
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from exchange.okx_client import OKXClient
from data_loaders.okx_klines import fetch_okx_klines
from signals.okx_signal import get_okx_signal, format_okx_signal_for_telegram


def main():
    parser = argparse.ArgumentParser(description="In tín hiệu OKX (regime + fusion + timeline), không đặt lệnh")
    parser.add_argument("--symbols", type=str, default="BTCUSDT,ETHUSDT", help="Cặp, cách nhau bởi dấu phẩy")
    parser.add_argument("--market", type=str, default="swap", choices=["spot", "swap", "um"])
    parser.add_argument("--interval", type=str, default="1h")
    args = parser.parse_args()

    market_type = "um" if args.market == "swap" else args.market
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    client = OKXClient(config=None)

    for symbol in symbols:
        try:
            klines = fetch_okx_klines(
                client,
                symbol=symbol,
                market_type=market_type,
                interval=args.interval,
                limit=300,
                use_history=True,
            )
        except Exception as e:
            print(f"[{symbol}] Lỗi lấy nến: {e}", file=sys.stderr)
            continue
        if klines is None:
            print(f"[{symbol}] Không có dữ liệu nến", file=sys.stderr)
            continue

        open_time, open_, high, low, close, volume = klines
        sig = get_okx_signal(
            open_time, open_, high, low, close, volume,
            symbol=symbol,
            market_type=market_type,
            interval=args.interval,
            use_timeline_modifier=True,
        )
        if sig is None:
            print(f"[{symbol}] Không có tín hiệu Long/Short")
            continue
        print(format_okx_signal_for_telegram(sig))
        print()


if __name__ == "__main__":
    main()
