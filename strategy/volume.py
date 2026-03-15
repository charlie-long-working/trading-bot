"""
Volume filters and confirmation for entries/breakouts.

- Volume SMA and relative volume (above/below average).
- Climactic volume (spike) detection.
- Volume confirmation flag for signals.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np


class VolumeState(Enum):
    HIGH = "high"       # above average
    NEUTRAL = "neutral" # near average
    LOW = "low"         # below average
    CLIMACTIC = "climactic"  # spike, possible exhaustion


@dataclass
class VolumeContext:
    """Volume state and metrics at a bar."""

    state: VolumeState
    volume: float
    volume_sma: float
    ratio: float  # volume / volume_sma
    is_climactic: bool


def volume_sma(volume: np.ndarray, period: int = 20) -> np.ndarray:
    """Rolling SMA of volume. Returns same length as volume; leading NaNs for warmup."""
    out = np.full_like(volume, np.nan, dtype=float)
    if len(volume) < period:
        return out
    for i in range(period - 1, len(volume)):
        out[i] = np.mean(volume[i - period + 1 : i + 1])
    return out


def get_volume_context(
    volume: np.ndarray,
    idx: int = -1,
    period: int = 20,
    high_ratio: float = 1.2,
    low_ratio: float = 0.8,
    climactic_ratio: float = 2.0,
) -> Optional[VolumeContext]:
    """
    Return volume context at bar idx (default last bar).

    - state: HIGH / NEUTRAL / LOW from ratio vs SMA; CLIMACTIC if ratio >= climactic_ratio.
    - ratio: volume / volume_sma.
    """
    if len(volume) < period or (idx < 0 and len(volume) + idx < period - 1):
        return None
    i = idx if idx >= 0 else len(volume) + idx
    v = float(volume[i])
    sma_arr = volume_sma(volume, period)
    sma = float(sma_arr[i])
    if np.isnan(sma) or sma <= 0:
        return None
    ratio = v / sma
    if ratio >= climactic_ratio:
        state = VolumeState.CLIMACTIC
        is_climactic = True
    elif ratio >= high_ratio:
        state = VolumeState.HIGH
        is_climactic = False
    elif ratio <= low_ratio:
        state = VolumeState.LOW
        is_climactic = False
    else:
        state = VolumeState.NEUTRAL
        is_climactic = False
    return VolumeContext(state=state, volume=v, volume_sma=sma, ratio=ratio, is_climactic=is_climactic)


def volume_confirmation(
    volume: np.ndarray,
    idx: int = -1,
    period: int = 20,
    min_ratio: float = 1.0,
) -> bool:
    """
    True if volume at bar idx is at or above min_ratio of its SMA (e.g. 1.0 = at least average).
    Use to confirm breakouts or OB/zone entries.
    """
    ctx = get_volume_context(volume, idx=idx, period=period)
    if ctx is None:
        return False
    return ctx.ratio >= min_ratio
