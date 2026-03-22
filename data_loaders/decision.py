"""
Understanding data and making a decision: market context from klines + regime + timeline.

Consumes loaded klines and outputs a concise context (regime, halving phase, seasonal,
favor long/short) for human or downstream use.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

import numpy as np

from strategy import RegimeClassifier, RegimeInputs, get_rules_for_regime
from strategy.timeline import halving_phase, is_weak_seasonal_month

from .load_klines import load_merged_klines
from .realtime import load_klines_with_realtime_fallback
from .glassnode import load_sopr_mvrv_for_klines, get_onchain_for_bar


@dataclass
class MarketContext:
    """Summary of market context for decision-making."""

    symbol: str
    market_type: str
    interval: str
    regime: str  # "bull" | "bear" | "sideways"
    favor: str   # "long" | "short" | "neutral"
    halving_phase: str  # "pre" | "post" | "neutral"
    seasonal_weak: bool
    start_ts: int
    end_ts: int
    bars: int
    last_close: float


def _ts_to_date(ts: int) -> datetime:
    """Convert open_time to datetime. Accepts ms or microseconds (if > 1e15)."""
    if ts > 1e15:
        ts = int(ts / 1000)
    return datetime.utcfromtimestamp(ts / 1000.0)


def make_decision(
    data_dir: Union[str, Path],
    market_type: str,
    symbol: str,
    interval: str,
    classifier: Optional[RegimeClassifier] = None,
    use_onchain: bool = True,
    use_realtime_fallback: bool = False,
) -> Optional[MarketContext]:
    """
    Load klines, compute regime and timeline, return a single MarketContext for decision-making.

    - regime: from RegimeClassifier on close (and optional SOPR/MVRV when use_onchain=True).
    - favor: long if regime allows long and is bull/sideways; short if bear/sideways allows short; else neutral.
    - halving_phase: from last bar's date.
    - seasonal_weak: true if last bar's month is in weak seasonal set.
    - use_realtime_fallback: nếu True, khi không có file thì lấy từ Binance REST API.
    """
    data_dir = Path(data_dir)
    if use_realtime_fallback:
        out = load_klines_with_realtime_fallback(
            data_dir, market_type, symbol, interval, limit=500
        )
    else:
        out = load_merged_klines(data_dir, market_type, symbol, interval)
    if out is None:
        return None
    open_time, open_, high, low, close, volume = out
    if len(close) < 50:
        return None
    sopr_last, mvrv_last = None, None
    if use_onchain:
        sopr_arr, mvrv_arr = load_sopr_mvrv_for_klines(
            open_time, symbol, str(data_dir), use_cache=True, save_cache=True
        )
        sopr_last, mvrv_last = get_onchain_for_bar(
            sopr_arr, mvrv_arr, len(close) - 1
        )
    if classifier is None:
        classifier = RegimeClassifier()
    regime = classifier.classify(
        RegimeInputs(close=close, high=high, low=low, sopr=sopr_last, mvrv=mvrv_last)
    )
    rules = get_rules_for_regime(regime)
    last_date = _ts_to_date(int(open_time[-1]))

    if regime.value == "bull":
        favor = "long"
    elif regime.value == "bear":
        favor = "short" if rules.allow_short else "neutral"
    else:
        # Sideways: neutral when both allowed, else long or short
        if rules.allow_long and rules.allow_short:
            favor = "neutral"
        elif rules.allow_long:
            favor = "long"
        else:
            favor = "short"

    return MarketContext(
        symbol=symbol,
        market_type=market_type,
        interval=interval,
        regime=regime.value,
        favor=favor,
        halving_phase=halving_phase(last_date.date()),
        seasonal_weak=is_weak_seasonal_month(last_date.month),
        start_ts=int(open_time[0]),
        end_ts=int(open_time[-1]),
        bars=len(close),
        last_close=float(close[-1]),
    )


