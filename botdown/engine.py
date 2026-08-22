"""Backtest engine: short-only downtrend strategy, enter at open, no lookahead."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

import numpy as np

from .indicators import rsi, sma
from .strategy import DowntrendParams, should_enter_short, should_exit_short, trend_bearish


@dataclass
class Trade:
    entry_idx: int
    exit_idx: int
    entry_price: float
    exit_price: float
    exit_reason: str
    pnl_pct: float


@dataclass
class BacktestResult:
    label: str
    start_ts: int
    end_ts: int
    trades: List[Trade] = field(default_factory=list)
    total_return_pct: float = 0.0
    buy_hold_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    num_trades: int = 0


def _ts_ms(s: str) -> int:
    dt = datetime.strptime(s.strip()[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def run_downtrend_short_backtest(
    open_time: np.ndarray,
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    start_date: str,
    end_date: str,
    params: Optional[DowntrendParams] = None,
    label: str = "",
) -> Optional[BacktestResult]:
    params = params or DowntrendParams()
    ot = np.asarray(open_time, dtype=np.int64)
    op = np.asarray(open_, dtype=float)
    hi = np.asarray(high, dtype=float)
    lo = np.asarray(low, dtype=float)
    cl = np.asarray(close, dtype=float)
    n = len(cl)
    if n < params.ma_trend + 5:
        return None

    start_ts = _ts_ms(start_date)
    end_ts = _ts_ms(end_date)
    i0 = int(np.searchsorted(ot, start_ts, side="left"))
    i1 = int(np.searchsorted(ot, end_ts, side="right")) - 1
    warmup = params.ma_trend + 2
    i_start = max(warmup, i0)
    i_end = min(i1, n - 1)
    if i_start >= i_end:
        return None

    ma_f = sma(cl, params.ma_fast)
    ma_s = sma(cl, params.ma_slow)
    ma_t = sma(cl, params.ma_trend)
    rsi_arr = rsi(cl, params.rsi_period)

    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    in_short = False
    entry_price = 0.0
    stop_px = 0.0
    tp_px = 0.0
    entry_idx = 0
    trades: List[Trade] = []

    for i in range(i_start, i_end + 1):
        sig = i - 1
        if sig < 1:
            continue

        if in_short:
            px_open = op[i]
            hit_stop = hi[i] >= stop_px
            hit_tp = lo[i] <= tp_px
            rsi_exit = should_exit_short(rsi_arr, sig, params.rsi_exit)
            exit_reason = ""
            exit_price = px_open
            if hit_stop:
                exit_reason = "stop"
                exit_price = stop_px
            elif hit_tp:
                exit_reason = "target"
                exit_price = tp_px
            elif rsi_exit:
                exit_reason = "rsi"
                exit_price = px_open

            if exit_reason:
                gross = (entry_price - exit_price) / entry_price
                net = gross - params.fee_roundtrip
                pnl_pct = net * 100
                equity *= 1 + net
                trades.append(
                    Trade(
                        entry_idx=entry_idx,
                        exit_idx=i,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        exit_reason=exit_reason,
                        pnl_pct=pnl_pct,
                    )
                )
                in_short = False
                peak = max(peak, equity)
                max_dd = max(max_dd, (peak - equity) / peak)
                continue

        if not in_short and should_enter_short(
            cl,
            rsi_arr,
            ma_f,
            ma_s,
            ma_t,
            sig,
            params.rsi_entry_cross,
            params.require_close_below_ma_fast,
        ):
            if not trend_bearish(cl, ma_f, ma_s, ma_t, sig):
                continue
            entry_price = float(op[i])
            stop_px = entry_price * (1 + params.stop_pct)
            tp_px = entry_price * (1 - params.take_profit_pct)
            entry_idx = i
            in_short = True

    if in_short:
        exit_price = float(cl[i_end])
        gross = (entry_price - exit_price) / entry_price
        net = gross - params.fee_roundtrip
        equity *= 1 + net
        trades.append(
            Trade(
                entry_idx=entry_idx,
                exit_idx=i_end,
                entry_price=entry_price,
                exit_price=exit_price,
                exit_reason="end",
                pnl_pct=net * 100,
            )
        )
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak)

    buy_hold = (cl[i_end] / cl[i_start] - 1.0) * 100
    wins = sum(1 for t in trades if t.pnl_pct > 0)
    wr = (wins / len(trades) * 100) if trades else 0.0

    return BacktestResult(
        label=label,
        start_ts=start_ts,
        end_ts=end_ts,
        trades=trades,
        total_return_pct=(equity - 1.0) * 100,
        buy_hold_pct=buy_hold,
        max_drawdown_pct=max_dd * 100,
        win_rate=wr,
        num_trades=len(trades),
    )
