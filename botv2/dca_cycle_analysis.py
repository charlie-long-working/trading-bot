"""
DCA Cycle Analysis – Mua vào không chốt, chốt khi x5/x10
=========================================================
- Phân tích chu kỳ BTC (halving cycles)
- So sánh chiến lược DCA khác nhau qua từng mùa
- Tìm cách DCA từ 03/2026 → 03/2027 có giá trung bình thấp nhất
- Tính target x5, x10 và thời gian đạt được

Usage:
    python -m botv2.dca_cycle_analysis
"""

import csv
import math
import numpy as np
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict

BOTV2 = Path(__file__).resolve().parent
CACHE = BOTV2 / "data" / "cache" / "binance" / "spot"
REPORTS = BOTV2 / "reports"


# ═══════════════════════════════════════════════════════════════════
#  DATA
# ═══════════════════════════════════════════════════════════════════

def load_daily():
    path = CACHE / "BTC_USDT_1d.csv"
    ts, op, hi, lo, cl = [], [], [], [], []
    with open(path) as f:
        reader = csv.reader(f)
        next(reader)
        for r in reader:
            if len(r) < 6:
                continue
            ts.append(int(r[0]))
            op.append(float(r[1]))
            hi.append(float(r[2]))
            lo.append(float(r[3]))
            cl.append(float(r[4]))
    return np.array(ts), np.array(op), np.array(hi), np.array(lo), np.array(cl)


def ts_to_date(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def date_to_str(dt):
    return dt.strftime("%Y-%m-%d")


def find_idx(ts_arr, target_date_str):
    """Find index closest to target date."""
    target = datetime.strptime(target_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    target_ms = int(target.timestamp() * 1000)
    idx = np.searchsorted(ts_arr, target_ms)
    return min(idx, len(ts_arr) - 1)


# ═══════════════════════════════════════════════════════════════════
#  CYCLE DEFINITIONS
# ═══════════════════════════════════════════════════════════════════

HALVING_DATES = [
    ("Halving 1", "2012-11-28"),
    ("Halving 2", "2016-07-09"),
    ("Halving 3", "2020-05-11"),
    ("Halving 4", "2024-04-20"),
]

CYCLE_PHASES = {
    "Cycle 2 (2016-2020)": {
        "halving": "2016-07-09",
        "bull_peak": "2017-12-17",
        "bear_bottom": "2018-12-15",
        "recovery_end": "2020-05-11",
    },
    "Cycle 3 (2020-2024)": {
        "halving": "2020-05-11",
        "bull_peak": "2021-11-10",
        "bear_bottom": "2022-11-21",
        "recovery_end": "2024-04-20",
    },
    "Cycle 4 (2024-now)": {
        "halving": "2024-04-20",
        "bull_peak": "2025-01-20",  # ATH ~$109k
        "bear_bottom": None,
        "recovery_end": None,
    },
}


# ═══════════════════════════════════════════════════════════════════
#  DCA SIMULATION (BUY ONLY, NO SELL)
# ═══════════════════════════════════════════════════════════════════

def dca_fixed(cl, ts, start_idx, end_idx, amount, frequency="daily"):
    """Fixed DCA: buy $amount every frequency. Never sell."""
    coins = 0.0
    invested = 0.0
    buys = 0
    last_buy_day = -1

    for i in range(start_idx, min(end_idx + 1, len(cl))):
        dt = ts_to_date(ts[i])

        should_buy = False
        if frequency == "daily":
            should_buy = True
        elif frequency == "weekly":
            if dt.weekday() == 0:  # Monday
                should_buy = True
        elif frequency == "biweekly":
            day_of_month = dt.day
            if day_of_month in (1, 15) or (day_of_month == 2 and last_buy_day != 1):
                should_buy = True
        elif frequency == "monthly":
            if dt.day == 1 or (dt.day == 2 and last_buy_day != 1):
                should_buy = True

        if should_buy and cl[i] > 0:
            coins += amount / cl[i]
            invested += amount
            buys += 1
            last_buy_day = dt.day

    avg_cost = invested / coins if coins > 0 else 0
    return coins, invested, avg_cost, buys


def dca_smart_dip(cl, ts, start_idx, end_idx, base_amount, frequency="daily"):
    """Smart DCA: buy more on dips (below MA), less on pumps."""
    coins = 0.0
    invested = 0.0
    buys = 0

    # Precompute 50-day MA
    ma50 = np.full(len(cl), np.nan)
    for i in range(49, len(cl)):
        ma50[i] = np.mean(cl[i-49:i+1])

    # Precompute 200-day MA
    ma200 = np.full(len(cl), np.nan)
    for i in range(199, len(cl)):
        ma200[i] = np.mean(cl[i-199:i+1])

    for i in range(start_idx, min(end_idx + 1, len(cl))):
        dt = ts_to_date(ts[i])

        should_buy = False
        if frequency == "daily":
            should_buy = True
        elif frequency == "weekly":
            if dt.weekday() == 0:
                should_buy = True

        if not should_buy or cl[i] <= 0:
            continue

        # Determine multiplier based on price vs MAs
        multiplier = 1.0

        if not np.isnan(ma200[i]):
            ratio = cl[i] / ma200[i]
            if ratio < 0.7:       # >30% below 200MA → buy 3x
                multiplier = 3.0
            elif ratio < 0.85:    # 15-30% below → buy 2x
                multiplier = 2.0
            elif ratio < 0.95:    # 5-15% below → buy 1.5x
                multiplier = 1.5
            elif ratio > 1.5:     # >50% above → buy 0.3x
                multiplier = 0.3
            elif ratio > 1.3:     # 30-50% above → buy 0.5x
                multiplier = 0.5
            elif ratio > 1.15:    # 15-30% above → buy 0.7x
                multiplier = 0.7

        amt = base_amount * multiplier
        coins += amt / cl[i]
        invested += amt
        buys += 1

    avg_cost = invested / coins if coins > 0 else 0
    return coins, invested, avg_cost, buys


def dca_rsi_based(cl, ts, start_idx, end_idx, base_amount, frequency="daily"):
    """RSI-based DCA: buy more when oversold, less when overbought."""
    coins = 0.0
    invested = 0.0
    buys = 0

    # Precompute RSI(14)
    rsi = np.full(len(cl), 50.0)
    period = 14
    for i in range(period, len(cl)):
        gains = []
        losses = []
        for j in range(i - period + 1, i + 1):
            change = cl[j] - cl[j-1]
            if change > 0:
                gains.append(change)
            else:
                losses.append(abs(change))
        avg_gain = np.mean(gains) if gains else 0
        avg_loss = np.mean(losses) if losses else 0.0001
        rs = avg_gain / avg_loss
        rsi[i] = 100 - 100 / (1 + rs)

    for i in range(start_idx, min(end_idx + 1, len(cl))):
        dt = ts_to_date(ts[i])

        should_buy = False
        if frequency == "daily":
            should_buy = True
        elif frequency == "weekly":
            if dt.weekday() == 0:
                should_buy = True

        if not should_buy or cl[i] <= 0:
            continue

        # Scale by RSI
        r = rsi[i]
        if r < 25:
            multiplier = 3.0
        elif r < 35:
            multiplier = 2.0
        elif r < 45:
            multiplier = 1.5
        elif r > 80:
            multiplier = 0.3
        elif r > 70:
            multiplier = 0.5
        elif r > 60:
            multiplier = 0.7
        else:
            multiplier = 1.0

        amt = base_amount * multiplier
        coins += amt / cl[i]
        invested += amt
        buys += 1

    avg_cost = invested / coins if coins > 0 else 0
    return coins, invested, avg_cost, buys


# ═══════════════════════════════════════════════════════════════════
#  x5 / x10 ANALYSIS
# ═══════════════════════════════════════════════════════════════════

def find_x_multiple(cl, ts, dca_start_idx, dca_end_idx, amount, frequency, target_x):
    """After DCA period, how long until portfolio reaches target_x of invested?"""
    coins = 0.0
    invested = 0.0

    for i in range(dca_start_idx, min(dca_end_idx + 1, len(cl))):
        dt = ts_to_date(ts[i])
        should_buy = (frequency == "daily" or
                      (frequency == "weekly" and dt.weekday() == 0))
        if should_buy and cl[i] > 0:
            coins += amount / cl[i]
            invested += amount

    if invested == 0 or coins == 0:
        return None, None, None

    avg_cost = invested / coins
    target_price = avg_cost * target_x

    # Search forward from end of DCA period
    for i in range(dca_end_idx, len(cl)):
        if cl[i] >= target_price:
            dt = ts_to_date(ts[i])
            days_from_end = (ts[i] - ts[dca_end_idx]) / 86_400_000
            return date_to_str(dt), int(days_from_end), cl[i]

    return None, None, None


# ═══════════════════════════════════════════════════════════════════
#  ROLLING 12-MONTH DCA ANALYSIS
# ═══════════════════════════════════════════════════════════════════

def rolling_12m_analysis(cl, ts):
    """Analyze every 12-month DCA window."""
    results = []
    # Step by ~3 months (90 days)
    step = 90
    for start in range(0, len(cl) - 365, step):
        end = start + 365
        if end >= len(cl):
            break
        start_dt = ts_to_date(ts[start])
        end_dt = ts_to_date(ts[end])

        coins_d, inv_d, avg_d, _ = dca_fixed(cl, ts, start, end, 10.0, "daily")
        coins_w, inv_w, avg_w, _ = dca_fixed(cl, ts, start, end, 70.0, "weekly")
        coins_m, inv_m, avg_m, _ = dca_fixed(cl, ts, start, end, 300.0, "monthly")

        # Smart DCA (same budget ~$10/day)
        coins_s, inv_s, avg_s, _ = dca_smart_dip(cl, ts, start, end, 10.0, "daily")

        # Final value at end of period
        val_d = coins_d * cl[end]
        val_w = coins_w * cl[end]
        val_s = coins_s * cl[end]

        # Also look ahead for x5 from avg cost
        future_max = 0
        lookahead = min(end + 365 * 3, len(cl))
        if end < len(cl):
            future_max = np.max(cl[end:lookahead])

        results.append({
            "start": date_to_str(start_dt),
            "end": date_to_str(end_dt),
            "price_start": cl[start],
            "price_end": cl[end],
            "avg_daily": avg_d,
            "avg_weekly": avg_w,
            "avg_monthly": avg_m,
            "avg_smart": avg_s,
            "inv_daily": inv_d,
            "inv_smart": inv_s,
            "roi_daily": (val_d / inv_d - 1) * 100 if inv_d > 0 else 0,
            "roi_smart": (val_s / inv_s - 1) * 100 if inv_s > 0 else 0,
            "future_max_3y": future_max,
            "x5_possible": future_max >= avg_d * 5 if avg_d > 0 else False,
            "x10_possible": future_max >= avg_d * 10 if avg_d > 0 else False,
        })
    return results


# ═══════════════════════════════════════════════════════════════════
#  CYCLE POSITION ANALYSIS
# ═══════════════════════════════════════════════════════════════════

def analyze_cycle_position(cl, ts):
    """Analyze where we are in the current cycle vs historical."""
    info = {}

    for cycle_name, phases in CYCLE_PHASES.items():
        halving_idx = find_idx(ts, phases["halving"])
        halving_price = cl[halving_idx]

        peak_idx = find_idx(ts, phases["bull_peak"])
        peak_price = cl[peak_idx]

        months_halving_to_peak = (ts[peak_idx] - ts[halving_idx]) / (86_400_000 * 30.44)

        bottom_price = None
        bottom_idx = None
        if phases["bear_bottom"]:
            bottom_idx = find_idx(ts, phases["bear_bottom"])
            bottom_price = cl[bottom_idx]

        # What happened in the 12 months AFTER the peak?
        post_peak_12m_idx = min(peak_idx + 365, len(cl) - 1)
        post_peak_12m_prices = cl[peak_idx:post_peak_12m_idx+1]
        post_peak_min = np.min(post_peak_12m_prices) if len(post_peak_12m_prices) > 0 else 0
        post_peak_max = np.max(post_peak_12m_prices) if len(post_peak_12m_prices) > 0 else 0

        # DCA in the 12 months after peak
        if peak_idx + 365 < len(cl):
            _, _, avg_post_peak, _ = dca_fixed(cl, ts, peak_idx, peak_idx + 365, 10, "daily")
        else:
            avg_post_peak = 0

        info[cycle_name] = {
            "halving_date": phases["halving"],
            "halving_price": halving_price,
            "peak_date": phases["bull_peak"],
            "peak_price": peak_price,
            "peak_multiple": peak_price / halving_price,
            "months_to_peak": months_halving_to_peak,
            "bottom_price": bottom_price,
            "bottom_date": phases.get("bear_bottom"),
            "drawdown_from_peak": ((peak_price - bottom_price) / peak_price * 100) if bottom_price else None,
            "post_peak_12m_low": post_peak_min,
            "post_peak_12m_high": post_peak_max,
            "dca_avg_12m_post_peak": avg_post_peak,
        }

    return info


# ═══════════════════════════════════════════════════════════════════
#  PROJECTION: DCA 03/2026 → 03/2027
# ═══════════════════════════════════════════════════════════════════

def project_dca_2026_2027(cl, ts):
    """
    Project DCA from 03/2026 using cycle analogies.
    Map current position to equivalent positions in past cycles.
    """
    current_idx = len(cl) - 1
    current_price = cl[current_idx]
    current_date = ts_to_date(ts[current_idx])

    halving4_idx = find_idx(ts, "2024-04-20")
    halving4_price = cl[halving4_idx]
    months_since_halving = (ts[current_idx] - ts[halving4_idx]) / (86_400_000 * 30.44)

    # ATH and drawdown
    ath_idx = halving4_idx + np.argmax(cl[halving4_idx:current_idx+1])
    ath_price = cl[ath_idx]
    drawdown_from_ath = (ath_price - current_price) / ath_price * 100

    # Map to past cycles at same months-since-halving
    analogs = {}
    for cycle_name, phases in CYCLE_PHASES.items():
        if phases["recovery_end"] is None:
            continue
        h_idx = find_idx(ts, phases["halving"])
        equiv_idx = h_idx + int(months_since_halving * 30.44)
        if equiv_idx >= len(cl):
            continue

        equiv_price = cl[equiv_idx]
        equiv_date = ts_to_date(ts[equiv_idx])

        # What happened next 12 months from equivalent point?
        next_12m_end = min(equiv_idx + 365, len(cl) - 1)
        next_12m_prices = cl[equiv_idx:next_12m_end+1]

        # DCA in those 12 months
        coins, inv, avg, _ = dca_fixed(cl, ts, equiv_idx, next_12m_end, 10, "daily")
        final_val = coins * cl[next_12m_end]

        # Smart DCA
        coins_s, inv_s, avg_s, _ = dca_smart_dip(cl, ts, equiv_idx, next_12m_end, 10, "daily")
        final_val_s = coins_s * cl[next_12m_end]

        # Price trajectory (monthly)
        monthly_prices = []
        for m in range(13):
            m_idx = min(equiv_idx + m * 30, len(cl) - 1)
            monthly_prices.append(cl[m_idx])

        analogs[cycle_name] = {
            "equiv_date": date_to_str(equiv_date),
            "equiv_price": equiv_price,
            "next_12m_low": np.min(next_12m_prices),
            "next_12m_high": np.max(next_12m_prices),
            "next_12m_end_price": cl[next_12m_end],
            "dca_avg_cost": avg,
            "dca_invested": inv,
            "dca_final": final_val,
            "dca_roi": (final_val / inv - 1) * 100 if inv > 0 else 0,
            "smart_avg_cost": avg_s,
            "smart_invested": inv_s,
            "smart_final": final_val_s,
            "smart_roi": (final_val_s / inv_s - 1) * 100 if inv_s > 0 else 0,
            "monthly_trajectory": monthly_prices,
        }

    return {
        "current_price": current_price,
        "current_date": date_to_str(current_date),
        "months_since_halving": months_since_halving,
        "ath_price": ath_price,
        "ath_date": date_to_str(ts_to_date(ts[ath_idx])),
        "drawdown_from_ath": drawdown_from_ath,
        "analogs": analogs,
    }


def project_scenarios(current_price, cycle_info):
    """Create 3 scenarios for 03/2026 → 03/2027 based on cycle analogs."""
    analogs = cycle_info["analogs"]

    scenarios = {}

    if "Cycle 2 (2016-2020)" in analogs:
        c2 = analogs["Cycle 2 (2016-2020)"]
        # Cycle 2 at equivalent point: post-peak crash
        price_ratio = current_price / c2["equiv_price"]
        trajectory = [p * price_ratio for p in c2["monthly_trajectory"]]
        scenarios["Giống Cycle 2 (bear kéo dài)"] = {
            "trajectory": trajectory,
            "description": "Bear market kéo dài, giá giảm sâu rồi hồi chậm",
            "avg_dca": c2["dca_avg_cost"] * price_ratio,
            "smart_avg": c2["smart_avg_cost"] * price_ratio,
            "end_price": trajectory[-1] if trajectory else current_price,
            "low": min(trajectory) if trajectory else current_price,
            "high": max(trajectory) if trajectory else current_price,
        }

    if "Cycle 3 (2020-2024)" in analogs:
        c3 = analogs["Cycle 3 (2020-2024)"]
        price_ratio = current_price / c3["equiv_price"]
        trajectory = [p * price_ratio for p in c3["monthly_trajectory"]]
        scenarios["Giống Cycle 3 (bear vừa)"] = {
            "trajectory": trajectory,
            "description": "Correction vừa, giá về đáy rồi recovery cuối năm",
            "avg_dca": c3["dca_avg_cost"] * price_ratio,
            "smart_avg": c3["smart_avg_cost"] * price_ratio,
            "end_price": trajectory[-1] if trajectory else current_price,
            "low": min(trajectory) if trajectory else current_price,
            "high": max(trajectory) if trajectory else current_price,
        }

    # Moderate/sideways scenario (mix)
    if scenarios:
        all_avgs = [s["avg_dca"] for s in scenarios.values()]
        all_lows = [s["low"] for s in scenarios.values()]
        all_highs = [s["high"] for s in scenarios.values()]
        scenarios["Sideways (trung bình)"] = {
            "trajectory": None,
            "description": "Thị trường đi ngang quanh mức hiện tại",
            "avg_dca": np.mean(all_avgs),
            "smart_avg": np.mean([s["smart_avg"] for s in scenarios.values()]),
            "end_price": current_price * 1.1,
            "low": current_price * 0.65,
            "high": current_price * 1.3,
        }

    return scenarios


# ═══════════════════════════════════════════════════════════════════
#  REPORT
# ═══════════════════════════════════════════════════════════════════

def fmt(n, dec=0):
    if dec == 0:
        return f"${n:,.0f}"
    return f"${n:,.{dec}f}"


def main():
    SEP = "═" * 80
    print(f"\n{SEP}")
    print("  DCA CYCLE ANALYSIS – Mua vào không chốt, chốt khi x5/x10")
    print(f"  BTC/USDT │ So sánh các mùa │ Tối ưu 03/2026 → 03/2027")
    print(SEP)

    ts, op, hi, lo, cl = load_daily()
    n = len(cl)
    print(f"\n▸ Data: {n:,} daily candles")
    print(f"  {date_to_str(ts_to_date(ts[0]))} → {date_to_str(ts_to_date(ts[-1]))}")
    print(f"  BTC: {fmt(cl[0])} → {fmt(cl[-1])}")

    lines = []
    def w(s=""):
        lines.append(s)

    w("# DCA Tích lũy BTC – Phân tích Chu kỳ & Tối ưu")
    w()
    w(f"**Chiến lược**: Chỉ MUA, không bán. Chốt lời khi x5 hoặc x10 tổng vốn.  ")
    w(f"**Data**: BTC/USDT daily, {date_to_str(ts_to_date(ts[0]))} → {date_to_str(ts_to_date(ts[-1]))}  ")
    w(f"**BTC hiện tại**: {fmt(cl[-1])}")
    w()

    # ══════════════════════════════════════════════════════
    # SECTION 1: CYCLE ANALYSIS
    # ══════════════════════════════════════════════════════
    print("\n▸ Analyzing cycles…")
    cycle_info = analyze_cycle_position(cl, ts)

    w("---")
    w()
    w("## 1. Phân tích chu kỳ BTC (Halving Cycles)")
    w()
    w("| Chu kỳ | Halving | Giá Halving | ATH | Giá ATH | Multiple | Tháng→ATH | Bear Bottom | Drawdown |")
    w("|--------|---------|-------------|-----|---------|----------|-----------|-------------|----------|")
    for name, info in cycle_info.items():
        dd_str = f"{info['drawdown_from_peak']:.0f}%" if info['drawdown_from_peak'] else "—"
        bottom_str = fmt(info['bottom_price']) if info['bottom_price'] else "—"
        bd_str = info['bottom_date'] if info['bottom_date'] else "—"
        w(f"| {name} | {info['halving_date']} | {fmt(info['halving_price'])} | "
          f"{info['peak_date']} | {fmt(info['peak_price'])} | "
          f"{info['peak_multiple']:.1f}x | {info['months_to_peak']:.0f}m | "
          f"{bottom_str} ({bd_str}) | {dd_str} |")
    w()

    # Current position
    proj = project_dca_2026_2027(cl, ts)
    w("### Vị trí hiện tại trong chu kỳ")
    w()
    w(f"- **BTC hiện tại**: {fmt(proj['current_price'])} ({proj['current_date']})")
    w(f"- **Tháng kể từ Halving 4**: {proj['months_since_halving']:.1f} tháng")
    w(f"- **ATH chu kỳ này**: {fmt(proj['ath_price'])} ({proj['ath_date']})")
    w(f"- **Drawdown từ ATH**: {proj['drawdown_from_ath']:.1f}%")
    w()

    w("### So sánh vị trí tương đương ở các chu kỳ trước")
    w()
    w(f"Tại ~{proj['months_since_halving']:.0f} tháng sau halving:")
    w()
    for cname, analog in proj["analogs"].items():
        w(f"**{cname}** ({analog['equiv_date']}, BTC = {fmt(analog['equiv_price'])})")
        w(f"- 12 tháng tiếp theo: Low {fmt(analog['next_12m_low'])} → High {fmt(analog['next_12m_high'])}")
        w(f"- DCA $10/ngày 12 tháng: avg cost {fmt(analog['dca_avg_cost'])}, "
          f"ROI {analog['dca_roi']:+.1f}%")
        w(f"- Smart DCA 12 tháng: avg cost {fmt(analog['smart_avg_cost'])}, "
          f"ROI {analog['smart_roi']:+.1f}%")
        w()

    print(f"  Months since halving 4: {proj['months_since_halving']:.1f}")
    print(f"  ATH: {fmt(proj['ath_price'])}  │  Drawdown: {proj['drawdown_from_ath']:.1f}%")

    # ══════════════════════════════════════════════════════
    # SECTION 2: DCA STRATEGY COMPARISON ACROSS SEASONS
    # ══════════════════════════════════════════════════════
    print("\n▸ Comparing DCA strategies across historical windows…")

    # Define key 12-month windows
    windows = [
        ("Bull 2017", "2017-01-01", "2017-12-31"),
        ("Bear 2018", "2018-01-01", "2018-12-31"),
        ("Recovery 2019", "2019-01-01", "2019-12-31"),
        ("Pre-bull 2020", "2020-01-01", "2020-12-31"),
        ("Bull 2021", "2021-01-01", "2021-12-31"),
        ("Bear 2022", "2022-01-01", "2022-12-31"),
        ("Recovery 2023", "2023-01-01", "2023-12-31"),
        ("Bull 2024", "2024-01-01", "2024-12-31"),
        ("Post-ATH 2025", "2025-01-01", "2025-12-31"),
    ]

    w("---")
    w()
    w("## 2. So sánh chiến lược DCA qua từng mùa")
    w()
    w("### Giá trung bình mua vào (avg cost) – $10/ngày hoặc tương đương")
    w()
    w("| Giai đoạn | BTC Start | BTC End | DCA Daily | DCA Weekly | Smart DCA | RSI DCA | Avg tốt nhất |")
    w("|-----------|-----------|---------|-----------|------------|-----------|---------|-------------|")

    for label, s_date, e_date in windows:
        si = find_idx(ts, s_date)
        ei = find_idx(ts, e_date)
        if si >= n or ei >= n or si >= ei:
            continue

        _, _, avg_d, _ = dca_fixed(cl, ts, si, ei, 10, "daily")
        _, _, avg_w, _ = dca_fixed(cl, ts, si, ei, 70, "weekly")
        _, _, avg_s, _ = dca_smart_dip(cl, ts, si, ei, 10, "daily")
        _, _, avg_r, _ = dca_rsi_based(cl, ts, si, ei, 10, "daily")

        avgs = {"Daily": avg_d, "Weekly": avg_w, "Smart": avg_s, "RSI": avg_r}
        best_name = min(avgs, key=avgs.get)

        w(f"| {label} | {fmt(cl[si])} | {fmt(cl[ei])} | "
          f"{fmt(avg_d)} | {fmt(avg_w)} | {fmt(avg_s)} | {fmt(avg_r)} | "
          f"**{best_name}** |")

    w()
    w("**Smart DCA**: Mua x3 khi giá <70% MA200, x2 khi <85%, x0.3 khi >150%  ")
    w("**RSI DCA**: Mua x3 khi RSI<25, x2 khi RSI<35, x0.3 khi RSI>80")
    w()

    # Detailed comparison table for ROI
    w("### ROI sau 12 tháng DCA (không bán)")
    w()
    w("| Giai đoạn | Fixed DCA ROI | Smart DCA ROI | Fixed Invested | Smart Invested |")
    w("|-----------|---------------|---------------|----------------|----------------|")

    for label, s_date, e_date in windows:
        si = find_idx(ts, s_date)
        ei = find_idx(ts, e_date)
        if si >= n or ei >= n or si >= ei:
            continue

        coins_d, inv_d, _, _ = dca_fixed(cl, ts, si, ei, 10, "daily")
        coins_s, inv_s, _, _ = dca_smart_dip(cl, ts, si, ei, 10, "daily")

        val_d = coins_d * cl[ei]
        val_s = coins_s * cl[ei]
        roi_d = (val_d / inv_d - 1) * 100 if inv_d > 0 else 0
        roi_s = (val_s / inv_s - 1) * 100 if inv_s > 0 else 0

        w(f"| {label} | {roi_d:+.1f}% | {roi_s:+.1f}% | {fmt(inv_d)} | {fmt(inv_s)} |")

    w()

    # ══════════════════════════════════════════════════════
    # SECTION 3: x5 / x10 ANALYSIS
    # ══════════════════════════════════════════════════════
    print("\n▸ Analyzing x5/x10 targets…")

    w("---")
    w()
    w("## 3. Phân tích mục tiêu x5 và x10")
    w()
    w("### Lịch sử: DCA 12 tháng → bao lâu đạt x5/x10?")
    w()
    w("| DCA Period | Avg Cost | x5 Target | x5 Reached? | x10 Target | x10 Reached? |")
    w("|------------|----------|-----------|-------------|------------|--------------|")

    for label, s_date, e_date in windows:
        si = find_idx(ts, s_date)
        ei = find_idx(ts, e_date)
        if si >= n or ei >= n or si >= ei:
            continue

        _, inv, avg, _ = dca_fixed(cl, ts, si, ei, 10, "daily")
        target_x5 = avg * 5
        target_x10 = avg * 10

        # Search forward for x5
        x5_date, x5_days, _ = find_x_multiple(cl, ts, si, ei, 10, "daily", 5)
        x10_date, x10_days, _ = find_x_multiple(cl, ts, si, ei, 10, "daily", 10)

        x5_str = f"✅ {x5_date} ({x5_days}d)" if x5_date else "❌ Chưa đạt"
        x10_str = f"✅ {x10_date} ({x10_days}d)" if x10_date else "❌ Chưa đạt"

        w(f"| {label} | {fmt(avg)} | {fmt(target_x5)} | {x5_str} | {fmt(target_x10)} | {x10_str} |")

    w()

    w("### Nhận xét x5/x10")
    w()
    w("- x5 thường đạt được khi DCA trong **bear market** (avg cost thấp → cần giá thấp hơn cho x5)")
    w("- x10 rất khó đạt trừ khi DCA rất sớm (2017-2019) hoặc trong bear bottom (2022)")
    w("- **Mua trong bear = cơ hội x5/x10 tốt nhất**")
    w()

    # ══════════════════════════════════════════════════════
    # SECTION 4: OPTIMAL DCA PLAN 03/2026 → 03/2027
    # ══════════════════════════════════════════════════════
    print("\n▸ Building optimal DCA plan for 03/2026 → 03/2027…")

    scenarios = project_scenarios(cl[-1], proj)

    w("---")
    w()
    w("## 4. Kế hoạch DCA tối ưu: 03/2026 → 03/2027")
    w()
    w(f"### Tình hình hiện tại")
    w()
    w(f"- BTC: {fmt(cl[-1])} (drawdown {proj['drawdown_from_ath']:.0f}% từ ATH {fmt(proj['ath_price'])})")
    w(f"- Vị trí: ~{proj['months_since_halving']:.0f} tháng sau Halving 4")
    w(f"- Tương đương: bear market đầu 2018 / giữa 2022 trong các chu kỳ trước")
    w()

    w("### Kịch bản giá BTC 12 tháng tới (dựa theo chu kỳ)")
    w()
    w("| Kịch bản | Mô tả | BTC Low | BTC High | BTC End | Avg DCA Cost | Smart DCA Cost |")
    w("|----------|-------|---------|----------|---------|-------------|----------------|")
    for sname, sdata in scenarios.items():
        w(f"| {sname} | {sdata['description']} | "
          f"{fmt(sdata['low'])} | {fmt(sdata['high'])} | "
          f"{fmt(sdata['end_price'])} | {fmt(sdata['avg_dca'])} | {fmt(sdata['smart_avg'])} |")
    w()

    # x5/x10 targets from projected avg costs
    w("### Target x5 và x10 từ giá DCA dự kiến")
    w()
    w("| Kịch bản | Avg Cost | x5 Target | x10 Target |")
    w("|----------|----------|-----------|------------|")
    for sname, sdata in scenarios.items():
        avg = sdata["avg_dca"]
        smart = sdata["smart_avg"]
        w(f"| {sname} (Fixed) | {fmt(avg)} | {fmt(avg * 5)} | {fmt(avg * 10)} |")
        w(f"| {sname} (Smart) | {fmt(smart)} | {fmt(smart * 5)} | {fmt(smart * 10)} |")
    w()

    # ══════════════════════════════════════════════════════
    # SECTION 5: SPECIFIC RECOMMENDATIONS
    # ══════════════════════════════════════════════════════

    w("---")
    w()
    w("## 5. Khuyến nghị cụ thể")
    w()
    w("### Chiến lược DCA tối ưu (Smart DCA – không FOMO)")
    w()
    w("| Điều kiện thị trường | Hành động | Mức mua |")
    w("|---------------------|-----------|---------|")
    w("| BTC < 70% MA200 (~bear bottom) | **MUA MẠNH** | 3x bình thường |")
    w("| BTC 70-85% MA200 (bear) | Mua nhiều hơn | 2x bình thường |")
    w("| BTC 85-95% MA200 (hồi phục) | Mua hơi nhiều | 1.5x bình thường |")
    w("| BTC 95-115% MA200 (bình thường) | Mua đều | 1x bình thường |")
    w("| BTC 115-130% MA200 (pump) | Giảm mua | 0.7x bình thường |")
    w("| BTC 130-150% MA200 (FOMO zone) | Mua ít | 0.5x bình thường |")
    w("| BTC > 150% MA200 (euphoria) | **HẠN CHẾ MUA** | 0.3x bình thường |")
    w()

    w("### Lịch mua cụ thể")
    w()
    w("| Tham số | Khuyến nghị | Lý do |")
    w("|---------|-------------|-------|")
    w("| **Tần suất** | **Hàng ngày $10** hoặc **Hàng tuần $70** | Daily cho avg cost thấp nhất |")
    w("| **Ngày mua** (nếu weekly) | **Thứ 2** hoặc **Thứ 6** | Historically lower prices |")
    w("| **Giờ mua** (UTC) | **14:00 UTC** (21:00 VN) | Từ kết quả tối ưu trước |")
    w("| **Ngân sách/tháng** | $300 base, linh hoạt $100-$900 | Theo Smart DCA multiplier |")
    w("| **Tổng 12 tháng dự kiến** | $3,650 - $6,000 | Tùy market condition |")
    w()

    w("### Kế hoạch chốt lời")
    w()

    # Calculate based on moderate scenario
    moderate_avg = None
    for sname, sdata in scenarios.items():
        if "trung bình" in sname.lower() or "Sideways" in sname:
            moderate_avg = sdata["smart_avg"]
            break
    if moderate_avg is None:
        moderate_avg = cl[-1] * 0.85

    w(f"Giả sử avg cost khoảng **{fmt(moderate_avg)}** (Smart DCA):")
    w()
    w("| Mục tiêu | BTC cần đạt | Khả năng | Chiến lược |")
    w("|----------|-------------|----------|------------|")
    w(f"| **x2** | {fmt(moderate_avg * 2)} | Cao (1-2 năm) | Chốt 20% portfolio |")
    w(f"| **x3** | {fmt(moderate_avg * 3)} | Trung bình (2-3 năm) | Chốt thêm 20% |")
    w(f"| **x5** | {fmt(moderate_avg * 5)} | Cần bull cycle mới | Chốt 30% portfolio |")
    w(f"| **x10** | {fmt(moderate_avg * 10)} | Cần 2+ chu kỳ | Chốt 30% còn lại |")
    w()
    w("### Quy tắc vàng")
    w()
    w("1. **KHÔNG FOMO**: Dùng Smart DCA, tự động giảm mua khi giá pump")
    w("2. **KHÔNG PANIC SELL**: Chỉ bán khi đạt target (x5/x10)")
    w("3. **MUA NHIỀU KHI SỢ**: Tăng gấp đôi/ba khi thị trường đỏ, RSI < 30")
    w("4. **KIÊN NHẪN**: x5 có thể mất 2-4 năm, x10 có thể mất 4-8 năm")
    w("5. **KHÔNG ALL-IN**: Luôn giữ reserve cash cho dip lớn")
    w()

    # Summary stats
    w("---")
    w()
    w("## 6. Tóm tắt so sánh mùa")
    w()
    w("| Metric | Bear 2018 | Bear 2022 | Hiện tại (03/2026) |")
    w("|--------|-----------|-----------|-------------------|")

    c2_info = cycle_info.get("Cycle 2 (2016-2020)", {})
    c3_info = cycle_info.get("Cycle 3 (2020-2024)", {})
    c4_info = cycle_info.get("Cycle 4 (2024-now)", {})

    w(f"| ATH trước đó | {fmt(c2_info.get('peak_price', 0))} | "
      f"{fmt(c3_info.get('peak_price', 0))} | {fmt(proj['ath_price'])} |")
    w(f"| Drawdown từ ATH | {c2_info.get('drawdown_from_peak', 0):.0f}% | "
      f"{c3_info.get('drawdown_from_peak', 0):.0f}% | {proj['drawdown_from_ath']:.0f}% |")
    w(f"| Bear bottom | {fmt(c2_info.get('bottom_price', 0))} | "
      f"{fmt(c3_info.get('bottom_price', 0))} | ? |")

    bear18_si = find_idx(ts, "2018-01-01")
    bear18_ei = find_idx(ts, "2018-12-31")
    _, _, avg_bear18, _ = dca_fixed(cl, ts, bear18_si, bear18_ei, 10, "daily")
    _, _, savg_bear18, _ = dca_smart_dip(cl, ts, bear18_si, bear18_ei, 10, "daily")

    bear22_si = find_idx(ts, "2022-01-01")
    bear22_ei = find_idx(ts, "2022-12-31")
    _, _, avg_bear22, _ = dca_fixed(cl, ts, bear22_si, bear22_ei, 10, "daily")
    _, _, savg_bear22, _ = dca_smart_dip(cl, ts, bear22_si, bear22_ei, 10, "daily")

    # Current 12-month from latest available
    cur_si = max(0, n - 365)
    _, _, avg_cur, _ = dca_fixed(cl, ts, cur_si, n - 1, 10, "daily")
    _, _, savg_cur, _ = dca_smart_dip(cl, ts, cur_si, n - 1, 10, "daily")

    w(f"| Avg DCA cost (12m) | {fmt(avg_bear18)} | {fmt(avg_bear22)} | {fmt(avg_cur)} (last 12m) |")
    w(f"| Smart DCA cost (12m) | {fmt(savg_bear18)} | {fmt(savg_bear22)} | {fmt(savg_cur)} (last 12m) |")
    w(f"| x5 target (DCA) | {fmt(avg_bear18 * 5)} | {fmt(avg_bear22 * 5)} | {fmt(avg_cur * 5)} |")
    w(f"| x10 target (DCA) | {fmt(avg_bear18 * 10)} | {fmt(avg_bear22 * 10)} | {fmt(avg_cur * 10)} |")
    w()

    # Check if x5/x10 from bear DCA was reached
    x5_18, x5d_18, _ = find_x_multiple(cl, ts, bear18_si, bear18_ei, 10, "daily", 5)
    x10_18, x10d_18, _ = find_x_multiple(cl, ts, bear18_si, bear18_ei, 10, "daily", 10)
    x5_22, x5d_22, _ = find_x_multiple(cl, ts, bear22_si, bear22_ei, 10, "daily", 5)
    x10_22, x10d_22, _ = find_x_multiple(cl, ts, bear22_si, bear22_ei, 10, "daily", 10)

    w(f"| x5 đạt? | {'✅ ' + str(x5_18) + ' (' + str(x5d_18) + 'd)' if x5_18 else '❌'} | "
      f"{'✅ ' + str(x5_22) + ' (' + str(x5d_22) + 'd)' if x5_22 else '❌'} | Đang chờ |")
    w(f"| x10 đạt? | {'✅ ' + str(x10_18) + ' (' + str(x10d_18) + 'd)' if x10_18 else '❌'} | "
      f"{'✅ ' + str(x10_22) + ' (' + str(x10d_22) + 'd)' if x10_22 else '❌'} | Đang chờ |")
    w()

    w("---")
    w()
    w(f"*Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*")

    # Write report
    report = "\n".join(lines)
    out_path = REPORTS / "dca_accumulation_plan.md"
    REPORTS.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        f.write(report)

    print(f"\n  ✔ Report saved: {out_path}")

    # Print summary
    print(f"\n{SEP}")
    print("  SUMMARY")
    print(SEP)
    print(f"  BTC hiện tại: {fmt(cl[-1])}")
    print(f"  Drawdown từ ATH: {proj['drawdown_from_ath']:.0f}%")
    print(f"  Tháng sau Halving 4: {proj['months_since_halving']:.0f}")
    print()
    print("  So sánh avg cost DCA 12 tháng:")
    print(f"    Bear 2018:    Fixed {fmt(avg_bear18)}  │  Smart {fmt(savg_bear18)}")
    print(f"    Bear 2022:    Fixed {fmt(avg_bear22)}  │  Smart {fmt(savg_bear22)}")
    print(f"    Last 12m:     Fixed {fmt(avg_cur)}     │  Smart {fmt(savg_cur)}")
    print()
    print("  Kịch bản 03/2026 → 03/2027:")
    for sname, sdata in scenarios.items():
        print(f"    {sname[:30]:<30} Avg DCA: {fmt(sdata['avg_dca'])}  │  "
              f"Smart: {fmt(sdata['smart_avg'])}")
    print()
    print(f"  x5 target (từ Smart DCA ~{fmt(moderate_avg)}): {fmt(moderate_avg * 5)}")
    print(f"  x10 target: {fmt(moderate_avg * 10)}")


if __name__ == "__main__":
    main()
