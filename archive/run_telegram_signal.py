#!/usr/bin/env python3
"""
Chạy tín hiệu khung 1h (indicator + regime), gửi Long/Short kèm TP, SL lên Telegram.

Cấu hình:
  - .env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (xem .env.example).
  - Data: cần có klines 1h trong data/{spot|um}/klines/{SYMBOL}/ (chạy crawler trước).

Chạy:
  python run_telegram_signal.py
  python run_telegram_signal.py --symbols BTCUSDT,ETHUSDT --market spot
"""

import argparse
import sys
from pathlib import Path

# project root – load .env ngay từ đây
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from signals.current_signal import get_current_signal_with_tp_sl
from notify.telegram import send_message


DATA_DIR = ROOT / "data"

# Cặp (market, symbol) mặc định cho tín hiệu 1h
DEFAULT_PAIRS = [
    ("spot", "BTCUSDT"),
    ("spot", "ETHUSDT"),
    ("um", "BTCUSDT"),
    ("um", "ETHUSDT"),
]


def _fmt_price(x: float, decimals: int = 2) -> str:
    if x >= 1000:
        return f"{x:,.0f}"
    if x >= 1:
        return f"{x:,.2f}"
    return f"{x:.4f}"


def format_signal_message(s) -> str:
    """Format SignalWithLevels thành tin nhắn Telegram (HTML)."""
    side_emoji = "🟢" if s.side == "long" else "🔴"
    side_text = "LONG" if s.side == "long" else "SHORT"
    lines = [
        f"{side_emoji} <b>{side_text}</b> {s.symbol} ({s.market_type} · 1h)",
        "",
        f"Entry: <code>{_fmt_price(s.entry)}</code>",
        f"SL: <code>{_fmt_price(s.sl)}</code>",
        f"TP: <code>{_fmt_price(s.tp)}</code>" if s.tp is not None else "TP: trend (không đặt TP cố định)",
        "",
        f"Regime: {s.regime} · Lý do: {s.reason}",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Gửi tín hiệu 1h Long/Short + TP/SL lên Telegram")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR, help="Thư mục data (klines)")
    parser.add_argument("--market", type=str, default=None, help="Chỉ chạy market: spot hoặc um")
    parser.add_argument("--symbols", type=str, default="BTCUSDT,ETHUSDT", help="Các symbol cách nhau bởi dấu phẩy")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ in ra, không gửi Telegram")
    args = parser.parse_args()

    data_dir = args.data_dir
    if not data_dir.exists():
        print(f"Data dir không tồn tại: {data_dir}", file=sys.stderr)
        sys.exit(1)

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    markets = ["spot", "um"] if args.market is None else [args.market.strip().lower()]
    if args.market and args.market.strip().lower() not in ("spot", "um"):
        markets = [args.market.strip().lower()]

    pairs = [(m, s) for m in markets for s in symbols]
    sent = 0
    for market, symbol in pairs:
        sig = get_current_signal_with_tp_sl(
            str(data_dir), market_type=market, symbol=symbol, interval="1h", use_onchain=True
        )
        if sig is None:
            continue
        msg = format_signal_message(sig)
        if args.dry_run:
            print("---")
            print(msg)
            sent += 1
            continue
        ok, err = send_message(msg)
        if ok:
            sent += 1
            print(f"Đã gửi: {sig.side} {symbol} ({market})")
        else:
            print(f"Gửi thất bại {symbol} {market}: {err}", file=sys.stderr)

    if not args.dry_run and sent == 0 and pairs:
        print("Không có tín hiệu Long/Short nào trong khung 1h cho các cặp đã chọn.", file=sys.stderr)


if __name__ == "__main__":
    main()
