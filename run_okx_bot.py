#!/usr/bin/env python3
"""
Bot giao dịch tự động trên OKX: lấy nến từ OKX -> chạy signal (regime + fusion) -> đặt lệnh trên OKX.

Cấu hình:
  - .env: OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE; tùy chọn OKX_DEMO=1 (demo trading).
  - Chạy với --paper để chỉ in lệnh, không gửi thật.

Chạy:
  python run_okx_bot.py --symbols BTCUSDT,ETHUSDT --market swap --paper
  python run_okx_bot.py --symbols BTCUSDT --market swap --size-usdt 100
"""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from exchange.okx_client import OKXClient, OKXConfig, _symbol_to_inst_id
from data_loaders.okx_klines import fetch_okx_klines
from signals.current_signal import get_current_signal_with_tp_sl_from_arrays


def _parse_env() -> OKXConfig:
    key = os.environ.get("OKX_API_KEY", "").strip()
    secret = os.environ.get("OKX_SECRET_KEY", "").strip()
    phrase = os.environ.get("OKX_PASSPHRASE", "").strip()
    demo = os.environ.get("OKX_DEMO", "").strip().lower() in ("1", "true", "yes")
    if not key or not secret or not phrase:
        raise SystemExit(
            "Cần cấu hình OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE trong .env. Xem docs/HUONG_DAN_BOT_OKX.md"
        )
    return OKXConfig(api_key=key, secret_key=secret, passphrase=phrase, demo=demo)


def _size_to_sz(market_type: str, symbol: str, size_usdt: float, last_price: float) -> str:
    """
    Chuyển size (USDT) sang sz cho OKX.
    - Spot: sz = base amount = size_usdt / price (làm tròn 4–8 số).
    - SWAP: sz = contracts; 1 contract BTC-USDT-SWAP = 0.01 BTC -> contracts = size_usdt / (price * 0.01).
    """
    if market_type in ("um", "swap", "futures"):
        # Contract size: BTC/ETH thường 0.01
        ct_val = 0.01 if "BTC" in symbol.upper() else 0.1
        contracts = size_usdt / (last_price * ct_val)
        return str(round(contracts, 0))  # OKX nhận số contract integer hoặc decimal
    # Spot: base amount
    base_sz = size_usdt / last_price
    if last_price >= 1000:
        return f"{base_sz:.4f}"
    if last_price >= 1:
        return f"{base_sz:.6f}"
    return f"{base_sz:.8f}"


def main():
    parser = argparse.ArgumentParser(
        description="Bot OKX: signal regime + fusion -> đặt lệnh (hoặc --paper chỉ in)"
    )
    parser.add_argument("--symbols", type=str, default="BTCUSDT,ETHUSDT", help="Cặp, cách nhau bởi dấu phẩy")
    parser.add_argument("--market", type=str, default="swap", choices=["spot", "swap", "um"], help="spot hoặc swap (perpetual)")
    parser.add_argument("--interval", type=str, default="1h", help="Khung nến (1h khuyến nghị)")
    parser.add_argument("--size-usdt", type=float, default=100.0, help="Size mỗi lệnh (USDT)")
    parser.add_argument("--paper", action="store_true", help="Chỉ in lệnh, không gửi OKX")
    parser.add_argument("--dry-run", action="store_true", help="Alias của --paper")
    args = parser.parse_args()

    paper = args.paper or args.dry_run
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    market_type = "um" if args.market == "swap" else args.market

    config = _parse_env()
    client = OKXClient(config)

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
            print(f"[{symbol}] Lỗi lấy nến OKX: {e}", file=sys.stderr)
            continue
        if klines is None:
            print(f"[{symbol}] Không có dữ liệu nến", file=sys.stderr)
            continue
        open_time, open_, high, low, close, volume = klines
        sig = get_current_signal_with_tp_sl_from_arrays(
            open_, high, low, close, volume,
            symbol=symbol,
            market_type=market_type,
            interval=args.interval,
            sopr=None,
            mvrv=None,
        )
        if sig is None:
            print(f"[{symbol}] Không có tín hiệu Long/Short")
            continue

        inst_id = _symbol_to_inst_id(symbol, market_type)
        entry = sig.entry
        side = "buy" if sig.side == "long" else "sell"
        sz = _size_to_sz(market_type, symbol, args.size_usdt, entry)
        td_mode = "cash" if market_type == "spot" else "cross"

        if paper:
            print(
                f"[PAPER] {symbol} {sig.side.upper()} | instId={inst_id} | entry≈{entry:.2f} | "
                f"SL={sig.sl:.2f} | TP={sig.tp or 'trend'} | sz={sz} | regime={sig.regime}"
            )
            continue

        try:
            # Gửi kèm SL/TP nếu có (OKX hỗ trợ slTriggerPx, tpTriggerPx trong cùng lệnh)
            sl_trigger = str(round(sig.sl, 2)) if sig.sl else None
            tp_trigger = str(round(sig.tp, 2)) if sig.tp else None
            result = client.place_order(
                inst_id=inst_id,
                side=side,
                ord_type="market",
                sz=sz,
                td_mode=td_mode,
                sl_trigger_px=sl_trigger,
                sl_ord_px=sl_trigger,  # market stop
                tp_trigger_px=tp_trigger,
                tp_ord_px=tp_trigger,
            )
            order_id = (result.get("data") or [{}])[0].get("ordId", "?")
            print(f"[OK] {symbol} {sig.side.upper()} đã đặt lệnh ordId={order_id}")
        except Exception as e:
            print(f"[{symbol}] Lỗi đặt lệnh: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
