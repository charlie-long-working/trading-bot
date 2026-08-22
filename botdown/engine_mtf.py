"""Backtest short trên nến H1 với bộ lọc D1 + H4."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

import numpy as np

from .indicators import rsi, sma
from .mtf import last_closed_htf_index, resample_ohlcv
from .strategy_mtf import (
    MtfParams,
    h1_rsi_entry_cross,
    h1_rsi_exit_below,
    trend_bearish_at,
    trend_bearish_h4_simple,
)


MS_DAY = 86_400_000
MS_4H = 4 * 3_600_000


@dataclass
class Trade:
    entry_idx: int
    exit_idx: int
    entry_price: float
    exit_price: float
    exit_reason: str
    pnl_pct: float


@dataclass
class MtfBacktestResult:
    label: str
    trades: List[Trade] = field(default_factory=list)
    total_return_pct: float = 0.0
    buy_hold_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    num_trades: int = 0


def _ts_ms(s: str) -> int:
    dt = datetime.strptime(s.strip()[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def run_mtf_short_backtest(
    h1_ot: np.ndarray,
    h1_o: np.ndarray,
    h1_h: np.ndarray,
    h1_l: np.ndarray,
    h1_c: np.ndarray,
    h1_v: np.ndarray,
    d1_ot: np.ndarray,
    d1_o: np.ndarray,
    d1_h: np.ndarray,
    d1_l: np.ndarray,
    d1_c: np.ndarray,
    start_date: str,
    end_date: str,
    params: Optional[MtfParams] = None,
    label: str = "",
) -> Optional[MtfBacktestResult]:
    params = params or MtfParams()

    h4_ot, h4_o, h4_h, h4_l, h4_c, _ = resample_ohlcv(h1_ot, h1_o, h1_h, h1_l, h1_c, h1_v, MS_4H)

    d1_ma_f = sma(d1_c, params.d1_ma_fast)
    d1_ma_s = sma(d1_c, params.d1_ma_slow)
    d1_ma_t = sma(d1_c, params.d1_ma_trend)

    h4_ma_f = sma(h4_c, params.h4_ma_fast)
    h4_ma_s = sma(h4_c, params.h4_ma_slow)
    h4_rsi_arr = rsi(h4_c, params.h1_rsi_period)

    h1_rsi_arr = rsi(h1_c, params.h1_rsi_period)

    d1_idx = last_closed_htf_index(d1_ot, MS_DAY, h1_ot)
    h4_idx = last_closed_htf_index(h4_ot, MS_4H, h1_ot)

    n = len(h1_c)
    start_ts = _ts_ms(start_date)
    end_ts = _ts_ms(end_date)
    i0 = int(np.searchsorted(h1_ot, start_ts, side="left"))
    i1 = int(np.searchsorted(h1_ot, end_ts, side="right")) - 1

    rsi_w = params.h1_rsi_period + 5
    i_start = max(rsi_w, i0)
    i_end = min(i1, n - 1)
    if i_start >= i_end:
        return None

    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    in_short = False
    entry_price = stop_px = tp_px = 0.0
    entry_idx = 0
    last_exit_i = -10_000
    trades: List[Trade] = []

    for i in range(i_start, i_end + 1):
        sig = i - 1
        if sig < 1:
            continue

        di = int(d1_idx[i])
        hi4 = int(h4_idx[i])

        if in_short:
            px_open = float(h1_o[i])
            hit_stop = h1_h[i] >= stop_px
            hit_tp = h1_l[i] <= tp_px
            rsi_x = h1_rsi_exit_below(h1_rsi_arr, sig, params.h1_rsi_exit)
            exit_reason = ""
            exit_price = px_open
            if hit_stop:
                exit_reason = "stop"
                exit_price = stop_px
            elif hit_tp:
                exit_reason = "target"
                exit_price = tp_px
            elif rsi_x:
                exit_reason = "rsi"
                exit_price = px_open

            if exit_reason:
                gross = (entry_price - exit_price) / entry_price
                net = gross - params.fee_roundtrip
                equity *= 1 + net
                trades.append(
                    Trade(entry_idx, i, entry_price, exit_price, exit_reason, net * 100)
                )
                in_short = False
                last_exit_i = i
                peak = max(peak, equity)
                max_dd = max(max_dd, (peak - equity) / peak)
            continue

        if di < 0 or hi4 < 0:
            continue
        if di < params.d1_ma_trend - 1 or hi4 < params.h4_ma_slow - 1:
            continue

        if i - last_exit_i < params.cooldown_bars_after_exit:
            continue

        d_ok = trend_bearish_at(d1_c, d1_ma_f, d1_ma_s, d1_ma_t, di)
        h4_ok = trend_bearish_h4_simple(h4_c, h4_ma_f, h4_ma_s, hi4)
        h4_r = h4_rsi_arr[hi4]
        h4_rsi_ok = not np.isnan(h4_r) and h4_r >= params.h4_rsi_entry_min
        h1_ok = h1_rsi_entry_cross(h1_rsi_arr, sig, params.h1_rsi_entry_cross)

        if d_ok and h4_ok and h4_rsi_ok and h1_ok:
            entry_price = float(h1_o[i])
            stop_px = entry_price * (1 + params.stop_pct)
            tp_px = entry_price * (1 - params.take_profit_pct)
            entry_idx = i
            in_short = True

    if in_short:
        exit_price = float(h1_c[i_end])
        gross = (entry_price - exit_price) / entry_price
        net = gross - params.fee_roundtrip
        equity *= 1 + net
        trades.append(
            Trade(entry_idx, i_end, entry_price, exit_price, "end", net * 100)
        )
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak)

    bh = (h1_c[i_end] / h1_c[i_start] - 1.0) * 100
    wins = [t for t in trades if t.pnl_pct > 0]
    wr = len(wins) / len(trades) * 100 if trades else 0.0

    return MtfBacktestResult(
        label=label,
        trades=trades,
        total_return_pct=(equity - 1.0) * 100,
        buy_hold_pct=bh,
        max_drawdown_pct=max_dd * 100,
        win_rate=wr,
        num_trades=len(trades),
    )
