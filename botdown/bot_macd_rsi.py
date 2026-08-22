#!/usr/bin/env python3
"""
Bot MACD histogram + RSI, TP/SL % (mặc định +10% / −4%), sàn **OKX swap** hoặc Binance USDT-M.

.env (thư mục Trading-bot) — OKX (khuyến nghị):
  MACD_RSI_EXCHANGE=okx
  OKX_API_KEY=...
  OKX_API_SECRET=...
  OKX_API_PASSPHRASE=...    # Passphrase khi tạo API key
  MACD_RSI_OKX_TDMODE=cross   # hoặc isolated
  OKX_SANDBOX=1             # tùy chọn: demo (nếu API demo)

  MACD_RSI_DRY_RUN=1
  MACD_RSI_NOTIONAL_USD=100
  MACD_RSI_SYMBOL=BTC/USDT:USDT
  MACD_RSI_LEVERAGE=1
  MACD_RSI_TIMEFRAME=1d

Binance (MACD_RSI_EXCHANGE=binanceusdm):
  BINANCE_API_KEY, BINANCE_API_SECRET

Chạy một lần:
  .venv/bin/python -m botdown.bot_macd_rsi --once

Chạy tự động lặp (ví dụ mỗi 5 phút quét TP/SL):
  .venv/bin/python -m botdown.bot_macd_rsi --loop 300

Production: dùng cron/systemd với --once theo khung nến + --loop nhỏ nếu cần.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import ccxt  # type: ignore
except ImportError:
    ccxt = None  # type: ignore

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*_a, **_k):  # type: ignore
        return False

from botdown.engine_macd_rsi_bt import (
    MacdRsiParams,
    macd_rsi_entry_snapshot,
    macd_rsi_exit_by_mark,
)
from botdown.exchange_factory import (
    create_futures_exchange,
    order_params_close,
    order_params_open,
)

log = logging.getLogger("botdown.macd_rsi")


def _state_path(exchange_tag: str) -> Path:
    return ROOT / "botdown" / f"state_macd_rsi_{exchange_tag}.json"


def load_state(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"position": None, "last_signal_entered_ms": 0}
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        if "last_signal_entered_ms" not in d:
            d["last_signal_entered_ms"] = 0
        return d
    except (json.JSONDecodeError, OSError):
        return {"position": None, "last_signal_entered_ms": 0}


def save_state(path: Path, st: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(st, indent=2), encoding="utf-8")


def _ohlcv_to_arrays(
    rows: List[List[float]], drop_last: bool
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if drop_last and len(rows) >= 2:
        rows = rows[:-1]
    if not rows:
        z = np.array([], dtype=np.int64)
        zf = np.array([], dtype=float)
        return z, zf, zf, zf, zf, zf
    ot = np.array([int(r[0]) for r in rows], dtype=np.int64)
    o = np.array([float(r[1]) for r in rows], dtype=float)
    h = np.array([float(r[2]) for r in rows], dtype=float)
    l_ = np.array([float(r[3]) for r in rows], dtype=float)
    c = np.array([float(r[4]) for r in rows], dtype=float)
    v = np.array([float(r[5]) if len(r) > 5 else 0.0 for r in rows], dtype=float)
    return ot, o, h, l_, c, v


def _round_amount(exchange: Any, symbol: str, amount: float) -> float:
    m = exchange.market(symbol)
    prec = m.get("precision", {}).get("amount")
    if prec is not None:
        amount = float(exchange.amount_to_precision(symbol, amount))
    return max(amount, 0.0)


def run_once(
    exchange: Any,
    exchange_tag: str,
    state_path: Path,
    dry_run: bool,
    notional_usd: float,
    symbol: str,
    leverage: int,
    timeframe: str,
    params: MacdRsiParams,
) -> None:
    if ccxt is None:
        raise RuntimeError("Cần cài ccxt")

    exchange.load_markets()
    if not dry_run:
        try:
            exchange.set_leverage(leverage, symbol)
        except Exception as e:
            log.warning("set_leverage: %s", e)

    limit = 500 if timeframe == "1d" else 800
    raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    ot, _, hi, lo, cl, _ = _ohlcv_to_arrays(raw, drop_last=True)

    lookback = params.slow_period + params.signal_period + 2
    if len(cl) < lookback:
        log.error("Không đủ nến cho MACD/RSI (cần >= %s)", lookback)
        return

    st = load_state(state_path)
    pos = st.get("position")
    ticker = exchange.fetch_ticker(symbol)
    mark = float(ticker.get("last") or ticker.get("close") or cl[-1])

    o_open = order_params_open(exchange_tag)
    o_close = order_params_close(exchange_tag)

    if pos is not None:
        side = str(pos["side"])
        stop_px = float(pos["stop"])
        tp_px = float(pos["tp"])
        amount = float(pos["amount"])
        ex = macd_rsi_exit_by_mark(side, stop_px, tp_px, mark)
        if ex is not None:
            reason, _ = ex
            log.info("Thoát %s: %s (mark=%.2f)", side, reason, mark)
            if not dry_run:
                if side == "long":
                    exchange.create_order(
                        symbol, "market", "sell", amount, None, o_close
                    )
                else:
                    exchange.create_order(
                        symbol, "market", "buy", amount, None, o_close
                    )
            st["position"] = None
            save_state(state_path, st)
        else:
            log.info("Giữ %s entry=%.2f stop=%.2f tp=%.2f mark=%.2f", side, pos["entry"], stop_px, tp_px, mark)
        return

    snap = macd_rsi_entry_snapshot(ot, hi, lo, cl, params, allow_short=True)
    last_sig = int(st.get("last_signal_entered_ms") or 0)
    if snap is None:
        log.info("Không có tín hiệu MACD+RSI trên nến đóng cuối (%s)", timeframe)
        return

    sig_t = int(snap["signal_open_time_ms"])
    if sig_t <= last_sig:
        log.info("Tín hiệu nến %s đã xử lý trước đó, bỏ qua", sig_t)
        return

    side = str(snap["side"])
    price_ref = mark
    if side == "long":
        stop_px = price_ref * (1.0 - params.stop_loss_pct)
        tp_px = price_ref * (1.0 + params.take_profit_pct)
    else:
        stop_px = price_ref * (1.0 + params.stop_loss_pct)
        tp_px = price_ref * (1.0 - params.take_profit_pct)
    amount = _round_amount(exchange, symbol, notional_usd / price_ref)
    if amount <= 0:
        log.error("amount sau làm tròn = 0")
        return

    log.info(
        "[%s] Vào %s ~%.2f SL=%.2f TP=%.2f notional~%.0f USDT",
        exchange_tag,
        side,
        price_ref,
        stop_px,
        tp_px,
        notional_usd,
    )

    if not dry_run:
        if side == "long":
            exchange.create_order(symbol, "market", "buy", amount, None, o_open)
        else:
            exchange.create_order(symbol, "market", "sell", amount, None, o_open)

    st["position"] = {
        "side": side,
        "entry": price_ref,
        "stop": stop_px,
        "tp": tp_px,
        "amount": amount,
        "symbol": symbol,
        "signal_open_time_ms": sig_t,
        "exchange": exchange_tag,
    }
    st["last_signal_entered_ms"] = sig_t
    save_state(state_path, st)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Bot MACD+RSI — OKX hoặc Binance futures")
    ap.add_argument("--once", action="store_true", help="Chạy một lần")
    ap.add_argument(
        "--loop",
        type=int,
        metavar="SEC",
        default=0,
        help="Lặp lại mỗi SEC giây (Ctrl+C dừng). 0 = không lặp",
    )
    args = ap.parse_args()

    if not args.once and args.loop <= 0:
        ap.error("Cần --once hoặc --loop SEC (vd --loop 300)")

    load_dotenv(ROOT / ".env")
    dry = os.environ.get("MACD_RSI_DRY_RUN", "1").strip() not in ("0", "false", "False")
    ex_raw = os.environ.get("MACD_RSI_EXCHANGE", "okx")
    notional = float(os.environ.get("MACD_RSI_NOTIONAL_USD", "100"))
    symbol = os.environ.get("MACD_RSI_SYMBOL", "BTC/USDT:USDT")
    lev = int(os.environ.get("MACD_RSI_LEVERAGE", "1"))
    tf = os.environ.get("MACD_RSI_TIMEFRAME", "1d")
    tp_pct = float(os.environ.get("MACD_RSI_TP_PCT", "0.10"))
    sl_pct = float(os.environ.get("MACD_RSI_SL_PCT", "0.04"))
    ema_trend = os.environ.get("MACD_RSI_EMA_TREND", "0").strip() in ("1", "true", "True")
    ema_fast = int(os.environ.get("MACD_RSI_EMA_FAST", "20"))
    ema_slow = int(os.environ.get("MACD_RSI_EMA_SLOW", "50"))

    exchange, exchange_tag = create_futures_exchange(ex_raw, dry_run=dry)
    state_path = _state_path(exchange_tag)

    params = MacdRsiParams(
        exit_mode="pct",
        take_profit_pct=tp_pct,
        stop_loss_pct=sl_pct,
        use_ema_trend_filter=ema_trend,
        ema_trend_fast=ema_fast,
        ema_trend_slow=ema_slow,
    )

    log.info(
        "exchange=%s dry_run=%s state=%s symbol=%s tf=%s TP=%.1f%% SL=%.1f%% ema_trend=%s EMA%d/%d",
        exchange_tag,
        dry,
        state_path.name,
        symbol,
        tf,
        tp_pct * 100,
        sl_pct * 100,
        ema_trend,
        ema_fast,
        ema_slow,
    )

    def one() -> None:
        run_once(
            exchange,
            exchange_tag,
            state_path,
            dry,
            notional,
            symbol,
            lev,
            tf,
            params,
        )

    if args.loop > 0:
        log.info("Loop mỗi %s giây (Ctrl+C để dừng)", args.loop)
        while True:
            try:
                one()
            except Exception as e:
                log.exception("Lỗi vòng lặp: %s", e)
            time.sleep(max(1, args.loop))
    else:
        one()


if __name__ == "__main__":
    main()
