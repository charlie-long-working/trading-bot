"""
Export backtest signals to CSV/JSON with entry, stop_loss, take_profit per trade.

Each row = one entry signal with clear Entry, SL, TP for indicator/strategy review.
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import numpy as np

from botv2.backtest.engine import BacktestResult, Trade
from botv2.data.fetcher import load_klines
from botv2.config import CACHE_DIR, REPO_ROOT


def _load_open_times(result: BacktestResult) -> Optional[np.ndarray]:
    """Load open_time array once for all trades in a result."""
    fallback = str(REPO_ROOT / "data") if (REPO_ROOT / "data").exists() else None
    out = load_klines(result.market_type, result.symbol, result.interval,
                      cache_dir=CACHE_DIR, fallback_data_dir=fallback)
    if out is None:
        return None
    return out[0]


def _build_rows(result: BacktestResult, open_times: Optional[np.ndarray]) -> list:
    rows = []
    for t in result.trades:
        ts = None
        if open_times is not None and t.entry_bar < len(open_times):
            ts = int(open_times[t.entry_bar])
        ts_str = datetime.utcfromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S") if ts else ""
        rows.append({
            "open_time": ts_str,
            "open_time_ms": ts or 0,
            "symbol": result.symbol,
            "timeframe": result.interval,
            "side": t.side,
            "entry": t.entry_price,
            "stop_loss": t.stop_loss or "",
            "take_profit": t.take_profit or "",
            "exit_price": t.exit_price,
            "exit_reason": t.exit_reason,
            "pnl_pct": round(t.pnl_pct, 2),
        })
    return rows


def export_trades_to_csv(result: BacktestResult, out_path: str) -> None:
    """Export trades to CSV with entry/SL/TP."""
    open_times = _load_open_times(result)
    rows = _build_rows(result, open_times)

    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "open_time", "open_time_ms", "symbol", "timeframe", "side",
            "entry", "stop_loss", "take_profit", "exit_price", "exit_reason", "pnl_pct"
        ])
        w.writeheader()
        w.writerows(rows)
    print(f"  Exported {len(rows)} signals to {path}")


def export_trades_to_json(result: BacktestResult, out_path: str) -> None:
    """Export trades to JSON."""
    open_times = _load_open_times(result)
    rows = []
    for t in result.trades:
        ts = None
        if open_times is not None and t.entry_bar < len(open_times):
            ts = int(open_times[t.entry_bar])
        rows.append({
            "open_time": ts,
            "symbol": result.symbol,
            "timeframe": result.interval,
            "side": t.side,
            "entry": t.entry_price,
            "stop_loss": t.stop_loss,
            "take_profit": t.take_profit,
            "exit_price": t.exit_price,
            "exit_reason": t.exit_reason,
            "pnl_pct": round(t.pnl_pct, 2),
        })

    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(rows, f, indent=2)
    print(f"  Exported {len(rows)} signals to {path}")


def export_all_configs(
    results: List[tuple],
    out_dir: str = "reports/indicators",
) -> None:
    """Export all backtest results to CSV and JSON."""
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    for label, r in results:
        safe = label.replace(" ", "_").replace("/", "_")
        export_trades_to_csv(r, str(out_path / f"{safe}.csv"))
        export_trades_to_json(r, str(out_path / f"{safe}.json"))
