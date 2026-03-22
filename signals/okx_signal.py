"""
Tín hiệu giao dịch cho OKX: regime + fusion + timeline (halving, seasonal).

Kết hợp theo plan Macro/Regime:
- Regime (bear/bull/sideways) + OB/FVG/supply-demand → hướng và vùng entry.
- Timeline: halving phase, seasonal (tháng yếu) → điều chỉnh position size (position_size_modifier).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import numpy as np

from strategy import (
    RegimeClassifier,
    get_rules_for_regime,
    halving_phase as get_halving_phase,
    is_weak_seasonal_month,
)
from signals.fusion import Signal, get_signal


@dataclass
class OKXSignalResult:
    """
    Tín hiệu đầy đủ cho OKX: entry, SL, TP và modifier size theo timeline.
    Dùng để đặt lệnh trên OKX (run_okx_bot) hoặc chỉ in tín hiệu.
    """

    side: str  # "long" | "short"
    symbol: str
    market_type: str
    interval: str
    entry: float
    sl: float
    tp: Optional[float]
    regime: str
    reason: str
    # Timeline: điều chỉnh size (0–1). Bot nhân size_usdt * position_size_modifier.
    position_size_modifier: float = 1.0
    halving_phase: str = ""  # "pre" | "post" | "neutral"
    seasonal_weak: bool = False  # True = tháng yếu, nên giảm size


def _inst_id(symbol: str, market_type: str) -> str:
    """OKX instId từ symbol + market_type."""
    from exchange.okx_client import _symbol_to_inst_id
    return _symbol_to_inst_id(symbol, market_type)


def get_okx_signal(
    open_time: np.ndarray,
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    volume: np.ndarray,
    symbol: str,
    market_type: str,
    interval: str = "1h",
    sopr: Optional[float] = None,
    mvrv: Optional[float] = None,
    m2_yoy: Optional[float] = None,
    require_volume_confirmation: bool = False,
    classifier: Optional[RegimeClassifier] = None,
    use_timeline_modifier: bool = True,
) -> Optional[OKXSignalResult]:
    """
    Tạo tín hiệu giao dịch cho OKX từ OHLCV (vd. từ fetch_okx_klines).

    - Regime + fusion (OB, FVG, supply/demand) → Long/Short + SL/TP.
    - Timeline: halving_phase, is_weak_seasonal_month → position_size_modifier (giảm size khi
      tháng yếu hoặc neutral halving).

    Trả về OKXSignalResult khi có LONG/SHORT; None nếu không có tín hiệu.
    """
    if len(close) < 50:
        return None
    if classifier is None:
        classifier = RegimeClassifier()

    res = get_signal(
        open_, high, low, close, volume,
        regime_classifier=classifier,
        require_volume_confirmation=require_volume_confirmation,
        ob_lookback=50,
        fvg_lookback=30,
        zone_lookback=50,
        sopr=sopr,
        mvrv=mvrv,
        m2_yoy=m2_yoy,
    )
    regime = res.regime
    rules = get_rules_for_regime(regime)

    if res.signal == Signal.NONE:
        return None

    entry = float(close[-1])
    stop_pct = rules.stop_pct or 0.02
    tp_pct = rules.take_profit_pct

    if res.signal == Signal.LONG:
        sl = res.stop_below if res.stop_below is not None else entry * (1 - stop_pct)
        tp = entry * (1 + tp_pct) if tp_pct is not None else None
        side = "long"
    elif res.signal == Signal.SHORT:
        sl = res.stop_above if res.stop_above is not None else entry * (1 + stop_pct)
        tp = entry * (1 - tp_pct) if tp_pct is not None else None
        side = "short"
    else:
        return None

    # Timeline: ngày của nến cuối (open_time ms)
    position_size_modifier = 1.0
    halving_phase_str = ""
    seasonal_weak = False
    if use_timeline_modifier and len(open_time) > 0:
        last_ts_ms = int(open_time[-1])
        as_of = datetime.utcfromtimestamp(last_ts_ms / 1000.0).date()
        halving_phase_str = get_halving_phase(as_of)
        seasonal_weak = is_weak_seasonal_month(as_of.month)
        if seasonal_weak:
            position_size_modifier *= 0.75
        if halving_phase_str == "neutral":
            position_size_modifier *= 0.85

    return OKXSignalResult(
        side=side,
        symbol=symbol,
        market_type=market_type,
        interval=interval,
        entry=entry,
        sl=sl,
        tp=tp,
        regime=regime.value,
        reason=res.reason,
        position_size_modifier=round(position_size_modifier, 2),
        halving_phase=halving_phase_str,
        seasonal_weak=seasonal_weak,
    )


def get_okx_signal_for_display(
    open_time: np.ndarray,
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    volume: np.ndarray,
    symbol: str,
    market_type: str,
    interval: str = "1h",
    **kwargs,
) -> Optional[OKXSignalResult]:
    """
    Giống get_okx_signal, dùng khi chỉ cần in/hiển thị tín hiệu (không cần inst_id trong result).
    """
    return get_okx_signal(
        open_time, open_, high, low, close, volume,
        symbol=symbol, market_type=market_type, interval=interval,
        **kwargs,
    )


def format_okx_signal_for_telegram(sig: OKXSignalResult) -> str:
    """Format tín hiệu OKX thành text (Telegram / log)."""
    inst_id = _inst_id(sig.symbol, sig.market_type)
    lines = [
        f"🪙 OKX | {sig.symbol} ({inst_id})",
        f"📊 {sig.side.upper()} @ ~{sig.entry:.2f} | SL={sig.sl:.2f} | TP={sig.tp or 'trend'}",
        f"Regime: {sig.regime} | {sig.reason}",
    ]
    if sig.position_size_modifier < 1.0:
        lines.append(f"⚠️ Size modifier: {sig.position_size_modifier:.0%} (halving={sig.halving_phase}, seasonal_weak={sig.seasonal_weak})")
    return "\n".join(lines)
