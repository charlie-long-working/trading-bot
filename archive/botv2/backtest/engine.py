"""
botv2 Backtest engine: walk klines, apply regime + technical fusion, simulate positions.

Uses data from botv2 cache (CCXT), strategy/signals from parent repo. No on-chain (Glassnode).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

import numpy as np

# Parent repo must be in path for these imports (run from project root)
from strategy import Regime, RegimeClassifier, RegimeInputs, get_rules_for_regime
from signals.fusion import get_signal, Signal

from botv2.data.fetcher import load_klines
from botv2.config import CACHE_DIR, REPO_ROOT


@dataclass
class Trade:
    entry_bar: int
    exit_bar: int
    side: str
    entry_price: float
    exit_price: float
    pnl_pct: float
    exit_reason: str
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


@dataclass
class BacktestResult:
    symbol: str
    market_type: str
    interval: str
    start_bar: int
    end_bar: int
    trades: List[Trade] = field(default_factory=list)
    equity_curve: Optional[np.ndarray] = None
    total_return_pct: float = 0.0
    hold_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    num_trades: int = 0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0


def _parse_date_to_ts_ms(date_str: Optional[str]) -> Optional[int]:
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str.strip()[:10], "%Y-%m-%d")
        return int(dt.replace(tzinfo=None).timestamp() * 1000)
    except Exception:
        return None


def run_backtest(
    market_type: str,
    symbol: str,
    interval: str,
    cache_dir: Optional[str] = None,
    lookback: int = 100,
    base_size: float = 1.0,
    require_volume_confirmation: bool = False,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    bull_flat_hold_pct: float = 0.0,
) -> Optional[BacktestResult]:
    """
    Run backtest on klines from botv2 cache.

    Uses parent strategy (regime + OB/FVG/zones) and signals. No on-chain.
    """
    cache = cache_dir or CACHE_DIR
    fallback = str(REPO_ROOT / "data") if (REPO_ROOT / "data").exists() else None
    out = load_klines(market_type, symbol, interval, cache_dir=cache, fallback_data_dir=fallback)
    if out is None:
        return None
    open_time, open_, high, low, close, volume = out
    n = len(close)
    if n < lookback:
        return None

    ot = np.asarray(open_time, dtype=np.int64)
    if ot.size and ot[0] < 1e12:
        ot = ot * 1000
    start_ts = _parse_date_to_ts_ms(start_date)
    end_ts = _parse_date_to_ts_ms(end_date)
    i_start = 0
    i_end = n - 1
    if start_ts is not None:
        idx = np.searchsorted(ot, start_ts, side="left")
        i_start = max(lookback, min(idx, n - 1))
    if end_ts is not None:
        idx = np.searchsorted(ot, end_ts, side="right")
        i_end = min(idx - 1, n - 1)
    if i_start > i_end:
        return None

    classifier = RegimeClassifier()
    trades: List[Trade] = []
    equity = 1.0
    equity_curve = np.ones(n)
    position: Optional[dict] = None

    for i in range(i_start, i_end + 1):
        o = open_[: i + 1]
        h = high[: i + 1]
        l_ = low[: i + 1]
        c = close[: i + 1]
        v = volume[: i + 1]

        if position is not None:
            exit_price = None
            exit_reason = None
            if position["side"] == "long":
                if l_[-1] <= position["stop"]:
                    exit_price = position["stop"]
                    exit_reason = "stop"
                elif position.get("target") is not None and h[-1] >= position["target"]:
                    exit_price = position["target"]
                    exit_reason = "target"
            else:
                if h[-1] >= position["stop"]:
                    exit_price = position["stop"]
                    exit_reason = "stop"
                elif position.get("target") is not None and l_[-1] <= position["target"]:
                    exit_price = position["target"]
                    exit_reason = "target"

            if exit_price is not None:
                pnl_pct = (exit_price - position["entry_price"]) / position["entry_price"] * 100
                if position["side"] == "short":
                    pnl_pct = -pnl_pct
                pnl_pct *= position["size_pct"]
                trades.append(
                    Trade(
                        entry_bar=position["entry_bar"],
                        exit_bar=i,
                        side=position["side"],
                        entry_price=position["entry_price"],
                        exit_price=exit_price,
                        pnl_pct=pnl_pct,
                        exit_reason=exit_reason or "signal",
                        stop_loss=position.get("stop"),
                        take_profit=position.get("target"),
                    )
                )
                equity *= 1 + pnl_pct / 100
                position = None

        if position is None:
            res = get_signal(
                o, h, l_, c, v,
                regime_classifier=classifier,
                require_volume_confirmation=require_volume_confirmation,
                ob_lookback=min(50, i),
                fvg_lookback=min(30, i),
                zone_lookback=min(50, i),
                sopr=None,
                mvrv=None,
            )
            regime = res.regime
            rules = get_rules_for_regime(regime)
            size_pct = rules.position_size_pct * base_size
            stop_pct = rules.stop_pct or 0.02
            tp_pct = rules.take_profit_pct

            if res.signal == Signal.LONG and rules.allow_long:
                stop = res.stop_below if res.stop_below is not None else close[i] * (1 - stop_pct)
                target = close[i] * (1 + tp_pct) if tp_pct is not None else None
                position = {
                    "side": "long",
                    "entry_price": close[i],
                    "entry_bar": i,
                    "stop": stop,
                    "target": target,
                    "size_pct": size_pct,
                }
            elif res.signal == Signal.SHORT and rules.allow_short:
                stop = res.stop_above if res.stop_above is not None else close[i] * (1 + stop_pct)
                target = close[i] * (1 - tp_pct) if tp_pct is not None else None
                position = {
                    "side": "short",
                    "entry_price": close[i],
                    "entry_bar": i,
                    "stop": stop,
                    "target": target,
                    "size_pct": size_pct,
                }

            if position is None and bull_flat_hold_pct > 0 and regime == Regime.BULL and i > i_start:
                bar_return = (close[i] / close[i - 1]) - 1.0
                equity *= 1.0 + bull_flat_hold_pct * bar_return

        equity_curve[i] = equity

    if position is not None:
        exit_bar = i_end
        exit_price = close[i_end]
        pnl_pct = (exit_price - position["entry_price"]) / position["entry_price"] * 100
        if position["side"] == "short":
            pnl_pct = -pnl_pct
        pnl_pct *= position["size_pct"]
        trades.append(
            Trade(
                entry_bar=position["entry_bar"],
                exit_bar=exit_bar,
                side=position["side"],
                entry_price=position["entry_price"],
                exit_price=exit_price,
                pnl_pct=pnl_pct,
                exit_reason="end",
                stop_loss=position.get("stop"),
                take_profit=position.get("target"),
            )
        )
        equity *= 1 + pnl_pct / 100
        equity_curve[exit_bar] = equity

    total_return_pct = (equity - 1.0) * 100
    hold_return_pct = float((close[i_end] / close[i_start] - 1.0) * 100) if close[i_start] != 0 else 0.0
    if not trades:
        return BacktestResult(
            symbol=symbol,
            market_type=market_type,
            interval=interval,
            start_bar=i_start,
            end_bar=i_end,
            trades=[],
            equity_curve=equity_curve,
            total_return_pct=total_return_pct,
            hold_return_pct=hold_return_pct,
            num_trades=0,
        )

    returns = np.array([t.pnl_pct for t in trades])
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    win_rate = len(wins) / len(trades) * 100 if trades else 0
    gross_profit = np.sum(wins) if len(wins) else 0
    gross_loss = abs(np.sum(losses)) if len(losses) else 1e-12
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
    avg_win_pct = float(np.mean(wins)) if len(wins) else 0.0
    avg_loss_pct = float(np.mean(losses)) if len(losses) else 0.0

    if len(returns) > 1 and np.std(returns) > 0:
        sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252)
    else:
        sharpe_ratio = 0.0

    curve_slice = equity_curve[i_start : i_end + 1]
    peak = np.maximum.accumulate(curve_slice)
    dd = (peak - curve_slice) / np.where(peak > 0, peak, 1)
    max_drawdown_pct = float(np.max(dd) * 100) if len(dd) else 0

    return BacktestResult(
        symbol=symbol,
        market_type=market_type,
        interval=interval,
        start_bar=i_start,
        end_bar=i_end,
        trades=trades,
        equity_curve=equity_curve,
        total_return_pct=total_return_pct,
        hold_return_pct=hold_return_pct,
        sharpe_ratio=sharpe_ratio,
        max_drawdown_pct=max_drawdown_pct,
        win_rate=win_rate,
        profit_factor=profit_factor,
        num_trades=len(trades),
        avg_win_pct=avg_win_pct,
        avg_loss_pct=avg_loss_pct,
    )
