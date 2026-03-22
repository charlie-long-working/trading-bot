#!/usr/bin/env python3
"""
TradingView webhook relay: TV -> this server -> OKX REST (place order).

TradingView should send JSON like:
{
  "symbol": "BTCUSDT",
  "market": "swap" | "spot",
  "side": "buy" | "sell",
  "entry": 71000.0,
  "sl": 69000.0,
  "tp": 73000.0,          // may be null
  "size_usdt": 100.0
}

The server then computes OKX order `sz` and calls OKX /api/v5/trade/order
with sl/tp trigger px when provided.

By default it runs in paper mode unless TV_OKX_PAPER=0.
"""

from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from exchange.okx_client import OKXClient, OKXConfig


def _load_env() -> None:
    # Load .env from project root
    here = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(here, ".env"), override=False)


def _parse_bool(x: str | None, default: bool) -> bool:
    if x is None:
        return default
    return x.strip().lower() in ("1", "true", "yes", "y", "on")


def _symbol_to_market_type(market: str) -> str:
    m = (market or "").strip().lower()
    if m in ("swap", "um", "futures"):
        return "um"  # OKX uses "-SWAP" instId suffix; OKXClient expects um/swap/futures
    return "spot"


def _td_mode_from_market_type(market_type: str) -> str:
    return "cash" if market_type == "spot" else "cross"


def _size_to_sz(market_type: str, symbol: str, size_usdt: float, last_price: float) -> str:
    """
    Replicates run_okx_bot.py logic for contract sizing.
    - SWAP: sz = contracts, ct_val = 0.01 for BTC, 0.1 for ETH.
    - Spot: sz = base amount = size_usdt/price
    """
    if last_price <= 0:
        raise ValueError("entry/last_price must be > 0")

    if market_type in ("um", "swap", "futures"):
        ct_val = 0.01 if "BTC" in symbol.upper() else 0.1
        contracts = size_usdt / (last_price * ct_val)
        return str(round(contracts, 0))

    base_sz = size_usdt / last_price
    if last_price >= 1000:
        return f"{base_sz:.4f}"
    if last_price >= 1:
        return f"{base_sz:.6f}"
    return f"{base_sz:.8f}"


def _json_float_or_none(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    # allow "null" string
    if isinstance(x, str) and x.strip().lower() == "null":
        return None
    return float(x)


class TVToOKXHandler(BaseHTTPRequestHandler):
    server: "TVToOKXHTTPServer"  # type: ignore[name-defined]

    def _send(self, code: int, payload: Dict[str, Any]) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            data = json.loads(body.decode("utf-8"))
        except Exception:
            self._send(400, {"ok": False, "error": "Invalid JSON"})
            return

        try:
            self.server.handle_payload(data)
            self._send(200, {"ok": True})
        except Exception as e:
            self._send(400, {"ok": False, "error": str(e)})

    # Silence default logging spam; uncomment if needed.
    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return


class TVToOKXHTTPServer(HTTPServer):
    def __init__(self, server_address: tuple[str, int], handler_cls, client: OKXClient, paper: bool):
        super().__init__(server_address, handler_cls)
        self._client = client
        self._paper = paper

    def handle_payload(self, data: Dict[str, Any]) -> None:
        # Required fields
        symbol = str(data.get("symbol", "")).strip()
        market = str(data.get("market", "swap")).strip()
        side = str(data.get("side", "")).strip().lower()
        entry = _json_float_or_none(data.get("entry"))
        sl = _json_float_or_none(data.get("sl"))
        tp = _json_float_or_none(data.get("tp"))
        size_usdt = _json_float_or_none(data.get("size_usdt"))

        if not symbol:
            raise ValueError("Missing field: symbol")
        if side not in ("buy", "sell"):
            raise ValueError("Field side must be buy|sell")
        if entry is None:
            raise ValueError("Missing/invalid field: entry")
        if size_usdt is None or size_usdt <= 0:
            raise ValueError("Missing/invalid field: size_usdt")

        market_type = _symbol_to_market_type(market)
        td_mode = _td_mode_from_market_type(market_type)
        inst_id = OKXClient.symbol_to_inst_id(symbol, market_type)
        sz = _size_to_sz(market_type, symbol, float(size_usdt), float(entry))

        if self._paper:
            print(
                f"[PAPER] {symbol} {side.upper()} instId={inst_id} sz={sz} "
                f"entry={entry} sl={sl} tp={tp} td_mode={td_mode}"
            )
            return

        sl_trigger = str(round(sl, 2)) if sl is not None else None
        tp_trigger = str(round(tp, 2)) if tp is not None else None

        # For market order, OKX in this project uses sl_ord_px=sl_trigger and tp_ord_px=tp_trigger
        result = self._client.place_order(
            inst_id=inst_id,
            side=side,
            ord_type="market",
            sz=sz,
            td_mode=td_mode,
            sl_trigger_px=sl_trigger,
            sl_ord_px=sl_trigger if sl_trigger is not None else None,
            tp_trigger_px=tp_trigger,
            tp_ord_px=tp_trigger if tp_trigger is not None else None,
        )
        ord_id = (result.get("data") or [{}])[0].get("ordId", "?")
        print(f"[OKX] {symbol} {side.upper()} placed ordId={ord_id}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--paper", type=str, default=os.environ.get("TV_OKX_PAPER", "1"))
    args = parser.parse_args()

    _load_env()

    api_key = os.environ.get("OKX_API_KEY", "").strip()
    secret_key = os.environ.get("OKX_SECRET_KEY", "").strip()
    passphrase = os.environ.get("OKX_PASSPHRASE", "").strip()
    paper = _parse_bool(args.paper, default=True)

    if not paper and (not api_key or not secret_key or not passphrase):
        raise SystemExit("Missing OKX_API_KEY / OKX_SECRET_KEY / OKX_PASSPHRASE for live mode.")

    config = OKXConfig(api_key=api_key, secret_key=secret_key, passphrase=passphrase, demo=False)
    client = OKXClient(config if not paper else None)

    server = TVToOKXHTTPServer(("0.0.0.0", args.port), TVToOKXHandler, client=client, paper=paper)
    print(f"TV->OKX webhook server listening on http://0.0.0.0:{args.port}/ (paper={paper})")
    print("Send POST JSON payload to this server.")
    server.serve_forever()


if __name__ == "__main__":
    main()

