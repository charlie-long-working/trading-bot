"""
Lấy klines từ OKX API, trả về cùng format với load_merged_klines: (open_time, open, high, low, close, volume).

Dùng cho bot OKX: không cần crawler Binance, lấy nến trực tiếp từ OKX để chạy regime + fusion signal.
"""

from typing import Optional, Tuple

import numpy as np

from exchange.okx_client import OKXClient, OKXConfig, INTERVAL_TO_BAR
from exchange.okx_client import _symbol_to_inst_id


def fetch_okx_klines(
    client: OKXClient,
    symbol: str,
    market_type: str,
    interval: str,
    limit: int = 300,
    use_history: bool = True,
) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    """
    Lấy klines từ OKX, trả về (open_time, open, high, low, close, volume) dạng numpy arrays.
    Thứ tự thời gian tăng dần (cũ -> mới), tương thích với load_merged_klines.
    """
    inst_id = _symbol_to_inst_id(symbol, market_type)
    bar = INTERVAL_TO_BAR.get(interval.lower(), "1H")
    rows = client.get_candles_asc(
        inst_id=inst_id,
        bar=bar,
        limit=limit,
        use_history=use_history,
    )
    if not rows or len(rows) < 2:
        return None
    open_time = np.array([int(r[0]) for r in rows])
    open_ = np.array([float(r[1]) for r in rows])
    high = np.array([float(r[2]) for r in rows])
    low = np.array([float(r[3]) for r in rows])
    close = np.array([float(r[4]) for r in rows])
    volume = np.array([float(r[5]) for r in rows])
    return open_time, open_, high, low, close, volume
