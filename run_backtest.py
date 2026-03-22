#!/usr/bin/env python3
"""
Run backtest for all data from 2017 to latest (plan: through 2026 when available).

Uses merged klines: spot + um, BTCUSDT + ETHUSDT, 1d + 1h.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtest import run_backtest


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest regime + fusion trên klines")
    parser.add_argument("--data-dir", type=str, default="data", help="Thư mục data")
    parser.add_argument("--no-onchain", action="store_true", help="Không dùng SOPR/MVRV (chỉ giá + volume)")
    parser.add_argument("--lookback", type=int, default=100, help="Số nến warmup")
    parser.add_argument("--symbol", type=str, default=None, help="Chỉ chạy 1 symbol, vd BTCUSDT")
    parser.add_argument("--interval", type=str, default=None, help="Chỉ chạy 1 khung, vd 1h hoặc 1d")
    parser.add_argument("--capital", type=float, default=None, help="Giả sử vốn (vd 1000) để in số dư cuối")
    parser.add_argument("--start", type=str, default=None, help="Ngày bắt đầu backtest YYYY-MM-DD (vd 2024-01-01)")
    parser.add_argument("--end", type=str, default=None, help="Ngày kết thúc backtest YYYY-MM-DD (mặc định: hết data)")
    parser.add_argument("--bull-hold", type=float, default=0.0, metavar="PCT", help="Khi bull và không có lệnh, tính PCT%% lợi nhuận theo giá (vd 0.5 = 50%%, để gần hold hơn)")
    args = parser.parse_args()

    data_dir = args.data_dir
    use_onchain = not args.no_onchain
    configs = [
        ("spot", "BTCUSDT", "1d"),
        ("spot", "BTCUSDT", "1h"),
        ("spot", "ETHUSDT", "1d"),
        ("spot", "ETHUSDT", "1h"),
        ("um", "BTCUSDT", "1d"),
        ("um", "BTCUSDT", "1h"),
        ("um", "ETHUSDT", "1d"),
        ("um", "ETHUSDT", "1h"),
    ]
    if args.symbol:
        configs = [(m, s, i) for m, s, i in configs if s == args.symbol]
    if args.interval:
        configs = [(m, s, i) for m, s, i in configs if i == args.interval]
    if not configs:
        print("Không có cấu hình nào thỏa --symbol/--interval")
        return

    date_range = ""
    if args.start or args.end:
        date_range = f" | Khoảng: {args.start or 'đầu data'} → {args.end or 'cuối data'}"
    bull_hold_note = f" | Bull-hold: {args.bull_hold*100:.0f}%" if args.bull_hold and args.bull_hold > 0 else ""
    print("Backtest (regime + OB/FVG/supply-demand + volume)")
    print(f"  Data: {data_dir} | On-chain: {'Có' if use_onchain else 'Không'} | Lookback: {args.lookback}{date_range}{bull_hold_note}\n")

    results = []
    for market_type, symbol, interval in configs:
        r = run_backtest(
            data_dir, market_type, symbol, interval,
            lookback=args.lookback,
            use_onchain=use_onchain,
            start_date=args.start,
            end_date=args.end,
            bull_flat_hold_pct=max(0.0, min(1.0, args.bull_hold)),
        )
        if r is None:
            print(f"  {market_type} {symbol} {interval}: không có dữ liệu")
            continue
        results.append((f"{market_type} {symbol} {interval}", r))
        vs_hold = r.total_return_pct - r.hold_return_pct
        line = (
            f"  {market_type} {symbol} {interval}: {r.num_trades} lệnh | "
            f"Strategy {r.total_return_pct:+.1f}% | Hold {r.hold_return_pct:+.1f}% | "
            f"Vs hold {vs_hold:+.1f}% | Max DD {r.max_drawdown_pct:.1f}% | "
            f"Win {r.win_rate:.1f}% | PF {r.profit_factor:.2f} | Sharpe {r.sharpe_ratio:.2f}"
        )
        if r.num_trades:
            line += f" | Avg win {r.avg_win_pct:+.1f}% | Avg loss {r.avg_loss_pct:.1f}%"
        print(line)

    if results:
        print("\n--- Strategy vs Hold (cùng kỳ) ---")
        for label, r in results:
            vs = r.total_return_pct - r.hold_return_pct
            print(f"  {label}: Strategy {r.total_return_pct:+.1f}% | Hold {r.hold_return_pct:+.1f}% | Vs hold {vs:+.1f}% | Max DD {r.max_drawdown_pct:.1f}%")
        cap = args.capital
        if cap is not None and cap > 0:
            print("\n--- Vốn giả định ${:,.0f} (cùng cách compound như backtest) ---".format(cap))
            for label, r in results:
                end = cap * (1 + r.total_return_pct / 100)
                print(f"  {label}: Số dư cuối ≈ ${end:,.0f}")
            print("\n  Sizing theo volatility (risk % mỗi lệnh): xem docs/POSITION_SIZING.md")
    print("\nXong.")


if __name__ == "__main__":
    main()
