#!/usr/bin/env python3
"""
Backtest MACD + RSI trên BTC spot (**mặc định nến 1D**; có thể `--interval 1h`), hai cửa sổ bear:

- 2017-12-11 → 2018-08-06
- 2021-11-08 → 2022-12-19

Điểm vào: MACD histogram cắt 0 + RSI (long / short).
Thoát mặc định: **chốt lời +10%**, **cắt lỗ −4%** (R:R ≈ 2,5), phí round-trip 0,1%.
  Đổi bằng `--tp-pct` / `--sl-pct`.

So sánh return strategy với **buy & hold** cùng kỳ.

Chạy:
  python -m botdown.run_backtest_macd_rsi
  python -m botdown.run_backtest_macd_rsi --interval 1h
  python -m botdown.run_backtest_macd_rsi --exit atr
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from botdown.data import load_btc_daily, load_btc_klines
from botdown.engine_macd_rsi_bt import MacdRsiParams, run_macd_rsi_backtest

WINDOWS = [
    ("Bear 2017–2018", "2017-12-11", "2018-08-06"),
    ("Bear 2021–2022", "2021-11-08", "2022-12-19"),
]


def main() -> None:
    ap = argparse.ArgumentParser(description="Backtest MACD+RSI BTC (1D hoặc 1h)")
    ap.add_argument(
        "--interval",
        choices=("1d", "1h"),
        default="1d",
        help="Khung nến dữ liệu spot (mặc định 1d — kết quả JSON trước đây là 1D)",
    )
    ap.add_argument(
        "--exit",
        choices=("pct", "atr"),
        default="pct",
        help="pct: TP/SL %% ; atr: theo ATR",
    )
    ap.add_argument("--tp-pct", type=float, default=0.10, help="Take profit (decimal), long +%%")
    ap.add_argument("--sl-pct", type=float, default=0.04, help="Stop loss (decimal), long -%%")
    ap.add_argument(
        "--ema-trend",
        action="store_true",
        help="Lọc: long chỉ khi bull (EMA fast>slow & close>EMA slow), short khi bear",
    )
    ap.add_argument("--ema-fast", type=int, default=20, help="EMA nhanh (xu hướng)")
    ap.add_argument("--ema-slow", type=int, default=50, help="EMA chậm (vd. 50)")
    args = ap.parse_args()

    if args.interval == "1d":
        data = load_btc_daily(ROOT, "spot")
        path_hint = "BTCUSDT-1d.csv"
    else:
        data = load_btc_klines(ROOT, "1h", "spot")
        path_hint = "BTCUSDT-1h.csv"
    if data is None:
        print(f"Không đọc được data/spot/klines/BTCUSDT/{path_hint}", file=sys.stderr)
        sys.exit(1)

    open_time, _, high, low, close, _ = data
    params = MacdRsiParams(
        exit_mode=args.exit,
        take_profit_pct=args.tp_pct,
        stop_loss_pct=args.sl_pct,
        use_ema_trend_filter=args.ema_trend,
        ema_trend_fast=args.ema_fast,
        ema_trend_slow=args.ema_slow,
    )

    rr = params.take_profit_pct / params.stop_loss_pct if params.stop_loss_pct > 0 else 0
    mode_label = (
        f"TP +{params.take_profit_pct*100:.1f}% / SL −{params.stop_loss_pct*100:.1f}% (R:R≈{rr:.2f})"
        if args.exit == "pct"
        else "ATR SL/TP"
    )
    trend_note = (
        f" | EMA trend: EMA{params.ema_trend_fast}/EMA{params.ema_trend_slow} + close vs EMA{params.ema_trend_slow}"
        if params.use_ema_trend_filter
        else ""
    )
    print(f"=== Backtest: MACD + RSI (BTC spot {args.interval}) | Thoát: {mode_label}{trend_note} ===\n")
    rows = []
    for label, start_d, end_d in WINDOWS:
        r = run_macd_rsi_backtest(
            open_time,
            high,
            low,
            close,
            start_date=start_d,
            end_date=end_d,
            params=params,
            allow_short=True,
        )
        if r is None:
            print(f"{label}: không đủ dữ liệu\n")
            continue
        rows.append(
            {
                "window": label,
                "start": start_d,
                "end": end_d,
                "strategy_return_pct": round(r.total_return_pct, 2),
                "buy_hold_return_pct": round(r.buy_hold_pct, 2),
                "strategy_vs_hold_pct": round(r.total_return_pct - r.buy_hold_pct, 2),
                "max_drawdown_pct": round(r.max_drawdown_pct, 2),
                "num_trades": r.num_trades,
                "win_rate": round(r.win_rate, 1),
                "sharpe_ratio": round(r.sharpe_ratio, 3),
                "profit_factor": round(r.profit_factor, 3),
                "trades": [
                    {
                        "entry_bar": t.entry_bar,
                        "exit_bar": t.exit_bar,
                        "side": t.side,
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
        print(
            f"  Strategy: {r.total_return_pct:+.2f}%  |  Buy & hold: {r.buy_hold_pct:+.2f}%  "
            f"|  Chênh lệch: {r.total_return_pct - r.buy_hold_pct:+.2f}%"
        )
        print(
            f"  Max DD: {r.max_drawdown_pct:.2f}%  |  Trades: {r.num_trades}  |  Win%: {r.win_rate:.1f}  "
            f"|  Sharpe~: {r.sharpe_ratio:.3f}  |  PF: {r.profit_factor:.3f}"
        )
        print()

    out_dir = ROOT / "botdown" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    suf = f"_{args.interval}" if args.interval != "1d" else ""
    out_name = (
        f"macd_rsi_backtest_btc{suf}.json"
        if args.exit == "pct"
        else f"macd_rsi_backtest_btc_atr{suf}.json"
    )
    out_path = out_dir / out_name
    payload = {
        "strategy": "macd_histogram_cross + rsi",
        "interval": args.interval,
        "exit_mode": params.exit_mode,
        "take_profit_pct": params.take_profit_pct,
        "stop_loss_pct": params.stop_loss_pct,
        "risk_reward_tp_sl": round(
            params.take_profit_pct / params.stop_loss_pct, 4
        )
        if params.stop_loss_pct > 0
        else None,
        "params": {
            "fast": params.fast_period,
            "slow": params.slow_period,
            "signal": params.signal_period,
            "rsi_period": params.rsi_period,
            "rsi_overbought": params.rsi_overbought,
            "rsi_oversold": params.rsi_oversold,
            "atr_period": params.atr_period,
            "atr_sl_mult": params.atr_sl_mult,
            "atr_tp_mult": params.atr_tp_mult,
            "fee_roundtrip": params.fee_roundtrip,
            "use_ema_trend_filter": params.use_ema_trend_filter,
            "ema_trend_fast": params.ema_trend_fast,
            "ema_trend_slow": params.ema_trend_slow,
        },
        "windows": rows,
        "note": (
            "Mặc định 10%/4% tối ưu trên **1D**; khung 1h cho nhiều tín hiệu hơn — thường cần TP/SL nhỏ hơn "
            "và phí round-trip đáng kể hơn. Chỉnh --tp-pct / --sl-pct / --interval."
        ),
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Đã ghi {out_path}")


if __name__ == "__main__":
    main()
