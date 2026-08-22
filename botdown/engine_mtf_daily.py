"""
Đa khung D1 + H4 + H1 nhưng **khớp lệnh theo nến D1** (open ngày kế).

- Cuối ngày UTC: dùng D1 đóng (di-1) cho bear, H4 đóng trước open hôm nay, **nến H1 cuối cùng của ngày di-1** cho RSI cắt.
- Vào short tại open D1[di].
- Thoát: high/low/RSI trên **nến D1** (ít lệnh, ít phí, ổn định hơn so với thoát từng giờ).

Không nhìn trước: tín hiệu chỉ dùng dữ liệu đến hết ngày di-1.
"""

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
class MtfDailyBacktestResult:
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


def _last_h1_index_for_day(
    h1_ot: np.ndarray,
    day_start_ms: int,
    next_day_start_ms: int,
) -> int:
    """Chỉ số H1 cuối cùng có open_time trong [day_start, next_day_start)."""
    ot = np.asarray(h1_ot, dtype=np.int64)
    m = (ot >= day_start_ms) & (ot < next_day_start_ms)
    idx = np.where(m)[0]
    if len(idx) == 0:
        return -1
    return int(idx[-1])


def run_mtf_daily_execution_backtest(
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
) -> Optional[MtfDailyBacktestResult]:
    params = params or MtfParams()

    h4_ot, _, h4_h, h4_l, h4_c, h4_v = resample_ohlcv(
        h1_ot, h1_o, h1_h, h1_l, h1_c, h1_v, MS_4H
    )

    d1_ma_f = sma(d1_c, params.d1_ma_fast)
    d1_ma_s = sma(d1_c, params.d1_ma_slow)
    d1_ma_t = sma(d1_c, params.d1_ma_trend)
    d1_rsi = rsi(d1_c, params.h1_rsi_period)

    h4_ma_f = sma(h4_c, params.h4_ma_fast)
    h4_ma_s = sma(h4_c, params.h4_ma_slow)
    h4_rsi_arr = rsi(h4_c, params.h1_rsi_period)

    h1_rsi_arr = rsi(h1_c, params.h1_rsi_period)

    d1_ot = np.asarray(d1_ot, dtype=np.int64)
    nd = len(d1_c)
    start_ts = _ts_ms(start_date)
    end_ts = _ts_ms(end_date)
    di0 = int(np.searchsorted(d1_ot, start_ts, side="left"))
    di1 = int(np.searchsorted(d1_ot, end_ts, side="right")) - 1

    di_start = max(params.d1_ma_trend + 2, di0 + 1)
    di_end = min(di1, nd - 1)
    if di_start > di_end:
        return None

    h4_idx_at_d1_open = last_closed_htf_index(h4_ot, MS_4H, d1_ot)

    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    in_short = False
    entry_price = stop_px = tp_px = 0.0
    entry_idx = 0
    last_exit_di = -10_000
    trades: List[Trade] = []

    for di in range(di_start, di_end + 1):
        prev = di - 1

        if in_short:
            px_open = float(d1_o[di])
            hit_stop = d1_h[di] >= stop_px
            hit_tp = d1_l[di] <= tp_px
            rsi_x = False
            if prev >= 0:
                rsi_x = h1_rsi_exit_below(d1_rsi, prev, params.h1_rsi_exit)
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
                    Trade(entry_idx, di, entry_price, exit_price, exit_reason, net * 100)
                )
                in_short = False
                last_exit_di = di
                peak = max(peak, equity)
                max_dd = max(max_dd, (peak - equity) / peak)
            continue

        if di - last_exit_di < params.cooldown_days_after_exit:
            continue

        if prev < params.d1_ma_trend - 1:
            continue

        d_ok = trend_bearish_at(d1_c, d1_ma_f, d1_ma_s, d1_ma_t, prev)
        hi4 = int(h4_idx_at_d1_open[di])
        if hi4 < params.h4_ma_slow - 1:
            continue
        h4_ok = trend_bearish_h4_simple(h4_c, h4_ma_f, h4_ma_s, hi4)
        h4_r = h4_rsi_arr[hi4]
        h4_rsi_ok = not np.isnan(h4_r) and h4_r >= params.h4_rsi_entry_min

        day_s, day_e = int(d1_ot[prev]), int(d1_ot[di])
        li1 = _last_h1_index_for_day(h1_ot, day_s, day_e)
        if li1 < 2:
            continue
        sig_h1 = li1 - 1
        h1_ok = h1_rsi_entry_cross(h1_rsi_arr, sig_h1, params.h1_rsi_entry_cross)

        if d_ok and h4_ok and h4_rsi_ok and h1_ok:
            entry_price = float(d1_o[di])
            stop_px = entry_price * (1 + params.stop_pct)
            tp_px = entry_price * (1 - params.take_profit_pct)
            entry_idx = di
            in_short = True

    if in_short:
        exit_price = float(d1_c[di_end])
        gross = (entry_price - exit_price) / entry_price
        net = gross - params.fee_roundtrip
        equity *= 1 + net
        trades.append(
            Trade(entry_idx, di_end, entry_price, exit_price, "end", net * 100)
        )
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak)

    bh = (d1_c[di_end] / d1_c[di0] - 1.0) * 100 if di0 < nd else 0.0
    wins = [t for t in trades if t.pnl_pct > 0]
    wr = len(wins) / len(trades) * 100 if trades else 0.0

    return MtfDailyBacktestResult(
        label=label,
        trades=trades,
        total_return_pct=(equity - 1.0) * 100,
        buy_hold_pct=bh,
        max_drawdown_pct=max_dd * 100,
        win_rate=wr,
        num_trades=len(trades),
    )
