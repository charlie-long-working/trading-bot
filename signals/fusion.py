"""
Fuse regime + technical (order blocks, FVG, supply/demand, volume) into a single signal.

Entry: regime allows direction + price at a valid zone (OB/FVG/zone) + optional volume confirmation.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

import numpy as np

from strategy import (
    Regime,
    RegimeClassifier,
    RegimeInputs,
    get_rules_for_regime,
    order_blocks,
    fair_value_gaps,
    supply_demand_zones,
    price_at_ob,
    price_at_fvg,
    price_at_zone,
    volume_confirmation,
    OBType,
    compute_volume_profile,
    vp_allows_long,
    vp_allows_short,
)


class Signal(Enum):
    LONG = "long"
    SHORT = "short"
    NONE = "none"


@dataclass
class SignalResult:
    """Fused signal with reason and optional stop/target hints."""

    signal: Signal
    regime: Regime
    reason: str  # e.g. "bull_ob", "bear_fvg", "sideways_zone"
    stop_below: Optional[float] = None
    stop_above: Optional[float] = None


def get_signal(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    volume: np.ndarray,
    regime_classifier: Optional[RegimeClassifier] = None,
    require_volume_confirmation: bool = False,
    volume_period: int = 20,
    ob_lookback: int = 50,
    fvg_lookback: int = 30,
    zone_lookback: int = 50,
    sopr: Optional[float] = None,
    mvrv: Optional[float] = None,
    m2_yoy: Optional[float] = None,
    use_volume_profile: bool = False,
    vp_lookback: int = 48,
    vp_bins: int = 32,
    vp_value_area_pct: float = 0.70,
    vp_mode: str = "discount_premium",
) -> SignalResult:
    """
    Compute current bar signal from regime + technical.

    - Uses last bar's close for "price at zone" checks.
    - Long: regime allows long (bull or sideways) + price at bullish OB / bullish FVG / demand zone.
    - Short: regime allows short (bear or sideways) + price at bearish OB / bearish FVG / supply zone.
    - If require_volume_confirmation=True, entry also requires volume >= volume_sma.
    - use_volume_profile: rolling VP (POC/VAL/VAH) on OHLCV; filters entries (not tick order flow).
      vp_mode: "discount_premium" — long only if close <= POC, short if close >= POC;
      "in_va" — close must lie inside [VAL, VAH].
    - sopr/mvrv/m2_yoy: optional on-chain and macro (e.g. Glassnode, FRED); passed to RegimeInputs.
    """
    if regime_classifier is None:
        regime_classifier = RegimeClassifier()
    regime = regime_classifier.classify(
        RegimeInputs(close=close, high=high, low=low, sopr=sopr, mvrv=mvrv, m2_yoy=m2_yoy)
    )
    rules = get_rules_for_regime(regime)
    last_close = float(close[-1])

    obs = order_blocks(open_, high, low, close, lookback=ob_lookback)
    fvgs = fair_value_gaps(high, low, lookback=fvg_lookback)
    zones = supply_demand_zones(open_, high, low, close, lookback=zone_lookback)

    vol_ok = not require_volume_confirmation or volume_confirmation(
        volume, idx=-1, period=volume_period
    )

    prof = None
    if use_volume_profile:
        lb = max(5, min(vp_lookback, len(high)))
        prof = compute_volume_profile(
            high,
            low,
            volume,
            lookback=lb,
            num_bins=max(4, vp_bins),
            value_area_pct=max(0.5, min(0.95, vp_value_area_pct)),
        )
    mode = vp_mode if vp_mode in ("discount_premium", "in_va") else "discount_premium"
    long_vp_ok = not use_volume_profile or vp_allows_long(last_close, prof, mode)
    short_vp_ok = not use_volume_profile or vp_allows_short(last_close, prof, mode)

    # Long: regime allows long + (at bullish OB or bullish FVG or demand) + vol_ok + VP filter
    if rules.allow_long and vol_ok and long_vp_ok:
        for ob in reversed(obs):
            if ob.ob_type == OBType.BULLISH and price_at_ob(last_close, ob):
                return SignalResult(
                    signal=Signal.LONG,
                    regime=regime,
                    reason="bull_ob",
                    stop_below=ob.low,
                )
        for fvg in reversed(fvgs):
            if fvg.fvg_type == OBType.BULLISH and price_at_fvg(last_close, fvg):
                return SignalResult(
                    signal=Signal.LONG,
                    regime=regime,
                    reason="bull_fvg",
                    stop_below=fvg.bottom,
                )
        for z in reversed(zones):
            if z.is_demand and price_at_zone(last_close, z):
                return SignalResult(
                    signal=Signal.LONG,
                    regime=regime,
                    reason="demand_zone",
                    stop_below=z.bottom,
                )

    # Short: regime allows short + (at bearish OB or bearish FVG or supply) + vol_ok + VP filter
    if rules.allow_short and vol_ok and short_vp_ok:
        for ob in reversed(obs):
            if ob.ob_type == OBType.BEARISH and price_at_ob(last_close, ob):
                return SignalResult(
                    signal=Signal.SHORT,
                    regime=regime,
                    reason="bear_ob",
                    stop_above=ob.high,
                )
        for fvg in reversed(fvgs):
            if fvg.fvg_type == OBType.BEARISH and price_at_fvg(last_close, fvg):
                return SignalResult(
                    signal=Signal.SHORT,
                    regime=regime,
                    reason="bear_fvg",
                    stop_above=fvg.top,
                )
        for z in reversed(zones):
            if not z.is_demand and price_at_zone(last_close, z):
                return SignalResult(
                    signal=Signal.SHORT,
                    regime=regime,
                    reason="supply_zone",
                    stop_above=z.top,
                )

    return SignalResult(signal=Signal.NONE, regime=regime, reason="no_zone")