"""
DCA Bot TP=500% – Tích lũy BTC, chỉ chốt khi x6 avg cost
============================================================
- Vốn: $3,000 + $400/tháng × 12 = $7,800
- TP: 500% (bán khi price = avg_entry × 6)
- Grid search params tối ưu trên nhiều 12-month windows
- So sánh với Simple DCA cùng ngân sách
- Hướng dẫn cài OKX

Usage:
    python -m botv2.dca_bot_500pct
"""

import csv
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
from itertools import product
import time

BOTV2 = Path(__file__).resolve().parent
CACHE = BOTV2 / "data" / "cache" / "binance" / "spot"
REPORTS = BOTV2 / "reports"

FEE = 0.001  # 0.1% per trade
TP_PCT = 5.0  # 500%
CAPITAL = 3000.0
MONTHLY = 400.0
MONTHS = 12
TOTAL_BUDGET = CAPITAL + MONTHLY * MONTHS  # $7,800


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


def load_hourly():
    path = CACHE / "BTC_USDT_1h.csv"
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


def ts_to_dt(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def find_idx(ts, date_str):
    target_ms = int(datetime.strptime(date_str, "%Y-%m-%d")
                    .replace(tzinfo=timezone.utc).timestamp() * 1000)
    idx = np.searchsorted(ts, target_ms)
    return min(idx, len(ts) - 1)


# ═══════════════════════════════════════════════════════════════
#  BOT ENGINE (TP=500%, monthly injection, partial SO fill)
# ═══════════════════════════════════════════════════════════════

class AccBot:
    """DCA Spot Bot for accumulation. TP=500%, monthly capital injection."""

    def __init__(self, capital, init_order, so_base, max_so,
                 dev, vol_sc, step_sc):
        self.capital = float(capital)
        self.total_injected = float(capital)
        self.init_order = init_order
        self.so_base = so_base
        self.max_so = max_so
        self.dev = dev
        self.tp = TP_PCT
        self.vol_sc = vol_sc
        self.step_sc = step_sc

        self.so_trig = np.zeros(max_so)
        self.so_amt = np.zeros(max_so)
        self.so_filled = np.zeros(max_so, dtype=bool)

        self.in_pos = False
        self.coins = 0.0
        self.cost = 0.0
        self.avg_entry = 0.0
        self.cycle_coins_history = []  # coins from closed cycles (already sold)
        self.realized_pnl = 0.0

        self.cycles = 0
        self.cur_price = 0.0
        self.peak = float(capital)
        self.max_dd = 0.0

    def _build_so(self, ep):
        cum = 0.0
        step = self.dev
        for i in range(self.max_so):
            cum += step
            self.so_trig[i] = ep * (1.0 - cum)
            self.so_amt[i] = self.so_base * (self.vol_sc ** i)
            self.so_filled[i] = False
            step *= self.step_sc

    def _open(self, price):
        amt = min(self.init_order, self.capital)
        if amt < 2:
            return
        fee = amt * FEE
        self.coins = (amt - fee) / price
        self.cost = amt
        self.avg_entry = price
        self.capital -= amt
        self.in_pos = True
        self._build_so(price)

    def _close(self, sell_price):
        rev = self.coins * sell_price
        fee = rev * FEE
        net = rev - fee
        pnl = net - self.cost
        self.capital += net
        self.realized_pnl += pnl
        self.cycles += 1
        self.in_pos = False
        self.coins = 0.0
        self.cost = 0.0

    def inject(self, amount):
        self.capital += amount
        self.total_injected += amount

    def process(self, high, low, close):
        self.cur_price = close
        if not self.in_pos:
            self._open(close)
            return

        # Safety orders
        for i in range(self.max_so):
            if self.so_filled[i]:
                continue
            if low <= self.so_trig[i]:
                fp = self.so_trig[i]
                amt = min(self.so_amt[i], self.capital)
                if amt >= 2:
                    fee = amt * FEE
                    nc = (amt - fee) / fp
                    old_n = self.avg_entry * self.coins
                    self.coins += nc
                    self.avg_entry = (old_n + fp * nc) / self.coins
                    self.cost += amt
                    self.capital -= amt
                self.so_filled[i] = True

        # Take profit at 500%
        if self.coins > 0:
            tp_price = self.avg_entry * (1.0 + self.tp)
            if high >= tp_price:
                self._close(tp_price)
                return

        # Track drawdown on total value
        val = self.value()
        self.peak = max(self.peak, val)
        dd = (self.peak - val) / self.peak * 100 if self.peak > 0 else 0
        self.max_dd = max(self.max_dd, dd)

    def value(self):
        unr = self.coins * self.cur_price if self.in_pos else 0
        return self.capital + unr

    def btc_held(self):
        return self.coins if self.in_pos else 0

    def avg_cost(self):
        return self.cost / self.coins if self.coins > 0 else 0

    def so_coverage(self):
        """How deep (%) the safety orders cover from entry."""
        if not self.in_pos or self.max_so == 0:
            return 0
        last_so = self.so_trig[self.max_so - 1]
        return (1 - last_so / self.avg_entry) * 100 if self.avg_entry > 0 else 0

    def capital_deployed_pct(self):
        if self.total_injected == 0:
            return 0
        deployed = self.cost
        return deployed / self.total_injected * 100

    def stats(self):
        v = self.value()
        return {
            "value": v,
            "roi": (v / self.total_injected - 1) * 100 if self.total_injected > 0 else 0,
            "btc": self.btc_held(),
            "avg_cost": self.avg_cost(),
            "cost_basis": self.cost,
            "capital_idle": self.capital,
            "deployed_pct": self.capital_deployed_pct(),
            "cycles": self.cycles,
            "realized_pnl": self.realized_pnl,
            "max_dd": self.max_dd,
            "so_coverage": self.so_coverage(),
            "injected": self.total_injected,
            "tp_price": self.avg_entry * (1 + self.tp) if self.in_pos else 0,
            "in_pos": self.in_pos,
        }


# ═══════════════════════════════════════════════════════════════
#  SIMULATION HELPERS
# ═══════════════════════════════════════════════════════════════

def calc_orders(budget, max_so, vol_sc):
    """Auto-size init and SO for total budget. Min $50 per order."""
    so_sum = sum(vol_sc ** i for i in range(max_so))
    total_parts = 1.0 + so_sum
    unit = budget * 0.95 / total_parts
    return max(unit, 50.0), max(unit, 50.0)


def run_12m(ts, hi, lo, cl, start_idx, capital, monthly,
            init_order, so_base, max_so, dev, vol_sc, step_sc):
    """Run bot for 12 months with monthly injection."""
    bot = AccBot(capital, init_order, so_base, max_so, dev, vol_sc, step_sc)

    end_idx = min(start_idx + 365, len(cl))
    last_month = -1

    for i in range(start_idx, end_idx):
        dt = ts_to_dt(ts[i])
        m = dt.month
        if m != last_month:
            if last_month != -1:
                bot.inject(monthly)
            last_month = m
        bot.process(hi[i], lo[i], cl[i])

    return bot


def simple_dca_12m(ts, cl, start_idx, daily_amt):
    """Simple DCA for 12 months: buy every day."""
    coins = 0.0
    invested = 0.0
    end_idx = min(start_idx + 365, len(cl))

    for i in range(start_idx, end_idx):
        if cl[i] > 0:
            coins += daily_amt / cl[i]
            invested += daily_amt

    val = coins * cl[min(end_idx - 1, len(cl) - 1)]
    avg = invested / coins if coins > 0 else 0
    roi = (val / invested - 1) * 100 if invested > 0 else 0
    return coins, invested, avg, val, roi


# ═══════════════════════════════════════════════════════════════
#  GRID SEARCH
# ═══════════════════════════════════════════════════════════════

# 12-month windows at similar cycle positions + key periods
WINDOWS = [
    ("Bear start 2018-01", "2018-01-01"),
    ("Deep bear 2018-06", "2018-06-01"),
    ("Recovery 2019-01", "2019-01-01"),
    ("Cycle2 equiv 2019-07", "2019-07-01"),   # ~23m post halving 2
    ("Pre-bull 2020-03", "2020-03-01"),
    ("Bull 2021-01", "2021-01-01"),
    ("Bear start 2022-01", "2022-01-01"),
    ("Cycle3 equiv 2022-04", "2022-04-01"),   # ~23m post halving 3
    ("Deep bear 2022-06", "2022-06-01"),
    ("Recovery 2023-01", "2023-01-01"),
    ("Bull 2024-01", "2024-01-01"),
    ("Post-ATH 2025-01", "2025-01-01"),
]


def grid_search(ts, hi, lo, cl):
    devs = [0.02, 0.03, 0.05, 0.08, 0.10, 0.15]
    msos = [6, 8, 10, 12, 15]
    vss = [1.0, 1.2, 1.3, 1.5, 2.0]
    sss = [1.0, 1.2, 1.3, 1.5]

    # Filter impractical combos (need min $50 per order)
    combos = []
    for d, mso, vs, ss in product(devs, msos, vss, sss):
        so_sum = sum(vs ** i for i in range(mso))
        unit = TOTAL_BUDGET * 0.95 / (1 + so_sum)
        if unit >= 50:
            combos.append((d, mso, vs, ss))
    total = len(combos)
    print(f"  Grid: {total} combos × {len(WINDOWS)} windows = {total * len(WINDOWS)} runs")

    # Precompute window start indices
    win_idxs = []
    for label, date in WINDOWS:
        idx = find_idx(ts, date)
        if idx + 365 <= len(cl):
            win_idxs.append((label, idx))

    results = []
    t0 = time.time()

    for ci, (d, mso, vs, ss) in enumerate(combos):
        io, so = calc_orders(TOTAL_BUDGET, mso, vs)

        # Track coverage for this combo
        cum = 0
        step = d
        for _ in range(mso):
            cum += step
            step *= ss
        coverage = cum * 100  # % drop covered

        window_scores = []

        for label, start_idx in win_idxs:
            bot = run_12m(ts, hi, lo, cl, start_idx, CAPITAL, MONTHLY,
                          io, so, mso, d, vs, ss)
            s = bot.stats()

            # Score: BTC accumulated + ROI + capital efficiency
            btc_score = s["btc"] * 1000  # scale BTC to comparable range
            roi_score = max(s["roi"], -100)
            deploy_score = s["deployed_pct"] * 0.5
            cycle_bonus = s["cycles"] * 50  # bonus for completing cycles

            win_score = btc_score + roi_score * 0.3 + deploy_score + cycle_bonus
            window_scores.append(win_score)

        avg_score = np.mean(window_scores)
        min_score = np.min(window_scores)
        # Robust score: penalize high variance
        robust_score = avg_score * 0.6 + min_score * 0.4

        results.append({
            "dev": d, "mso": mso, "vs": vs, "ss": ss,
            "io": io, "so": so,
            "coverage": coverage,
            "score": robust_score,
            "avg_score": avg_score,
        })

        if (ci + 1) % 100 == 0:
            el = time.time() - t0
            eta = el / (ci + 1) * (total - ci - 1)
            print(f"    {ci+1}/{total}  ({el:.0f}s, ETA {eta:.0f}s)")

    results.sort(key=lambda x: -x["score"])
    print(f"  Done in {time.time()-t0:.1f}s")
    return results


# ═══════════════════════════════════════════════════════════════
#  DETAILED COMPARISON
# ═══════════════════════════════════════════════════════════════

def detailed_comparison(ts, hi, lo, cl, best_cfg):
    """Run bot vs simple DCA on each window, detailed results."""
    daily_dca_amt = TOTAL_BUDGET / 365  # ~$21.37/day to match total budget

    rows = []
    for label, date in WINDOWS:
        start = find_idx(ts, date)
        if start + 365 > len(cl):
            continue

        io, so = calc_orders(TOTAL_BUDGET, best_cfg["mso"], best_cfg["vs"])
        bot = run_12m(ts, hi, lo, cl, start, CAPITAL, MONTHLY,
                      io, so, best_cfg["mso"], best_cfg["dev"],
                      best_cfg["vs"], best_cfg["ss"])
        bs = bot.stats()

        coins_dca, inv_dca, avg_dca, val_dca, roi_dca = simple_dca_12m(
            ts, cl, start, daily_dca_amt)

        end_idx = min(start + 365, len(cl)) - 1
        rows.append({
            "label": label,
            "btc_start": cl[start],
            "btc_end": cl[end_idx],
            "btc_low": np.min(lo[start:end_idx+1]),
            "btc_high": np.max(hi[start:end_idx+1]),
            # Bot
            "bot_btc": bs["btc"],
            "bot_avg": bs["avg_cost"],
            "bot_value": bs["value"],
            "bot_roi": bs["roi"],
            "bot_cycles": bs["cycles"],
            "bot_deployed": bs["deployed_pct"],
            "bot_tp": bs["tp_price"],
            # DCA
            "dca_btc": coins_dca,
            "dca_avg": avg_dca,
            "dca_value": val_dca,
            "dca_roi": roi_dca,
        })

    return rows


# ═══════════════════════════════════════════════════════════════
#  FULL BACKTEST (2017-2026)
# ═══════════════════════════════════════════════════════════════

def full_backtest(ts, hi, lo, cl, cfg):
    """Run bot on full period with $3000 initial + $400/month."""
    io, so = calc_orders(TOTAL_BUDGET, cfg["mso"], cfg["vs"])
    bot = AccBot(CAPITAL, io, so, cfg["mso"], cfg["dev"], cfg["vs"], cfg["ss"])

    last_month = -1
    months = 0
    snapshots = []

    for i in range(len(cl)):
        dt = ts_to_dt(ts[i])
        m = (dt.year, dt.month)
        if m != last_month:
            if last_month != -1:
                bot.inject(MONTHLY)
                months += 1
            last_month = m
            # Monthly snapshot
            s = bot.stats()
            snapshots.append({
                "date": dt.strftime("%Y-%m"),
                "price": cl[i],
                "value": s["value"],
                "btc": s["btc"],
                "avg_cost": s["avg_cost"],
                "capital": s["capital_idle"],
                "cycles": s["cycles"],
                "injected": s["injected"],
            })
        bot.process(hi[i], lo[i], cl[i])

    return bot, snapshots


# ═══════════════════════════════════════════════════════════════
#  REPORT
# ═══════════════════════════════════════════════════════════════

def fmt(n, d=0):
    return f"${n:,.{d}f}"


def main():
    SEP = "═" * 80
    print(f"\n{SEP}")
    print("  DCA BOT TP=500%  │  $3,000 + $400/mo  │  Tối ưu cho OKX")
    print(SEP)

    ts, hi, lo, cl = load_daily()
    n = len(cl)
    print(f"\n▸ Data: {n:,} daily candles, "
          f"{ts_to_dt(ts[0]).strftime('%Y-%m-%d')} → {ts_to_dt(ts[-1]).strftime('%Y-%m-%d')}")
    print(f"  BTC: {fmt(cl[0])} → {fmt(cl[-1])}")
    print(f"  Budget: {fmt(CAPITAL)} initial + {fmt(MONTHLY)}/mo × {MONTHS} = {fmt(TOTAL_BUDGET)}")

    lines = []
    def w(s=""):
        lines.append(s)

    w("# DCA Bot TP=500% – Tối ưu cho OKX")
    w()
    w(f"**Chiến lược**: DCA Bot mua vào, chỉ chốt khi lời **500%** (giá = avg cost × 6)  ")
    w(f"**Vốn**: {fmt(CAPITAL)} ban đầu + {fmt(MONTHLY)}/tháng × {MONTHS} tháng = **{fmt(TOTAL_BUDGET)}**  ")
    w(f"**Data**: BTC/USDT daily, {ts_to_dt(ts[0]).strftime('%Y-%m-%d')} → "
      f"{ts_to_dt(ts[-1]).strftime('%Y-%m-%d')}  ")
    w(f"**BTC hiện tại**: {fmt(cl[-1])}")
    w()

    # ── Grid search ──────────────────────────────────
    print(f"\n{'─'*80}")
    print("  GRID SEARCH – tìm params tốt nhất qua nhiều 12-month windows")
    print(f"{'─'*80}")

    grid = grid_search(ts, hi, lo, cl)

    print(f"\n  TOP 10:")
    print(f"  {'#':>3} {'Dev':>5} {'MSO':>4} {'VS':>5} {'SS':>5} {'Cover':>7} │ {'Score':>8}")
    print(f"  {'─'*50}")
    for i, r in enumerate(grid[:10]):
        print(f"  {i+1:>3} {r['dev']*100:>4.0f}% {r['mso']:>4} {r['vs']:>4.1f}x "
              f"{r['ss']:>4.1f}x {r['coverage']:>5.0f}% │ {r['score']:>7.1f}")

    best = grid[0]
    io_best, so_best = calc_orders(TOTAL_BUDGET, best["mso"], best["vs"])

    print(f"\n  ★ BEST: dev={best['dev']*100:.0f}%  MSO={best['mso']}  "
          f"VS={best['vs']}x  SS={best['ss']}x  Coverage={best['coverage']:.0f}%")

    w("---")
    w()
    w("## 1. Thông số tối ưu (Grid Search)")
    w()
    w(f"Grid search qua {len(grid)} combinations × {len(WINDOWS)} windows thời kỳ khác nhau.")
    w()
    w("### TOP 5")
    w()
    w("| # | Dev | Max SO | Vol Scale | Step Scale | Coverage | Score |")
    w("|---|-----|--------|-----------|------------|----------|-------|")
    for i, r in enumerate(grid[:5]):
        w(f"| {i+1} | {r['dev']*100:.0f}% | {r['mso']} | {r['vs']:.1f}x | "
          f"{r['ss']:.1f}x | {r['coverage']:.0f}% | {r['score']:.1f} |")
    w()

    # ── Detailed comparison ──────────────────────────
    print(f"\n{'─'*80}")
    print("  DETAILED COMPARISON – Bot vs Simple DCA qua từng mùa")
    print(f"{'─'*80}")

    rows = detailed_comparison(ts, hi, lo, cl, best)

    w("---")
    w()
    w("## 2. So sánh Bot vs Simple DCA qua từng mùa")
    w()
    w("| Giai đoạn | BTC Range | Bot BTC | Bot Avg | Bot ROI | DCA BTC | DCA Avg | DCA ROI | Winner |")
    w("|-----------|-----------|---------|---------|---------|---------|---------|---------|--------|")

    bot_wins = 0
    dca_wins = 0
    for r in rows:
        winner = "**Bot**" if r["bot_roi"] > r["dca_roi"] else "**DCA**"
        if r["bot_roi"] > r["dca_roi"]:
            bot_wins += 1
        else:
            dca_wins += 1

        print(f"  {r['label']:<25} BTC {fmt(r['btc_start'])}-{fmt(r['btc_end'])}  │  "
              f"Bot: {r['bot_btc']:.4f} BTC, ROI {r['bot_roi']:+.0f}%  │  "
              f"DCA: {r['dca_btc']:.4f} BTC, ROI {r['dca_roi']:+.0f}%  │  {winner}")

        w(f"| {r['label']} | {fmt(r['btc_low'])}-{fmt(r['btc_high'])} | "
          f"{r['bot_btc']:.4f} | {fmt(r['bot_avg'])} | {r['bot_roi']:+.1f}% | "
          f"{r['dca_btc']:.4f} | {fmt(r['dca_avg'])} | {r['dca_roi']:+.1f}% | {winner} |")

    w()
    w(f"**Bot thắng {bot_wins}/{len(rows)} windows** | **DCA thắng {dca_wins}/{len(rows)} windows**")
    w()

    # ── Full backtest ────────────────────────────────
    print(f"\n{'─'*80}")
    print("  FULL BACKTEST 2017-2026")
    print(f"{'─'*80}")

    bot_full, snapshots = full_backtest(ts, hi, lo, cl, best)
    fs = bot_full.stats()

    # Simple DCA full period
    daily_equiv = MONTHLY / 30.44
    coins_full = 0.0
    inv_full = 0.0
    last_m = -1
    months_dca = 0
    for i in range(len(cl)):
        dt = ts_to_dt(ts[i])
        m = (dt.year, dt.month)
        if m != last_m:
            last_m = m
        if cl[i] > 0:
            coins_full += daily_equiv / cl[i]
            inv_full += daily_equiv
    val_full = coins_full * cl[-1]
    roi_full = (val_full / inv_full - 1) * 100

    print(f"  Bot:  Value {fmt(fs['value'])}  │  BTC {fs['btc']:.6f}  │  "
          f"Avg {fmt(fs['avg_cost'])}  │  Cycles {fs['cycles']}  │  ROI {fs['roi']:+.1f}%")
    print(f"  DCA:  Value {fmt(val_full)}  │  BTC {coins_full:.6f}  │  "
          f"Avg {fmt(inv_full/coins_full)}  │  ROI {roi_full:+.1f}%")
    print(f"  Bot injected: {fmt(fs['injected'])}  │  Idle capital: {fmt(fs['capital_idle'])}")

    w("---")
    w()
    w("## 3. Full Backtest 2017-2026 ($3,000 + $400/tháng)")
    w()
    w("| Metric | DCA Bot TP=500% | Simple DCA |")
    w("|--------|----------------|------------|")
    w(f"| Tổng nạp | {fmt(fs['injected'])} | {fmt(inv_full)} |")
    w(f"| Final Value | {fmt(fs['value'])} | {fmt(val_full)} |")
    w(f"| ROI | {fs['roi']:+.1f}% | {roi_full:+.1f}% |")
    w(f"| BTC held | {fs['btc']:.6f} | {coins_full:.6f} |")
    w(f"| Avg cost | {fmt(fs['avg_cost'])} | {fmt(inv_full/coins_full)} |")
    w(f"| Cycles hoàn thành | {fs['cycles']} | — |")
    w(f"| Realized PnL | {fmt(fs['realized_pnl'])} | — |")
    w(f"| Capital idle | {fmt(fs['capital_idle'])} | $0 |")
    w(f"| Max Drawdown | {fs['max_dd']:.1f}% | — |")
    w()

    if fs["in_pos"]:
        w(f"**Đang giữ position**: avg cost {fmt(fs['avg_cost'])}, "
          f"TP tại {fmt(fs['tp_price'])}")
        w()

    # Cycle history from snapshots
    w("### Timeline (monthly snapshots)")
    w()
    w("| Tháng | BTC Price | Bot Value | BTC Held | Avg Cost | Cycles | Tổng nạp |")
    w("|-------|-----------|-----------|----------|----------|--------|---------|")
    for snap in snapshots[::6]:  # every 6 months
        w(f"| {snap['date']} | {fmt(snap['price'])} | {fmt(snap['value'])} | "
          f"{snap['btc']:.4f} | {fmt(snap['avg_cost'])} | "
          f"{snap['cycles']} | {fmt(snap['injected'])} |")
    # Always include last
    if snapshots:
        snap = snapshots[-1]
        w(f"| {snap['date']} | {fmt(snap['price'])} | {fmt(snap['value'])} | "
          f"{snap['btc']:.4f} | {fmt(snap['avg_cost'])} | "
          f"{snap['cycles']} | {fmt(snap['injected'])} |")
    w()

    # ── Projection for 03/2026 → 03/2027 ────────────
    print(f"\n{'─'*80}")
    print("  PROJECTION 03/2026 → 03/2027")
    print(f"{'─'*80}")

    # Use cycle-equivalent windows for projection
    equiv_windows = [
        ("Cycle2 equiv (2019-07)", "2019-07-01"),
        ("Cycle3 equiv (2022-04)", "2022-04-01"),
    ]

    w("---")
    w()
    w("## 4. Dự phóng 03/2026 → 03/2027")
    w()
    w(f"BTC hiện tại: {fmt(cl[-1])}, drawdown ~43% từ ATH.  ")
    w(f"Vị trí: ~23 tháng sau Halving 4 → tương đương mid-2019 hoặc 04/2022.")
    w()

    w("### Kịch bản dựa trên cycle tương đương")
    w()

    for label, date in equiv_windows:
        start = find_idx(ts, date)
        end_idx = min(start + 365, len(cl)) - 1
        start_price = cl[start]
        end_price = cl[end_idx]
        low = np.min(lo[start:end_idx+1])
        high = np.max(hi[start:end_idx+1])

        # Price ratios to project
        ratio = cl[-1] / start_price
        proj_low = low * ratio
        proj_high = high * ratio
        proj_end = end_price * ratio

        # Bot simulation at equivalent
        io_b, so_b = calc_orders(TOTAL_BUDGET, best["mso"], best["vs"])
        bot_eq = run_12m(ts, hi, lo, cl, start, CAPITAL, MONTHLY,
                         io_b, so_b, best["mso"], best["dev"],
                         best["vs"], best["ss"])
        bs_eq = bot_eq.stats()

        # Project avg cost
        proj_avg = bs_eq["avg_cost"] * ratio

        w(f"**{label}**")
        w(f"- BTC lúc đó: {fmt(start_price)} → {fmt(end_price)} (Low {fmt(low)}, High {fmt(high)})")
        w(f"- Projected BTC: {fmt(cl[-1])} → ~{fmt(proj_end)} (Low ~{fmt(proj_low)}, High ~{fmt(proj_high)})")
        w(f"- Bot avg cost (projected): ~{fmt(proj_avg)}")
        w(f"- Bot ROI 12m: {bs_eq['roi']:+.1f}%")
        w(f"- Bot cycles completed: {bs_eq['cycles']}")
        w(f"- x5 target: ~{fmt(proj_avg * 5)}")
        w(f"- x10 target: ~{fmt(proj_avg * 10)}")
        w()

        print(f"  {label}: Projected avg cost ~{fmt(proj_avg)}, "
              f"ROI {bs_eq['roi']:+.1f}%, x5 target ~{fmt(proj_avg * 5)}")

    # ── OKX Setup ────────────────────────────────────
    w("---")
    w()
    w("## 5. Hướng dẫn cài đặt OKX")
    w()
    w("### Đường dẫn: Trade → Trading Bots → DCA (Spot)")
    w()

    # Calculate SO trigger prices from current BTC price
    entry = cl[-1]
    so_triggers = []
    cum = 0
    step = best["dev"]
    for i in range(best["mso"]):
        cum += step
        trigger = entry * (1 - cum)
        amount = so_best * (best["vs"] ** i)
        so_triggers.append((i + 1, cum * 100, trigger, amount))
        step *= best["ss"]

    w("| Tham số OKX | Giá trị | Ghi chú |")
    w("|-------------|---------|---------|")
    w(f"| **Pair** | BTC/USDT | — |")
    w(f"| **Direction** | Buy Low (Long) | — |")
    w(f"| **Price deviation** | **{best['dev']*100:.0f}%** | Bước giá mỗi SO |")
    w(f"| **Take profit** | **500%** | Chốt khi avg × 6 |")
    w(f"| **Max safety orders** | **{best['mso']}** | — |")
    w(f"| **Vol. scale** | **{best['vs']:.1f}x** | Mua nhiều hơn ở giá thấp |")
    w(f"| **Step scale** | **{best['ss']:.1f}x** | Giãn khoảng cách SO |")
    w(f"| **Initial order** | **{fmt(io_best)}** | — |")
    w(f"| **Safety order** | **{fmt(so_best)}** | Base amount |")
    w(f"| **Stop loss** | **Không** | Tích lũy dài hạn |")
    w(f"| **Vốn ban đầu** | **{fmt(CAPITAL)}** | — |")
    w(f"| **Nạp thêm** | **{fmt(MONTHLY)}/tháng** | Thêm vào bot mỗi tháng |")
    w()

    w("### Chi tiết Safety Orders (giả sử entry tại BTC = {})".format(fmt(entry)))
    w()
    w("| SO # | Drop từ entry | Trigger Price | Amount | Tổng tích lũy |")
    w("|------|-------------|---------------|--------|---------------|")
    w(f"| Init | 0% | {fmt(entry)} | {fmt(io_best)} | {fmt(io_best)} |")
    running = io_best
    for i, pct, trig, amt in so_triggers:
        running += amt
        w(f"| SO {i} | -{pct:.1f}% | {fmt(trig)} | {fmt(amt)} | {fmt(running)} |")
    w()
    w(f"**Tổng vốn cần nếu tất cả SO filled**: {fmt(running)}")
    w(f"  → Vốn ban đầu $3,000 cover đến ~SO {sum(1 for _, _, _, a in so_triggers if running <= CAPITAL + MONTHLY * 3)}")
    w(f"  → Monthly injection $400 fund thêm các SO sâu hơn")
    w()

    w("### Lịch nạp vốn")
    w()
    w("| Tháng | Nạp | Tổng nạp | Ghi chú |")
    w("|-------|-----|---------|---------|")
    total = CAPITAL
    w(f"| 03/2026 | {fmt(CAPITAL)} | {fmt(total)} | Khởi tạo bot |")
    for m in range(1, 13):
        total += MONTHLY
        month_name = f"{(2 + m) % 12 + 1:02d}/{2026 + (2 + m) // 12}"
        if m <= 3:
            note = "Fund thêm SO sâu"
        elif m <= 6:
            note = "Reserve cho dip"
        else:
            note = "Tích lũy thêm"
        w(f"| {month_name} | {fmt(MONTHLY)} | {fmt(total)} | {note} |")
    w()

    # ── Key targets ──────────────────────────────────
    w("---")
    w()
    w("## 6. Mục tiêu chốt lời")
    w()

    # Estimate avg cost range
    avg_costs = [r["bot_avg"] for r in rows if r["bot_avg"] > 0]
    avg_costs_scaled = [a * cl[-1] / cl[find_idx(ts, WINDOWS[i][1])]
                        for i, a in enumerate(avg_costs) if i < len(rows)]
    if avg_costs_scaled:
        low_avg = min(avg_costs_scaled)
        high_avg = max(avg_costs_scaled)
        mid_avg = np.median(avg_costs_scaled)
    else:
        mid_avg = cl[-1] * 0.7
        low_avg = cl[-1] * 0.5
        high_avg = cl[-1] * 0.9

    w(f"Avg cost dự kiến: **{fmt(low_avg)}** – **{fmt(high_avg)}** "
      f"(median ~{fmt(mid_avg)})")
    w()
    w("| Mục tiêu | BTC cần đạt (từ median) | Thời gian dự kiến |")
    w("|----------|------------------------|-------------------|")
    w(f"| **x2** | {fmt(mid_avg * 2)} | 1-2 năm |")
    w(f"| **x3** | {fmt(mid_avg * 3)} | 2-3 năm |")
    w(f"| **x5** | {fmt(mid_avg * 5)} | 3-5 năm (next bull) |")
    w(f"| **x6 (TP 500%)** | {fmt(mid_avg * 6)} | Bot tự chốt |")
    w(f"| **x10** | {fmt(mid_avg * 10)} | 5-8 năm |")
    w()

    w("### So sánh nhanh")
    w()
    w("| | DCA Bot TP=500% | Simple DCA |")
    w("|---|---|---|")
    w("| Cách hoạt động | Tự mua nhiều khi giá giảm, chốt khi x6 | Mua đều mỗi ngày |")
    w("| Ưu điểm | Avg cost thấp hơn (mua mạnh lúc dip) | Đơn giản, deploy 100% vốn |")
    w("| Nhược điểm | Vốn nhàn rỗi khi thị trường ổn | Không tận dụng dip |")
    w("| Phù hợp | Bear/sideways market | Mọi market condition |")
    w("| Chốt lời | Tự động khi x6 | Phải chốt thủ công |")
    w()

    w("### Khuyến nghị kết hợp")
    w()
    w(f"- **{fmt(CAPITAL)}** → OKX DCA Bot TP=500% (thông số ở trên)")
    w(f"- **{fmt(MONTHLY)}/tháng**: Chia đôi")
    w(f"  - **$200** → Nạp thêm vào Bot (fund SO sâu)")
    w(f"  - **$200** → Simple DCA (Recurring Buy) để deploy ngay")
    w("- Cách này đảm bảo **100% vốn luôn làm việc** thay vì idle trong bot")
    w()

    w("---")
    w()
    w(f"*Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*")

    # Write report
    report = "\n".join(lines)
    out_path = REPORTS / "dca_bot_500pct.md"
    REPORTS.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        f.write(report)
    print(f"\n  ✔ Report: {out_path}")

    # Summary
    print(f"\n{SEP}")
    print("  SUMMARY")
    print(SEP)
    print(f"  Best config: dev={best['dev']*100:.0f}% MSO={best['mso']} "
          f"VS={best['vs']}x SS={best['ss']}x (coverage {best['coverage']:.0f}%)")
    print(f"  Init order: {fmt(io_best)}  │  SO base: {fmt(so_best)}")
    print(f"  Bot wins {bot_wins}/{len(rows)} windows vs Simple DCA")
    print()


if __name__ == "__main__":
    main()
