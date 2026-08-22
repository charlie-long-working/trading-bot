"""
Session / rolling volume profile from OHLCV (approximation of VPVR).

Splits each bar's volume across price bins proportional to overlap with [low, high].
POC = bin with max volume; VAL/VAH from expanding from POC until value_area_pct of volume is captured.

Not tick order flow — only distributional volume-at-price from candles.
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class VolumeProfile:
    poc: float
    val: float
    vah: float
    total_volume: float


def compute_volume_profile(
    high: np.ndarray,
    low: np.ndarray,
    volume: np.ndarray,
    lookback: int,
    num_bins: int = 32,
    value_area_pct: float = 0.70,
) -> Optional[VolumeProfile]:
    """
    Rolling profile over the last `lookback` bars (inclusive of last bar).

    Returns None if not enough data or flat range / zero volume.
    """
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    volume = np.asarray(volume, dtype=float)
    n = len(high)
    if n < 2 or lookback < 5 or num_bins < 4:
        return None
    start = max(0, n - lookback)
    h = high[start:]
    l_ = low[start:]
    v = volume[start:]
    if len(h) < 5:
        return None

    lo = float(np.min(l_))
    hi = float(np.max(h))
    if hi <= lo * 1.0000001:
        tv = float(np.sum(v))
        if tv <= 0:
            return None
        mid = 0.5 * (lo + hi)
        return VolumeProfile(poc=mid, val=mid, vah=mid, total_volume=tv)

    edges = np.linspace(lo, hi, num_bins + 1)
    bin_vol = np.zeros(num_bins, dtype=float)

    for i in range(len(h)):
        bar_low, bar_high, vol = l_[i], h[i], v[i]
        if vol <= 0:
            continue
        if bar_high <= bar_low:
            idx = int(np.searchsorted(edges, bar_low, side="right") - 1)
            idx = max(0, min(num_bins - 1, idx))
            bin_vol[idx] += vol
            continue
        span = bar_high - bar_low
        for b in range(num_bins):
            bl, bh = edges[b], edges[b + 1]
            o_low = max(bar_low, bl)
            o_high = min(bar_high, bh)
            if o_high > o_low:
                bin_vol[b] += vol * (o_high - o_low) / span

    total = float(np.sum(bin_vol))
    if total <= 0:
        return None

    poc_i = int(np.argmax(bin_vol))
    poc = float(0.5 * (edges[poc_i] + edges[poc_i + 1]))

    target = value_area_pct * total
    cum = float(bin_vol[poc_i])
    lo_i = poc_i
    hi_i = poc_i
    while cum < target - 1e-12:
        ni_left = lo_i - 1
        ni_right = hi_i + 1
        vl = float(bin_vol[ni_left]) if ni_left >= 0 else -1.0
        vr = float(bin_vol[ni_right]) if ni_right < num_bins else -1.0
        if vl < 0 and vr < 0:
            break
        if vr < 0 or (vl >= 0 and vl >= vr):
            cum += vl
            lo_i = ni_left
        else:
            cum += vr
            hi_i = ni_right

    val = float(edges[lo_i])
    vah = float(edges[hi_i + 1])
    return VolumeProfile(poc=poc, val=val, vah=vah, total_volume=total)


def vp_allows_long(
    close: float,
    prof: Optional[VolumeProfile],
    mode: str,
) -> bool:
    """If prof is None, allow (no filter)."""
    if prof is None:
        return True
    if mode == "in_va":
        return prof.val <= close <= prof.vah
    if mode == "discount_premium":
        return close <= prof.poc
    return True


def vp_allows_short(
    close: float,
    prof: Optional[VolumeProfile],
    mode: str,
) -> bool:
    if prof is None:
        return True
    if mode == "in_va":
        return prof.val <= close <= prof.vah
    if mode == "discount_premium":
        return close >= prof.poc
    return True
