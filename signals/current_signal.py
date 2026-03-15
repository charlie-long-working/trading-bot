"""
Lấy tín hiệu hiện tại (Long/Short) với TP/SL từ indicator + regime, dùng cho khung 1h tích hợp Telegram.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

import numpy as np

from strategy import RegimeClassifier, get_rules_for_regime
from signals.fusion import Signal, SignalResult, get_signal

from data_loaders.load_klines import load_merged_klines
from data_loaders.glassnode import load_sopr_mvrv_for_klines, get_onchain_for_bar


@dataclass
class SignalWithLevels:
    """Tín hiệu kèm giá entry, SL, TP."""

    side: str  # "long" | "short"
    symbol: str
    market_type: str
    interval: str
    entry: float
    sl: float
    tp: Optional[float]
    regime: str
    reason: str


def get_current_signal_with_tp_sl_from_arrays(
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
    require_volume_confirmation: bool = False,
    classifier: Optional[RegimeClassifier] = None,
) -> Optional[SignalWithLevels]:
    """
    Tính tín hiệu Long/Short + TP/SL từ các mảng OHLCV (vd. lấy từ OKX API).
    Không cần data_dir; on-chain truyền qua sopr/mvrv nếu có.
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
    )
    if res.signal == Signal.NONE:
        return None
    rules = get_rules_for_regime(res.regime)
    entry = float(close[-1])
    stop_pct = rules.stop_pct or 0.02
    tp_pct = rules.take_profit_pct
    if res.signal == Signal.LONG:
        sl = res.stop_below if res.stop_below is not None else entry * (1 - stop_pct)
        tp = entry * (1 + tp_pct) if tp_pct is not None else None
        return SignalWithLevels(
            side="long",
            symbol=symbol,
            market_type=market_type,
            interval=interval,
            entry=entry,
            sl=sl,
            tp=tp,
            regime=res.regime.value,
            reason=res.reason,
        )
    if res.signal == Signal.SHORT:
        sl = res.stop_above if res.stop_above is not None else entry * (1 + stop_pct)
        tp = entry * (1 - tp_pct) if tp_pct is not None else None
        return SignalWithLevels(
            side="short",
            symbol=symbol,
            market_type=market_type,
            interval=interval,
            entry=entry,
            sl=sl,
            tp=tp,
            regime=res.regime.value,
            reason=res.reason,
        )
    return None


def get_current_signal_with_tp_sl(
    data_dir: Union[str, Path],
    market_type: str,
    symbol: str,
    interval: str = "1h",
    use_onchain: bool = True,
    require_volume_confirmation: bool = False,
    classifier: Optional[RegimeClassifier] = None,
) -> Optional[SignalWithLevels]:
    """
    Load klines (1h) từ data_dir, chạy indicator + regime -> signal.
    Trả về SignalWithLevels (entry, sl, tp) khi có LONG hoặc SHORT; None nếu không có tín hiệu.
    """
    data_dir = Path(data_dir)
    out = load_merged_klines(data_dir, market_type, symbol, interval)
    if out is None:
        return None
    open_time, open_, high, low, close, volume = out
    sopr_i, mvrv_i = None, None
    if use_onchain:
        sopr_arr, mvrv_arr = load_sopr_mvrv_for_klines(
            open_time, symbol, str(data_dir), use_cache=True, save_cache=True
        )
        idx = len(close) - 1
        sopr_i, mvrv_i = get_onchain_for_bar(sopr_arr, mvrv_arr, idx)
    return get_current_signal_with_tp_sl_from_arrays(
        open_, high, low, close, volume,
        symbol=symbol,
        market_type=market_type,
        interval=interval,
        sopr=sopr_i,
        mvrv=mvrv_i,
        require_volume_confirmation=require_volume_confirmation,
        classifier=classifier,
    )
