"""
Backtest MACD histogram cross + RSI (giống botv2.strategy.macd_rsi), trên OHLCV numpy.

- LONG: hist cắt lên 0, RSI < rsi_overbought
- SHORT: hist cắt xuống 0, RSI > rsi_oversold
- Tùy chọn `use_ema_trend_filter`: long chỉ khi bull (EMA_fast > EMA_slow và close > EMA_slow),
  short chỉ khi bear (EMA_fast < EMA_slow và close < EMA_slow). Mặc định EMA 20 / 50.
- Thoát: ATR hoặc **% cố định** (take_profit_pct / stop_loss_pct) — long & short đối xứng.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


def _ema(data: np.ndarray, period: int) -> np.ndarray:
    x = np.asarray(data, dtype=np.float64)
    out = np.empty_like(x, dtype=np.float64)
    out[0] = x[0]
    alpha = 2.0 / (period + 1)
    for i in range(1, len(x)):
        out[i] = alpha * x[i] + (1 - alpha) * out[i - 1]
    return out


def _rsi_wilder(close: np.ndarray, period: int) -> np.ndarray:
    n = len(close)
    rsi = np.full(n, 50.0)
    if n < period + 1:
        return rsi
    delta = np.diff(close)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = np.mean(gain[:period])
    avg_loss = np.mean(loss[:period])
    if avg_loss == 0:
        rsi[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi[period] = 100.0 - 100.0 / (1.0 + rs)
    for i in range(period, len(delta)):
        avg_gain = (avg_gain * (period - 1) + gain[i]) / period
        avg_loss = (avg_loss * (period - 1) + loss[i]) / period
        if avg_loss == 0:
            rsi[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i + 1] = 100.0 - 100.0 / (1.0 + rs)
    return rsi


def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    n = len(close)
    tr = np.empty(n, dtype=np.float64)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )
    atr = np.empty(n, dtype=np.float64)
    atr[:period] = np.mean(tr[:period])
    for i in range(period, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


@dataclass
class MacdRsiParams:
    fast_period: int = 12
    slow_period: int = 26
    signal_period: int = 9
    rsi_period: int = 14
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0
    atr_period: int = 14
    atr_sl_mult: float = 1.5
    atr_tp_mult: float = 2.5
    fee_roundtrip: float = 0.001
    # "atr" | "pct" — pct: TP +take_profit_pct, SL -stop_loss_pct (long); short đối xứng
    exit_mode: str = "atr"
    # Mặc định tối ưu grid trên 2 cửa sổ bear BTC 1D (spot): tổng return ~132%, R:R ≈ 2.5
    take_profit_pct: float = 0.10
    stop_loss_pct: float = 0.04
    # EMA xu hướng: long chỉ khi bull, short chỉ khi bear (khớp Pine).
    use_ema_trend_filter: bool = False
    ema_trend_fast: int = 20
    ema_trend_slow: int = 50


@dataclass
class MacdRsiTrade:
    entry_bar: int
    exit_bar: int
    side: str
    entry_price: float
    exit_price: float
    pnl_pct: float
    exit_reason: str


@dataclass
class MacdRsiBacktestResult:
    trades: List[MacdRsiTrade] = field(default_factory=list)
    total_return_pct: float = 0.0
    buy_hold_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    num_trades: int = 0
    sharpe_ratio: float = 0.0
    profit_factor: float = 0.0


def _ts_ms(s: str) -> int:
    dt = datetime.strptime(s.strip()[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def ema_trend_bull_bear(
    close: np.ndarray, fast: int, slow: int
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Bull: EMA(fast) > EMA(slow) và close > EMA(slow).
    Bear: EMA(fast) < EMA(slow) và close < EMA(slow).
    """
    cl = np.asarray(close, dtype=np.float64)
    ef = _ema(cl, fast)
    es = _ema(cl, slow)
    bull = (ef > es) & (cl > es)
    bear = (ef < es) & (cl < es)
    return bull, bear


def run_macd_rsi_backtest(
    open_time: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    start_date: str,
    end_date: str,
    params: Optional[MacdRsiParams] = None,
    allow_short: bool = True,
) -> Optional[MacdRsiBacktestResult]:
    params = params or MacdRsiParams()
    ot = np.asarray(open_time, dtype=np.int64)
    hi = np.asarray(high, dtype=float)
    lo = np.asarray(low, dtype=float)
    cl = np.asarray(close, dtype=float)
    n = len(cl)

    lookback = params.slow_period + params.signal_period + 2
    if params.use_ema_trend_filter:
        lookback = max(lookback, params.ema_trend_slow + 2)
    if n < lookback:
        return None

    ema_f = _ema(cl, params.fast_period)
    ema_s = _ema(cl, params.slow_period)
    macd_line = ema_f - ema_s
    sig_line = _ema(macd_line, params.signal_period)
    hist = macd_line - sig_line
    rsi_arr = _rsi_wilder(cl, params.rsi_period)
    use_atr = params.exit_mode.lower() == "atr"
    atr_arr = _atr(hi, lo, cl, params.atr_period) if use_atr else None
    bull_mask, bear_mask = (
        ema_trend_bull_bear(cl, params.ema_trend_fast, params.ema_trend_slow)
        if params.use_ema_trend_filter
        else (None, None)
    )

    if ot.size and ot[0] < 1e12:
        ot = ot * 1000

    start_ts = _ts_ms(start_date)
    end_ts = _ts_ms(end_date)
    i0 = int(np.searchsorted(ot, start_ts, side="left"))
    i1 = int(np.searchsorted(ot, end_ts, side="right")) - 1
    i_start = max(lookback, i0)
    i_end = min(i1, n - 1)
    if i_start > i_end:
        return None

    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    equity_curve = np.ones(n)
    position: Optional[dict] = None
    trades: List[MacdRsiTrade] = []

    for i in range(i_start, i_end + 1):
        if position is not None:
            exit_price = None
            exit_reason = None
            if position["side"] == "long":
                if lo[i] <= position["stop"]:
                    exit_price = position["stop"]
                    exit_reason = "stop"
                elif position["target"] is not None and hi[i] >= position["target"]:
                    exit_price = position["target"]
                    exit_reason = "target"
            else:
                if hi[i] >= position["stop"]:
                    exit_price = position["stop"]
                    exit_reason = "stop"
                elif position["target"] is not None and lo[i] <= position["target"]:
                    exit_price = position["target"]
                    exit_reason = "target"

            if exit_price is not None:
                gross = (exit_price - position["entry_price"]) / position["entry_price"]
                if position["side"] == "short":
                    gross = -gross
                net = gross - params.fee_roundtrip
                pnl_pct = net * 100
                equity *= 1 + net
                trades.append(
                    MacdRsiTrade(
                        position["entry_bar"],
                        i,
                        position["side"],
                        position["entry_price"],
                        exit_price,
                        pnl_pct,
                        exit_reason or "exit",
                    )
                )
                position = None
                peak = max(peak, equity)
                max_dd = max(max_dd, (peak - equity) / peak)

        if position is None and i >= 1:
            cur_h, prev_h = hist[i], hist[i - 1]
            cur_rsi = rsi_arr[i]
            cur_c = cl[i]

            long_ok = prev_h <= 0 < cur_h and cur_rsi < params.rsi_overbought
            if params.use_ema_trend_filter and bull_mask is not None:
                long_ok = long_ok and bool(bull_mask[i])
            if long_ok:
                if use_atr:
                    cur_atr = atr_arr[i]  # type: ignore[index]
                    sl = cur_c - params.atr_sl_mult * cur_atr
                    tp = cur_c + params.atr_tp_mult * cur_atr
                else:
                    sl = cur_c * (1.0 - params.stop_loss_pct)
                    tp = cur_c * (1.0 + params.take_profit_pct)
                position = {
                    "side": "long",
                    "entry_price": cur_c,
                    "entry_bar": i,
                    "stop": sl,
                    "target": tp,
                }
            elif allow_short:
                short_ok = prev_h >= 0 > cur_h and cur_rsi > params.rsi_oversold
                if params.use_ema_trend_filter and bear_mask is not None:
                    short_ok = short_ok and bool(bear_mask[i])
                if short_ok:
                    if use_atr:
                        cur_atr = atr_arr[i]  # type: ignore[index]
                        sl = cur_c + params.atr_sl_mult * cur_atr
                        tp = cur_c - params.atr_tp_mult * cur_atr
                    else:
                        sl = cur_c * (1.0 + params.stop_loss_pct)
                        tp = cur_c * (1.0 - params.take_profit_pct)
                    position = {
                        "side": "short",
                        "entry_price": cur_c,
                        "entry_bar": i,
                        "stop": sl,
                        "target": tp,
                    }

        equity_curve[i] = equity

    if position is not None:
        exit_price = float(cl[i_end])
        gross = (exit_price - position["entry_price"]) / position["entry_price"]
        if position["side"] == "short":
            gross = -gross
        net = gross - params.fee_roundtrip
        equity *= 1 + net
        trades.append(
            MacdRsiTrade(
                position["entry_bar"],
                i_end,
                position["side"],
                position["entry_price"],
                exit_price,
                net * 100,
                "end",
            )
        )
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak)

    bh = (cl[i_end] / cl[i_start] - 1.0) * 100
    wins = [t for t in trades if t.pnl_pct > 0]
    wr = len(wins) / len(trades) * 100 if trades else 0.0

    rets = np.array([t.pnl_pct for t in trades]) if trades else np.array([])
    sharpe = 0.0
    if len(rets) > 1 and np.std(rets) > 0:
        sharpe = float(np.mean(rets) / np.std(rets) * np.sqrt(252))
    gp = float(np.sum(rets[rets > 0])) if np.any(rets > 0) else 0.0
    gl = abs(float(np.sum(rets[rets < 0]))) if np.any(rets < 0) else 1e-12
    pf = gp / gl if gl > 0 else 0.0

    return MacdRsiBacktestResult(
        trades=trades,
        total_return_pct=(equity - 1.0) * 100,
        buy_hold_pct=bh,
        max_drawdown_pct=max_dd * 100,
        win_rate=wr,
        num_trades=len(trades),
        sharpe_ratio=sharpe,
        profit_factor=pf,
    )


def _hist_rsi_arrays(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    params: MacdRsiParams,
) -> Tuple[np.ndarray, np.ndarray, int]:
    cl = np.asarray(close, dtype=float)
    hi = np.asarray(high, dtype=float)
    lo = np.asarray(low, dtype=float)
    n = len(cl)
    lookback = params.slow_period + params.signal_period + 2
    ema_f = _ema(cl, params.fast_period)
    ema_s = _ema(cl, params.slow_period)
    macd_line = ema_f - ema_s
    sig_line = _ema(macd_line, params.signal_period)
    hist = macd_line - sig_line
    rsi_arr = _rsi_wilder(cl, params.rsi_period)
    return hist, rsi_arr, lookback


def macd_rsi_entry_snapshot(
    open_time_ms: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    params: Optional[MacdRsiParams] = None,
    allow_short: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Chỉ dùng nến **đã đóng** (OHLCV không gồm nến đang chạy).

    Nếu nến cuối có tín hiệu MACD hist cross + RSI, trả về dict:
      side, entry_ref (close tín hiệu), stop, tp, signal_open_time_ms
    """
    params = params or MacdRsiParams()
    ot = np.asarray(open_time_ms, dtype=np.int64)
    hi = np.asarray(high, dtype=float)
    lo = np.asarray(low, dtype=float)
    cl = np.asarray(close, dtype=float)
    n = len(cl)
    hist, rsi_arr, lookback = _hist_rsi_arrays(hi, lo, cl, params)
    if params.use_ema_trend_filter:
        lookback = max(lookback, params.ema_trend_slow + 2)
    if n < lookback or n < 2:
        return None

    i = n - 1
    cur_h, prev_h = hist[i], hist[i - 1]
    cur_rsi = rsi_arr[i]
    cur_c = cl[i]
    use_atr = params.exit_mode.lower() == "atr"
    atr_arr = _atr(hi, lo, cl, params.atr_period) if use_atr else None
    t_sig = int(ot[i])
    bull_mask, bear_mask = (
        ema_trend_bull_bear(cl, params.ema_trend_fast, params.ema_trend_slow)
        if params.use_ema_trend_filter
        else (None, None)
    )

    long_ok = prev_h <= 0 < cur_h and cur_rsi < params.rsi_overbought
    if bull_mask is not None:
        long_ok = long_ok and bool(bull_mask[i])
    if long_ok:
        if use_atr:
            cur_atr = atr_arr[i]  # type: ignore[index]
            sl = cur_c - params.atr_sl_mult * cur_atr
            tp = cur_c + params.atr_tp_mult * cur_atr
        else:
            sl = cur_c * (1.0 - params.stop_loss_pct)
            tp = cur_c * (1.0 + params.take_profit_pct)
        return {
            "side": "long",
            "entry_ref": float(cur_c),
            "stop": float(sl),
            "tp": float(tp),
            "signal_open_time_ms": t_sig,
        }
    short_ok = allow_short and prev_h >= 0 > cur_h and cur_rsi > params.rsi_oversold
    if bear_mask is not None:
        short_ok = short_ok and bool(bear_mask[i])
    if short_ok:
        if use_atr:
            cur_atr = atr_arr[i]  # type: ignore[index]
            sl = cur_c + params.atr_sl_mult * cur_atr
            tp = cur_c - params.atr_tp_mult * cur_atr
        else:
            sl = cur_c * (1.0 + params.stop_loss_pct)
            tp = cur_c * (1.0 - params.take_profit_pct)
        return {
            "side": "short",
            "entry_ref": float(cur_c),
            "stop": float(sl),
            "tp": float(tp),
            "signal_open_time_ms": t_sig,
        }
    return None


def macd_rsi_exit_by_mark(
    side: str,
    stop: float,
    tp: float,
    mark: float,
) -> Optional[Tuple[str, float]]:
    """
    Kiểm tra thoát theo giá tham chiếu (last / mark). Ưu tiên stop trước (bảo thủ).
    Trả về (reason, exit_price) hoặc None.
    """
    m = float(mark)
    if side == "long":
        if m <= stop:
            return "stop", float(stop)
        if m >= tp:
            return "target", float(tp)
    else:
        if m >= stop:
            return "stop", float(stop)
        if m <= tp:
            return "target", float(tp)
    return None
