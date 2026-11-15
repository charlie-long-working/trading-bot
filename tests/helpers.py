"""Synthetic OHLC helpers for offline tests."""

import numpy as np
import pandas as pd


def trend_ohlc(n: int, start: float = 100.0, step: float = 0.01, seed: int = 1, freq: str = "D",
               t0: str = "2024-01-01") -> pd.DataFrame:
    """Geometric trend (step>0 up, step<0 down) with small noise; columns date/open/high/low/close/volume."""
    rng = np.random.default_rng(seed)
    r = step + rng.normal(0, 0.002, n)
    close = start * np.exp(np.cumsum(r))
    open_ = np.r_[start, close[:-1]]
    high = np.maximum(open_, close) * 1.003
    low = np.minimum(open_, close) * 0.997
    return pd.DataFrame({
        "date": pd.date_range(t0, periods=n, freq=freq),
        "open": open_, "high": high, "low": low, "close": close, "volume": 1000.0,
    })
