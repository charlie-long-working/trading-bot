"""
Timeline factors: halving dates, seasonal (month) for strategy context.

M2 and on-chain are to be supplied externally (e.g. FRED, Glassnode).
"""

from datetime import date
from typing import Literal

# BTC halving block heights and approximate dates (for context only).
HALVING_DATES = [
    date(2012, 11, 28),
    date(2016, 7, 9),
    date(2020, 5, 11),
    date(2024, 4, 19),
    # date(2028, ...) next
]


def halving_phase(as_of: date) -> Literal["pre", "post", "neutral"]:
    """
    Return phase relative to nearest halving: pre (accumulation/run-up), post (discovery), or neutral.
    """
    for i, h in enumerate(HALVING_DATES):
        if as_of < h:
            months_to = (h.year - as_of.year) * 12 + (h.month - as_of.month)
            if months_to <= 3:
                return "pre"
            if months_to <= 24:
                return "pre"
            return "neutral"
        # as_of >= h
        months_since = (as_of.year - h.year) * 12 + (as_of.month - h.month)
        if months_since <= 24:
            return "post"
    return "neutral"


def is_weak_seasonal_month(month: int) -> bool:
    """
    Placeholder: historically weak months for crypto (e.g. summer, post-halving year-2).
    Refine with your own seasonality study.
    """
    # Example: June–August sometimes weaker; adjust from backtests.
    return month in (6, 7, 8)
