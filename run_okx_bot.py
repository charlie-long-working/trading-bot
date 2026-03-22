#!/usr/bin/env python3
"""
Bot giao dịch tự động trên OKX: lấy nến từ OKX -> chạy signal (regime + fusion) -> đặt lệnh trên OKX.

Cấu hình:
  - .env: OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE; tùy chọn OKX_DEMO=1 (demo trading).
  - Chạy với --paper để chỉ in lệnh, không gửi thật.

Chạy:
  python run_okx_bot.py --symbols BTCUSDT,ETHUSDT --market swap --paper
  python run_okx_bot.py --symbols BTCUSDT --market swap --size-usdt 100
  python run_okx_bot.py --symbols BTCUSDT --market swap --size-usdt 100 --interval-minutes 60   # chạy mỗi 60 phút (daemon)
"""

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def _load_env_file():
    """Nạp .env từ thư mục project (và cwd) vào os.environ."""
    try:
        from dotenv import load_dotenv
        for path in (ROOT / ".env", Path.cwd() / ".env"):
            if path.exists():
                load_dotenv(path)
    except ImportError:
        pass
    # Fallback: đọc trực tiếp .env nếu OKX_* vẫn trống (tránh lỗi dotenv/encoding)
    if not os.environ.get("OKX_API_KEY", "").strip():
        for path in (ROOT / ".env", Path.cwd() / ".env"):
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8-sig") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                k, _, v = line.partition("=")
                                k, v = k.strip(), v.strip().strip('"').strip("'")
                                if k in ("OKX_API_KEY", "OKX_SECRET_KEY", "OKX_PASSPHRASE", "OKX_DEMO"):
                                    os.environ.setdefault(k, v)
                except Exception:
                    pass
                break


_load_env_file()

from exchange.okx_client import OKXClient, OKXConfig, _symbol_to_inst_id
from data_loaders.okx_klines import fetch_okx_klines
from signals.okx_signal import get_okx_signal


def _parse_env() -> OKXConfig:
    key = os.environ.get("OKX_API_KEY", "").strip()
    secret = os.environ.get("OKX_SECRET_KEY", "").strip()
    phrase = os.environ.get("OKX_PASSPHRASE", "").strip()
    demo = os.environ.get("OKX_DEMO", "").strip().lower() in ("1", "true", "yes")
    missing = []
    if not key:
        missing.append("OKX_API_KEY")
    if not secret:
        missing.append("OKX_SECRET_KEY")
    if not phrase:
        missing.append("OKX_PASSPHRASE")
    if missing:
        env_path = ROOT / ".env"
        raise SystemExit(
            f"Thiếu trong .env: {', '.join(missing)}.\n"
            f"Kiểm tra file {env_path} có đúng 3 dòng (không dấu cách thừa):\n"
            "  OKX_API_KEY=...\n"
            "  OKX_SECRET_KEY=...\n"
            "  OKX_PASSPHRASE=...\n"
            "Xem docs/HUONG_DAN_BOT_OKX.md"
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
    parser.add_argument(
        "--interval-minutes",
        type=float,
        default=0,
        help="Chạy lặp mỗi N phút (0 = chạy 1 lần rồi thoát). Dùng để bot chạy 24/7 trên VPS.",
    )
    args = parser.parse_args()

    paper = args.paper or args.dry_run
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    market_type = "um" if args.market == "swap" else args.market

    config = _parse_env()
    client = OKXClient(config)
    if config.demo:
        print("(Chế độ DEMO: API key từ tài khoản Demo OKX — lệnh dùng số dư demo)")

    run_count = 0
    while True:
        run_count += 1
        if args.interval_minutes > 0 and run_count > 1:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Chu kỳ #{run_count} — kiểm tra tín hiệu...")
        _run_one_cycle(client, config, symbols, market_type, args, paper)
        if args.interval_minutes <= 0:
            break
        sec = int(args.interval_minutes * 60)
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Chờ {args.interval_minutes:.0f} phút đến chu kỳ tiếp theo...")
        time.sleep(sec)


def _run_one_cycle(client, config, symbols, market_type, args, paper):
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
        sig = get_okx_signal(
            open_time, open_, high, low, close, volume,
            symbol=symbol,
            market_type=market_type,
            interval=args.interval,
            sopr=None,
            mvrv=None,
            use_timeline_modifier=True,
        )
        if sig is None:
            print(f"[{symbol}] Không có tín hiệu Long/Short")
            continue

        inst_id = _symbol_to_inst_id(symbol, market_type)
        entry = sig.entry
        side = "buy" if sig.side == "long" else "sell"
        size_usdt = args.size_usdt * sig.position_size_modifier
        sz = _size_to_sz(market_type, symbol, size_usdt, entry)
        td_mode = "cash" if market_type == "spot" else "cross"

        if paper:
            mod = f" (size_mod={sig.position_size_modifier})" if sig.position_size_modifier < 1.0 else ""
            print(
                f"[PAPER] {symbol} {sig.side.upper()} | instId={inst_id} | entry≈{entry:.2f} | "
                f"SL={sig.sl:.2f} | TP={sig.tp or 'trend'} | sz={sz} | regime={sig.regime}{mod}"
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
