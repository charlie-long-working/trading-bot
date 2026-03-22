"""botv2 backtest: regime + fusion strategy vs buy-and-hold."""

from .engine import run_backtest, BacktestResult, Trade

__all__ = ["run_backtest", "BacktestResult", "Trade"]
