"""
Rule sets per regime: entry, exit, position size, max leverage.

Separate logic (or weights) for bear / bull / sideways.
"""

from dataclasses import dataclass
from typing import Optional

from .regime import Regime


@dataclass
class RuleSet:
    """Rules for one regime."""

    max_leverage: float
    position_size_pct: float  # 0–1, relative to base size
    allow_long: bool
    allow_short: bool
    # Optional: tighter stops in bear/sideways
    stop_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None


def get_rules_for_regime(regime: Regime) -> RuleSet:
    """
    Return entry/exit/sizing rules for the given regime.

    Bear: preserve capital, rare longs; reduced size, no or low leverage.
    Bull: long bias, normal/aggressive size; trend-follow.
    Sideways: mean reversion; tighter stops, reduced size.
    """
    if regime == Regime.BEAR:
        return RuleSet(
            max_leverage=1.0,
            position_size_pct=0.25,
            allow_long=True,
            allow_short=True,
            stop_pct=0.02,
            take_profit_pct=0.03,
        )
    if regime == Regime.BULL:
        return RuleSet(
            max_leverage=2.0,
            position_size_pct=1.0,
            allow_long=True,
            allow_short=False,
            stop_pct=0.03,
            take_profit_pct=None,  # trend-follow, no fixed target
        )
    # Sideways
    return RuleSet(
        max_leverage=1.0,
        position_size_pct=0.5,
        allow_long=True,
        allow_short=True,
        stop_pct=0.015,
        take_profit_pct=0.02,
    )
