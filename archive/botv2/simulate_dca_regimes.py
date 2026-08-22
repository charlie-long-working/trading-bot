#!/usr/bin/env python3
"""
Test DCA bot configs on different market regimes to find
the best setup for March 2026 → March 2027.

Regimes tested:
  - Bull run  (2020-10 → 2021-04): $10K → $64K
  - Crash     (2021-11 → 2022-06): $69K → $17K
  - Bear      (2022-06 → 2022-12): $17K → $16K (sideways bottom)
  - Recovery  (2023-01 → 2024-03): $16K → $73K
  - Recent    (2024-03 → 2026-03): $73K → $73K (volatile sideways/up)

Run: python -m botv2.simulate_dca_regimes
"""

import sys
import time as _time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from botv2.config import BOTV2_ROOT
from botv2.simulate_dca_bot import (
    Cfg, simulate_fast, load_btc, resample_15m_to_4h, _ts_to_str,
    REPORT_DIR,
)

# ── Market regimes (timestamps in ms) ────────────────────────────────────────

def _date_ms(y, m, d):
    return int(datetime(y, m, d, tzinfo=timezone.utc).timestamp() * 1000)

REGIMES = {
    "Bull 2020-2021":    (_date_ms(2020, 10, 1),  _date_ms(2021, 4, 15)),
    "Crash 2021":        (_date_ms(2021, 11, 1),  _date_ms(2022, 6, 30)),
    "Bear bottom 2022":  (_date_ms(2022, 6, 1),   _date_ms(2022, 12, 31)),
    "Recovery 2023-24":  (_date_ms(2023, 1, 1),   _date_ms(2024, 3, 15)),
    "Recent 2024-26":    (_date_ms(2024, 3, 1),   _date_ms(2026, 3, 16)),
}


def slice_data(ot, hi, lo, cl, start_ms, end_ms):
    mask = (ot >= start_ms) & (ot <= end_ms)
    return ot[mask], hi[mask], lo[mask], cl[mask]


# ── Candidate configs ────────────────────────────────────────────────────────

def make_candidates(capital):
    """Hand-crafted + grid candidates optimized for different regimes."""
    cfgs = {}

    # Screenshot original
    cfgs["Screenshot (10x, 0.75%, TP1.5%)"] = Cfg(
        lev=10, ps=0.75, tp=1.5, init_m=28, so_m=11, max_so=13, ss=1.1)

    # Conservative: low leverage, wide steps
    cfgs["Conservative (3x, 2%, TP2%)"] = Cfg(
        lev=3, ps=2.0, tp=2.0, init_m=int(capital*0.05), so_m=int(capital*0.02),
        max_so=10, ss=1.2)

    # Moderate
    cfgs["Moderate (5x, 1.5%, TP1.5%)"] = Cfg(
        lev=5, ps=1.5, tp=1.5, init_m=int(capital*0.04), so_m=int(capital*0.02),
        max_so=10, ss=1.1)

    # Aggressive sideway
    cfgs["Aggressive SW (8x, 0.75%, TP1%)"] = Cfg(
        lev=8, ps=0.75, tp=1.0, init_m=int(capital*0.06), so_m=int(capital*0.02),
        max_so=8, ss=1.1)

    # Wide grid (crash-resistant)
    cfgs["Wide Grid (3x, 3%, TP3%)"] = Cfg(
        lev=3, ps=3.0, tp=3.0, init_m=int(capital*0.06), so_m=int(capital*0.03),
        max_so=8, ss=1.3)

    # Scalper (fast TP, few SOs)
    cfgs["Scalper (5x, 1%, TP0.8%)"] = Cfg(
        lev=5, ps=1.0, tp=0.8, init_m=int(capital*0.03), so_m=int(capital*0.015),
        max_so=6, ss=1.0)

    # Balanced for $300
    if capital <= 350:
        cfgs["Balanced 300 (5x, 1.5%, TP1.5%)"] = Cfg(
            lev=5, ps=1.5, tp=1.5, init_m=10, so_m=5, max_so=10, ss=1.15)
        cfgs["Safe 300 (3x, 2.5%, TP2%)"] = Cfg(
            lev=3, ps=2.5, tp=2.0, init_m=8, so_m=4, max_so=10, ss=1.2)

    # Balanced for $500
    if capital >= 450:
        cfgs["Balanced 500 (5x, 1.5%, TP1.5%)"] = Cfg(
            lev=5, ps=1.5, tp=1.5, init_m=15, so_m=8, max_so=13, ss=1.15)
        cfgs["Safe 500 (3x, 2.5%, TP2%)"] = Cfg(
            lev=3, ps=2.5, tp=2.0, init_m=15, so_m=8, max_so=13, ss=1.2)

    # Filter: total margin must fit in capital
    valid = {}
    for name, c in cfgs.items():
        if c.total_margin <= capital * 0.95 and c.init_m >= 1 and c.so_m >= 1:
            valid[name] = c
    return valid


# ── Run analysis ─────────────────────────────────────────────────────────────

def run_regime_analysis(capital, ot, hi, lo, cl, tf_hours, tf_label):
    """Run all candidates on all regimes."""
    candidates = make_candidates(capital)
    results = {}  # {config_name: {regime_name: result}}

    for cname, cfg in candidates.items():
        results[cname] = {"cfg": cfg}
        for rname, (start_ms, end_ms) in REGIMES.items():
            rot, rhi, rlo, rcl = slice_data(ot, hi, lo, cl, start_ms, end_ms)
            if len(rcl) < 50:
                results[cname][rname] = None
                continue
            r = simulate_fast(cfg, capital, rhi, rlo, rcl, tf_hours)
            results[cname][rname] = r

    return results, candidates


def score_for_2026(results):
    """
    Score configs based on how well they'd do in 2026-2027.
    Weight recent performance highest, penalize crash losses heavily.
    """
    weights = {
        "Recent 2024-26": 3.0,
        "Recovery 2023-24": 2.0,
        "Bear bottom 2022": 1.5,
        "Crash 2021": 2.0,
        "Bull 2020-2021": 1.0,
    }

    scores = {}
    for cname, data in results.items():
        if "cfg" not in data:
            continue
        total_score = 0
        valid_regimes = 0

        for rname, w in weights.items():
            r = data.get(rname)
            if r is None:
                continue
            regime_score = (
                r["ret_pct"] * 0.4
                - r["n_liq"] * 30
                - r["max_dd"] * 0.3
                + (r["win_rate"] - 80) * 0.2
            )
            total_score += regime_score * w
            valid_regimes += 1

        if valid_regimes > 0:
            scores[cname] = total_score / valid_regimes
    return scores


# ── Report ───────────────────────────────────────────────────────────────────

def write_regime_report(results_300, results_500, scores_300, scores_500,
                        candidates_300, candidates_500, tf_label):
    md = []
    md.append("# DCA Bot — Phân tích theo giai đoạn thị trường")
    md.append("")
    md.append(f"Mục tiêu: Tìm config tốt nhất cho **03/2026 → 03/2027** | TF: {tf_label}")
    md.append("")

    # Regime descriptions
    md.append("## Các giai đoạn thị trường đã test")
    md.append("")
    md.append("| Giai đoạn | Thời gian | BTC | Đặc điểm |")
    md.append("|-----------|-----------|-----|----------|")
    md.append("| Bull run | 10/2020 → 04/2021 | $10K → $64K | Tăng mạnh, ít pullback sâu |")
    md.append("| Crash | 11/2021 → 06/2022 | $69K → $17K | Giảm -75%, bear market |")
    md.append("| Bear bottom | 06/2022 → 12/2022 | $17K → $16K | Sideway đáy, accumulation |")
    md.append("| Recovery | 01/2023 → 03/2024 | $16K → $73K | Hồi phục mạnh |")
    md.append("| Recent | 03/2024 → 03/2026 | $60K → $73K | Volatile sideway/up |")
    md.append("")

    for cap_label, results, scores, candidates in [
        ("$300", results_300, scores_300, candidates_300),
        ("$500", results_500, scores_500, candidates_500),
    ]:
        md.append(f"## Kết quả với vốn {cap_label}")
        md.append("")

        # Main comparison table
        regime_names = list(REGIMES.keys())
        header = "| Config | " + " | ".join(regime_names) + " | Score |"
        sep = "|--------|" + "|".join(["-----" for _ in regime_names]) + "|-------|"
        md.append(header)
        md.append(sep)

        sorted_configs = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        for cname in sorted_configs:
            data = results[cname]
            cells = []
            for rn in regime_names:
                r = data.get(rn)
                if r is None:
                    cells.append("N/A")
                else:
                    liq_mark = f" ⚠{r['n_liq']}" if r['n_liq'] > 0 else ""
                    cells.append(f"{r['ret_pct']:+.0f}%{liq_mark}")
            score = scores.get(cname, 0)
            md.append(f"| {cname} | " + " | ".join(cells) + f" | {score:.0f} |")
        md.append("")

        # Detail tables for each regime
        md.append(f"### Chi tiết từng giai đoạn ({cap_label})")
        md.append("")
        for rname in regime_names:
            md.append(f"**{rname}:**")
            md.append("")
            md.append("| Config | Final | Return | Cycles | TP | Liq | WR | DD | Avg PnL/TP |")
            md.append("|--------|-------|--------|--------|----|-----|----|----|------------|")
            for cname in sorted_configs:
                r = results[cname].get(rname)
                if r is None:
                    continue
                cap = int(cap_label.replace("$", ""))
                md.append(
                    f"| {cname} | ${r['final']:,.0f} | {r['ret_pct']:+.1f}% | "
                    f"{r['n_cycles']} | {r['n_tp']} | {r['n_liq']} | "
                    f"{r['win_rate']:.0f}% | {r['max_dd']:.1f}% | ${r['avg_pnl_tp']:.2f} |"
                )
            md.append("")

        # Top recommendation
        if sorted_configs:
            top = sorted_configs[0]
            cfg = candidates[top]
            md.append(f"### Khuyến nghị #{1} cho {cap_label}: **{top}**")
            md.append("")
            md.append("| Parameter | Value |")
            md.append("|-----------|-------|")
            md.append(f"| Leverage | {cfg.lev}x |")
            md.append(f"| Price step | {cfg.ps}% |")
            md.append(f"| Take profit | {cfg.tp}% |")
            md.append(f"| Initial margin | ${cfg.init_m} |")
            md.append(f"| SO margin | ${cfg.so_m} |")
            md.append(f"| Max SOs | {cfg.max_so} |")
            md.append(f"| Step scale | {cfg.ss}x |")
            md.append(f"| Total margin | ${cfg.total_margin:.0f} ({cfg.total_margin/int(cap_label.replace('$',''))*100:.0f}% vốn) |")
            md.append("")

            # Show results for each regime
            data = results[top]
            recent = data.get("Recent 2024-26")
            crash = data.get("Crash 2021")
            if recent:
                md.append(f"- **Giai đoạn gần nhất (2024-26):** {recent['ret_pct']:+.1f}%, "
                          f"{recent['n_liq']} liq, DD {recent['max_dd']:.1f}%")
            if crash:
                md.append(f"- **Crash test (2021-22):** {crash['ret_pct']:+.1f}%, "
                          f"{crash['n_liq']} liq, DD {crash['max_dd']:.1f}%")
            md.append("")

            # Runner-up
            if len(sorted_configs) > 1:
                runner = sorted_configs[1]
                cfg2 = candidates[runner]
                md.append(f"### Khuyến nghị #2 cho {cap_label}: **{runner}**")
                md.append("")
                md.append(f"- Leverage: {cfg2.lev}x, PS: {cfg2.ps}%, TP: {cfg2.tp}%")
                md.append(f"- Init: ${cfg2.init_m}, SO: ${cfg2.so_m}, Max SO: {cfg2.max_so}, SS: {cfg2.ss}x")
                md.append(f"- Total margin: ${cfg2.total_margin:.0f}")
                r2_recent = results[runner].get("Recent 2024-26")
                r2_crash = results[runner].get("Crash 2021")
                if r2_recent:
                    md.append(f"- Recent: {r2_recent['ret_pct']:+.1f}%, Liq: {r2_recent['n_liq']}")
                if r2_crash:
                    md.append(f"- Crash: {r2_crash['ret_pct']:+.1f}%, Liq: {r2_crash['n_liq']}")
                md.append("")

    # ── Scenarios for 2026-2027 ──
    md.append("## Kịch bản 03/2026 → 03/2027")
    md.append("")
    md.append("Không ai biết trước thị trường, nhưng dựa trên cycle BTC:")
    md.append("")
    md.append("### Kịch bản 1: Tiếp tục tăng (xác suất ~30%)")
    md.append("- BTC $73K → $100K+")
    md.append("- DCA bot Long hoạt động tốt, ít kích hoạt SO")
    md.append("- **Config tốt:** Aggressive hoặc Scalper (nhiều cycle nhanh)")
    md.append("")
    md.append("### Kịch bản 2: Sideway $60K-$85K (xác suất ~35%)")
    md.append("- Lý tưởng nhất cho DCA bot")
    md.append("- **Config tốt:** Moderate hoặc Balanced (đủ SO để catch dip, TP đều)")
    md.append("")
    md.append("### Kịch bản 3: Correction -30-50% (xác suất ~25%)")
    md.append("- Post-halving cycle top → correction")
    md.append("- **Config tốt:** Wide Grid hoặc Conservative (chịu được giảm sâu)")
    md.append("- ⚠️ Screenshot config (10x) sẽ bị liquidation!")
    md.append("")
    md.append("### Kịch bản 4: Black swan crash >50% (xác suất ~10%)")
    md.append("- Mọi DCA futures bot đều cháy")
    md.append("- **Giải pháp duy nhất:** Stop loss thủ công hoặc tắt bot khi BTC break support lớn")
    md.append("")

    md.append("## Chiến lược phòng thủ")
    md.append("")
    md.append("Dù chọn config nào, **luôn áp dụng:**")
    md.append("")
    md.append("1. **Chỉ dùng 50-60% vốn cho bot**, giữ 40-50% dự phòng")
    md.append("2. **Đặt alert khi SO >= 8** → chuẩn bị add margin hoặc đóng lệnh")
    md.append("3. **Tắt bot khi BTC break dưới MA200 Daily** (trend bearish)")
    md.append("4. **Không chạy bot trong tuần có FOMC, CPI, NFP** nếu vốn nhỏ")
    md.append("5. **Review hàng tuần:** Nếu lỗ >15% trong 1 tuần → dừng 1 tuần")
    md.append("")
    md.append("## So sánh: DCA Bot vs Regime+Fusion")
    md.append("")
    md.append("| Tiêu chí | DCA Bot (best config) | Regime+Fusion |")
    md.append("|----------|----------------------|---------------|")
    md.append("| Tự động | ✅ 100% auto | ❌ Cần theo dõi signal |")
    md.append("| Rủi ro cháy | ⚠️ Có (leverage) | ✅ Có SL, DD thấp |")
    md.append("| Return dài hạn | Trung bình-Cao | Cao |")
    md.append("| Phù hợp | Sideway market | Mọi market |")
    md.append("| Vốn nhỏ ($300-500) | ⚠️ Rủi ro cao | ✅ Phù hợp hơn |")
    md.append("")
    md.append("**Kết luận:** Với vốn $300-$500, **Regime+Fusion** an toàn hơn nhiều. "
              "DCA bot chỉ nên dùng khi bạn chấp nhận rủi ro cháy tài khoản "
              "và có quỹ dự phòng để add margin.")
    md.append("")

    out = REPORT_DIR / "dca_bot_regimes.md"
    with open(out, "w") as f:
        f.write("\n".join(md))
    return out


def main():
    t0 = _time.time()
    print("=" * 70)
    print("  DCA Bot — Regime Analysis for 2026-2027")
    print("=" * 70)

    # Load 1h data (best balance of speed and accuracy)
    data_1h = load_btc("1h")
    if data_1h is None:
        print("ERROR: No data")
        return

    ot, _, hi, lo, cl, _ = data_1h
    tf_h = 1.0
    print(f"  1h: {len(cl):,} candles ({_ts_to_str(ot[0])} → {_ts_to_str(ot[-1])})")

    # Verify regimes have data
    for rname, (s, e) in REGIMES.items():
        mask = (ot >= s) & (ot <= e)
        n = mask.sum()
        if n > 0:
            print(f"  {rname}: {n:,} candles, "
                  f"${cl[mask][0]:,.0f} → ${cl[mask][-1]:,.0f}")

    # ── $300 ──
    print("\n── Analyzing $300 ──")
    results_300, cands_300 = run_regime_analysis(300, ot, hi, lo, cl, tf_h, "1h")
    scores_300 = score_for_2026(results_300)
    top3 = sorted(scores_300.items(), key=lambda x: x[1], reverse=True)[:3]
    for name, score in top3:
        print(f"  {score:+.0f} | {name}")

    # ── $500 ──
    print("\n── Analyzing $500 ──")
    results_500, cands_500 = run_regime_analysis(500, ot, hi, lo, cl, tf_h, "1h")
    scores_500 = score_for_2026(results_500)
    top3 = sorted(scores_500.items(), key=lambda x: x[1], reverse=True)[:3]
    for name, score in top3:
        print(f"  {score:+.0f} | {name}")

    out = write_regime_report(results_300, results_500, scores_300, scores_500,
                              cands_300, cands_500, "1h")
    elapsed = _time.time() - t0
    print(f"\n  Report: {out}")
    print(f"  Done in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
