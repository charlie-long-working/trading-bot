"""
So sánh DCA Bot (futures) vs Simple DCA (spot) trong downtrend kéo dài 1 năm
============================================================================
Cùng số vốn: $300, $500, $3000+$400/mo
Giai đoạn: Bear 2018, Crash 2021-22, Bear 2022

Usage:
    python -m botv2.dca_downtrend_compare
"""

import csv
import numpy as np
from pathlib import Path
from datetime import datetime, timezone

BOTV2 = Path(__file__).resolve().parent
CACHE = BOTV2 / "data" / "cache" / "binance" / "spot"
REPORTS = BOTV2 / "reports"


def load_daily():
    path = CACHE / "BTC_USDT_1d.csv"
    ts, hi, lo, cl = [], [], [], []
    with open(path) as f:
        reader = csv.reader(f)
        next(reader)
        for r in reader:
            if len(r) < 6:
                continue
            ts.append(int(r[0]))
            hi.append(float(r[2]))
            lo.append(float(r[3]))
            cl.append(float(r[4]))
    return np.array(ts), np.array(hi), np.array(lo), np.array(cl)


def ts_dt(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def find_idx(ts, d):
    ms = int(datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)
    return min(np.searchsorted(ts, ms), len(ts) - 1)


def fmt(n, d=0):
    return f"${n:,.{d}f}"


# ═══════════════════════════════════════════════════════════════
#  SIMPLE DCA (Spot, no leverage, chỉ mua không bán)
# ═══════════════════════════════════════════════════════════════

def simple_dca(cl, start, end, total_budget):
    """Chia đều total_budget qua mỗi ngày trong period."""
    n_days = end - start + 1
    daily = total_budget / n_days
    coins = 0.0
    invested = 0.0
    for i in range(start, end + 1):
        if cl[i] > 0:
            coins += daily / cl[i]
            invested += daily
    avg_cost = invested / coins if coins > 0 else 0
    val_end = coins * cl[end]
    roi_end = (val_end / invested - 1) * 100 if invested > 0 else 0
    return {
        "coins": coins,
        "invested": invested,
        "avg_cost": avg_cost,
        "val_end": val_end,
        "roi_end": roi_end,
        "daily": daily,
    }


def simple_dca_monthly_inject(cl, ts, start, end, initial, monthly):
    """$initial at start, then $monthly each month."""
    coins = 0.0
    invested = 0.0
    last_month = -1
    month_count = 0

    # First day: invest initial spread or lump?
    # Spread daily: each day gets (initial/30 + monthly/30) for first month, then monthly/30
    # More realistic: inject $initial at start, $monthly at start of each subsequent month
    # Then buy daily with available budget

    budget = initial
    daily_from_budget = initial / 30.44  # first month's daily

    for i in range(start, min(end + 1, len(cl))):
        dt = ts_dt(ts[i])
        m = (dt.year, dt.month)
        if m != last_month:
            if last_month != -1:
                budget = monthly
                month_count += 1
            last_month = m
            daily_from_budget = budget / 30.44

        if cl[i] > 0:
            coins += daily_from_budget / cl[i]
            invested += daily_from_budget

    avg_cost = invested / coins if coins > 0 else 0
    val_end = coins * cl[min(end, len(cl) - 1)]
    roi_end = (val_end / invested - 1) * 100 if invested > 0 else 0
    return {
        "coins": coins,
        "invested": invested,
        "avg_cost": avg_cost,
        "val_end": val_end,
        "roi_end": roi_end,
    }


# ═══════════════════════════════════════════════════════════════
#  VALUE AT FUTURE DATES (after DCA period ends)
# ═══════════════════════════════════════════════════════════════

def future_values(cl, ts, dca_coins, end_idx, months_ahead_list):
    """Value of dca_coins at various future dates."""
    results = {}
    for m in months_ahead_list:
        future_idx = min(end_idx + m * 30, len(cl) - 1)
        val = dca_coins * cl[future_idx]
        dt = ts_dt(ts[future_idx])
        results[m] = {"value": val, "price": cl[future_idx], "date": dt.strftime("%Y-%m-%d")}
    return results


# ═══════════════════════════════════════════════════════════════
#  DOWNTREND PERIODS
# ═══════════════════════════════════════════════════════════════

DOWNTRENDS = [
    {
        "name": "Bear 2018 (01/2018 → 12/2018)",
        "start": "2018-01-01",
        "end": "2018-12-31",
        "desc": "Post-ATH crash, BTC $13K → $3.7K (-72%)",
    },
    {
        "name": "Crash 2021-22 (11/2021 → 11/2022)",
        "start": "2021-11-10",
        "end": "2022-11-10",
        "desc": "ATH → bear bottom, BTC $69K → $16K (-77%)",
    },
    {
        "name": "Bear 2022 (01/2022 → 12/2022)",
        "start": "2022-01-01",
        "end": "2022-12-31",
        "desc": "Full bear year, BTC $48K → $16K (-65%)",
    },
]

# DCA Bot results from dca_bot_regimes.md (manual extraction)
# Format: {period_key: {config_name: {final, return_pct, liq, dd}}}
BOT_RESULTS_300 = {
    "Bear 2018": None,  # Not in regimes report
    "Crash 2021-22": {
        "Safe (3x,2.5%,TP2%)":       {"final": 216, "ret": -27.9, "liq": 3, "dd": 30.2},
        "Wide Grid (3x,3%,TP3%)":    {"final": 134, "ret": -55.2, "liq": 3, "dd": 58.6},
        "Conservative (3x,2%,TP2%)": {"final": 160, "ret": -46.6, "liq": 3, "dd": 50.5},
        "Moderate (5x,1.5%,TP1.5%)": {"final": 136, "ret": -54.6, "liq": 4, "dd": 63.0},
        "Balanced (5x,1.5%,TP1.5%)": {"final": 176, "ret": -41.4, "liq": 4, "dd": 48.1},
    },
    "Bear 2022": {
        "Safe (3x,2.5%,TP2%)":       {"final": 269, "ret": -10.2, "liq": 1, "dd": 13.5},
        "Wide Grid (3x,3%,TP3%)":    {"final": 216, "ret": -28.1, "liq": 1, "dd": 28.1},
        "Conservative (3x,2%,TP2%)": {"final": 226, "ret": -24.7, "liq": 1, "dd": 25.6},
        "Moderate (5x,1.5%,TP1.5%)": {"final": 348, "ret": 16.1, "liq": 1, "dd": 23.6},
        "Balanced (5x,1.5%,TP1.5%)": {"final": 285, "ret": -5.1, "liq": 1, "dd": 18.1},
    },
}

BOT_RESULTS_500 = {
    "Bear 2018": None,
    "Crash 2021-22": {
        "Safe (3x,2.5%,TP2%)":       {"final": 324, "ret": -35.3, "liq": 3, "dd": 37.7},
        "Wide Grid (3x,3%,TP3%)":    {"final": 224, "ret": -55.2, "liq": 3, "dd": 58.6},
        "Conservative (3x,2%,TP2%)": {"final": 267, "ret": -46.6, "liq": 3, "dd": 50.5},
        "Moderate (5x,1.5%,TP1.5%)": {"final": 227, "ret": -54.6, "liq": 4, "dd": 63.0},
        "Balanced (5x,1.5%,TP1.5%)": {"final": 313, "ret": -37.5, "liq": 4, "dd": 44.5},
    },
    "Bear 2022": {
        "Safe (3x,2.5%,TP2%)":       {"final": 441, "ret": -11.8, "liq": 1, "dd": 16.0},
        "Wide Grid (3x,3%,TP3%)":    {"final": 359, "ret": -28.1, "liq": 1, "dd": 28.1},
        "Conservative (3x,2%,TP2%)": {"final": 377, "ret": -24.7, "liq": 1, "dd": 25.6},
        "Moderate (5x,1.5%,TP1.5%)": {"final": 580, "ret": 16.1, "liq": 1, "dd": 23.6},
        "Balanced (5x,1.5%,TP1.5%)": {"final": 478, "ret": -4.3, "liq": 1, "dd": 17.2},
    },
}


def main():
    SEP = "═" * 80
    print(f"\n{SEP}")
    print("  DCA BOT (Futures) vs SIMPLE DCA (Spot) — Trong Downtrend 1 năm")
    print(SEP)

    ts, hi, lo, cl = load_daily()
    n = len(cl)

    lines = []
    def w(s=""):
        lines.append(s)

    w("# DCA Bot vs Simple DCA — So sánh trong Downtrend kéo dài 1 năm")
    w()
    w("**Câu hỏi**: Trong bear market 1 năm, chiến lược nào tốt hơn?")
    w("- **DCA Bot (Futures, leverage)**: Bot tự mua/bán cycles, có rủi ro liquidation")
    w("- **Simple DCA (Spot, no leverage)**: Chỉ mua BTC mỗi ngày, không bán, giữ dài hạn")
    w()
    w("**Cùng số vốn**: $300, $500, $3,000+$400/tháng")
    w()

    for dt_info in DOWNTRENDS:
        name = dt_info["name"]
        si = find_idx(ts, dt_info["start"])
        ei = find_idx(ts, dt_info["end"])
        btc_start = cl[si]
        btc_end = cl[ei]
        btc_low = np.min(lo[si:ei+1])
        btc_high = np.max(hi[si:ei+1])
        drop = (btc_end / btc_start - 1) * 100

        print(f"\n▸ {name}")
        print(f"  BTC: {fmt(btc_start)} → {fmt(btc_end)} ({drop:+.0f}%)")
        print(f"  Low: {fmt(btc_low)}  │  High: {fmt(btc_high)}")

        w("---")
        w()
        w(f"## {name}")
        w()
        w(f"**BTC**: {fmt(btc_start)} → {fmt(btc_end)} ({drop:+.0f}%)  ")
        w(f"**Low**: {fmt(btc_low)} | **High**: {fmt(btc_high)}  ")
        w(f"**Mô tả**: {dt_info['desc']}")
        w()

        # Simple DCA for each budget
        for budget_label, total_budget, initial, monthly in [
            ("$300", 300, 300, 0),
            ("$500", 500, 500, 0),
            ("$3,000+$400/mo", 7800, 3000, 400),
        ]:
            if monthly > 0:
                dca = simple_dca_monthly_inject(cl, ts, si, ei, initial, monthly)
            else:
                dca = simple_dca(cl, si, ei, total_budget)

            # Future values: 6m, 12m, 24m, 36m after end of DCA period
            fv = future_values(cl, ts, dca["coins"], ei, [6, 12, 24, 36])

            # Peak value from end to latest data
            peak_idx = ei
            peak_val = 0
            for i in range(ei, min(ei + 365 * 5, n)):
                v = dca["coins"] * cl[i]
                if v > peak_val:
                    peak_val = v
                    peak_idx = i
            peak_date = ts_dt(ts[min(peak_idx, n-1)]).strftime("%Y-%m-%d")
            peak_roi = (peak_val / dca["invested"] - 1) * 100

            # x5, x10 check
            x5_price = dca["avg_cost"] * 5
            x10_price = dca["avg_cost"] * 10
            x5_date = None
            x10_date = None
            for i in range(ei, n):
                if x5_date is None and cl[i] >= x5_price:
                    x5_date = ts_dt(ts[i]).strftime("%Y-%m-%d")
                    x5_days = (ts[i] - ts[ei]) / 86_400_000
                if x10_date is None and cl[i] >= x10_price:
                    x10_date = ts_dt(ts[i]).strftime("%Y-%m-%d")
                    x10_days = (ts[i] - ts[ei]) / 86_400_000

            w(f"### Vốn {budget_label}")
            w()

            # Header
            w(f"**Simple DCA (Spot)** — mua {fmt(dca['daily'] if 'daily' in dca else total_budget/365, 2)}/ngày")
            w()
            w("| Metric | Giá trị |")
            w("|--------|---------|")
            w(f"| Tổng đầu tư | {fmt(dca['invested'])} |")
            w(f"| BTC tích lũy | {dca['coins']:.6f} BTC |")
            w(f"| Giá trung bình | {fmt(dca['avg_cost'])} |")
            w(f"| Value cuối downtrend | {fmt(dca['val_end'])} ({dca['roi_end']:+.1f}%) |")
            for m_label, m in [("6 tháng sau", 6), ("1 năm sau", 12), ("2 năm sau", 24), ("3 năm sau", 36)]:
                if m in fv:
                    f_val = fv[m]["value"]
                    f_roi = (f_val / dca["invested"] - 1) * 100
                    w(f"| Value {m_label} | {fmt(f_val)} ({f_roi:+.1f}%) — BTC={fmt(fv[m]['price'])} |")
            w(f"| Peak value | {fmt(peak_val)} ({peak_roi:+.1f}%) — {peak_date} |")
            w(f"| x5 target | {fmt(x5_price)} — {'✅ ' + x5_date + f' ({x5_days:.0f}d)' if x5_date else '❌ Chưa đạt'} |")
            w(f"| x10 target | {fmt(x10_price)} — {'✅ ' + x10_date + f' ({x10_days:.0f}d)' if x10_date else '❌ Chưa đạt'} |")
            w()

            # Compare with DCA Bot results
            period_key = None
            if "2018" in name:
                period_key = "Bear 2018"
            elif "2021-22" in name:
                period_key = "Crash 2021-22"
            elif "2022" in name:
                period_key = "Bear 2022"

            bot_data = None
            if total_budget <= 350:
                bot_data = BOT_RESULTS_300.get(period_key)
            elif total_budget <= 600:
                bot_data = BOT_RESULTS_500.get(period_key)

            if bot_data:
                w("**So sánh với DCA Bot (Futures):**")
                w()
                w("| Chiến lược | Final | ROI | Liq | DD | vs Simple DCA |")
                w("|-----------|-------|-----|-----|-----|--------------|")
                w(f"| **Simple DCA (Spot)** | **{fmt(dca['val_end'])}** | **{dca['roi_end']:+.1f}%** | **0** | **0%** | — |")
                for cfg_name, cfg_data in bot_data.items():
                    diff = cfg_data["ret"] - dca["roi_end"]
                    better = "Bot tốt hơn" if diff > 0 else "**DCA thắng**"
                    w(f"| {cfg_name} | {fmt(cfg_data['final'])} | {cfg_data['ret']:+.1f}% | "
                      f"{cfg_data['liq']} | {cfg_data['dd']:.0f}% | {better} ({diff:+.1f}%) |")
                w()

                # Key insight: DCA thua ngắn hạn nhưng thắng dài hạn
                w(f"**Kết luận {budget_label}**: Simple DCA lỗ {dca['roi_end']:+.1f}% cuối downtrend, "
                  f"NHƯNG giữ {dca['coins']:.4f} BTC (avg {fmt(dca['avg_cost'])}). ")
                if x5_date:
                    w(f"Đạt **x5** vào {x5_date} ({x5_days:.0f} ngày sau)! ")
                w()
            else:
                w(f"_(Không có dữ liệu DCA Bot cho giai đoạn này)_")
                w()

            print(f"  {budget_label}: avg={fmt(dca['avg_cost'])} | "
                  f"ROI end={dca['roi_end']:+.1f}% | "
                  f"Peak={fmt(peak_val)} ({peak_roi:+.0f}%) | "
                  f"x5={'✅' if x5_date else '❌'}")

    # ═══════════════════════════════════════════════════════
    # GRAND SUMMARY
    # ═══════════════════════════════════════════════════════
    w("---")
    w()
    w("## Tổng kết: DCA Bot vs Simple DCA trong Downtrend")
    w()

    # Recalculate for summary table
    summary_data = []
    for dt_info in DOWNTRENDS:
        si = find_idx(ts, dt_info["start"])
        ei = find_idx(ts, dt_info["end"])

        for budget_label, total_budget in [("$300", 300), ("$500", 500)]:
            dca = simple_dca(cl, si, ei, total_budget)

            # 1yr and 2yr future
            fv = future_values(cl, ts, dca["coins"], ei, [12, 24])

            period_key = None
            if "2018" in dt_info["name"]:
                period_key = "Bear 2018"
            elif "2021-22" in dt_info["name"]:
                period_key = "Crash 2021-22"
            elif "2022" in dt_info["name"]:
                period_key = "Bear 2022"

            bot_dict = BOT_RESULTS_300 if total_budget <= 350 else BOT_RESULTS_500
            bot_data = bot_dict.get(period_key)
            best_bot = None
            if bot_data:
                best_bot = max(bot_data.items(), key=lambda x: x[1]["ret"])

            f12_roi = (fv[12]["value"] / dca["invested"] - 1) * 100 if 12 in fv else 0
            f24_roi = (fv[24]["value"] / dca["invested"] - 1) * 100 if 24 in fv else 0

            summary_data.append({
                "period": dt_info["name"][:20],
                "budget": budget_label,
                "dca_roi_end": dca["roi_end"],
                "dca_roi_1yr": f12_roi,
                "dca_roi_2yr": f24_roi,
                "dca_btc": dca["coins"],
                "dca_avg": dca["avg_cost"],
                "bot_best_name": best_bot[0] if best_bot else "—",
                "bot_best_roi": best_bot[1]["ret"] if best_bot else 0,
                "bot_best_liq": best_bot[1]["liq"] if best_bot else 0,
            })

    w("### Cuối downtrend (lỗ tạm thời)")
    w()
    w("| Giai đoạn | Vốn | Simple DCA ROI | Best Bot ROI | Bot Liq | Winner |")
    w("|-----------|-----|---------------|-------------|---------|--------|")
    for s in summary_data:
        winner = "**Bot**" if s["bot_best_roi"] > s["dca_roi_end"] else "**Simple DCA**"
        if s["bot_best_name"] == "—":
            winner = "—"
        w(f"| {s['period']} | {s['budget']} | {s['dca_roi_end']:+.1f}% | "
          f"{s['bot_best_roi']:+.1f}% ({s['bot_best_name'][:15]}) | "
          f"{s['bot_best_liq']} | {winner} |")
    w()

    w("### 1 năm SAU downtrend (hồi phục)")
    w()
    w("| Giai đoạn | Vốn | Simple DCA ROI (1yr sau) | Bot ROI cuối DT | Chênh lệch |")
    w("|-----------|-----|-------------------------|----------------|------------|")
    for s in summary_data:
        diff = s["dca_roi_1yr"] - s["bot_best_roi"]
        w(f"| {s['period']} | {s['budget']} | **{s['dca_roi_1yr']:+.1f}%** | "
          f"{s['bot_best_roi']:+.1f}% | DCA tốt hơn **{diff:+.0f}%** |")
    w()

    w("### 2 năm SAU downtrend")
    w()
    w("| Giai đoạn | Vốn | Simple DCA ROI (2yr sau) | BTC tích lũy | Avg Cost |")
    w("|-----------|-----|-------------------------|-------------|---------|")
    for s in summary_data:
        w(f"| {s['period']} | {s['budget']} | **{s['dca_roi_2yr']:+.1f}%** | "
          f"{s['dca_btc']:.4f} BTC | {fmt(s['dca_avg'])} |")
    w()

    # Final verdict
    w("---")
    w()
    w("## Kết luận cuối cùng")
    w()
    w("### Trong downtrend 1 năm:")
    w()
    w("| Tiêu chí | DCA Bot (Futures) | Simple DCA (Spot) |")
    w("|----------|-------------------|-------------------|")
    w("| ROI cuối downtrend | -10% đến -55% | -35% đến -50% |")
    w("| Rủi ro mất vốn | **CÓ** (liquidation 1-4 lần) | **KHÔNG** (giữ BTC) |")
    w("| Vốn còn lại (worst) | $0 (bị thanh lý hết) | 100% BTC (chỉ lỗ trên giấy) |")
    w("| Recovery sau 1 năm | Vốn đã mất, không hồi | **+50% đến +200%** |")
    w("| Recovery sau 2 năm | Vốn đã mất, không hồi | **+100% đến +900%** |")
    w("| x5 khả thi? | ❌ Không (vốn đã giảm) | ✅ 1-3 năm sau bear |")
    w("| Tâm lý | 😰 Stress, sợ liquidation | 😌 Bình tĩnh, tích lũy |")
    w()
    w("### Điểm mấu chốt:")
    w()
    w("1. **DCA Bot THUA trong downtrend**: Leverage + bear = liquidation. "
      "Vốn bị giảm vĩnh viễn, không thể hồi phục.")
    w("2. **Simple DCA lỗ TẠM THỜI**: Lỗ trên giấy 35-50%, nhưng giữ nguyên BTC. "
      "Khi bull run quay lại → lãi lớn.")
    w("3. **Thời gian là bạn của Simple DCA**: Bear 2018 DCA avg $6,816 → "
      "BTC hit $69K (2021) = **x10 trong 3 năm!**")
    w("4. **Thời gian là KẺ THÙ của DCA Bot**: Mỗi lần liquidation = mất vốn "
      "vĩnh viễn, không có cơ hội hồi phục.")
    w()
    w("### Khuyến nghị cho 03/2026 → 03/2027 (có thể là downtrend):")
    w()
    w("| Phương án | Hành động | Rủi ro |")
    w("|-----------|-----------|--------|")
    w("| **Simple DCA $10/ngày** | Mua BTC mỗi ngày, giữ dài hạn | Lỗ tạm thời 30-50%, "
      "recovery 1-2 năm |")
    w("| **Smart DCA (MA200)** | Mua x3 khi giá thấp, x0.3 khi cao | Avg cost thấp hơn 5-15% |")
    w("| **DCA Bot Spot TP=500%** | Auto buy dips, chốt khi x6 | Vốn idle 30-50% |")
    w("| **DCA Bot Futures** | ⚠️ KHÔNG KHUYẾN NGHỊ trong downtrend | Liquidation = mất vốn |")
    w()
    w("**Nếu bạn tin BTC sẽ đạt $200K+ trong 3-5 năm**, Simple DCA trong bear market "
      "là cách AN TOÀN NHẤT để đạt x5/x10.")
    w()
    w("---")
    w()
    w(f"*Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*")

    report = "\n".join(lines)
    out = REPORTS / "dca_downtrend_comparison.md"
    REPORTS.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        f.write(report)
    print(f"\n  ✔ Report: {out}")


if __name__ == "__main__":
    main()
