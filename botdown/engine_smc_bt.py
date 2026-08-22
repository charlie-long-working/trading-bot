"""
Backtest Smart Money Concepts (đơn giản hóa, khớp `strategy/technical.py`):

- Vào **long** khi giá **vừa chạm** vùng bull: bullish Order Block HOẶC bullish FVG HOẶC demand zone
  (cạnh lên: trong zone ở nến i nhưng không trong zone long ở nến i-1).
- Vào **short** khi **vừa chạm** bear: bearish OB / bearish FVG / supply zone.
- Nếu cùng nến vừa long vừa short → bỏ qua.
- Thoát: giống MACD+RSI — **TP/SL %** + phí round-trip (mặc định 10% / 4% / 0.1%).

Không gồm regime filter, BOS/CHoCH đầy đủ — để so sánh “thuần SMC zone retest” với MACD+RSI.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

import numpy as np

from strategy.technical import (
    OBType,
    fair_value_gaps,
    order_blocks,
    price_at_fvg,
    price_at_ob,
    price_at_zone,
    supply_demand_zones,
)

from botdown.engine_macd_rsi_bt import (
    MacdRsiBacktestResult,
    MacdRsiTrade,
    ema_trend_bull_bear,
)


def _ts_ms(s: str) -> int:
    dt = datetime.strptime(s.strip()[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


@dataclass
class SmcParams:
    take_profit_pct: float = 0.10
    stop_loss_pct: float = 0.04
    fee_roundtrip: float = 0.001
    ob_lookback: int = 50
    fvg_lookback: int = 30
    zone_lookback: int = 50
    move_bars: int = 5
    min_move_pct: float = 0.5
    use_ema_trend_filter: bool = False
    ema_trend_fast: int = 20
    ema_trend_slow: int = 50


def _in_long_zones(px: float, o, h, l, c, p: SmcParams) -> bool:
    obs = order_blocks(o, h, l, c, p.ob_lookback, p.move_bars, p.min_move_pct)
    fvgs = fair_value_gaps(h, l, p.fvg_lookback)
    zones = supply_demand_zones(o, h, l, c, p.zone_lookback)
    for ob in reversed(obs):
        if ob.ob_type == OBType.BULLISH and price_at_ob(px, ob):
            return True
    for fvg in reversed(fvgs):
        if fvg.fvg_type == OBType.BULLISH and price_at_fvg(px, fvg):
            return True
    for z in reversed(zones):
        if z.is_demand and price_at_zone(px, z):
            return True
    return False


def _in_short_zones(px: float, o, h, l, c, p: SmcParams) -> bool:
    obs = order_blocks(o, h, l, c, p.ob_lookback, p.move_bars, p.min_move_pct)
    fvgs = fair_value_gaps(h, l, p.fvg_lookback)
    zones = supply_demand_zones(o, h, l, c, p.zone_lookback)
    for ob in reversed(obs):
        if ob.ob_type == OBType.BEARISH and price_at_ob(px, ob):
            return True
    for fvg in reversed(fvgs):
        if fvg.fvg_type == OBType.BEARISH and price_at_fvg(px, fvg):
            return True
    for z in reversed(zones):
        if not z.is_demand and price_at_zone(px, z):
            return True
    return False


def smc_entry_snapshot(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    params: Optional[SmcParams] = None,
    allow_short: bool = True,
) -> Optional[dict]:
    """
    Edge-touch SMC entry on the last closed bar (same logic as backtest loop).
    Returns dict with side, entry_ref, stop, tp or None.
    """
    params = params or SmcParams()
    o = np.asarray(open_, dtype=float)
    hi = np.asarray(high, dtype=float)
    lo = np.asarray(low, dtype=float)
    cl = np.asarray(close, dtype=float)
    n = len(cl)
    lookback = max(params.ob_lookback, params.zone_lookback, params.fvg_lookback) + 8
    if n < lookback + 2:
        return None

    bull_mask, bear_mask = (
        ema_trend_bull_bear(cl, params.ema_trend_fast, params.ema_trend_slow)
        if params.use_ema_trend_filter
        else (None, None)
    )

    i = n - 1
    o_i, h_i, l_i, c_i = o[: i + 1], hi[: i + 1], lo[: i + 1], cl[: i + 1]
    o_p, h_p, l_p, c_p = o[:i], hi[:i], lo[:i], cl[:i]
    cur, prev = float(cl[i]), float(cl[i - 1])

    now_long = _in_long_zones(cur, o_i, h_i, l_i, c_i, params)
    prev_long = _in_long_zones(prev, o_p, h_p, l_p, c_p, params)
    long_sig = now_long and not prev_long
    if bull_mask is not None:
        long_sig = long_sig and bool(bull_mask[i])

    now_short = _in_short_zones(cur, o_i, h_i, l_i, c_i, params)
    prev_short = _in_short_zones(prev, o_p, h_p, l_p, c_p, params)
    short_sig = allow_short and now_short and not prev_short
    if bear_mask is not None:
        short_sig = short_sig and bool(bear_mask[i])

    tp, sl = params.take_profit_pct, params.stop_loss_pct
    if long_sig and not short_sig:
        return {
            "side": "long",
            "entry_ref": cur,
            "stop": cur * (1.0 - sl),
            "tp": cur * (1.0 + tp),
        }
    if short_sig and not long_sig:
        return {
            "side": "short",
            "entry_ref": cur,
            "stop": cur * (1.0 + sl),
            "tp": cur * (1.0 - tp),
        }
    return None


def run_smc_backtest(
    open_time: np.ndarray,
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    start_date: str,
    end_date: str,
    params: Optional[SmcParams] = None,
    allow_short: bool = True,
) -> Optional[MacdRsiBacktestResult]:
    params = params or SmcParams()
    ot = np.asarray(open_time, dtype=np.int64)
    o = np.asarray(open_, dtype=float)
    hi = np.asarray(high, dtype=float)
    lo = np.asarray(low, dtype=float)
    cl = np.asarray(close, dtype=float)
    n = len(cl)

    lookback = max(params.ob_lookback, params.zone_lookback, params.fvg_lookback) + 8
    if params.use_ema_trend_filter:
        lookback = max(lookback, params.ema_trend_slow + 2)
    if n < lookback + 2:
        return None

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

    tp = params.take_profit_pct
    sl = params.stop_loss_pct
    fee = params.fee_roundtrip

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
                net = gross - fee
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
            o_i = o[: i + 1]
            h_i = hi[: i + 1]
            l_i = lo[: i + 1]
            c_i = cl[: i + 1]
            o_p = o[:i]
            h_p = hi[:i]
            l_p = lo[:i]
            c_p = cl[:i]

            cur = float(cl[i])
            prev = float(cl[i - 1])
            now_long = _in_long_zones(cur, o_i, h_i, l_i, c_i, params)
            prev_long = _in_long_zones(prev, o_p, h_p, l_p, c_p, params)
            long_sig = now_long and not prev_long
            if bull_mask is not None:
                long_sig = long_sig and bool(bull_mask[i])

            now_short = _in_short_zones(cur, o_i, h_i, l_i, c_i, params)
            prev_short = _in_short_zones(prev, o_p, h_p, l_p, c_p, params)
            short_sig = allow_short and now_short and not prev_short
            if bear_mask is not None:
                short_sig = short_sig and bool(bear_mask[i])

            if long_sig and short_sig:
                pass
            elif long_sig:
                position = {
                    "side": "long",
                    "entry_price": cur,
                    "entry_bar": i,
                    "stop": cur * (1.0 - sl),
                    "target": cur * (1.0 + tp),
                }
            elif short_sig:
                position = {
                    "side": "short",
                    "entry_price": cur,
                    "entry_bar": i,
                    "stop": cur * (1.0 + sl),
                    "target": cur * (1.0 - tp),
                }

        equity_curve[i] = equity

    if position is not None:
        exit_price = float(cl[i_end])
        gross = (exit_price - position["entry_price"]) / position["entry_price"]
        if position["side"] == "short":
            gross = -gross
        net = gross - fee
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
