"""
MACD + RSI combined strategy.

Signal logic:
  LONG  – MACD histogram crosses above 0  AND  RSI < overbought threshold
  SHORT – MACD histogram crosses below 0  AND  RSI > oversold threshold

Stop-loss / take-profit derived from ATR.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np


class MACDRSISignal(Enum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


@dataclass
class MACDRSIParams:
    fast_period: int = 12
    slow_period: int = 26
    signal_period: int = 9
    rsi_period: int = 14
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0
    atr_period: int = 14
    atr_sl_mult: float = 1.5
    atr_tp_mult: float = 2.5


@dataclass
class MACDRSIResult:
    signal: MACDRSISignal
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    macd_hist: float = 0.0
    rsi: float = 50.0


def _ema(data: np.ndarray, period: int) -> np.ndarray:
    """Exponential moving average."""
    out = np.empty_like(data, dtype=np.float64)
    out[0] = data[0]
    alpha = 2.0 / (period + 1)
    for i in range(1, len(data)):
        out[i] = alpha * data[i] + (1 - alpha) * out[i - 1]
    return out


def _rsi(close: np.ndarray, period: int) -> np.ndarray:
    """Wilder-style RSI."""
    n = len(close)
    rsi = np.full(n, 50.0)
    if n < period + 1:
        return rsi
    delta = np.diff(close)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = np.mean(gain[:period])
    avg_loss = np.mean(loss[:period])
    if avg_loss == 0:
        rsi[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi[period] = 100.0 - 100.0 / (1.0 + rs)
    for i in range(period, len(delta)):
        avg_gain = (avg_gain * (period - 1) + gain[i]) / period
        avg_loss = (avg_loss * (period - 1) + loss[i]) / period
        if avg_loss == 0:
            rsi[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i + 1] = 100.0 - 100.0 / (1.0 + rs)
    return rsi


def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    """Average True Range."""
    n = len(close)
    tr = np.empty(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
    atr = np.empty(n)
    atr[:period] = np.mean(tr[:period])
    for i in range(period, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


def macd_rsi_signal(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    params: Optional[MACDRSIParams] = None,
) -> MACDRSIResult:
    """
    Evaluate MACD+RSI at the latest bar.

    Requires at least slow_period + signal_period bars.
    """
    if params is None:
        params = MACDRSIParams()

    n = len(close)
    min_bars = params.slow_period + params.signal_period + 1
    if n < min_bars:
        return MACDRSIResult(signal=MACDRSISignal.NEUTRAL)

    ema_fast = _ema(close, params.fast_period)
    ema_slow = _ema(close, params.slow_period)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, params.signal_period)
    histogram = macd_line - signal_line

    rsi_arr = _rsi(close, params.rsi_period)
    atr_arr = _atr(high, low, close, params.atr_period)

    cur_hist = histogram[-1]
    prev_hist = histogram[-2]
    cur_rsi = rsi_arr[-1]
    cur_atr = atr_arr[-1]
    cur_close = close[-1]

    sig = MACDRSISignal.NEUTRAL
    sl = None
    tp = None

    # LONG: histogram crosses above zero, RSI not overbought
    if prev_hist <= 0 < cur_hist and cur_rsi < params.rsi_overbought:
        sig = MACDRSISignal.LONG
        sl = cur_close - params.atr_sl_mult * cur_atr
        tp = cur_close + params.atr_tp_mult * cur_atr

    # SHORT: histogram crosses below zero, RSI not oversold
    elif prev_hist >= 0 > cur_hist and cur_rsi > params.rsi_oversold:
        sig = MACDRSISignal.SHORT
        sl = cur_close + params.atr_sl_mult * cur_atr
        tp = cur_close - params.atr_tp_mult * cur_atr

    return MACDRSIResult(
        signal=sig,
        stop_loss=sl,
        take_profit=tp,
        macd_hist=float(cur_hist),
        rsi=float(cur_rsi),
    )
