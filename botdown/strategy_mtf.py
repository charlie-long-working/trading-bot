"""Tham số và điều kiện đa khung: D1 xu hướng, H4 xác nhận, H1 trigger."""

from dataclasses import dataclass

import numpy as np

from .indicators import rsi, sma


@dataclass
class MtfParams:
    # D1 — bộ lọc bear (MA trend 120 để đủ lịch sử từ listing Binance ~08/2017)
    d1_ma_fast: int = 20
    d1_ma_slow: int = 50
    d1_ma_trend: int = 120

    # H4 — xác nhận xu hướng trung hạn (nhanh hơn D1)
    h4_ma_fast: int = 10
    h4_ma_slow: int = 34

    # H1 — vào / thoát
    h1_rsi_period: int = 14
    h1_rsi_entry_cross: float = 52.0
    h1_rsi_exit: float = 40.0
    stop_pct: float = 0.03
    take_profit_pct: float = 0.08
    fee_roundtrip: float = 0.001
    # Engine H1: cooldown theo số nến H1
    cooldown_bars_after_exit: int = 24
    # Engine khớp D1: cooldown theo số **ngày** sau khi thoát
    cooldown_days_after_exit: int = 1
    # Chỉ short khi H4 đã “hồi” đủ (RSI cao)
    h4_rsi_entry_min: float = 38.0


def trend_bearish_at(
    close: np.ndarray,
    ma_f: np.ndarray,
    ma_s: np.ndarray,
    ma_t: np.ndarray,
    i: int,
) -> bool:
    if i < 0 or i >= len(close):
        return False
    if np.isnan(ma_t[i]) or np.isnan(ma_s[i]) or np.isnan(ma_f[i]):
        return False
    return bool(close[i] < ma_t[i] and ma_f[i] < ma_s[i])


def trend_bearish_h4_simple(
    close: np.ndarray,
    ma_f: np.ndarray,
    ma_s: np.ndarray,
    i: int,
) -> bool:
    """H4 bear: giá dưới SMA chậm và SMA nhanh < SMA chậm (không cần SMA200 trên H4)."""
    if i < 0 or i >= len(close):
        return False
    if np.isnan(ma_s[i]) or np.isnan(ma_f[i]):
        return False
    return bool(close[i] < ma_s[i] and ma_f[i] < ma_s[i])


def h1_rsi_entry_cross(
    rsi_arr: np.ndarray,
    i_signal: int,
    cross: float,
) -> bool:
    if i_signal < 2:
        return False
    r0, r1 = rsi_arr[i_signal], rsi_arr[i_signal - 1]
    if np.isnan(r0) or np.isnan(r1):
        return False
    return bool(r1 < cross <= r0)


def h1_rsi_exit_below(rsi_arr: np.ndarray, i_signal: int, level: float) -> bool:
    r = rsi_arr[i_signal]
    if np.isnan(r):
        return False
    return bool(r < level)
