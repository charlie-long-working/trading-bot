"""Đa khung: resample 1h → 4h, map thời gian H1 → D1/H4 (chỉ nến đã đóng)."""

from typing import Tuple

import numpy as np


def resample_ohlcv(
    open_time: np.ndarray,
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    volume: np.ndarray,
    period_ms: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Gộp nến H1 thành H4 (period_ms = 4 * 3600 * 1000)."""
    ot = np.asarray(open_time, dtype=np.int64)
    o = np.asarray(open_, dtype=float)
    h = np.asarray(high, dtype=float)
    l_ = np.asarray(low, dtype=float)
    c = np.asarray(close, dtype=float)
    v = np.asarray(volume, dtype=float)
    n = len(ot)
    if n == 0:
        z = np.array([], dtype=np.int64)
        zf = np.array([], dtype=float)
        return zf, zf, zf, zf, zf, zf

    order = np.argsort(ot, kind="mergesort")
    ot = ot[order]
    o, h, l_, c, v = o[order], h[order], l_[order], c[order], v[order]
    bucket = (ot // period_ms) * period_ms

    out_ot, out_o, out_h, out_l, out_c, out_v = [], [], [], [], [], []
    i = 0
    while i < n:
        b = int(bucket[i])
        j = i
        while j < n and int(bucket[j]) == b:
            j += 1
        sl = slice(i, j)
        out_ot.append(b)
        out_o.append(float(o[sl][0]))
        out_h.append(float(np.max(h[sl])))
        out_l.append(float(np.min(l_[sl])))
        out_c.append(float(c[sl][-1]))
        out_v.append(float(np.sum(v[sl])))
        i = j

    return (
        np.array(out_ot, dtype=np.int64),
        np.array(out_o, dtype=float),
        np.array(out_h, dtype=float),
        np.array(out_l, dtype=float),
        np.array(out_c, dtype=float),
        np.array(out_v, dtype=float),
    )


def last_closed_htf_index(htf_open_time: np.ndarray, htf_period_ms: int, bar_open_time: np.ndarray) -> np.ndarray:
    """
    Với mỗi `bar_open_time` (H1), chỉ số nến HTF cuối cùng đã đóng trước khi nến đó mở.
    Đóng HTF tại htf_open + htf_period_ms.
    """
    htf_ot = np.asarray(htf_open_time, dtype=np.int64)
    ltf_ot = np.asarray(bar_open_time, dtype=np.int64)
    htf_end = htf_ot + int(htf_period_ms)
    return np.searchsorted(htf_end, ltf_ot, side="right") - 1
