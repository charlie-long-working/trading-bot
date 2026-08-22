"""Tín hiệu live: D1 + H4 (từ 1h) + H1 — khớp engine_mtf."""

from typing import Optional, Tuple

import numpy as np

from .indicators import rsi, sma
from .mtf import last_closed_htf_index, resample_ohlcv
from .strategy_mtf import (
    MtfParams,
    h1_rsi_entry_cross,
    h1_rsi_exit_below,
    trend_bearish_at,
    trend_bearish_h4_simple,
)

MS_DAY = 86_400_000
MS_4H = 4 * 3_600_000


def _closed_only(
    op: np.ndarray, hi: np.ndarray, lo: np.ndarray, cl: np.ndarray, vol: np.ndarray
) -> Tuple[np.ndarray, ...]:
    if len(cl) < 2:
        return cl[:0], cl[:0], cl[:0], cl[:0], cl[:0]
    return op[:-1], hi[:-1], lo[:-1], cl[:-1], vol[:-1]


def mtf_should_enter_short(
    h1_o: np.ndarray,
    h1_h: np.ndarray,
    h1_l: np.ndarray,
    h1_c: np.ndarray,
    h1_v: np.ndarray,
    h1_ot: np.ndarray,
    d1_ot: np.ndarray,
    d1_c: np.ndarray,
    params: Optional[MtfParams] = None,
) -> bool:
    """
    OHLCV H1 / thời gian H1 / D1 chỉ gồm nến đã đóng (đã bỏ nến cuối nếu đang chạy).
    D1 đủ dài để có SMA trend.
    """
    params = params or MtfParams()
    h4_ot, _, h4_h, h4_l, h4_c, h4_v = resample_ohlcv(
        h1_ot, h1_o, h1_h, h1_l, h1_c, h1_v, MS_4H
    )
    d1_ma_f = sma(d1_c, params.d1_ma_fast)
    d1_ma_s = sma(d1_c, params.d1_ma_slow)
    d1_ma_t = sma(d1_c, params.d1_ma_trend)
    h4_ma_f = sma(h4_c, params.h4_ma_fast)
    h4_ma_s = sma(h4_c, params.h4_ma_slow)
    h1_r = rsi(h1_c, params.h1_rsi_period)

    n = len(h1_c)
    if n < params.h1_rsi_period + 3:
        return False

    d1_idx = last_closed_htf_index(d1_ot, MS_DAY, h1_ot)
    h4_idx = last_closed_htf_index(h4_ot, MS_4H, h1_ot)
    i = n - 1
    sig = n - 2
    di = int(d1_idx[i])
    hi4 = int(h4_idx[i])
    if di < params.d1_ma_trend - 1 or hi4 < params.h4_ma_slow - 1:
        return False
    if di < 0 or hi4 < 0:
        return False

    d_ok = trend_bearish_at(d1_c, d1_ma_f, d1_ma_s, d1_ma_t, di)
    h4_ok = trend_bearish_h4_simple(h4_c, h4_ma_f, h4_ma_s, hi4)
    h1_ok = h1_rsi_entry_cross(h1_r, sig, params.h1_rsi_entry_cross)
    return bool(d_ok and h4_ok and h1_ok)


def mtf_should_exit_short(
    h1_h: np.ndarray,
    h1_l: np.ndarray,
    h1_c: np.ndarray,
    entry: float,
    stop_px: float,
    tp_px: float,
    params: Optional[MtfParams] = None,
) -> Tuple[bool, str]:
    """
    Khớp engine_mtf: stop/tp trên high/low nến cuối cùng đã đóng;
    RSI thoát dùng nến trước đó (sig = i-1 trong vòng lặp tại i = n-1).
    """
    params = params or MtfParams()
    h1_r = rsi(h1_c, params.h1_rsi_period)
    n = len(h1_c)
    if n < 3:
        return False, ""
    sig_rsi = n - 2
    last_h, last_l = float(h1_h[-1]), float(h1_l[-1])
    if last_h >= stop_px:
        return True, "stop"
    if last_l <= tp_px:
        return True, "target"
    if h1_rsi_exit_below(h1_r, sig_rsi, params.h1_rsi_exit):
        return True, "rsi"
    return False, ""
