#!/usr/bin/env python3
"""
Compare MACD+RSI vs Regime+Fusion vs Buy-and-Hold across all configs.

MACD+RSI runs live (fast, O(n) precomputed indicators).
Regime+Fusion uses cached results from previous backtest report (O(n²) per-bar
signal computation is too slow for 1h data).

Run from project root: python -m botv2.run_compare
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from botv2.backtest.engine_macd_rsi import run_backtest_macd_rsi
from botv2.config import CACHE_DIR, SYMBOLS, TIMEFRAMES, BOTV2_ROOT
from botv2.indicators.export_signals import export_trades_to_csv, export_trades_to_json

REPORT_DIR = BOTV2_ROOT / "reports"

# Regime+Fusion results from previous backtest (see reports/backtest_summary.md)
REGIME_RESULTS = {
    "spot BTC/USDT 1h":    {"ret": 898.3,  "hold": 1454.3, "trades": 463, "wr": 19.7, "pf": 13.78, "sharpe": 0.71, "dd": 46.3},
    "spot BTC/USDT 1d":    {"ret": 1104.1, "hold": 1462.9, "trades": 75,  "wr": 38.7, "pf": 27.41, "sharpe": 1.80, "dd": 33.2},
    "spot ETH/USDT 1h":    {"ret": 460.9,  "hold": 551.3,  "trades": 703, "wr": 21.8, "pf": 7.51,  "sharpe": 0.56, "dd": 68.7},
    "spot ETH/USDT 1d":    {"ret": 653.9,  "hold": 550.5,  "trades": 136, "wr": 48.5, "pf": 12.12, "sharpe": 1.31, "dd": 38.2},
    "future BTC/USDT 1h":  {"ret": 1147.5, "hold": 833.4,  "trades": 40,  "wr": 32.5, "pf": 99.08, "sharpe": 2.54, "dd": 4.0},
    "future BTC/USDT 1d":  {"ret": 558.4,  "hold": 830.0,  "trades": 43,  "wr": 39.5, "pf": 24.27, "sharpe": 2.40, "dd": 15.2},
    "future ETH/USDT 1h":  {"ret": 1509.9, "hold": 1424.2, "trades": 91,  "wr": 22.0, "pf": 76.77, "sharpe": 1.67, "dd": 11.0},
    "future ETH/USDT 1d":  {"ret": 708.2,  "hold": 1403.2, "trades": 41,  "wr": 48.8, "pf": 21.54, "sharpe": 2.43, "dd": 33.6},
}


def _fmt(v: float) -> str:
    return f"{v:+.1f}%"


def main():
    configs = []
    for market in ("spot", "future"):
        for symbol in SYMBOLS:
            for tf in TIMEFRAMES:
                configs.append((market, symbol, tf))

    rows = []
    macd_results = []

    print("=" * 110)
    print("  botv2  Strategy Comparison: MACD+RSI  vs  Regime+Fusion  vs  Buy & Hold")
    print("=" * 110)
    print()

    for market_type, symbol, interval in configs:
        label = f"{market_type} {symbol} {interval}"
        print(f"  Running MACD+RSI backtest: {label} ... ", end="", flush=True)
        r_macd = run_backtest_macd_rsi(market_type, symbol, interval, cache_dir=CACHE_DIR)

        if r_macd is None:
            print("no data")
            continue
        print(f"{r_macd.num_trades} trades")

        rg = REGIME_RESULTS.get(label, {})
        hold_ret = rg.get("hold", r_macd.hold_return_pct)

        rows.append({
            "label": label,
            "hold": hold_ret,
            "regime_ret": rg.get("ret", 0),
            "regime_trades": rg.get("trades", 0),
            "regime_wr": rg.get("wr", 0),
            "regime_pf": rg.get("pf", 0),
            "regime_sharpe": rg.get("sharpe", 0),
            "regime_dd": rg.get("dd", 0),
            "macd_ret": r_macd.total_return_pct,
            "macd_trades": r_macd.num_trades,
            "macd_wr": r_macd.win_rate,
            "macd_pf": r_macd.profit_factor,
            "macd_sharpe": r_macd.sharpe_ratio,
            "macd_dd": r_macd.max_drawdown_pct,
            "macd_avg_win": r_macd.avg_win_pct,
            "macd_avg_loss": r_macd.avg_loss_pct,
        })
        macd_results.append((label, r_macd))

    if not rows:
        print("No data found. Run python -m botv2.run_data first.")
        return

    # ── Detailed comparison table ──
    print()
    print("─" * 110)
    hdr = (
        f"{'Config':<28} {'Hold':>10} {'Regime':>10} {'MACD+RSI':>10} │ "
        f"{'#Tr(R)':>6} {'WR(R)':>6} {'PF(R)':>7} {'Sh(R)':>6} {'DD(R)':>6} │ "
        f"{'#Tr(M)':>6} {'WR(M)':>6} {'PF(M)':>7} {'Sh(M)':>6} {'DD(M)':>6}"
    )
    print(hdr)
    print("─" * 110)
    for r in rows:
        line = (
            f"{r['label']:<28} "
            f"{_fmt(r['hold']):>10} "
            f"{_fmt(r['regime_ret']):>10} "
            f"{_fmt(r['macd_ret']):>10} │ "
            f"{r['regime_trades']:>6} "
            f"{r['regime_wr']:>5.1f}% "
            f"{r['regime_pf']:>7.2f} "
            f"{r['regime_sharpe']:>6.2f} "
            f"{r['regime_dd']:>5.1f}% │ "
            f"{r['macd_trades']:>6} "
            f"{r['macd_wr']:>5.1f}% "
            f"{r['macd_pf']:>7.2f} "
            f"{r['macd_sharpe']:>6.2f} "
            f"{r['macd_dd']:>5.1f}%"
        )
        print(line)
    print("─" * 110)

    # ── Winner per config ──
    print()
    print("Winner per config (by total return):")
    for r in rows:
        strats = {"Buy & Hold": r["hold"], "Regime+Fusion": r["regime_ret"], "MACD+RSI": r["macd_ret"]}
        winner = max(strats, key=strats.get)
        print(f"  {r['label']:<28} → {winner} ({_fmt(strats[winner])})")

    print()
    print("Risk-adjusted winner per config (by Sharpe ratio):")
    for r in rows:
        strats = {"Regime+Fusion": r["regime_sharpe"], "MACD+RSI": r["macd_sharpe"]}
        winner = max(strats, key=strats.get)
        print(f"  {r['label']:<28} → {winner} (Sharpe {strats[winner]:.2f})")

    # ── MACD+RSI detailed stats ──
    print()
    print("MACD+RSI detailed stats:")
    for r in rows:
        print(
            f"  {r['label']:<28} "
            f"Return {r['macd_ret']:+.1f}%  "
            f"Trades {r['macd_trades']}  "
            f"Win {r['macd_wr']:.1f}%  "
            f"PF {r['macd_pf']:.2f}  "
            f"Sharpe {r['macd_sharpe']:.2f}  "
            f"MaxDD {r['macd_dd']:.1f}%  "
            f"AvgWin {r['macd_avg_win']:+.1f}%  "
            f"AvgLoss {r['macd_avg_loss']:.1f}%"
        )

    # ── Export MACD+RSI indicators ──
    ind_dir = REPORT_DIR / "indicators_macd_rsi"
    ind_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nExporting MACD+RSI signals to {ind_dir}")
    for label, res in macd_results:
        safe = label.replace(" ", "_").replace("/", "_")
        export_trades_to_csv(res, str(ind_dir / f"{safe}.csv"))
        export_trades_to_json(res, str(ind_dir / f"{safe}.json"))

    # ── Generate markdown report ──
    _write_report(rows)
    print(f"\nReport saved to {REPORT_DIR / 'strategy_comparison.md'}")
    print("Done.")


def _write_report(rows):
    report_path = REPORT_DIR / "strategy_comparison.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Strategy Comparison: MACD+RSI vs Regime+Fusion vs Buy & Hold",
        "",
        "## Tham số",
        "",
        "| Strategy | Mô tả |",
        "|----------|-------|",
        "| **MACD+RSI** | MACD(12,26,9) + RSI(14), OB=70 / OS=30. SL = 1.5×ATR(14), TP = 2.5×ATR(14) |",
        "| **Regime+Fusion** | Regime (MA20/50 + volatility) + Order Blocks + FVG + Supply/Demand |",
        "| **Buy & Hold** | Mua tại bar đầu, giữ đến bar cuối |",
        "",
        "## Kết quả tổng hợp",
        "",
        "| Config | Hold | Regime+Fusion | MACD+RSI | #Tr (R) | WR (R) | PF (R) | Sharpe (R) | DD (R) | #Tr (M) | WR (M) | PF (M) | Sharpe (M) | DD (M) |",
        "|--------|------|---------------|----------|---------|--------|--------|------------|--------|---------|--------|--------|------------|--------|",
    ]
    for r in rows:
        lines.append(
            f"| {r['label']} "
            f"| {r['hold']:+.1f}% "
            f"| {r['regime_ret']:+.1f}% "
            f"| {r['macd_ret']:+.1f}% "
            f"| {r['regime_trades']} "
            f"| {r['regime_wr']:.1f}% "
            f"| {r['regime_pf']:.2f} "
            f"| {r['regime_sharpe']:.2f} "
            f"| {r['regime_dd']:.1f}% "
            f"| {r['macd_trades']} "
            f"| {r['macd_wr']:.1f}% "
            f"| {r['macd_pf']:.2f} "
            f"| {r['macd_sharpe']:.2f} "
            f"| {r['macd_dd']:.1f}% |"
        )

    lines += [
        "",
        "## Winner (theo tổng lợi nhuận)",
        "",
    ]
    for r in rows:
        strats = {"Buy & Hold": r["hold"], "Regime+Fusion": r["regime_ret"], "MACD+RSI": r["macd_ret"]}
        winner = max(strats, key=strats.get)
        lines.append(f"- **{r['label']}**: {winner} ({strats[winner]:+.1f}%)")

    lines += [
        "",
        "## Winner (theo Sharpe – risk-adjusted)",
        "",
    ]
    for r in rows:
        strats = {"Regime+Fusion": r["regime_sharpe"], "MACD+RSI": r["macd_sharpe"]}
        winner = max(strats, key=strats.get)
        lines.append(f"- **{r['label']}**: {winner} (Sharpe {strats[winner]:.2f})")

    lines += [
        "",
        "## Nhận xét",
        "",
        "### MACD+RSI",
        "- Đơn giản, dễ tái tạo, phù hợp làm baseline.",
        "- Momentum-following: hoạt động tốt khi thị trường trending rõ ràng.",
        "- Sinh nhiều false signal trong giai đoạn sideways / choppy.",
        "- ATR-based SL/TP tự động điều chỉnh theo volatility.",
        "",
        "### Regime+Fusion",
        "- Phức tạp hơn, thích nghi theo market regime (bull/bear/ranging).",
        "- Profit Factor cao (ít loss lớn), nhưng Win Rate thấp hơn trên 1h.",
        "- Phù hợp futures (có short) hơn spot.",
        "",
        "### Kết luận",
        "- Cả hai strategy đều cần kết hợp với risk management chặt chẽ.",
        "- **Hold portfolio (DCA)** vẫn là lựa chọn an toàn cho phần vốn dài hạn.",
        "- **Trading portfolio**: chọn strategy phù hợp dựa trên Sharpe và Max DD, không chỉ total return.",
        "",
        "## Files",
        "",
        "- Regime+Fusion indicators: `reports/indicators/`",
        "- MACD+RSI indicators: `reports/indicators_macd_rsi/`",
        "",
    ]

    with open(report_path, "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
