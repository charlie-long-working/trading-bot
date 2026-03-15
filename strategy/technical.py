"""
Smart money and structure: order blocks, fair value gaps, liquidity levels, supply/demand zones.

Uses OHLCV arrays (index 0 = oldest, -1 = latest). All functions accept numpy arrays or lists.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple

import numpy as np


# --- Swing points (for liquidity and structure) ---

def swing_highs(high: np.ndarray, left: int = 2, right: int = 2) -> np.ndarray:
    """Indices where high[i] is >= high[i-left:i+right+1]. left/right = lookback/lookahead bars."""
    high = np.asarray(high, dtype=float)
    n = len(high)
    out = []
    for i in range(left, n - right):
        window = list(range(i - left, i)) + list(range(i + 1, i + right + 1))
        if all(high[i] >= high[j] for j in window):
            out.append(i)
    return np.array(out) if out else np.array([], dtype=int)


def swing_lows(low: np.ndarray, left: int = 2, right: int = 2) -> np.ndarray:
    """Indices where low[i] is <= low[i-left:i+right+1]."""
    low = np.asarray(low, dtype=float)
    n = len(low)
    out = []
    for i in range(left, n - right):
        window = list(range(i - left, i)) + list(range(i + 1, i + right + 1))
        if all(low[i] <= low[j] for j in window):
            out.append(i)
    return np.array(out) if out else np.array([], dtype=int)


def liquidity_sweep(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    level: float,
    is_high: bool,
    lookback: int = 5,
) -> bool:
    """
    True if in the last `lookback` bars price swept beyond `level` then closed back.
    - is_high=True: level is a swing high; sweep = low went above level then closed below (bearish sweep).
    - is_high=False: level is a swing low; sweep = high went below level then closed above (bullish sweep).
    Simplified: we check if any bar had (high > level and close < level) for a high, or (low < level and close > level) for a low.
    """
    high = np.asarray(high[-lookback:])
    low = np.asarray(low[-lookback:])
    close = np.asarray(close[-lookback:])
    if is_high:
        return np.any((high > level) & (close < level))
    return np.any((low < level) & (close > level))


# --- Order blocks ---

class OBType(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"


@dataclass
class OrderBlock:
    """Order block zone: high and low of the OB candle, type, and bar index."""

    bar_index: int
    ob_type: OBType
    high: float
    low: float
    # Optional: strength (e.g. move size after OB)
    move_size: float = 0.0


def order_blocks(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    lookback: int = 50,
    move_bars: int = 5,
    min_move_pct: float = 0.5,
) -> List[OrderBlock]:
    """
    Detect order blocks in the last `lookback` bars.

    Bullish OB: last bearish (or doji) candle before a strong up move. Strong move = one of the next
    `move_bars` closes at least `min_move_pct` (e.g. 0.5%) above that candle's high.
    Bearish OB: last bullish (or doji) candle before a strong down move.

    Returns list of OrderBlock (most recent last in array order).
    """
    o = np.asarray(open_, dtype=float)
    h = np.asarray(high, dtype=float)
    l = np.asarray(low, dtype=float)
    c = np.asarray(close, dtype=float)
    n = len(c)
    start = max(0, n - lookback)
    result: List[OrderBlock] = []

    for i in range(start, n - move_bars):
        # Bearish candle: close < open (or near doji)
        bearish = c[i] <= o[i] or (abs(c[i] - o[i]) / (o[i] + 1e-12) < 0.001)
        # Bullish candle: close > open
        bullish = c[i] > o[i] or (abs(c[i] - o[i]) / (o[i] + 1e-12) < 0.001)

        # Strong up move after candle i
        hi = h[i]
        for j in range(1, move_bars + 1):
            if i + j >= n:
                break
            if hi > 0 and (c[i + j] - hi) / hi >= min_move_pct / 100.0:
                if bearish or abs(c[i] - o[i]) < 1e-12 * o[i]:
                    result.append(OrderBlock(
                        bar_index=i, ob_type=OBType.BULLISH, high=hi, low=l[i],
                        move_size=(c[i + j] - l[i]) / (l[i] + 1e-12) * 100,
                    ))
                break

        # Strong down move after candle i
        li = l[i]
        for j in range(1, move_bars + 1):
            if i + j >= n:
                break
            if li > 0 and (li - c[i + j]) / li >= min_move_pct / 100.0:
                if bullish or abs(c[i] - o[i]) < 1e-12 * o[i]:
                    result.append(OrderBlock(
                        bar_index=i, ob_type=OBType.BEARISH, high=h[i], low=li,
                        move_size=(h[i] - c[i + j]) / (h[i] + 1e-12) * 100,
                    ))
                break

    return result


# --- Fair value gaps ---

@dataclass
class FairValueGap:
    """FVG: top and bottom of the gap, type, bar index of the gap (middle candle)."""

    bar_index: int
    fvg_type: OBType  # BULLISH = bullish FVG, BEARISH = bearish FVG
    top: float
    bottom: float


def fair_value_gaps(
    high: np.ndarray,
    low: np.ndarray,
    lookback: int = 30,
) -> List[FairValueGap]:
    """
    Detect FVGs in the last `lookback` bars (3-candle pattern).
    Bullish FVG: candle 1 high < candle 3 low → gap between them.
    Bearish FVG: candle 1 low > candle 3 high → gap.
    """
    h = np.asarray(high, dtype=float)
    l = np.asarray(low, dtype=float)
    n = len(h)
    start = max(0, n - lookback)
    result: List[FairValueGap] = []

    for i in range(start, n - 2):
        # Bullish FVG: gap between candle 1 high and candle 3 low
        if h[i] < l[i + 2]:
            result.append(FairValueGap(
                bar_index=i + 1, fvg_type=OBType.BULLISH, top=l[i + 2], bottom=h[i],
            ))
        # Bearish FVG: gap between candle 1 low and candle 3 high
        if l[i] > h[i + 2]:
            result.append(FairValueGap(
                bar_index=i + 1, fvg_type=OBType.BEARISH, top=l[i], bottom=h[i + 2],
            ))

    return result


# --- Supply / demand zones ---

@dataclass
class Zone:
    """Supply or demand zone: top, bottom, type, bar index where zone formed."""

    bar_index: int
    is_demand: bool  # True = demand (support), False = supply (resistance)
    top: float
    bottom: float


def supply_demand_zones(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    lookback: int = 50,
    expansion_pct: float = 0.3,
    base_bars: int = 3,
) -> List[Zone]:
    """
    Simplified supply/demand: look for a small range (base) followed by a strong move.
    Demand: base then close significantly above base high.
    Supply: base then close significantly below base low.

    base_bars: number of bars in the "base" (consolidation).
    expansion_pct: minimum move in % from base high (demand) or base low (supply) to confirm.
    """
    o = np.asarray(open_, dtype=float)
    h = np.asarray(high, dtype=float)
    l = np.asarray(low, dtype=float)
    c = np.asarray(close, dtype=float)
    n = len(c)
    start = max(0, n - lookback)
    result: List[Zone] = []

    for i in range(start, n - base_bars - 1):
        base_high = np.max(h[i : i + base_bars])
        base_low = np.min(l[i : i + base_bars])
        mid = (base_high + base_low) / 2
        if mid <= 0:
            continue
        # Candle after base
        k = i + base_bars
        if k >= n:
            break
        # Demand: close above base high by expansion_pct
        if (c[k] - base_high) / mid * 100 >= expansion_pct:
            result.append(Zone(
                bar_index=i + base_bars - 1, is_demand=True,
                top=base_high, bottom=base_low,
            ))
        # Supply: close below base low by expansion_pct
        if (base_low - c[k]) / mid * 100 >= expansion_pct:
            result.append(Zone(
                bar_index=i + base_bars - 1, is_demand=False,
                top=base_high, bottom=base_low,
            ))

    return result


# --- Price at zone (for entry logic) ---

def price_at_ob(close: float, ob: OrderBlock, tolerance_pct: float = 0.1) -> bool:
    """True if current close is inside or within tolerance of the OB zone."""
    if ob.ob_type == OBType.BULLISH:
        zone_high = ob.high
        zone_low = ob.low
    else:
        zone_high = ob.high
        zone_low = ob.low
    tol = (zone_high - zone_low) * (tolerance_pct / 100.0) if zone_high != zone_low else close * 0.001
    return zone_low - tol <= close <= zone_high + tol


def price_at_fvg(close: float, fvg: FairValueGap, tolerance_pct: float = 0.1) -> bool:
    """True if close is inside or within tolerance of the FVG range [bottom, top]."""
    w = fvg.top - fvg.bottom
    tol = w * (tolerance_pct / 100.0) if w > 0 else close * 0.001
    return fvg.bottom - tol <= close <= fvg.top + tol


def price_at_zone(close: float, zone: Zone, tolerance_pct: float = 0.1) -> bool:
    """True if close is inside or within tolerance of the zone [bottom, top]."""
    w = zone.top - zone.bottom
    tol = w * (tolerance_pct / 100.0) if w > 0 else close * 0.001
    return zone.bottom - tol <= close <= zone.top + tol
