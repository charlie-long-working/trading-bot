"""Tín hiệu MTF khớp D1 — dùng khi đã có đủ nến D1/H1 đóng (sau đóng nến ngày UTC)."""

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


def _last_h1_index_for_day(
    h1_ot: np.ndarray,
    day_start_ms: int,
    next_day_start_ms: int,
) -> int:
    ot = np.asarray(h1_ot, dtype=np.int64)
    m = (ot >= day_start_ms) & (ot < next_day_start_ms)
    idx = np.where(m)[0]
    if len(idx) == 0:
        return -1
    return int(idx[-1])


def mtf_daily_should_enter_short(
    h1_ot: np.ndarray,
    h1_o: np.ndarray,
    h1_h: np.ndarray,
    h1_l: np.ndarray,
    h1_c: np.ndarray,
    h1_v: np.ndarray,
    d1_ot: np.ndarray,
    d1_c: np.ndarray,
    params: Optional[MtfParams] = None,
) -> bool:
    """
    `d1_*` / `h1_*` là nến **đã đóng** (đã bỏ nến ngày đang chạy nếu có).
    Giả định nến D1 cuối = **hôm qua**; kiểm tra điều kiện vào short tại **open hôm nay**
    (bot dùng giá market thay cho open chưa có trong CSV).
    """
    params = params or MtfParams()
    d1_ot = np.asarray(d1_ot, dtype=np.int64)
    d1_c = np.asarray(d1_c, dtype=float)
    nd = len(d1_c)
    if nd < params.d1_ma_trend + 3:
        return False

    L = nd - 1
    prev = L
    if prev < params.d1_ma_trend - 1:
        return False

    h4_ot, _, h4_h, h4_l, h4_c, h4_v = resample_ohlcv(
        h1_ot, h1_o, h1_h, h1_l, h1_c, h1_v, MS_4H
    )
    d1_ma_f = sma(d1_c, params.d1_ma_fast)
    d1_ma_s = sma(d1_c, params.d1_ma_slow)
    d1_ma_t = sma(d1_c, params.d1_ma_trend)
    h4_ma_f = sma(h4_c, params.h4_ma_fast)
    h4_ma_s = sma(h4_c, params.h4_ma_slow)
    h4_rsi_arr = rsi(h4_c, params.h1_rsi_period)
    h1_rsi_arr = rsi(h1_c, params.h1_rsi_period)

    d_ok = trend_bearish_at(d1_c, d1_ma_f, d1_ma_s, d1_ma_t, prev)
    next_open = int(d1_ot[L] + MS_DAY)
    h4_idx = int(last_closed_htf_index(h4_ot, MS_4H, np.array([next_open], dtype=np.int64))[0])
    if h4_idx < params.h4_ma_slow - 1:
        return False
    h4_ok = trend_bearish_h4_simple(h4_c, h4_ma_f, h4_ma_s, h4_idx)
    h4_r = h4_rsi_arr[h4_idx]
    if np.isnan(h4_r) or h4_r < params.h4_rsi_entry_min:
        return False

    day_s = int(d1_ot[L])
    day_e = next_open
    li1 = _last_h1_index_for_day(h1_ot, day_s, day_e)
    if li1 < 2:
        return False
    sig_h1 = li1 - 1
    return bool(h1_rsi_entry_cross(h1_rsi_arr, sig_h1, params.h1_rsi_entry_cross))


def mtf_daily_should_exit_short(
    d1_h: np.ndarray,
    d1_l: np.ndarray,
    d1_c: np.ndarray,
    stop_px: float,
    tp_px: float,
    params: Optional[MtfParams] = None,
) -> Tuple[bool, str]:
    """Khớp engine: nến D1 cuối = ngày `di`, RSI thoát = chỉ số `di-1`."""
    params = params or MtfParams()
    d1_rsi = rsi(d1_c, params.h1_rsi_period)
    n = len(d1_c)
    if n < 2:
        return False, ""
    L = n - 1
    if d1_h[L] >= stop_px:
        return True, "stop"
    if d1_l[L] <= tp_px:
        return True, "target"
    if L >= 1 and h1_rsi_exit_below(d1_rsi, L - 1, params.h1_rsi_exit):
        return True, "rsi"
    return False, ""
