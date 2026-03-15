"""
Build bar-by-bar regime, favor, signal and trade list for charting.

Uses same logic as backtest: RegimeClassifier + get_signal + get_rules_for_regime.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from strategy import RegimeClassifier, RegimeInputs, get_rules_for_regime
from signals.fusion import get_signal, Signal


@dataclass
class TradeEvent:
    """Single trade for drawing on chart."""
    entry_bar: int
    exit_bar: int
    side: str  # "long" | "short"
    entry_price: float
    exit_price: float
    exit_reason: str


def build_decision_timeline(
    open_time: np.ndarray,
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    volume: np.ndarray,
    lookback: int = 100,
    require_volume_confirmation: bool = False,
    max_bars: Optional[int] = None,
) -> Tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    List[TradeEvent],
]:
    """
    Walk bars from lookback to end; at each bar compute regime, favor, signal; simulate trades.

    Returns:
        open_time, open_, high, low, close, volume (possibly trimmed to last max_bars),
        regime_bar (str: "bull"|"bear"|"sideways", "" before lookback),
        favor_bar (str: "long"|"short"|"neutral", "" before lookback),
        signal_bar (str: "long"|"short"|"none", "" before lookback),
        trades (list of TradeEvent).
    """
    n = len(close)
    if n < lookback:
        raise ValueError(f"Need at least {lookback} bars, got {n}")

    if max_bars is not None and n > max_bars:
        start = n - max_bars
        open_time = open_time[start:]
        open_ = open_[start:]
        high = high[start:]
        low = low[start:]
        close = close[start:]
        volume = volume[start:]
        n = len(close)
        lookback_in_slice = min(lookback, n - 1)
    else:
        start = 0
        lookback_in_slice = lookback

    regime_bar = np.array([""] * n, dtype=object)
    favor_bar = np.array([""] * n, dtype=object)
    signal_bar = np.array([""] * n, dtype=object)

    classifier = RegimeClassifier()
    trades: List[TradeEvent] = []
    position: Optional[dict] = None

    for i in range(lookback_in_slice, n):
        o = open_[: i + 1]
        h = high[: i + 1]
        l_ = low[: i + 1]
        c = close[: i + 1]
        v = volume[: i + 1]

        # Regime and signal (current bar)
        regime = classifier.classify(RegimeInputs(close=c, high=h, low=l_))
        rules = get_rules_for_regime(regime)
        res = get_signal(
            o, h, l_, c, v,
            regime_classifier=classifier,
            require_volume_confirmation=require_volume_confirmation,
            ob_lookback=min(50, i + 1),
            fvg_lookback=min(30, i + 1),
            zone_lookback=min(50, i + 1),
        )

        regime_bar[i] = regime.value
        if regime.value == "bull":
            favor_bar[i] = "long"
        elif regime.value == "bear":
            favor_bar[i] = "short" if rules.allow_short else "neutral"
        else:
            favor_bar[i] = "neutral"
            if rules.allow_long and not rules.allow_short:
                favor_bar[i] = "long"
            elif rules.allow_short and not rules.allow_long:
                favor_bar[i] = "short"
        signal_bar[i] = res.signal.value

        # Exit check
        if position is not None:
            exit_price = None
            exit_reason = None
            if position["side"] == "long":
                if l_[-1] <= position["stop"]:
                    exit_price = position["stop"]
                    exit_reason = "stop"
                elif position.get("target") is not None and h[-1] >= position["target"]:
                    exit_price = position["target"]
                    exit_reason = "target"
            else:
                if h[-1] >= position["stop"]:
                    exit_price = position["stop"]
                    exit_reason = "stop"
                elif position.get("target") is not None and l_[-1] <= position["target"]:
                    exit_price = position["target"]
                    exit_reason = "target"

            if exit_price is not None:
                trades.append(
                    TradeEvent(
                        entry_bar=position["entry_bar"],
                        exit_bar=i,
                        side=position["side"],
                        entry_price=position["entry_price"],
                        exit_price=exit_price,
                        exit_reason=exit_reason or "signal",
                    )
                )
                position = None

        # Entry
        if position is None:
            stop_pct = rules.stop_pct or 0.02
            tp_pct = rules.take_profit_pct
            if res.signal == Signal.LONG and rules.allow_long:
                stop = res.stop_below if res.stop_below is not None else close[i] * (1 - stop_pct)
                target = close[i] * (1 + tp_pct) if tp_pct is not None else None
                position = {
                    "side": "long",
                    "entry_price": close[i],
                    "entry_bar": i,
                    "stop": stop,
                    "target": target,
                    "size_pct": rules.position_size_pct,
                }
            elif res.signal == Signal.SHORT and rules.allow_short:
                stop = res.stop_above if res.stop_above is not None else close[i] * (1 + stop_pct)
                target = close[i] * (1 - tp_pct) if tp_pct is not None else None
                position = {
                    "side": "short",
                    "entry_price": close[i],
                    "entry_bar": i,
                    "stop": stop,
                    "target": target,
                    "size_pct": rules.position_size_pct,
                }

    if position is not None:
        trades.append(
            TradeEvent(
                entry_bar=position["entry_bar"],
                exit_bar=n - 1,
                side=position["side"],
                entry_price=position["entry_price"],
                exit_price=close[-1],
                exit_reason="end",
            )
        )

    return (
        open_time,
        open_,
        high,
        low,
        close,
        volume,
        regime_bar,
        favor_bar,
        signal_bar,
        trades,
    )
