"""
Backtest engine for MACD+RSI strategy – vectorised indicator precomputation.

Computes MACD, RSI, ATR once upfront (O(n)), then walks the bar array once
to find crossover entry signals and simulate SL/TP exits.
"""

from typing import List, Optional

import numpy as np

from botv2.backtest.engine import BacktestResult, Trade, _parse_date_to_ts_ms
from botv2.data.fetcher import load_klines
from botv2.config import CACHE_DIR, REPO_ROOT
from botv2.strategy.macd_rsi import MACDRSIParams, _ema, _rsi, _atr


def run_backtest_macd_rsi(
    market_type: str,
    symbol: str,
    interval: str,
    cache_dir: Optional[str] = None,
    params: Optional[MACDRSIParams] = None,
    allow_short: bool = True,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Optional[BacktestResult]:
    """
    Backtest MACD+RSI strategy on cached klines.

    Spot markets automatically disable short signals.
    """
    if params is None:
        params = MACDRSIParams()

    cache = cache_dir or CACHE_DIR
    fallback = str(REPO_ROOT / "data") if (REPO_ROOT / "data").exists() else None
    out = load_klines(market_type, symbol, interval, cache_dir=cache, fallback_data_dir=fallback)
    if out is None:
        return None
    open_time, open_, high, low, close, volume = out
    n = len(close)

    lookback = params.slow_period + params.signal_period + 2
    if n < lookback:
        return None

    if market_type == "spot":
        allow_short = False

    # ── Precompute indicators (O(n)) ──
    ema_fast = _ema(close, params.fast_period)
    ema_slow = _ema(close, params.slow_period)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, params.signal_period)
    histogram = macd_line - signal_line
    rsi_arr = _rsi(close, params.rsi_period)
    atr_arr = _atr(high, low, close, params.atr_period)

    # ── Determine start/end bars ──
    ot = np.asarray(open_time, dtype=np.int64)
    if ot.size and ot[0] < 1e12:
        ot = ot * 1000

    start_ts = _parse_date_to_ts_ms(start_date)
    end_ts = _parse_date_to_ts_ms(end_date)
    i_start = lookback
    i_end = n - 1
    if start_ts is not None:
        idx = int(np.searchsorted(ot, start_ts, side="left"))
        i_start = max(lookback, min(idx, n - 1))
    if end_ts is not None:
        idx = int(np.searchsorted(ot, end_ts, side="right"))
        i_end = min(idx - 1, n - 1)
    if i_start > i_end:
        return None

    # ── Walk bars once ──
    trades: List[Trade] = []
    equity = 1.0
    equity_curve = np.ones(n)
    position: Optional[dict] = None

    for i in range(i_start, i_end + 1):
        # Check SL/TP on open position
        if position is not None:
            exit_price = None
            exit_reason = None
            if position["side"] == "long":
                if low[i] <= position["stop"]:
                    exit_price = position["stop"]
                    exit_reason = "stop"
                elif position["target"] is not None and high[i] >= position["target"]:
                    exit_price = position["target"]
                    exit_reason = "target"
            else:
                if high[i] >= position["stop"]:
                    exit_price = position["stop"]
                    exit_reason = "stop"
                elif position["target"] is not None and low[i] <= position["target"]:
                    exit_price = position["target"]
                    exit_reason = "target"

            if exit_price is not None:
                pnl_pct = (exit_price - position["entry_price"]) / position["entry_price"] * 100
                if position["side"] == "short":
                    pnl_pct = -pnl_pct
                trades.append(Trade(
                    entry_bar=position["entry_bar"],
                    exit_bar=i,
                    side=position["side"],
                    entry_price=position["entry_price"],
                    exit_price=exit_price,
                    pnl_pct=pnl_pct,
                    exit_reason=exit_reason or "signal",
                    stop_loss=position.get("stop"),
                    take_profit=position.get("target"),
                ))
                equity *= 1 + pnl_pct / 100
                position = None

        # Entry signals from precomputed arrays
        if position is None and i >= 1:
            cur_hist = histogram[i]
            prev_hist = histogram[i - 1]
            cur_rsi = rsi_arr[i]
            cur_atr = atr_arr[i]
            cur_close = close[i]

            if prev_hist <= 0 < cur_hist and cur_rsi < params.rsi_overbought:
                position = {
                    "side": "long",
                    "entry_price": cur_close,
                    "entry_bar": i,
                    "stop": cur_close - params.atr_sl_mult * cur_atr,
                    "target": cur_close + params.atr_tp_mult * cur_atr,
                }
            elif allow_short and prev_hist >= 0 > cur_hist and cur_rsi > params.rsi_oversold:
                position = {
                    "side": "short",
                    "entry_price": cur_close,
                    "entry_bar": i,
                    "stop": cur_close + params.atr_sl_mult * cur_atr,
                    "target": cur_close - params.atr_tp_mult * cur_atr,
                }

        equity_curve[i] = equity

    # Close open position at end
    if position is not None:
        exit_price = close[i_end]
        pnl_pct = (exit_price - position["entry_price"]) / position["entry_price"] * 100
        if position["side"] == "short":
            pnl_pct = -pnl_pct
        trades.append(Trade(
            entry_bar=position["entry_bar"],
            exit_bar=i_end,
            side=position["side"],
            entry_price=position["entry_price"],
            exit_price=exit_price,
            pnl_pct=pnl_pct,
            exit_reason="end",
            stop_loss=position.get("stop"),
            take_profit=position.get("target"),
        ))
        equity *= 1 + pnl_pct / 100
        equity_curve[i_end] = equity

    # ── Compute metrics ──
    total_return_pct = (equity - 1.0) * 100
    hold_return_pct = float((close[i_end] / close[i_start] - 1.0) * 100) if close[i_start] != 0 else 0.0

    if not trades:
        return BacktestResult(
            symbol=symbol, market_type=market_type, interval=interval,
            start_bar=i_start, end_bar=i_end, trades=[], equity_curve=equity_curve,
            total_return_pct=total_return_pct, hold_return_pct=hold_return_pct, num_trades=0,
        )

    returns = np.array([t.pnl_pct for t in trades])
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    win_rate = len(wins) / len(trades) * 100 if trades else 0
    gross_profit = float(np.sum(wins)) if len(wins) else 0
    gross_loss = abs(float(np.sum(losses))) if len(losses) else 1e-12
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
    avg_win_pct = float(np.mean(wins)) if len(wins) else 0.0
    avg_loss_pct = float(np.mean(losses)) if len(losses) else 0.0

    if len(returns) > 1 and np.std(returns) > 0:
        sharpe_ratio = float(np.mean(returns) / np.std(returns) * np.sqrt(252))
    else:
        sharpe_ratio = 0.0

    curve_slice = equity_curve[i_start: i_end + 1]
    peak = np.maximum.accumulate(curve_slice)
    dd = (peak - curve_slice) / np.where(peak > 0, peak, 1)
    max_drawdown_pct = float(np.max(dd) * 100) if len(dd) else 0

    return BacktestResult(
        symbol=symbol, market_type=market_type, interval=interval,
        start_bar=i_start, end_bar=i_end, trades=trades, equity_curve=equity_curve,
        total_return_pct=total_return_pct, hold_return_pct=hold_return_pct,
        sharpe_ratio=sharpe_ratio, max_drawdown_pct=max_drawdown_pct,
        win_rate=win_rate, profit_factor=profit_factor, num_trades=len(trades),
        avg_win_pct=avg_win_pct, avg_loss_pct=avg_loss_pct,
    )
