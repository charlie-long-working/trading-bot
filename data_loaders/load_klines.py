"""
Load klines from crawler output: merged CSV or directory of ZIPs.

Returns pandas DataFrame (if available) or numpy arrays for use with strategy/backtest.
"""

from pathlib import Path
from typing import Optional, Tuple, Union

import numpy as np


def load_merged_klines(
    data_dir: Union[str, Path],
    market_type: str,
    symbol: str,
    interval: str,
) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    """
    Load merged CSV from data/{market_type}/klines/{symbol}/{symbol}-{interval}.csv.

    Returns (open_time, open, high, low, close, volume) as numpy arrays, or None if missing.
    First row is header; data rows are numeric only.
    """
    data_dir = Path(data_dir)
    path = data_dir / market_type / "klines" / symbol / f"{symbol}-{interval}.csv"
    if not path.exists():
        return None
    rows = []
    with open(path) as f:
        header = f.readline()
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            if len(parts) < 6:
                continue
            try:
                open_time = int(parts[0])
                open_ = float(parts[1])
                high = float(parts[2])
                low = float(parts[3])
                close = float(parts[4])
                volume = float(parts[5])
            except (ValueError, IndexError):
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


def load_klines_as_arrays(
    data_dir: Union[str, Path],
    market_type: str,
    symbol: str,
    interval: str,
) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    """Alias for load_merged_klines."""
    return load_merged_klines(data_dir, market_type, symbol, interval)
