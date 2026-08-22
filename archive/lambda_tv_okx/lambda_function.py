"""
AWS Lambda — nhận POST (TradingView webhook) → đặt lệnh OKX swap.

Biến môi trường Lambda (Configuration → Environment variables):
  TV_WEBHOOK_SECRET   — bắt buộc; khớp ?secret= hoặc JSON {"secret":"..."}
  OKX_API_KEY
  OKX_API_SECRET
  OKX_API_PASSPHRASE
  OKX_TDMODE          — cross | isolated (mặc định cross)
  OKX_SYMBOL          — BTC/USDT:USDT
  OKX_NOTIONAL_USD    — 100
  OKX_LEVERAGE        — 1

Body JSON: {"cmd":"long"|"short"|"close"}  (+ secret nếu không gửi trên URL)
Xem README.md trong thư mục này để deploy.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any, Dict, Optional, Tuple

import ccxt  # type: ignore

log = logging.getLogger()
log.setLevel(logging.INFO)

_exchange: Optional[Any] = None


def _exchange() -> Any:
    global _exchange
    if _exchange is None:
        _exchange = ccxt.okx(
            {
                "apiKey": os.environ.get("OKX_API_KEY", ""),
                "secret": os.environ.get("OKX_API_SECRET", ""),
                "password": os.environ.get("OKX_API_PASSPHRASE", ""),
                "enableRateLimit": True,
                "options": {"defaultType": "swap"},
            }
        )
        _exchange.load_markets()
    return _exchange


def _response(status: int, body: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _parse_event(event: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[Dict[str, str]]]:
    """Trả về (payload dict, query_params)."""
    qs = event.get("queryStringParameters") or {}
    if isinstance(qs, str):
        qs = {}
    body_raw = event.get("body")
    if body_raw is None:
        return {}, qs
    if event.get("isBase64Encoded"):
        body_raw = base64.b64decode(body_raw).decode("utf-8", errors="replace")
    if isinstance(body_raw, dict):
        return body_raw, qs
    try:
        return json.loads(body_raw or "{}"), qs
    except json.JSONDecodeError:
        return {}, qs


def _check_secret(data: Dict[str, Any], qs: Dict[str, str]) -> bool:
    exp = (os.environ.get("TV_WEBHOOK_SECRET") or "").strip()
    if not exp:
        return False
    if (qs.get("secret") or "").strip() == exp:
        return True
    if (data.get("secret") or "").strip() == exp:
        return True
    return False


def _td_mode() -> str:
    return (os.environ.get("OKX_TDMODE") or "cross").strip().lower() or "cross"


def _round_amount(ex: Any, symbol: str, amount: float) -> float:
    m = ex.market(symbol)
    prec = m.get("precision", {}).get("amount")
    if prec is not None:
        amount = float(ex.amount_to_precision(symbol, amount))
    return max(amount, 0.0)


def _net_contracts(ex: Any, symbol: str) -> float:
    net = 0.0
    try:
        positions = ex.fetch_positions([symbol])
    except Exception as e:
        log.warning("fetch_positions: %s", e)
        return 0.0
    for p in positions:
        if p.get("symbol") != symbol:
            continue
        c = p.get("contracts")
        if c is None:
            c = p.get("size")
        try:
            v = float(c or 0)
        except (TypeError, ValueError):
            v = 0.0
        side = (p.get("side") or "").lower()
        if side == "short":
            net -= abs(v)
        else:
            net += abs(v)
    return net


def _handle_cmd(cmd: str, data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    symbol = (data.get("symbol") or os.environ.get("OKX_SYMBOL") or "BTC/USDT:USDT").strip()
    notional = float(data.get("notional_usd") or os.environ.get("OKX_NOTIONAL_USD") or "100")
    lev = int(os.environ.get("OKX_LEVERAGE") or "1")
    td = _td_mode()
    o_open = {"tdMode": td}
    o_close = {"tdMode": td, "reduceOnly": True}

    ex = _exchange()
    try:
        ex.set_leverage(lev, symbol)
    except Exception as e:
        log.warning("set_leverage: %s", e)

    ticker = ex.fetch_ticker(symbol)
    price = float(ticker.get("last") or ticker.get("close") or 0)
    if price <= 0:
        return {"ok": False, "error": "no price"}, 500

    cmd = cmd.strip().lower()

    if cmd in ("long", "buy"):
        amt = _round_amount(ex, symbol, notional / price)
        if amt <= 0:
            return {"ok": False, "error": "amount=0"}, 400
        r = ex.create_order(symbol, "market", "buy", amt, None, o_open)
        return {"ok": True, "side": "buy", "amount": amt, "id": r.get("id")}, 200

    if cmd in ("short", "sell_open"):
        amt = _round_amount(ex, symbol, notional / price)
        if amt <= 0:
            return {"ok": False, "error": "amount=0"}, 400
        r = ex.create_order(symbol, "market", "sell", amt, None, o_open)
        return {"ok": True, "side": "sell", "amount": amt, "id": r.get("id")}, 200

    if cmd in ("close", "flat", "exit"):
        pos = _net_contracts(ex, symbol)
        if abs(pos) < 1e-12:
            return {"ok": True, "message": "flat"}, 200
        amt = _round_amount(ex, symbol, abs(pos))
        if pos > 0:
            r = ex.create_order(symbol, "market", "sell", amt, None, o_close)
        else:
            r = ex.create_order(symbol, "market", "buy", amt, None, o_close)
        return {"ok": True, "closed": amt, "id": r.get("id")}, 200

    return {"ok": False, "error": f"unknown cmd: {cmd}"}, 400


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    if not isinstance(event, dict):
        return _response(400, {"ok": False, "error": "bad event"})

    # Function URL / HTTP API: POST
    method = (
        event.get("requestContext", {})
        .get("http", {})
        .get("method", event.get("httpMethod", "POST"))
    )
    if str(method).upper() not in ("POST", "GET"):
        return _response(405, {"ok": False, "error": "method"})

    if str(method).upper() == "GET":
        return _response(200, {"ok": True, "ping": "tv-okx-lambda"})

    data, qs = _parse_event(event)
    if not _check_secret(data, qs):
        log.warning("unauthorized")
        return _response(401, {"ok": False, "error": "unauthorized"})

    cmd = (data.get("cmd") or data.get("action") or "").strip()
    if not cmd:
        return _response(400, {"ok": False, "error": "missing cmd"})

    try:
        body, code = _handle_cmd(cmd, data)
    except Exception as e:
        log.exception("handle")
        return _response(500, {"ok": False, "error": str(e)})

    return _response(code, body)
