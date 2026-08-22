#!/usr/bin/env python3
"""
Backtest short downtrend đa khung: D1 + H4 (từ 1h) + H1 (RSI cuối ngày).
Khớp lệnh & thoát theo **nến D1** (ít phí hơn so với thoát từng giờ).

Khoảng thời gian (UTC):
- 2017-12-11 → 2018-08-06
- 2021-11-08 → 2022-12-19

Chạy từ thư mục Trading-bot:
  python -m botdown.run_backtest
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from botdown.data import load_btc_daily, load_btc_klines
from botdown.engine_mtf_daily import run_mtf_daily_execution_backtest
from botdown.strategy_mtf import MtfParams


WINDOWS = [
    ("Bear 2017–2018", "2017-12-11", "2018-08-06"),
    ("Bear 2021–2022", "2021-11-08", "2022-12-19"),
]


def main() -> None:
    h1 = load_btc_klines(ROOT, "1h", "spot")
    d1 = load_btc_daily(ROOT, "spot")
    if h1 is None or d1 is None:
        print("Thiếu data spot 1h hoặc 1d BTCUSDT", file=sys.stderr)
        sys.exit(1)

    h1_ot, h1_o, h1_h, h1_l, h1_c, h1_v = h1
    d1_ot, d1_o, d1_h, d1_l, d1_c, _ = d1

    params = MtfParams()
    rows = []
    print("=== Backtest: MTF D1+H4+H1 → khớp D1 (BTC spot) ===\n")
    for label, start_d, end_d in WINDOWS:
        r = run_mtf_daily_execution_backtest(
            h1_ot,
            h1_o,
            h1_h,
            h1_l,
            h1_c,
            h1_v,
            d1_ot,
            d1_o,
            d1_h,
            d1_l,
            d1_c,
            start_date=start_d,
            end_date=end_d,
            params=params,
            label=label,
        )
        if r is None:
            print(f"{label}: không đủ dữ liệu\n")
            continue
        rows.append(
            {
                "window": label,
                "start": start_d,
                "end": end_d,
                "total_return_pct": round(r.total_return_pct, 2),
                "buy_hold_pct": round(r.buy_hold_pct, 2),
                "max_drawdown_pct": round(r.max_drawdown_pct, 2),
                "num_trades": r.num_trades,
                "win_rate": round(r.win_rate, 1),
                "trades": [
                    {
                        "entry_bar": t.entry_idx,
                        "exit_bar": t.exit_idx,
                        "entry": round(t.entry_price, 2),
                        "exit": round(t.exit_price, 2),
                        "reason": t.exit_reason,
                        "pnl_pct": round(t.pnl_pct, 3),
                    }
                    for t in r.trades
                ],
            }
        )
        print(f"{label} ({start_d} → {end_d})")
        print(f"  Return strategy: {r.total_return_pct:+.2f}%  |  Buy&hold (D1): {r.buy_hold_pct:+.2f}%")
        print(f"  Max DD: {r.max_drawdown_pct:.2f}%  |  Trades: {r.num_trades}  |  Win%: {r.win_rate:.1f}")
        print()

    out_dir = ROOT / "botdown" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "downtrend_backtest_btc.json"
    payload = {
        "mode": "mtf_d1_h4_h1_execute_on_daily",
        "params": {
            "d1_ma_fast": params.d1_ma_fast,
            "d1_ma_slow": params.d1_ma_slow,
            "d1_ma_trend": params.d1_ma_trend,
            "h4_ma_fast": params.h4_ma_fast,
            "h4_ma_slow": params.h4_ma_slow,
            "h1_rsi_period": params.h1_rsi_period,
            "h1_rsi_entry_cross": params.h1_rsi_entry_cross,
            "h1_rsi_exit": params.h1_rsi_exit,
            "stop_pct": params.stop_pct,
            "take_profit_pct": params.take_profit_pct,
            "fee_roundtrip": params.fee_roundtrip,
            "cooldown_days_after_exit": params.cooldown_days_after_exit,
            "h4_rsi_entry_min": params.h4_rsi_entry_min,
        },
        "windows": rows,
        "logic": (
            "Cuối ngày UTC: D1 bear, H4 bear + H4 RSI>=h4_rsi_entry_min, nến H1 cuối của ngày có RSI cắt lên; "
            "vào open D1 ngày kế. Thoát: stop/tp/RSI trên nến D1."
        ),
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Đã ghi {out_path}")


if __name__ == "__main__":
    main()
