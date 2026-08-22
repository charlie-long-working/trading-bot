#!/usr/bin/env python3
"""
Bot Binance USD-M (BTC): short MTF — D1 + H4 (resample từ 1h) + H1 (RSI cuối ngày),
khớp lệnh theo giá thị trường sau khi nến **D1 UTC** đóng (cron ~ 00:05 UTC).

.env (thư mục Trading-bot):
  BINANCE_API_KEY, BINANCE_API_SECRET — nếu BOTDOWN_DRY_RUN=0
  BOTDOWN_DRY_RUN=1
  BOTDOWN_NOTIONAL_USD=100
  BOTDOWN_SYMBOL=BTC/USDT:USDT
  BOTDOWN_LEVERAGE=1

  .venv/bin/python -m botdown.bot --once
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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

from botdown.signals_mtf_daily import mtf_daily_should_enter_short, mtf_daily_should_exit_short
from botdown.strategy_mtf import MtfParams

log = logging.getLogger("botdown")

MS_DAY = 86_400_000


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


def _state_path() -> Path:
    return ROOT / "botdown" / "state.json"


def load_state() -> Dict[str, Any]:
    p = _state_path()
    if not p.exists():
        return {"short": None, "last_exit_d1_open_ms": None}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        if "last_exit_d1_open_ms" not in d:
            d["last_exit_d1_open_ms"] = None
        return d
    except (json.JSONDecodeError, OSError):
        return {"short": None, "last_exit_d1_open_ms": None}


def save_state(st: Dict[str, Any]) -> None:
    p = _state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(st, indent=2), encoding="utf-8")


def _round_amount(exchange: Any, symbol: str, amount: float) -> float:
    m = exchange.market(symbol)
    prec = m.get("precision", {}).get("amount")
    if prec is not None:
        amount = float(exchange.amount_to_precision(symbol, amount))
    return max(amount, 0.0)


def run_once(
    dry_run: bool,
    notional_usd: float,
    symbol: str,
    leverage: int,
    params: MtfParams,
) -> None:
    if ccxt is None:
        raise RuntimeError("Cần cài ccxt")

    load_dotenv(ROOT / ".env")
    api_key = os.environ.get("BINANCE_API_KEY", "")
    api_secret = os.environ.get("BINANCE_API_SECRET", "")

    exchange = ccxt.binanceusdm(
        {
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
            "options": {"defaultType": "future"},
        }
    )

    if not dry_run and (not api_key or not api_secret):
        raise RuntimeError("Thiếu BINANCE_API_KEY / BINANCE_API_SECRET khi BOTDOWN_DRY_RUN=0")

    exchange.load_markets()
    if not dry_run:
        try:
            exchange.set_leverage(leverage, symbol)
        except Exception as e:
            log.warning("set_leverage: %s", e)

    raw_d1 = exchange.fetch_ohlcv(symbol, timeframe="1d", limit=500)
    raw_h1 = exchange.fetch_ohlcv(symbol, timeframe="1h", limit=3000)

    d1_ot, d1_o, d1_h, d1_l, d1_c, d1_v = _ohlcv_to_arrays(raw_d1, drop_last=True)
    h1_ot, h1_o, h1_h, h1_l, h1_c, h1_v = _ohlcv_to_arrays(raw_h1, drop_last=True)

    if len(d1_c) < params.d1_ma_trend + 5 or len(h1_c) < 500:
        log.error("Không đủ dữ liệu D1/H1 đóng")
        return

    st = load_state()
    pos = st.get("short")
    last_exit_ms = st.get("last_exit_d1_open_ms")

    if pos is not None:
        entry = float(pos["entry"])
        stop_px = float(pos["stop"])
        tp_px = float(pos["tp"])
        amount = float(pos["amount"])
        ex, reason = mtf_daily_should_exit_short(d1_h, d1_l, d1_c, stop_px, tp_px, params)
        if ex:
            log.info("Thoát short: %s entry=%.2f", reason, entry)
            if not dry_run:
                exchange.create_order(
                    symbol, "market", "buy", amount, None, {"reduceOnly": True}
                )
            st["short"] = None
            st["last_exit_d1_open_ms"] = int(d1_ot[-1])
            save_state(st)
        else:
            log.info("Giữ short entry=%.2f stop=%.2f tp=%.2f", entry, stop_px, tp_px)
        return

    if last_exit_ms is not None:
        cd_ms = params.cooldown_days_after_exit * MS_DAY
        if int(d1_ot[-1]) - int(last_exit_ms) < cd_ms:
            log.info("Cooldown sau thoát, bỏ qua vào lệnh")
            return

    enter = mtf_daily_should_enter_short(
        h1_ot, h1_o, h1_h, h1_l, h1_c, h1_v, d1_ot, d1_c, params
    )
    if not enter:
        log.info("Không có tín hiệu MTF (D1+H4+H1) sau đóng D1")
        return

    price_ref = float(exchange.fetch_ticker(symbol)["last"] or d1_c[-1])
    amount = _round_amount(exchange, symbol, notional_usd / price_ref)
    if amount <= 0:
        log.error("amount sau làm tròn = 0")
        return

    entry = price_ref
    stop_px = entry * (1 + params.stop_pct)
    tp_px = entry * (1 - params.take_profit_pct)

    log.info(
        "SHORT MTF notional~%.2f USDT amount=%s ~entry=%.2f stop=%.2f tp=%.2f",
        notional_usd,
        amount,
        entry,
        stop_px,
        tp_px,
    )

    if not dry_run:
        exchange.create_order(symbol, "market", "sell", amount)

    st["short"] = {
        "entry": entry,
        "stop": stop_px,
        "tp": tp_px,
        "amount": amount,
        "symbol": symbol,
    }
    save_state(st)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="Một lần rồi thoát")
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")
    dry = os.environ.get("BOTDOWN_DRY_RUN", "1").strip() not in ("0", "false", "False")
    notional = float(os.environ.get("BOTDOWN_NOTIONAL_USD", "100"))
    symbol = os.environ.get("BOTDOWN_SYMBOL", "BTC/USDT:USDT")
    lev = int(os.environ.get("BOTDOWN_LEVERAGE", "1"))
    params = MtfParams()

    if not args.once:
        ap.error("Hiện chỉ hỗ trợ --once (cron sau đóng D1 UTC).")

    log.info("dry_run=%s symbol=%s MTF→D1 execution", dry, symbol)
    run_once(dry, notional, symbol, lev, params)


if __name__ == "__main__":
    main()
