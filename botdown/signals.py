"""Tín hiệu realtime / paper — cùng logic với backtest (numpy 1 bar)."""

from typing import Optional, Tuple

import numpy as np

from .indicators import rsi, sma
from .strategy import DowntrendParams, should_enter_short, trend_bearish


def compute_state(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    params: Optional[DowntrendParams] = None,
) -> Tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
]:
    params = params or DowntrendParams()
    c = np.asarray(close, dtype=float)
    ma_f = sma(c, params.ma_fast)
    ma_s = sma(c, params.ma_slow)
    ma_t = sma(c, params.ma_trend)
    rsi_arr = rsi(c, params.rsi_period)
    return c, ma_f, ma_s, ma_t, rsi_arr


def last_signal_enter_short(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    params: Optional[DowntrendParams] = None,
) -> bool:
    """
    `close/high/low` chỉ gồm nến **đã đóng** (không gồm nến đang chạy).
    True nếu nến đóng cuối cùng là tín hiệu vào short (khớp với backtest: vào ở phiên sau).
    """
    params = params or DowntrendParams()
    c, ma_f, ma_s, ma_t, rsi_arr = compute_state(close, high, low, params)
    n = len(c)
    if n < params.ma_trend + 3:
        return False
    sig = n - 1
    return should_enter_short(
        c,
        rsi_arr,
        ma_f,
        ma_s,
        ma_t,
        sig,
        params.rsi_entry_cross,
        params.require_close_below_ma_fast,
    )


def is_structural_bear(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    params: Optional[DowntrendParams] = None,
) -> bool:
    params = params or DowntrendParams()
    c, ma_f, ma_s, ma_t, _ = compute_state(close, high, low, params)
    n = len(c)
    if n < 2:
        return False
    return trend_bearish(c, ma_f, ma_s, ma_t, n - 1)
