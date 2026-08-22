"""
Chiến lược ưu tiên downtrend (backtest trên BTC futures logic — PnL theo giá).

Ý tưởng (điều chỉnh sau backtest 2017–2018 & 2021–2022):
- Chỉ xét short khi cấu trúc giảm: giá đóng cửa dưới SMA(chậm) và SMA(nhanh) < SMA(chậm).
- Vào short khi phục hồi yếu: RSI vừa cắt lên ngưỡng (quá mua nhẹ trong xu hướng giảm).
- Thoát: chạm stop %, chạm take-profit %, hoặc RSI hạ xuống dưới ngưỡng (hết đà hồi).

Không nhìn trước: tín hiệu tại nến i-1, vào lệnh tại giá mở cửa nến i.
"""

from dataclasses import dataclass
from typing import Literal, Optional, Tuple

import numpy as np

from .indicators import rsi, sma


@dataclass
class DowntrendParams:
    ma_fast: int = 20
    ma_slow: int = 50
    ma_trend: int = 200
    rsi_period: int = 14
    # Đã grid-search trên spot: 2017-12→2018-08 và 2021-11→2022-12 (BTC 1D)
    rsi_entry_cross: float = 52.0
    rsi_exit: float = 40.0
    stop_pct: float = 0.03
    take_profit_pct: float = 0.08
    fee_roundtrip: float = 0.001
    require_close_below_ma_fast: bool = False


Side = Literal["flat", "short"]


def trend_bearish(
    close: np.ndarray,
    ma_fast: np.ndarray,
    ma_slow: np.ndarray,
    ma_trend: np.ndarray,
    i: int,
) -> bool:
    """Bearish structure at bar i (chỉ dùng chỉ báo đã khóa tại i)."""
    if i < 1:
        return False
    if np.isnan(ma_trend[i]) or np.isnan(ma_slow[i]) or np.isnan(ma_fast[i]):
        return False
    return bool(close[i] < ma_trend[i] and ma_fast[i] < ma_slow[i])


def should_enter_short(
    close: np.ndarray,
    rsi_arr: np.ndarray,
    ma_fast: np.ndarray,
    ma_slow: np.ndarray,
    ma_trend: np.ndarray,
    i_signal: int,
    cross: float,
    require_below_ma_fast: bool,
) -> bool:
    """Tín hiệu tại chỉ số i_signal (thường là i-1)."""
    if i_signal < 2:
        return False
    if not trend_bearish(close, ma_fast, ma_slow, ma_trend, i_signal):
        return False
    r0 = rsi_arr[i_signal]
    r1 = rsi_arr[i_signal - 1]
    if np.isnan(r0) or np.isnan(r1):
        return False
    if not (r1 < cross <= r0):
        return False
    if require_below_ma_fast:
        mf = ma_fast[i_signal]
        if np.isnan(mf):
            return False
        if not (close[i_signal] < mf):
            return False
    return True


def should_exit_short(rsi_arr: np.ndarray, i_signal: int, exit_level: float) -> bool:
    if i_signal < 0:
        return False
    r = rsi_arr[i_signal]
    if np.isnan(r):
        return False
    return bool(r < exit_level)
