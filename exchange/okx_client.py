"""
OKX REST API v5 client: candles (public) và place order (private).

- Candles: GET /api/v5/market/candles hoặc history-candles.
- Place order: POST /api/v5/trade/order.
- Auth: OK-ACCESS-KEY, OK-ACCESS-SIGN, OK-ACCESS-TIMESTAMP, OK-ACCESS-PASSPHRASE.
"""

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests


# OKX bar: 1m, 3m, 5m, 15m, 30m, 1H, 2H, 4H, 6H, 12H, 1D, 1W, 1M
INTERVAL_TO_BAR = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1H",
    "2h": "2H",
    "4h": "4H",
    "1d": "1D",
    "1w": "1W",
}


def _symbol_to_inst_id(symbol: str, market_type: str) -> str:
    """Chuyển BTCUSDT + spot/um -> OKX instId (BTC-USDT hoặc BTC-USDT-SWAP)."""
    # Giả định symbol dạng BTCUSDT, ETHUSDT
    if "-" in symbol:
        base, quote = symbol.split("-", 1)
    else:
        for q in ("USDT", "USDC", "USD", "BUSD"):
            if symbol.endswith(q):
                base = symbol[: -len(q)]
                quote = q
                break
        else:
            base, quote = symbol[:-4], symbol[-4:]
    inst = f"{base}-{quote}"
    if market_type in ("um", "swap", "futures"):
        inst = f"{inst}-SWAP"
    return inst


@dataclass
class OKXConfig:
    api_key: str
    secret_key: str
    passphrase: str
    demo: bool = False  # True = demo trading


class OKXClient:
    """
    Client OKX REST API v5.
    - get_candles: lấy nến (public, không cần API key).
    - place_order, get_max_avail_size: cần API key (Trade/Read).
    """

    def __init__(self, config: Optional[OKXConfig] = None):
        self.config = config
        self._base = "https://www.okx.com" if not (config and config.demo) else "https://www.okx.com"  # Demo: same domain, flag in header not used for public endpoints
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    def _sign(self, method: str, path: str, body: str = "") -> Dict[str, str]:
        if not self.config:
            return {}
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        prehash = timestamp + method.upper() + path + body
        sig = base64.b64encode(
            hmac.new(
                self.config.secret_key.encode("utf-8"),
                prehash.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        ).decode("utf-8")
        return {
            "OK-ACCESS-KEY": self.config.api_key,
            "OK-ACCESS-SIGN": sig,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.config.passphrase,
        }

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict] = None,
        json_body: Optional[Dict] = None,
        signed: bool = False,
    ) -> Dict[str, Any]:
        url = self._base + path
        body = json.dumps(json_body) if json_body else ""
        headers = {}
        if signed and self.config:
            headers = self._sign(method, path, body)
        resp = self._session.request(
            method,
            url,
            params=params,
            data=body if method != "GET" else None,
            headers=headers,
            timeout=30,
        )
        out = resp.json() if resp.text else {}
        if resp.status_code != 200:
            raise RuntimeError(f"OKX API error {resp.status_code}: {out}")
        return out

    def get_candles(
        self,
        inst_id: str,
        bar: str = "1H",
        limit: int = 300,
        after: Optional[str] = None,
        before: Optional[str] = None,
        use_history: bool = False,
    ) -> List[List[str]]:
        """
        Lấy nến. Mỗi phần tử: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm].
        OKX trả về mới nhất trước; có thể cần reverse để thứ tự thời gian tăng dần.
        """
        path = "/api/v5/market/history-candles" if use_history else "/api/v5/market/candles"
        params = {"instId": inst_id, "bar": bar, "limit": str(min(limit, 300))}
        if after:
            params["after"] = after
        if before:
            params["before"] = before
        data = self._request("GET", path, params=params, signed=False)
        if data.get("code") != "0":
            raise RuntimeError(f"OKX candles error: {data}")
        return data.get("data", [])

    def get_candles_asc(
        self,
        inst_id: str,
        bar: str = "1H",
        limit: int = 300,
        use_history: bool = False,
    ) -> List[List[str]]:
        """Lấy nến và sắp xếp theo thời gian tăng dần (cũ -> mới)."""
        rows = self.get_candles(inst_id=inst_id, bar=bar, limit=limit, use_history=use_history)
        if not rows:
            return []
        rows = sorted(rows, key=lambda r: int(r[0]))
        return rows

    def place_order(
        self,
        inst_id: str,
        side: str,
        ord_type: str,
        sz: str,
        td_mode: str = "cross",
        px: Optional[str] = None,
        sl_trigger_px: Optional[str] = None,
        sl_ord_px: Optional[str] = None,
        tp_trigger_px: Optional[str] = None,
        tp_ord_px: Optional[str] = None,
        cl_ord_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Đặt lệnh. side: buy | sell; ord_type: market | limit; sz: số contract (SWAP) hoặc base (SPOT).
        td_mode: cross | isolated | cash (spot).
        """
        body = {
            "instId": inst_id,
            "tdMode": td_mode,
            "side": side.lower(),
            "ordType": ord_type.lower(),
            "sz": str(sz),
        }
        if px and ord_type.lower() == "limit":
            body["px"] = str(px)
        if sl_trigger_px is not None:
            body["slTriggerPx"] = str(sl_trigger_px)
        if sl_ord_px is not None:
            body["slOrdPx"] = str(sl_ord_px)
        if tp_trigger_px is not None:
            body["tpTriggerPx"] = str(tp_trigger_px)
        if tp_ord_px is not None:
            body["tpOrdPx"] = str(tp_ord_px)
        if cl_ord_id:
            body["clOrdId"] = cl_ord_id
        data = self._request("POST", "/api/v5/trade/order", json_body=body, signed=True)
        if data.get("code") != "0":
            raise RuntimeError(f"OKX place order error: {data}")
        return data

    def get_max_avail_size(self, inst_id: str, td_mode: str = "cross") -> Dict[str, Any]:
        """Lấy size tối đa có thể mua/bán (để tính position size)."""
        data = self._request(
            "GET",
            "/api/v5/account/max-avail-size",
            params={"instId": inst_id, "tdMode": td_mode},
            signed=True,
        )
        if data.get("code") != "0":
            raise RuntimeError(f"OKX max-avail-size error: {data}")
        return data

    @staticmethod
    def symbol_to_inst_id(symbol: str, market_type: str) -> str:
        return _symbol_to_inst_id(symbol, market_type)
