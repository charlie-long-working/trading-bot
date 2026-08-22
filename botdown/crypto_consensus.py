"""
Crypto consensus scanner: MACD+RSI + SMC + Regime Fusion (+ liquidation map overlay).

Technical models still need 2 agreeing votes. Liquidation map is a 4th vote
(always live; not in the kill registry) and is stored on signal.meta.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from botdown.engine_macd_rsi_bt import (
    MacdRsiParams,
    _hist_rsi_arrays,
    ema_trend_bull_bear,
    macd_rsi_entry_snapshot,
)
from botdown.engine_smc_bt import SmcParams, smc_entry_snapshot
from botdown.ml_ops import (
    CRYPTO_LIVE_CUTOFF,
    ConsensusResult,
    StrategyVote,
    macd_rsi_confidence,
    regime_fusion_confidence,
    resolve_consensus,
    smc_zone_confidence,
)
from signals.fusion import Signal, get_signal

LIQ_STRATEGY = "liquidation_map"


@dataclass
class CryptoConsensusSignal:
    symbol: str
    interval: str
    consensus: ConsensusResult
    close: float = 0.0
    data_cutoff: str = CRYPTO_LIVE_CUTOFF
    meta: Dict[str, Any] = field(default_factory=dict)


def _fusion_vote(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    volume: np.ndarray,
) -> Optional[StrategyVote]:
    res = get_signal(
        open_, high, low, close, volume,
        require_volume_confirmation=False,
    )
    side = "none"
    if res.signal == Signal.LONG:
        side = "long"
    elif res.signal == Signal.SHORT:
        side = "short"
    if side == "none":
        return StrategyVote("regime_fusion", "none", 0.0, res.reason)

    conf = regime_fusion_confidence(res.regime.value if hasattr(res.regime, "value") else str(res.regime), res.reason)
    cur = float(close[-1])
    sl = res.stop_below if side == "long" else res.stop_above
    tp = None
    if sl is not None:
        risk = abs(cur - sl)
        tp = cur + 2.5 * risk if side == "long" else cur - 2.5 * risk

    return StrategyVote(
        strategy="regime_fusion",
        side=side,
        confidence=conf,
        reason=res.reason,
        entry_price=cur,
        stop_loss=float(sl) if sl is not None else None,
        take_profit=float(tp) if tp is not None else None,
        extra={"regime": str(res.regime)},
    )


def _macd_vote(
    open_time: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    params: MacdRsiParams,
) -> StrategyVote:
    snap = macd_rsi_entry_snapshot(open_time, high, low, close, params, allow_short=True)
    hist, rsi_arr, _ = _hist_rsi_arrays(high, low, close, params)
    h, r = float(hist[-1]), float(rsi_arr[-1])
    if not snap:
        return StrategyVote("macd_rsi", "none", 0.0, "no_cross", float(close[-1]))
    side = snap["side"]
    conf = macd_rsi_confidence(h, r, side=side, rsi_ob=params.rsi_overbought, rsi_os=params.rsi_oversold)
    return StrategyVote(
        strategy="macd_rsi",
        side=side,
        confidence=conf,
        reason=f"hist_cross rsi={r:.1f}",
        entry_price=snap["entry_ref"],
        stop_loss=snap["stop"],
        take_profit=snap["tp"],
    )


def _smc_vote(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    params: SmcParams,
) -> StrategyVote:
    snap = smc_entry_snapshot(open_, high, low, close, params, allow_short=True)
    bull, _ = ema_trend_bull_bear(close, params.ema_trend_fast, params.ema_trend_slow) if params.use_ema_trend_filter else (None, None)
    ema_ok = bool(bull[-1]) if bull is not None else True
    if not snap:
        return StrategyVote("smc", "none", 0.0, "no_zone_touch", float(close[-1]))
    conf = smc_zone_confidence(True, ema_bull=ema_ok if snap["side"] == "long" else not ema_ok)
    return StrategyVote(
        strategy="smc",
        side=snap["side"],
        confidence=conf,
        reason="zone_edge_touch",
        entry_price=snap["entry_ref"],
        stop_loss=snap["stop"],
        take_profit=snap["tp"],
    )


def _liq_vote(symbol: str) -> tuple[Optional[StrategyVote], Optional[dict]]:
    try:
        from data_loaders.liquidation_map import (
            fetch_liquidation_map,
            liquidation_vote_dict,
            save_liquidation_reports,
        )
    except ImportError:
        return None, None
    try:
        snap = fetch_liquidation_map(symbol)
        save_liquidation_reports(snap)
        d = liquidation_vote_dict(snap)
        vote = StrategyVote(
            strategy=LIQ_STRATEGY,
            side=d["side"],
            confidence=float(d["confidence"]),
            reason=d["reason"],
            entry_price=float(d["entry_price"] or 0.0),
            stop_loss=d["stop_loss"],
            take_profit=d["take_profit"],
            extra=d.get("extra") or {},
        )
        return vote, snap.summary()
    except Exception as e:
        return None, {"error": str(e)}


def _vote_is_live(strategy: str, live_models: Optional[List[str]]) -> bool:
    if live_models is None:
        return True
    if strategy == LIQ_STRATEGY:
        return True
    allowed = set(live_models)
    return strategy in allowed or f"crypto_{strategy}" in allowed


def scan_crypto_consensus(
    symbol: str,
    open_time: np.ndarray,
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    volume: np.ndarray,
    interval: str = "1d",
    min_votes: int = 2,
    macd_params: Optional[MacdRsiParams] = None,
    smc_params: Optional[SmcParams] = None,
    live_models: Optional[List[str]] = None,
) -> CryptoConsensusSignal:
    macd_p = macd_params or MacdRsiParams(
        exit_mode="pct",
        take_profit_pct=0.10,
        stop_loss_pct=0.04,
        fee_roundtrip=0.001,
        use_ema_trend_filter=True,
        ema_trend_fast=20,
        ema_trend_slow=50,
    )
    smc_p = smc_params or SmcParams(
        take_profit_pct=0.10,
        stop_loss_pct=0.04,
        fee_roundtrip=0.001,
        use_ema_trend_filter=True,
        ema_trend_fast=20,
        ema_trend_slow=50,
    )

    votes: List[StrategyVote] = [
        _macd_vote(open_time, high, low, close, macd_p),
        _smc_vote(open_, high, low, close, smc_p),
    ]
    fv = _fusion_vote(open_, high, low, close, volume)
    if fv:
        votes.append(fv)

    liq_vote, liq_summary = _liq_vote(symbol)
    if liq_vote:
        votes.append(liq_vote)

    votes = [v for v in votes if _vote_is_live(v.strategy, live_models)]

    consensus = resolve_consensus(votes, min_votes=min_votes)
    return CryptoConsensusSignal(
        symbol=symbol,
        interval=interval,
        consensus=consensus,
        close=float(close[-1]),
        meta={
            "votes": len(votes),
            "min_votes": min_votes,
            "liquidation_map": liq_summary,
        },
    )
