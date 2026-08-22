"""Load BTC klines; drop rows with invalid open_time (ms)."""

from pathlib import Path
from typing import Optional, Tuple

import numpy as np

from data_loaders.load_klines import load_merged_klines


def _valid_time_mask(t: np.ndarray) -> np.ndarray:
    t = np.asarray(t, dtype=np.int64)
    # Binance spot/um klines use 13-digit Unix ms
    return (t >= 1_000_000_000_000) & (t < 10_000_000_000_000)


def load_btc_daily(
    repo_root: Path,
    market_type: str = "spot",
) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    """
    Mặc định spot để có lịch sử từ 2017; UM futures Binance chỉ có từ ~2020.
    Logic short giả định giá futures ~ spot trong backtest lịch sử.
    """
    data_dir = repo_root / "data"
    raw = load_merged_klines(str(data_dir), market_type, "BTCUSDT", "1d")
    if raw is None:
        return None
    open_time, open_, high, low, close, volume = raw
    m = _valid_time_mask(open_time)
    if not np.all(m):
        open_time = open_time[m]
        open_ = open_[m]
        high = high[m]
        low = low[m]
        close = close[m]
        volume = volume[m]
    return open_time, open_, high, low, close, volume


def load_btc_klines(
    repo_root: Path,
    interval: str,
    market_type: str = "spot",
) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    """interval: '1h', '1d', ... — file BTCUSDT-{interval}.csv"""
    data_dir = repo_root / "data"
    raw = load_merged_klines(str(data_dir), market_type, "BTCUSDT", interval)
    if raw is None:
        return None
    open_time, open_, high, low, close, volume = raw
    m = _valid_time_mask(open_time)
    if not np.all(m):
        open_time = open_time[m]
        open_ = open_[m]
        high = high[m]
        low = low[m]
        close = close[m]
        volume = volume[m]
    return open_time, open_, high, low, close, volume
