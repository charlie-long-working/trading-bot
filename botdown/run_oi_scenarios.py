#!/usr/bin/env python3
"""
Crawl OI + USDT.D + nến 2022→nay, xếp kịch bản theo **win rate** (không tối ưu ROI).

  cd Trading-bot
  PYTHONPATH=. python3 -m botdown.run_oi_scenarios --refresh
  PYTHONPATH=. python3 -m botdown.run_oi_scenarios --interval 1h,4h
  PYTHONPATH=. python3 -m botdown.run_oi_scenarios --interval 1d --refresh
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

import pandas as pd

from data_loaders.oi_history import REPORT_SUFFIX, build_oi_panel, save_panel_reports
from botdown.oi_liq_strategy import (
    TF_DEFAULTS,
    current_scenario_state,
    min_trades_for,
    rank_key_winrate,
    run_all_scenarios,
    signal_oi_usdtd_confluence,
    _simulate,
)


def _span_label(panel: "pd.DataFrame") -> Tuple[str, str]:
    a = pd.Timestamp(panel["date"].min())
    b = pd.Timestamp(panel["date"].max())
    def fmt(t):
        return str(t.date()) if t.hour == 0 and t.minute == 0 else t.strftime("%Y-%m-%d %H:%M")
    return fmt(a), fmt(b)


def _report_stem(symbol: str, interval: str) -> str:
    if interval == "1d":
        return f"oi_scenarios_{symbol.lower()}"
    return f"oi_scenarios_{symbol.lower()}_{interval}"


def run_interval(
    symbol: str,
    interval: str,
    start: str,
    refresh: bool,
    tp: float,
    sl: float,
    max_hold: int,
) -> Dict[str, Any]:
    print(f"\n======== {symbol} {interval} ========")
    print(f"Fetching OI + USDT.D + klines {symbol} {interval} from {start}...")
    panel = build_oi_panel(symbol, start=start, force_refresh=refresh, interval=interval)
    panel_path = save_panel_reports(panel, symbol, interval=interval)
    has_usdtd = "usdt_d" in panel.columns and panel["usdt_d"].notna().sum() > 0
    span0, span1 = _span_label(panel)
    print(
        f"Panel rows={len(panel)}  {span0} → {span1}  "
        f"USDT.D={'yes' if has_usdtd else 'NO'}"
    )
    if has_usdtd:
        src = "?"
        if "usdt_d_source" in panel.columns:
            src = str(panel["usdt_d_source"].iloc[-1])
        print(f"  USDT.D last={panel['usdt_d'].iloc[-1]:.3f}%  source={src}")
    print(f"Wrote {panel_path}")

    results, books, feat = run_all_scenarios(
        panel, tp=tp, sl=sl, max_hold=max_hold, interval=interval
    )
    cfg = TF_DEFAULTS.get(interval, TF_DEFAULTS["1d"])
    bpd = int(cfg["bars_per_day"])
    min_n = min_trades_for(interval)

    year_rows = []
    k_sig = signal_oi_usdtd_confluence(feat)
    feat2 = feat.copy()
    feat2["sig"] = k_sig.values
    for y in sorted(feat2["date"].dt.year.unique()):
        sub = feat2[feat2["date"].dt.year == y].reset_index(drop=True)
        min_bars = 40 * bpd
        if len(sub) < min_bars:
            continue
        _, m = _simulate(
            sub, sub["sig"], tp=tp, sl=sl, max_hold=max_hold, interval=interval, bars_per_day=bpd
        )
        year_rows.append({"year": int(y), **m})

    liq = None
    try:
        from data_loaders.liquidation_map import fetch_liquidation_map
        snap = fetch_liquidation_map(symbol)
        liq = snap.summary()
    except Exception as e:
        liq = {"error": str(e)}

    play = current_scenario_state(feat, liq)

    reports = ROOT / "botdown" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    stem = _report_stem(symbol, interval)

    summary = {
        "symbol": symbol,
        "interval": interval,
        "bars_per_day": bpd,
        "rank_metric": "win_rate",
        "min_trades_rank": min_n,
        "start": start,
        "panel_rows": len(panel),
        "panel_span": [span0, span1],
        "params": {"tp": tp, "sl": sl, "max_hold": max_hold, "interval": interval},
        "scenarios": [r.as_dict() for r in results],
        "k_confluence_by_year": year_rows,
        "playbook_now": play,
        "liquidation_map": {
            k: liq.get(k)
            for k in (
                "mark", "vote_side", "vote_reason", "nearby_long_usd", "nearby_short_usd",
                "nearest_long_cluster", "nearest_short_cluster", "source", "error",
            )
        } if liq else None,
    }
    out_json = reports / f"{stem}.json"
    out_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    best = max(results, key=rank_key_winrate)
    tf_tag = "" if interval == "1d" else f"_{interval}"
    trades_path = reports / f"oi_scenario_trades_{best.name}_{symbol.lower()}{tf_tag}.csv"
    pd.DataFrame(books.get(best.name) or []).to_csv(trades_path, index=False)
    k_trades_path = reports / f"oi_scenario_trades_K_oi_usdtd_confluence_{symbol.lower()}{tf_tag}.csv"
    if best.name != "K_oi_usdtd_confluence":
        pd.DataFrame(books.get("K_oi_usdtd_confluence") or []).to_csv(k_trades_path, index=False)

    hold_note = f"{max_hold}d" if interval == "1d" else f"{max_hold} bars (~{max_hold / bpd:.1f}d)"
    md_path = reports / f"{stem}.md"
    lines = [
        f"# OI + USDT.D Scenarios — {symbol} **{interval}**",
        "",
        f"Window: **{span0} → {span1}** ({len(panel)} nến {interval}).",
        "Nguồn: Bybit OI · Binance funding/giá · **USDT.D** (DefiLlama USDT mcap / CMC total, proxy hiệu chỉnh trước ~2025-04).",
        "Lookback OI/USDT.D/funding theo **lịch** (3 ngày / 30 ngày); EMA 20/50 trên nến khung.",
        f"Xếp hạng theo **win rate** (min {min_n} trades). Profit = compound 100% notional/trade, vốn gốc $1,000.",
        f"Exit: TP {tp*100:.1f}% / SL {sl*100:.1f}% → **R:R kế hoạch {tp/sl:.2f}:1** / max hold {hold_note}. Fee RT 0.04%.",
        "",
        "## Bảng kịch bản (sort win rate ↓)",
        "",
        "| # | Scenario | n | **Win%** | R:R kế hoạch | R:R thực | Exp R | Profit $1k | CAGR | MaxDD | PF |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for i, r in enumerate(results, 1):
        flag = "" if r.n_trades >= min_n else " *"
        lines.append(
            f"| {i} | `{r.name}`{flag} | {r.n_trades} | **{r.win_rate:.1f}** | "
            f"{r.planned_rr:.2f} | {r.realized_rr:.2f} | {r.expectancy_r:+.2f} | "
            f"**${r.profit_usd_1k:+,.0f}** | {r.cagr_pct:+.1f}% | {r.max_dd_pct:.1f}% | {r.profit_factor:.2f} |"
        )
    lines.extend([
        "",
        "\\* n thấp hơn ngưỡng rank. R:R thực = avg win / |avg loss| (gồm time/flip, nên khác kế hoạch). "
        "Profit compound trên $1,000, 1 position, không lev. BE WR ≈ 1/(1+R:R thực).",
        "",
        "## `K_oi_usdtd_confluence` theo năm",
        "",
        "| Year | n | Win% | R:R thực | Exp R | Profit $1k |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for yr in year_rows:
        lines.append(
            f"| {yr['year']} | {yr['n_trades']} | **{yr['win_rate']:.1f}** | "
            f"{yr.get('realized_rr', 0):.2f} | {yr.get('expectancy_r', 0):+.2f} | "
            f"${yr.get('profit_usd_1k', 0):+,.0f} |"
        )
    lines.extend([
        "",
        "## Playbook hiện tại",
        "",
        f"- Time / close: **{play['date']}** / `{play['close']}`",
        f"- OI Δ3d: {play['oi_chg_3_pct']}% | z30: {play['oi_z_30']} | fund z: {play['funding_z_30']}",
        f"- **USDT.D:** `{play.get('usdt_d')}`% (Δ3d {play.get('usdt_d_chg_3')}, z {play.get('usdt_d_z_30')}) "
        f"| risk-off={play.get('usdtd_risk_off')} risk-on={play.get('usdtd_risk_on')}",
        f"- EMA regime ({interval}): **{play['regime_ema']}**",
    ])
    rec = play.get("recommended") or {}
    lines.extend([
        "",
        f"**Khuyến nghị:** `{rec.get('side', 'none').upper()}` "
        f"(conf={rec.get('confidence')}) — {rec.get('thesis')}",
    ])
    if rec.get("entry"):
        lines.append(f"- Entry ~ `{rec.get('entry')}` | SL `{rec.get('stop')}` | TP `{rec.get('target')}`")
    if play.get("liq_vote"):
        lines.extend([
            "",
            "### Liquidation map",
            f"- Vote: **{play.get('liq_vote')}** ({play.get('liq_reason')})",
            f"- Long cluster: `{play.get('liq_long_cluster')}` | Short: `{play.get('liq_short_cluster')}`",
        ])
    lines.extend([
        "",
        "## Logic `K_oi_usdtd_confluence`",
        "",
        "1. **SHORT:** EMA bear + OI↑3d >2% + **USDT.D** Δ3d>+0.2 (hoặc z>1) + fund z>0.3",
        "2. **LONG:** EMA bull + OI↑3d >1.5% + **USDT.D** Δ3d<−0.2 (hoặc z<−1) + fund z<−0.5",
        "3. USDT.D ↑ = tiền trú ẩn stable → áp lực BTC; USDT.D ↓ = risk-on.",
        "4. USDT.D daily được ffill lên nến H1/H4 (bước ngày, không nội suy trong ngày).",
        "",
        f"Best by win rate: `{best.name}` — WR **{best.win_rate:.1f}%** · R:R thực **{best.realized_rr:.2f}:1** "
        f"(kế hoạch {best.planned_rr:.2f}) · profit **${best.profit_usd_1k:+,.0f}** / $1k "
        f"(+{best.return_pct:.1f}%, CAGR {best.cagr_pct:+.1f}%) · n={best.n_trades} → `{trades_path.name}`",
        "",
        f"Panel: `{panel_path.name}` · klines: `klines_{symbol.lower()}_{REPORT_SUFFIX[interval]}.csv`",
        "",
        "*Không phải tư vấn đầu tư.*",
    ])
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"\n=== {interval} leaderboard by WIN RATE (min n={min_n}) ===")
    print(
        f"{'#':>2} {'name':24} {'n':>4} {'WR%':>6} {'RR pln':>7} {'RR real':>8} "
        f"{'expR':>7} {'P$1k':>10}  CAGR"
    )
    for i, r in enumerate(results, 1):
        mark = "★" if r.name == best.name else " "
        print(
            f"{i:2d}{mark} {r.name:24} {r.n_trades:4d} {r.win_rate:6.1f} "
            f"{r.planned_rr:7.2f} {r.realized_rr:8.2f} {r.expectancy_r:7.2f} "
            f"{r.profit_usd_1k:10.0f}  {r.cagr_pct:+.1f}%"
        )
    print(f"\n>>> NOW [{interval}]: {rec.get('side', 'none').upper()} ({rec.get('confidence')})")
    print(f"    USDT.D={play.get('usdt_d')}  {rec.get('thesis')}")
    print(
        f"    BEST {best.name}: WR {best.win_rate:.1f}%  RR {best.realized_rr:.2f}  "
        f"profit ${best.profit_usd_1k:+,.0f} on $1k"
    )
    print(f"Wrote {out_json}")
    print(f"Wrote {md_path}")
    print(f"Wrote {trades_path}")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description="OI + USDT.D scenarios on 1d/4h/1h (rank by win rate)")
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--start", default="2022-01-01")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument(
        "--interval",
        default="1d",
        help="1d, 4h, 1h — comma-separated to run several (e.g. 1h,4h)",
    )
    ap.add_argument("--tp", type=float, default=None, help="override TP (default depends on interval)")
    ap.add_argument("--sl", type=float, default=None, help="override SL")
    ap.add_argument("--max-hold", type=int, default=None, help="override max hold bars")
    args = ap.parse_args()

    intervals = [x.strip() for x in args.interval.split(",") if x.strip()]
    unknown = [i for i in intervals if i not in TF_DEFAULTS]
    if unknown:
        print(f"Unknown interval {unknown}; use {list(TF_DEFAULTS)}", file=sys.stderr)
        return 2

    for iv in intervals:
        cfg = TF_DEFAULTS[iv]
        tp = args.tp if args.tp is not None else cfg["tp"]
        sl = args.sl if args.sl is not None else cfg["sl"]
        max_hold = args.max_hold if args.max_hold is not None else cfg["max_hold"]
        run_interval(args.symbol, iv, args.start, args.refresh, tp, sl, max_hold)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
