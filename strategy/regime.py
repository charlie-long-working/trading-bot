"""
Regime classifier: label market as bear, bull, or sideways.

Uses price (trend + volatility) first; can be extended with M2 and on-chain (SOPR/MVRV).
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np


class Regime(Enum):
    BEAR = "bear"
    BULL = "bull"
    SIDEWAYS = "sideways"


@dataclass
class RegimeInputs:
    """Inputs for regime classification (extend with M2, on-chain later)."""

    # Price-based: numpy arrays or lists, most recent last
    close: np.ndarray
    high: Optional[np.ndarray] = None
    low: Optional[np.ndarray] = None
    # Optional: M2 YoY growth (single value or last value)
    m2_yoy: Optional[float] = None
    # Optional: on-chain (e.g. SOPR, MVRV)
    sopr: Optional[float] = None
    mvrv: Optional[float] = None


class RegimeClassifier:
    """
    Classify regime from price (and optionally M2/on-chain).

    - Bull: short MA above long MA, volatility not spiking, optional M2 > 0, MVRV not extreme.
    - Bear: short MA below long MA, optional M2 < 0 or SOPR < 1.
    - Sideways: range / volatility contraction; mixed signals.
    """

    def __init__(
        self,
        short_period: int = 20,
        long_period: int = 50,
        vol_period: int = 20,
        m2_bull_threshold: float = 0.0,
        m2_bear_threshold: float = 0.0,
        mvrv_fomo_threshold: float = 3.5,
        sopr_capitulation_threshold: float = 1.0,
    ) -> None:
        self.short_period = short_period
        self.long_period = long_period
        self.vol_period = vol_period
        self.m2_bull_threshold = m2_bull_threshold
        self.m2_bear_threshold = m2_bear_threshold
        self.mvrv_fomo_threshold = mvrv_fomo_threshold
        self.sopr_capitulation_threshold = sopr_capitulation_threshold

    def classify(self, inputs: RegimeInputs) -> Regime:
        """Return current regime from price (and optional M2/on-chain)."""
        c = np.asarray(inputs.close, dtype=float)
        if len(c) < self.long_period:
            return Regime.SIDEWAYS

        short_ma = np.mean(c[-self.short_period :])
        long_ma = np.mean(c[-self.long_period :])
        recent_std = np.std(c[-self.vol_period :]) if len(c) >= self.vol_period else 0.0
        prev_std = (
            np.std(c[-self.vol_period * 2 : -self.vol_period])
            if len(c) >= self.vol_period * 2
            else recent_std
        )
        vol_contracting = prev_std > 0 and recent_std < prev_std * 0.8

        # M2 / on-chain overrides (if provided)
        if inputs.m2_yoy is not None and inputs.m2_yoy < self.m2_bear_threshold:
            if short_ma < long_ma:
                return Regime.BEAR
        if inputs.sopr is not None and inputs.sopr < self.sopr_capitulation_threshold:
            if short_ma < long_ma:
                return Regime.BEAR
        if inputs.mvrv is not None and inputs.mvrv >= self.mvrv_fomo_threshold:
            return Regime.SIDEWAYS  # late cycle, treat as sideways / reduce size

        if short_ma > long_ma and not vol_contracting:
            return Regime.BULL
        if short_ma < long_ma:
            return Regime.BEAR
        return Regime.SIDEWAYS
