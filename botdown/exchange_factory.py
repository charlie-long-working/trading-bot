"""Khởi tạo ccxt cho MACD bot: OKX swap hoặc Binance USDT-M."""

from __future__ import annotations

import os
from typing import Any, Tuple

try:
    import ccxt  # type: ignore
except ImportError:
    ccxt = None  # type: ignore


def normalize_exchange_id(raw: str) -> str:
    x = (raw or "binanceusdm").strip().lower()
    if x in ("okex", "okx"):
        return "okx"
    if x in ("binance", "binanceusdm", "binance_futures"):
        return "binanceusdm"
    return x


def create_futures_exchange(
    exchange_id: str,
    *,
    dry_run: bool,
) -> Tuple[Any, str]:
    """
    Trả về (exchange, tag) với tag ∈ okx | binanceusdm.

    Biến môi trường:
    - OKX: OKX_API_KEY, OKX_API_SECRET, OKX_API_PASSPHRASE (bắt buộc khi không dry_run)
      OKX_SANDBOX=1 — demo/sandbox nếu bật trên tài khoản
    - Binance: BINANCE_API_KEY, BINANCE_API_SECRET
    """
    if ccxt is None:
        raise RuntimeError("Cần: pip install ccxt")

    tag = normalize_exchange_id(exchange_id)

    if tag == "okx":
        api_key = os.environ.get("OKX_API_KEY", "")
        secret = os.environ.get("OKX_API_SECRET", "")
        passphrase = os.environ.get("OKX_API_PASSPHRASE", "") or os.environ.get(
            "OKX_PASSWORD", ""
        )
        ex = ccxt.okx(
            {
                "apiKey": api_key,
                "secret": secret,
                "password": passphrase,
                "enableRateLimit": True,
                "options": {"defaultType": "swap"},
            }
        )
        if os.environ.get("OKX_SANDBOX", "").strip().lower() in ("1", "true", "yes"):
            ex.set_sandbox_mode(True)
        if not dry_run:
            if not api_key or not secret or not passphrase:
                raise RuntimeError(
                    "OKX cần OKX_API_KEY, OKX_API_SECRET, OKX_API_PASSPHRASE trong .env"
                )
        return ex, "okx"

    if tag == "binanceusdm":
        api_key = os.environ.get("BINANCE_API_KEY", "")
        secret = os.environ.get("BINANCE_API_SECRET", "")
        ex = ccxt.binanceusdm(
            {
                "apiKey": api_key,
                "secret": secret,
                "enableRateLimit": True,
                "options": {"defaultType": "future"},
            }
        )
        if not dry_run and (not api_key or not secret):
            raise RuntimeError("Binance cần BINANCE_API_KEY, BINANCE_API_SECRET khi MACD_RSI_DRY_RUN=0")
        return ex, "binanceusdm"

    raise ValueError(f"MACD_RSI_EXCHANGE không hỗ trợ: {exchange_id!r} (dùng okx hoặc binanceusdm)")


def okx_td_mode() -> str:
    return os.environ.get("MACD_RSI_OKX_TDMODE", "cross").strip().lower() or "cross"


def order_params_open(exchange_tag: str) -> dict:
    if exchange_tag == "okx":
        return {"tdMode": okx_td_mode()}
    return {}


def order_params_close(exchange_tag: str) -> dict:
    p = order_params_open(exchange_tag)
    p["reduceOnly"] = True
    return p
