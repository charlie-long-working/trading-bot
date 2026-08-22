#!/usr/bin/env python3
"""
So sánh backtest cùng dữ liệu spot BTC 1D, cùng hai cửa sổ bear:

- MACD + RSI: engine_macd_rsi_bt (hist cross + RSI, TP/SL %% , phí round-trip).
- Regime Fusion: backtest.engine.run_backtest (regime + OB/FVG/zone, sizing theo regime).

Chạy từ thư mục Trading-bot:
  python -m botdown.compare_macd_fusion_windows
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtest.engine import run_backtest  # noqa: E402
from botdown.data import load_btc_daily  # noqa: E402
from botdown.engine_macd_rsi_bt import MacdRsiParams, run_macd_rsi_backtest  # noqa: E402

WINDOWS = [
    ("Bear 2017–2018", "2017-12-11", "2018-08-06"),
    ("Bear 2021–2022", "2021-11-08", "2022-12-19"),
]


def _macd_row(label: str, start_d: str, end_d: str, r) -> Dict[str, Any]:
    return {
        "strategy": "macd_rsi_pct",
        "window": label,
        "start": start_d,
        "end": end_d,
        "total_return_pct": round(r.total_return_pct, 2),
        "buy_hold_pct": round(r.buy_hold_pct, 2),
        "vs_hold_pct": round(r.total_return_pct - r.buy_hold_pct, 2),
        "max_drawdown_pct": round(r.max_drawdown_pct, 2),
        "num_trades": r.num_trades,
        "win_rate": round(r.win_rate, 1),
        "sharpe_ratio": round(r.sharpe_ratio, 3),
        "profit_factor": round(r.profit_factor, 3),
    }


def _fusion_row(label: str, start_d: str, end_d: str, r) -> Dict[str, Any]:
    vs = r.total_return_pct - r.hold_return_pct
    return {
        "strategy": "regime_fusion",
        "window": label,
        "start": start_d,
        "end": end_d,
        "total_return_pct": round(r.total_return_pct, 2),
        "buy_hold_pct": round(r.hold_return_pct, 2),
        "vs_hold_pct": round(vs, 2),
        "max_drawdown_pct": round(r.max_drawdown_pct, 2),
        "num_trades": r.num_trades,
        "win_rate": round(r.win_rate, 1),
        "sharpe_ratio": round(r.sharpe_ratio, 3),
        "profit_factor": round(r.profit_factor, 3),
    }


def main() -> None:
    data_dir = str(ROOT / "data")
    macd_params = MacdRsiParams(
        exit_mode="pct",
        take_profit_pct=0.10,
        stop_loss_pct=0.04,
    )

    data = load_btc_daily(ROOT, "spot")
    if data is None:
        print("Không đọc được BTC 1D spot.", file=sys.stderr)
        sys.exit(1)
    open_time, _, high, low, close, _ = data

    rows: List[Dict[str, Any]] = []
    print(
        "=== So sánh: MACD+RSI (TP 10% / SL 4%, phí 0.1%) vs Regime Fusion "
        "(on-chain tắt, sizing theo regime, không phí trong engine) ===\n"
    )

    for label, start_d, end_d in WINDOWS:
        m = run_macd_rsi_backtest(
            open_time,
            high,
            low,
            close,
            start_date=start_d,
            end_date=end_d,
            params=macd_params,
            allow_short=True,
        )
        f = run_backtest(
            data_dir,
            "spot",
            "BTCUSDT",
            "1d",
            lookback=100,
            use_onchain=False,
            start_date=start_d,
            end_date=end_d,
            bull_flat_hold_pct=0.0,
        )
        if m is None or f is None:
            print(f"{label}: thiếu dữ liệu (macd={m is not None}, fusion={f is not None})")
            continue

        rows.append(_macd_row(label, start_d, end_d, m))
        rows.append(_fusion_row(label, start_d, end_d, f))

        print(f"{label} ({start_d} → {end_d})")
        print(
            f"  MACD+RSI:  {m.total_return_pct:+.2f}%  vs hold {m.buy_hold_pct:+.2f}%  "
            f"| DD {m.max_drawdown_pct:.1f}% | {m.num_trades} lệnh | WR {m.win_rate:.1f}% | PF {m.profit_factor:.2f}"
        )
        print(
            f"  Fusion:    {f.total_return_pct:+.2f}%  vs hold {f.hold_return_pct:+.2f}%  "
            f"| DD {f.max_drawdown_pct:.1f}% | {f.num_trades} lệnh | WR {f.win_rate:.1f}% | PF {f.profit_factor:.2f}"
        )
        print()

    out_dir = ROOT / "botdown" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "compare_macd_fusion_btc_1d_bear_windows.json"
    payload = {
        "data": "spot BTCUSDT 1d",
        "macd_rsi": {
            "exit": "pct",
            "take_profit_pct": macd_params.take_profit_pct,
            "stop_loss_pct": macd_params.stop_loss_pct,
            "fee_roundtrip": macd_params.fee_roundtrip,
            "note": "100% equity mỗi lệnh (trong engine).",
        },
        "regime_fusion": {
            "use_onchain": False,
            "bull_flat_hold_pct": 0.0,
            "note": (
                "Sizing theo regime (bear 0.25, sideways 0.5, bull 1.0); "
                "SL/TP theo strategy/rules.py và stop cấu trúc khi có; engine không trừ phí giao dịch."
            ),
        },
        "windows": WINDOWS,
        "results": rows,
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Đã ghi {out_path}")


if __name__ == "__main__":
    main()
