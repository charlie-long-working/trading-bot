#!/usr/bin/env python3
"""
Nhận **TradingView alert → Webhook** rồi đặt lệnh **OKX swap** (ccxt).

TradingView **không** gửi thẳng tới OKX; luồng chuẩn là:
  Pine `alert()` / cảnh báo chiến lược → POST tới URL công khai của bạn → script này → OKX API.

## 1) Chuẩn bị
- Tài khoản TV có **Webhook URL** trong hộp thoại alert (thường cần gói trả phí — kiểm tra trang Pricing).
- Máy có **URL public** (VPS + domain, hoặc tunnel: `cloudflared tunnel`, `ngrok http 8787`).
- `.env` trong `Trading-bot/` (cùng các biến OKX như bot MACD):

  TRADINGVIEW_WEBHOOK_SECRET=một-chuỗi-ngẫu-nhiên-dài
  OKX_API_KEY=...
  OKX_API_SECRET=...
  OKX_API_PASSPHRASE=...
  MACD_RSI_OKX_TDMODE=cross
  TV_OKX_SYMBOL=BTC/USDT:USDT
  TV_OKX_NOTIONAL_USD=100
  TV_OKX_LEVERAGE=1

## 2) URL alert trên TradingView
  https://YOUR_DOMAIN/tv/okx?secret=YOUR_SECRET

  (Hoặc để secret chỉ trong JSON message — xem dưới.)

## 3) Nội dung Message (JSON) — ví dụ
  {"cmd":"long"}
  {"cmd":"short"}
  {"cmd":"close"}

  Nếu không dùng `?secret=` trên URL, bắt buộc:
  {"secret":"YOUR_SECRET","cmd":"long"}

## 4) Pine Script — gọi alert (ví dụ)
  if ta.crossover(close, ma)
      alert('{"cmd":"long"}', alert.freq_once_per_bar_close)

  if ta.crossunder(close, ma)
      alert('{"cmd":"short"}', alert.freq_once_per_bar_close)

  (Chiến lược: có thể dùng alertmessage trong strategy — tùy bạn đồng bộ với điều kiện vào/ra.)

## 5) Chạy server
  cd Trading-bot
  export TRADINGVIEW_WEBHOOK_SECRET=...
  .venv/bin/python -m botdown.tradingview_okx_webhook

  Mặc định port 8787 — đổi bằng biến TV_WEBHOOK_PORT

**Bảo mật:** luôn dùng HTTPS + secret mạnh; giới hạn IP nếu có (firewall / Cloudflare).

**Không phải lời khuyên đầu tư** — chỉ là mẫu kỹ thuật; kiểm tra kỹ trên demo trước.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*_a, **_k):  # type: ignore
        return False

from flask import Flask, request

from botdown.exchange_factory import (
    create_futures_exchange,
    order_params_close,
    order_params_open,
)

log = logging.getLogger("botdown.tv_webhook")

app = Flask(__name__)
_exchange: Any = None


def _get_exchange():
    global _exchange
    if _exchange is None:
        _exchange, _ = create_futures_exchange("okx", dry_run=False)
        _exchange.load_markets()
    return _exchange


def _parse_payload() -> Tuple[Dict[str, Any], str]:
    """Trả về (dict, raw_text)."""
    raw = request.get_data(as_text=True) or ""
    if not raw.strip():
        return {}, raw
    try:
        return json.loads(raw), raw
    except json.JSONDecodeError:
        return {}, raw


def _check_secret(data: Dict[str, Any]) -> bool:
    expected = (os.environ.get("TRADINGVIEW_WEBHOOK_SECRET") or "").strip()
    if not expected:
        log.error("Thiếu TRADINGVIEW_WEBHOOK_SECRET trong .env")
        return False
    q = (request.args.get("secret") or "").strip()
    if q and q == expected:
        return True
    if (data.get("secret") or "").strip() == expected:
        return True
    return False


def _round_amount(exchange: Any, symbol: str, amount: float) -> float:
    m = exchange.market(symbol)
    prec = m.get("precision", {}).get("amount")
    if prec is not None:
        amount = float(exchange.amount_to_precision(symbol, amount))
    return max(amount, 0.0)


def _set_lev(exchange: Any, symbol: str) -> None:
    lev = int(os.environ.get("TV_OKX_LEVERAGE", "1"))
    try:
        exchange.set_leverage(lev, symbol)
    except Exception as e:
        log.warning("set_leverage: %s", e)


@app.route("/tv/okx", methods=["POST"])
@app.route("/tv/okx/", methods=["POST"])
def tv_okx() -> Tuple[Dict[str, Any], int]:
    data, raw = _parse_payload()
    if not data and raw.strip():
        return {"ok": False, "error": "body phải là JSON hợp lệ"}, 400

    if not _check_secret(data):
        log.warning("secret sai hoặc thiếu")
        return {"ok": False, "error": "unauthorized"}, 401

    cmd = (data.get("cmd") or data.get("action") or "").strip().lower()
    if not cmd:
        return {"ok": False, "error": "thiếu cmd (long|short|close)"}, 400

    symbol = (data.get("symbol") or os.environ.get("TV_OKX_SYMBOL") or "BTC/USDT:USDT").strip()
    notional = float(data.get("notional_usd") or os.environ.get("TV_OKX_NOTIONAL_USD") or "100")

    try:
        ex = _get_exchange()
    except Exception as e:
        log.exception("exchange")
        return {"ok": False, "error": str(e)}, 500

    _set_lev(ex, symbol)
    ticker = ex.fetch_ticker(symbol)
    price = float(ticker.get("last") or ticker.get("close") or 0)
    if price <= 0:
        return {"ok": False, "error": "không lấy được giá"}, 500

    o_open = order_params_open("okx")
    o_close = order_params_close("okx")

    if cmd in ("long", "buy"):
        amt = _round_amount(ex, symbol, notional / price)
        if amt <= 0:
            return {"ok": False, "error": "amount=0"}, 400
        r = ex.create_order(symbol, "market", "buy", amt, None, o_open)
        log.info("LONG %s amount=%s", symbol, amt)
        return {"ok": True, "side": "buy", "amount": amt, "order": r.get("id")}, 200

    if cmd in ("short", "sell_open"):
        amt = _round_amount(ex, symbol, notional / price)
        if amt <= 0:
            return {"ok": False, "error": "amount=0"}, 400
        r = ex.create_order(symbol, "market", "sell", amt, None, o_open)
        log.info("SHORT %s amount=%s", symbol, amt)
        return {"ok": True, "side": "sell", "amount": amt, "order": r.get("id")}, 200

    if cmd in ("close", "flat", "exit"):
        pos = _fetch_net_contracts(ex, symbol)
        if pos is None or abs(pos) < 1e-12:
            return {"ok": True, "message": "không có vị thế"}, 200
        amt = abs(_round_amount(ex, symbol, abs(pos)))
        if pos > 0:
            r = ex.create_order(symbol, "market", "sell", amt, None, o_close)
        else:
            r = ex.create_order(symbol, "market", "buy", amt, None, o_close)
        log.info("CLOSE %s net=%s", symbol, pos)
        return {"ok": True, "closed": amt, "order": r.get("id")}, 200

    return {"ok": False, "error": f"cmd không hỗ trợ: {cmd}"}, 400


def _fetch_net_contracts(ex: Any, symbol: str) -> Optional[float]:
    """Số coin net (long + / short -) cho symbol — one-way."""
    try:
        positions = ex.fetch_positions([symbol])
    except Exception as e:
        log.warning("fetch_positions: %s", e)
        return None
    net = 0.0
    for p in positions:
        if p.get("symbol") != symbol:
            continue
        contracts = p.get("contracts")
        if contracts is None:
            contracts = p.get("size") or p.get("info", {}).get("pos")
        try:
            c = float(contracts or 0)
        except (TypeError, ValueError):
            c = 0.0
        side = (p.get("side") or "").lower()
        if side == "short":
            net -= abs(c)
        else:
            net += abs(c)
    return net


@app.route("/health", methods=["GET"])
def health() -> Tuple[Dict[str, str], int]:
    return {"status": "ok"}, 200


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    load_dotenv(ROOT / ".env")
    port = int(os.environ.get("TV_WEBHOOK_PORT", "8787"))
    if not (os.environ.get("TRADINGVIEW_WEBHOOK_SECRET") or "").strip():
        log.error("Đặt TRADINGVIEW_WEBHOOK_SECRET trong .env trước khi chạy.")
        sys.exit(1)
    log.info("Webhook OKX lắng nghe 0.0.0.0:%s POST /tv/okx", port)
    app.run(host="0.0.0.0", port=port, threaded=True)


if __name__ == "__main__":
    main()
