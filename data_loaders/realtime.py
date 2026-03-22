"""
Realtime klines từ Binance REST API (public, không cần API key).

Trả về cùng format với load_merged_klines: (open_time, open, high, low, close, volume).
Dùng cho signal realtime khi không có dữ liệu crawler hoặc cần cập nhật mới nhất.
"""

import time
from pathlib import Path
from typing import Optional, Tuple, Union

import numpy as np

try:
    import requests
except ImportError:
    requests = None

# Binance REST API base URLs (public endpoints, no API key)
BINANCE_SPOT_BASE = "https://api.binance.com"
BINANCE_FUTURES_BASE = "https://fapi.binance.com"

# Intervals supported by Binance REST API
BINANCE_INTERVALS = (
    "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h",
    "1d", "3d", "1w", "1M",
)


def _get_base_url(market_type: str) -> str:
    """Chọn base URL theo market_type."""
    if market_type in ("um", "futures", "swap"):
        return BINANCE_FUTURES_BASE
    return BINANCE_SPOT_BASE


def _get_klines_path(market_type: str) -> str:
    """Chọn path klines theo market_type."""
    if market_type in ("um", "futures", "swap"):
        return "/fapi/v1/klines"
    return "/api/v3/klines"


def fetch_binance_klines(
    symbol: str,
    interval: str,
    market_type: str = "spot",
    limit: int = 500,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
    retries: int = 3,
) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    """
    Lấy klines realtime từ Binance REST API.

    Args:
        symbol: Cặp giao dịch (vd: BTCUSDT, ETHUSDT).
        interval: Khung thời gian (1m, 5m, 15m, 1h, 4h, 1d, ...).
        market_type: "spot" hoặc "um" (futures USD-M).
        limit: Số nến (mặc định 500, tối đa 1500).
        start_time: Timestamp ms (optional).
        end_time: Timestamp ms (optional).
        retries: Số lần retry khi 429.

    Returns:
        (open_time, open, high, low, close, volume) dạng numpy arrays,
        thứ tự tăng dần (cũ -> mới), tương thích load_merged_klines.
        None nếu lỗi.
    """
    if requests is None:
        raise ImportError("Cần cài requests: pip install requests")

    base = _get_base_url(market_type)
    path = _get_klines_path(market_type)
    url = f"{base}{path}"

    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": min(limit, 1500),
    }
    if start_time is not None:
        params["startTime"] = start_time
    if end_time is not None:
        params["endTime"] = end_time

    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=30)
            if r.status_code == 429:
                wait = 2 ** attempt
                time.sleep(wait)
                continue
            r.raise_for_status()
            data = r.json()
            break
        except Exception:
            if attempt == retries - 1:
                return None
            time.sleep(2 ** attempt)

    if not data or not isinstance(data, list):
        return None

    rows = []
    for row in data:
        if len(row) < 6:
            continue
        try:
            open_time = int(row[0])
            open_ = float(row[1])
            high = float(row[2])
            low = float(row[3])
            close = float(row[4])
            volume = float(row[5])
        except (ValueError, IndexError, TypeError):
            continue
        rows.append((open_time, open_, high, low, close, volume))

    if not rows:
        return None

    open_time = np.array([r[0] for r in rows])
    open_ = np.array([r[1] for r in rows])
    high = np.array([r[2] for r in rows])
    low = np.array([r[3] for r in rows])
    close = np.array([r[4] for r in rows])
    volume = np.array([r[5] for r in rows])

    return open_time, open_, high, low, close, volume


def load_klines_with_realtime_fallback(
    data_dir: Union[str, Path],
    market_type: str,
    symbol: str,
    interval: str,
    limit: int = 500,
):
    """
    Thử load từ file trước; nếu không có thì lấy realtime từ Binance.

    Returns:
        (open_time, open, high, low, close, volume) hoặc None.
    """
    from .load_klines import load_merged_klines

    out = load_merged_klines(data_dir, market_type, symbol, interval)
    if out is not None:
        return out
    return fetch_binance_klines(symbol, interval, market_type, limit=limit)


def fetch_binance_ticker_price(
    symbol: str,
    market_type: str = "spot",
) -> Optional[float]:
    """
    Lấy giá hiện tại (last price) từ Binance.

    Returns:
        Giá float hoặc None nếu lỗi.
    """
    if requests is None:
        raise ImportError("Cần cài requests: pip install requests")

    base = _get_base_url(market_type)
    path = "/fapi/v1/ticker/price" if market_type in ("um", "futures", "swap") else "/api/v3/ticker/price"
    url = f"{base}{path}"

    try:
        r = requests.get(url, params={"symbol": symbol}, timeout=10)
        r.raise_for_status()
        data = r.json()
        return float(data.get("price", 0))
    except Exception:
        return None
