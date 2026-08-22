"""
Binance DCA Spot Bot – Backtest & Comparison with Simple DCA
============================================================
Simulates the Binance DCA Spot bot on BTC/USDT (screenshot settings).
Compares with simple DCA ($10/day) and Buy & Hold.
Grid-searches optimal parameters.
Projects to 03/2027 and 12/2027.

Usage:
    python -m botv2.backtest_dca_spot_bot
"""

import csv
import math
import time
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from itertools import product

BOTV2 = Path(__file__).resolve().parent
CACHE = BOTV2 / "data" / "cache" / "binance" / "spot"
REPORTS = BOTV2 / "reports"

FEE = 0.001  # 0.1% per trade (Binance spot default)


# ═══════════════════════════════════════════════════════════════════
#  DATA
# ═══════════════════════════════════════════════════════════════════

def load_candles(tf="1h"):
    path = CACHE / f"BTC_USDT_{tf}.csv"
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


# ═══════════════════════════════════════════════════════════════════
#  DCA SPOT BOT ENGINE
# ═══════════════════════════════════════════════════════════════════

class DCASpotBot:
    """
    Binance DCA Spot Bot (no leverage).
    1. Buy initial_order at market price
    2. Safety orders on price_deviation drops
    3. Sell all when avg_entry × (1 + tp_pct) reached
    4. Repeat
    """
    __slots__ = (
        "capital", "init_cap", "init_order", "so_base", "max_so",
        "dev", "tp", "vol_sc", "step_sc", "sl",
        "in_pos", "coins", "cost", "avg_entry",
        "so_trig", "so_amt", "so_filled",
        "cycles", "wins", "losses", "tot_profit", "tot_loss",
        "max_dd", "peak", "cur_price",
        "cycle_bars", "longest_cycle",
        "earn_rate_per_bar",
    )

    def __init__(self, capital, initial_order, safety_order, max_so,
                 price_deviation, tp_pct,
                 volume_scale=1.0, step_scale=1.0, stop_loss=None,
                 earn_apr=0.0, bar_hours=1):
        self.capital = float(capital)
        self.init_cap = float(capital)
        self.init_order = initial_order
        self.so_base = safety_order
        self.max_so = max_so
        self.dev = price_deviation
        self.tp = tp_pct
        self.vol_sc = volume_scale
        self.step_sc = step_scale
        self.sl = stop_loss

        self.so_trig = np.zeros(max_so)
        self.so_amt = np.zeros(max_so)
        self.so_filled = np.zeros(max_so, dtype=bool)

        self.in_pos = False
        self.coins = 0.0
        self.cost = 0.0
        self.avg_entry = 0.0

        self.cycles = 0
        self.wins = 0
        self.losses = 0
        self.tot_profit = 0.0
        self.tot_loss = 0.0
        self.max_dd = 0.0
        self.peak = float(capital)
        self.cur_price = 0.0
        self.cycle_bars = 0
        self.longest_cycle = 0

        self.earn_rate_per_bar = earn_apr / (365 * 24 / bar_hours) if earn_apr else 0.0

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
        if amt < 2.0:
            return
        fee = amt * FEE
        self.coins = (amt - fee) / price
        self.cost = amt
        self.avg_entry = price
        self.capital -= amt
        self.in_pos = True
        self.cycle_bars = 0
        self._build_so(price)

    def _close(self, sell_price):
        rev = self.coins * sell_price
        fee = rev * FEE
        net = rev - fee
        pnl = net - self.cost

        self.capital += net
        self.cycles += 1
        if pnl >= 0:
            self.wins += 1
            self.tot_profit += pnl
        else:
            self.losses += 1
            self.tot_loss += abs(pnl)

        self.peak = max(self.peak, self.capital)
        dd = (self.peak - self.capital) / self.peak * 100.0
        if dd > self.max_dd:
            self.max_dd = dd
        self.longest_cycle = max(self.longest_cycle, self.cycle_bars)

        self.in_pos = False
        self.coins = 0.0
        self.cost = 0.0
        self.avg_entry = 0.0

    def process(self, high, low, close):
        self.cur_price = close

        # Earn on idle capital
        if self.earn_rate_per_bar and self.capital > 0:
            self.capital += self.capital * self.earn_rate_per_bar

        if not self.in_pos:
            self._open(close)
            return

        self.cycle_bars += 1

        # Safety orders
        for i in range(self.max_so):
            if self.so_filled[i]:
                continue
            if low <= self.so_trig[i]:
                fp = self.so_trig[i]
                amt = min(self.so_amt[i], self.capital)
                if amt >= 2.0:
                    fee = amt * FEE
                    nc = (amt - fee) / fp
                    old_n = self.avg_entry * self.coins
                    self.coins += nc
                    self.avg_entry = (old_n + fp * nc) / self.coins
                    self.cost += amt
                    self.capital -= amt
                self.so_filled[i] = True

        # Take profit
        if self.coins > 0:
            tp_p = self.avg_entry * (1.0 + self.tp)
            if high >= tp_p:
                self._close(tp_p)
                return

        # Stop loss
        if self.sl and self.coins > 0:
            sl_p = self.avg_entry * (1.0 - self.sl)
            if low <= sl_p:
                self._close(sl_p)

    def value(self):
        unr = self.coins * self.cur_price if self.in_pos else 0.0
        return self.capital + unr

    def unrealized(self):
        if not self.in_pos:
            return 0.0
        return self.coins * self.cur_price - self.cost

    def stats(self):
        v = self.value()
        return {
            "final": v,
            "roi": (v / self.init_cap - 1) * 100 if self.init_cap > 0 else 0,
            "pnl": self.tot_profit - self.tot_loss + self.unrealized(),
            "cycles": self.cycles,
            "wins": self.wins,
            "losses": self.losses,
            "wr": self.wins / max(self.cycles, 1) * 100,
            "pf": self.tot_profit / max(self.tot_loss, 0.01),
            "dd": self.max_dd,
            "longest": self.longest_cycle,
            "in_pos": self.in_pos,
            "unr": self.unrealized(),
        }


# ═══════════════════════════════════════════════════════════════════
#  SIMULATION HELPERS
# ═══════════════════════════════════════════════════════════════════

def run_bot(hi, lo, cl, capital, init_order, so_base, max_so,
            dev, tp, vol_sc=1.0, step_sc=1.0, sl=None,
            earn_apr=0.0, bar_hours=1):
    bot = DCASpotBot(capital, init_order, so_base, max_so,
                     dev, tp, vol_sc, step_sc, sl,
                     earn_apr, bar_hours)
    for i in range(len(cl)):
        bot.process(hi[i], lo[i], cl[i])
    return bot


def run_bot_daily_inject(ts, hi, lo, cl, daily_amt,
                         max_so, dev, tp, vol_sc=1.0, step_sc=1.0,
                         bar_hours=1):
    """Bot that receives $daily_amt each day with dynamic order sizing."""
    # Start with enough for first cycle
    start_cap = daily_amt * 7
    init_io, init_so = calc_order_sizes(start_cap, max_so, vol_sc)
    bot = DCASpotBot(0.0, init_io, init_so, max_so,
                     dev, tp, vol_sc, step_sc,
                     earn_apr=0.0, bar_hours=bar_hours)
    last_day = -1
    total_injected = 0.0

    for i in range(len(cl)):
        day = int(ts[i] // 86_400_000)
        if day != last_day:
            bot.capital += daily_amt
            total_injected += daily_amt
            # Dynamic resize when not in position
            if not bot.in_pos:
                avail = bot.capital
                if avail > 50:
                    new_io, new_so = calc_order_sizes(avail, max_so, vol_sc)
                    bot.init_order = new_io
                    bot.so_base = new_so
            last_day = day
        bot.process(hi[i], lo[i], cl[i])

    bot.init_cap = total_injected
    return bot, total_injected


def simple_dca(ts, cl, daily_amt, bar_hours=1):
    """Simple DCA: buy $daily_amt of BTC at close every day."""
    coins = 0.0
    invested = 0.0
    last_day = -1
    bars_per_day = 24 // bar_hours
    bar_count = 0

    for i in range(len(cl)):
        day = int(ts[i] // 86_400_000)
        if day != last_day:
            if cl[i] > 0:
                coins += daily_amt / cl[i]
                invested += daily_amt
            last_day = day

    final = coins * cl[-1]
    roi = (final / invested - 1) * 100 if invested > 0 else 0
    return final, invested, roi, coins


def buy_hold(cl, capital):
    coins = capital / cl[0]
    final = coins * cl[-1]
    roi = (final / capital - 1) * 100
    return final, roi


# ═══════════════════════════════════════════════════════════════════
#  GRID SEARCH
# ═══════════════════════════════════════════════════════════════════

def calc_order_sizes(capital, max_so, vol_sc):
    """Auto-size orders so total ≈ 95% of capital."""
    so_sum = sum(vol_sc ** i for i in range(max_so))
    total_parts = 1.0 + so_sum
    unit = capital * 0.95 / total_parts
    return unit, unit  # init_order ≈ safety_order base


def grid_search(hi, lo, cl, capital, verbose=True):
    devs = [0.008, 0.01, 0.012, 0.015, 0.02, 0.025, 0.03]
    tps = [0.008, 0.01, 0.012, 0.015, 0.02, 0.025, 0.03]
    msos = [4, 6, 8, 10, 12]
    vss = [1.0, 1.05, 1.1, 1.2, 1.3]
    sss = [1.0, 1.1, 1.2, 1.3]

    combos = list(product(devs, tps, msos, vss, sss))
    total = len(combos)
    if verbose:
        print(f"  Grid: {total} combinations…")

    results = []
    t0 = time.time()

    for idx, (d, t, m, vs, ss) in enumerate(combos):
        io, so = calc_order_sizes(capital, m, vs)
        bot = run_bot(hi, lo, cl, capital, io, so, m, d, t, vs, ss)
        s = bot.stats()

        score = (s["roi"] * 0.35
                 + (100 - min(s["dd"], 100)) * 0.25
                 + min(s["wr"], 99) * 0.2
                 + min(s["pf"], 10) * 5 * 0.2)
        if s["dd"] > 60:
            score -= (s["dd"] - 60) * 3
        if s["cycles"] < 10:
            score -= 50

        results.append({**s, "dev": d, "tp": t, "mso": m, "vs": vs, "ss": ss,
                        "io": io, "so": so, "score": score})

        if verbose and (idx + 1) % 500 == 0:
            el = time.time() - t0
            eta = el / (idx + 1) * (total - idx - 1)
            print(f"    {idx+1}/{total}  ({el:.0f}s, ETA {eta:.0f}s)")

    results.sort(key=lambda x: -x["score"])
    if verbose:
        print(f"  Done in {time.time()-t0:.1f}s")
    return results


# ═══════════════════════════════════════════════════════════════════
#  PROJECTION
# ═══════════════════════════════════════════════════════════════════

def calc_monthly_returns(ts, cl):
    """Monthly close-to-close returns."""
    by_month = {}
    for i in range(len(ts)):
        dt = datetime.utcfromtimestamp(ts[i] / 1000)
        key = (dt.year, dt.month)
        by_month[key] = cl[i]
    months = sorted(by_month)
    rets = []
    for i in range(1, len(months)):
        rets.append(by_month[months[i]] / by_month[months[i-1]] - 1)
    return np.array(rets)


def project(current_price, monthly_rets, months_ahead):
    """3-scenario projection using historical monthly return distribution."""
    avg = np.mean(monthly_rets)
    med = np.median(monthly_rets)
    std = np.std(monthly_rets)
    p25 = np.percentile(monthly_rets, 25)
    p75 = np.percentile(monthly_rets, 75)

    scenarios = {
        "bearish":  p25,
        "moderate": med,
        "bullish":  p75,
    }
    out = {}
    for name, mr in scenarios.items():
        projected_price = current_price * ((1 + mr) ** months_ahead)
        out[name] = {"price": projected_price, "mr": mr}
    return out, {"avg": avg, "med": med, "std": std, "p25": p25, "p75": p75}


# ═══════════════════════════════════════════════════════════════════
#  REPORT
# ═══════════════════════════════════════════════════════════════════

def fmt(n, decimals=0, prefix="$"):
    if decimals == 0:
        return f"{prefix}{n:,.0f}"
    return f"{prefix}{n:,.{decimals}f}"


def write_report(path, **kw):
    REPORTS.mkdir(parents=True, exist_ok=True)

    bs = kw["bot_stats"]
    os_ = kw["opt_stats"]
    oc = kw["opt_cfg"]
    ds = kw["dca_stats"]
    hs = kw["hold_stats"]
    bi = kw["bot_inj"]
    bi_inv = kw["bot_inj_invested"]
    sett = kw["settings"]
    cur = kw["current_price"]
    start_p = kw["start_price"]
    start_d = kw["start_date"]
    end_d = kw["end_date"]
    cap = kw["capital"]
    proj12 = kw["proj12"]
    proj21 = kw["proj21"]
    mstats = kw["mstats"]

    bis = bi.stats()

    # DCA projections
    dca_coins = ds["coins"]
    dca_inv = ds["invested"]
    dca_val = ds["final"]

    lines = []
    def w(s=""):
        lines.append(s)

    w(f"# DCA Spot Bot vs Simple DCA – Backtest & Dự phóng")
    w()
    w(f"**Period**: {start_d} → {end_d}  ")
    w(f"**BTC**: {fmt(start_p)} → {fmt(cur)}  ")
    w()
    w("---")
    w()

    # ── Section 1: Screenshot bot ────────────────────────
    w("## 1. Binance DCA Spot Bot (Cài đặt Screenshot)")
    w()
    w("| Tham số | Giá trị |")
    w("|---------|---------|")
    w(f"| Bước giá (Price Dev) | {sett['dev']*100:.1f}% |")
    w(f"| TP mỗi kỳ | {sett['tp']*100:.1f}% |")
    w(f"| Lệnh an toàn max | {sett['mso']} |")
    w(f"| Volume Scale | {sett['vs']:.2f}x |")
    w(f"| Step Scale | {sett['ss']:.2f}x |")
    w(f"| Vốn ban đầu | {fmt(cap)} |")
    w(f"| Lệnh ban đầu | {fmt(sett['io'], 0)} |")
    w(f"| Lệnh an toàn | {fmt(sett['so'], 0)} |")
    w()
    w("### Kết quả")
    w()
    w("| Metric | Giá trị |")
    w("|--------|---------|")
    w(f"| Final Value | {fmt(bs['final'], 2)} |")
    w(f"| ROI | {bs['roi']:+.1f}% |")
    w(f"| Total PnL | {fmt(bs['pnl'], 2, '$')} |")
    w(f"| Cycles | {bs['cycles']:,} |")
    w(f"| Win Rate | {bs['wr']:.1f}% |")
    w(f"| Profit Factor | {bs['pf']:.2f} |")
    w(f"| Max Drawdown | {bs['dd']:.1f}% |")
    w(f"| Longest Cycle | {bs['longest']} bars (~{bs['longest']//24} ngày) |")
    if bs["in_pos"]:
        w(f"| Unrealized PnL | {fmt(bs['unr'], 2, '$')} |")
    w()

    # ── Section 2: Optimized bot ─────────────────────────
    w("---")
    w()
    w("## 2. DCA Bot Tối ưu (Grid Search)")
    w()
    w("| Tham số | Giá trị |")
    w("|---------|---------|")
    w(f"| Bước giá | {oc['dev']*100:.1f}% |")
    w(f"| TP mỗi kỳ | {oc['tp']*100:.1f}% |")
    w(f"| Lệnh an toàn max | {oc['mso']} |")
    w(f"| Volume Scale | {oc['vs']:.2f}x |")
    w(f"| Step Scale | {oc['ss']:.2f}x |")
    w(f"| Lệnh ban đầu | {fmt(oc['io'], 0)} |")
    w(f"| Lệnh an toàn | {fmt(oc['so'], 0)} |")
    w()
    w("### Kết quả (1h data)")
    w()
    w("| Metric | Giá trị |")
    w("|--------|---------|")
    w(f"| Final Value | {fmt(os_['final'], 2)} |")
    w(f"| ROI | {os_['roi']:+.1f}% |")
    w(f"| Cycles | {os_['cycles']:,} |")
    w(f"| Win Rate | {os_['wr']:.1f}% |")
    w(f"| Profit Factor | {os_['pf']:.2f} |")
    w(f"| Max Drawdown | {os_['dd']:.1f}% |")
    w()

    # ── Section 3: Comparison ────────────────────────────
    w("---")
    w()
    w("## 3. So sánh tổng hợp")
    w()
    w("### A. Vốn cố định $350")
    w()
    w("| Chiến lược | Vốn đầu | Final Value | ROI | Ghi chú |")
    w("|------------|---------|-------------|-----|---------|")
    w(f"| DCA Bot (screenshot) | {fmt(cap)} | {fmt(bs['final'])} | {bs['roi']:+.1f}% | {bs['cycles']} cycles, WR {bs['wr']:.0f}% |")
    w(f"| DCA Bot (tối ưu) | {fmt(cap)} | {fmt(os_['final'])} | {os_['roi']:+.1f}% | {os_['cycles']} cycles, WR {os_['wr']:.0f}% |")
    w(f"| Buy & Hold | {fmt(cap)} | {fmt(hs['final'])} | {hs['roi']:+.1f}% | Mua 1 lần, giữ |")
    w()
    w("### B. Đầu tư $10/ngày (so sánh cùng ngân sách)")
    w()
    w("| Chiến lược | Tổng đầu tư | Final Value | ROI | Ghi chú |")
    w("|------------|-------------|-------------|-----|---------|")
    w(f"| Simple DCA | {fmt(dca_inv)} | {fmt(dca_val)} | {ds['roi']:+.1f}% | Mua mỗi ngày, không bán |")
    w(f"| DCA Bot + $10/ngày | {fmt(bi_inv)} | {fmt(bis['final'])} | {bis['roi']:+.1f}% | Bot trade + nạp $10/ngày |")
    w()

    # ── Section 4: Projection ────────────────────────────
    w("---")
    w()
    w("## 4. Dự phóng (Projection)")
    w()
    w(f"BTC monthly return: avg={mstats['avg']*100:.1f}%, median={mstats['med']*100:.1f}%, "
      f"std={mstats['std']*100:.1f}%")
    w()
    w("### BTC Price Forecast")
    w()
    w("| Kịch bản | Monthly Return | BTC 03/2027 | BTC 12/2027 |")
    w("|----------|---------------|-------------|-------------|")
    for sc in ["bearish", "moderate", "bullish"]:
        p12 = proj12[sc]
        p21 = proj21[sc]
        w(f"| {sc.capitalize()} | {p12['mr']*100:+.1f}%/tháng | {fmt(p12['price'])} | {fmt(p21['price'])} |")
    w()

    # DCA projection
    w("### Simple DCA $10/ngày – Dự phóng (tiếp tục từ hiện tại)")
    w()
    w(f"Hiện tại: {dca_coins:.6f} BTC, portfolio {fmt(dca_val)}  ")
    w(f"Tiếp tục $10/ngày → thêm $3,650 (12 tháng) / $6,388 (21 tháng)")
    w()
    w("| Kịch bản | BTC 03/2027 | Portfolio 03/2027 | Portfolio 12/2027 |")
    w("|----------|-------------|-------------------|-------------------|")
    for sc in ["bearish", "moderate", "bullish"]:
        p12_price = proj12[sc]["price"]
        p21_price = proj21[sc]["price"]
        mr = proj12[sc]["mr"]
        # Existing coins at projected price
        exist_val_12 = dca_coins * p12_price
        exist_val_21 = dca_coins * p21_price
        # New investments: approximate avg buy price
        avg_buy_12 = sum(cur * ((1 + mr) ** (m/12)) for m in range(13)) / 13
        avg_buy_21 = sum(cur * ((1 + mr) ** (m/12)) for m in range(22)) / 22
        new_coins_12 = (10 * 365) / avg_buy_12
        new_coins_21 = (10 * 365 * 21 / 12) / avg_buy_21
        new_val_12 = new_coins_12 * p12_price
        new_val_21 = new_coins_21 * p21_price
        total_12 = exist_val_12 + new_val_12
        total_21 = exist_val_21 + new_val_21
        w(f"| {sc.capitalize()} | {fmt(p12_price)} | {fmt(total_12)} | {fmt(total_21)} |")
    w()

    # Bot projection
    w("### DCA Bot – Dự phóng")
    w()
    if bs["cycles"] > 0:
        avg_pnl = (bs["tot_profit"] - bs["tot_loss"]) / bs["cycles"]
        total_bars = len(kw["cl_1h"])
        months_hist = total_bars / (24 * 30.44)
        cpm = bs["cycles"] / months_hist
        w(f"Historical: {cpm:.1f} cycles/tháng, avg PnL/cycle: {fmt(avg_pnl, 2)}")
        w()
        w("| Kịch bản | Cycle adj. | Monthly gain | Bot 03/2027 | Bot 12/2027 |")
        w("|----------|-----------|-------------|-------------|-------------|")
        for sc, factor in [("Bearish", 0.5), ("Moderate", 0.8), ("Bullish", 1.2)]:
            adj_cpm = cpm * factor
            monthly_pnl = adj_cpm * avg_pnl
            mg = monthly_pnl / max(bs["final"], 1) * 100
            v12 = bs["final"] * ((1 + mg / 100) ** 12)
            v21 = bs["final"] * ((1 + mg / 100) ** 21)
            w(f"| {sc} | {factor}x ({adj_cpm:.1f}/mo) | {mg:+.2f}%/mo | {fmt(v12)} | {fmt(v21)} |")
    w()

    # Optimized bot projection
    if os_["cycles"] > 0:
        avg_pnl_opt = (os_["tot_profit"] - os_["tot_loss"]) / os_["cycles"]
        cpm_opt = os_["cycles"] / months_hist
        w("### DCA Bot Tối ưu – Dự phóng")
        w()
        w(f"Historical: {cpm_opt:.1f} cycles/tháng, avg PnL/cycle: {fmt(avg_pnl_opt, 2)}")
        w()
        w("| Kịch bản | Cycle adj. | Monthly gain | Bot 03/2027 | Bot 12/2027 |")
        w("|----------|-----------|-------------|-------------|-------------|")
        for sc, factor in [("Bearish", 0.5), ("Moderate", 0.8), ("Bullish", 1.2)]:
            adj = cpm_opt * factor
            mp = adj * avg_pnl_opt
            mg = mp / max(os_["final"], 1) * 100
            v12 = os_["final"] * ((1 + mg / 100) ** 12)
            v21 = os_["final"] * ((1 + mg / 100) ** 21)
            w(f"| {sc} | {factor}x ({adj:.1f}/mo) | {mg:+.2f}%/mo | {fmt(v12)} | {fmt(v21)} |")
        w()

    # ── Section 5: Recommendation ────────────────────────
    w("---")
    w()
    w("## 5. Khuyến nghị thông số tối ưu cho DCA Bot BTC")
    w()
    w("### Cài đặt Binance DCA Spot:")
    w()
    w("| Tham số | Khuyến nghị | Screenshot | Lý do |")
    w("|---------|-------------|-----------|-------|")
    w(f"| Bước giá | **{oc['dev']*100:.1f}%** | 1.0% | "
      f"Cover correction ~{oc['dev']*100*oc['mso']:.0f}% tổng |")
    w(f"| TP mỗi kỳ | **{oc['tp']*100:.1f}%** | 1.5% | "
      f"Cân bằng tần suất cycle & lợi nhuận |")
    w(f"| Lệnh an toàn max | **{oc['mso']}** | 8 | "
      f"Đủ buffer cho dip |")
    w(f"| Volume Scale | **{oc['vs']:.2f}x** | 1.00x | "
      f"{'Tăng size khi giá giảm sâu' if oc['vs'] > 1.01 else 'Giữ đều'} |")
    w(f"| Step Scale | **{oc['ss']:.2f}x** | 1.00x | "
      f"{'Giãn khoảng cách safety order' if oc['ss'] > 1.01 else 'Khoảng cách đều'} |")
    w()

    w("### Phân tích")
    w()
    w("1. **DCA Bot** phù hợp thị trường **sideways/ranging** – kiếm lợi nhuận nhỏ mỗi cycle")
    w("2. **Simple DCA** phù hợp **long-term accumulation** – hưởng lợi khi BTC tăng dài hạn")
    w("3. **Buy & Hold** ROI cao nhất nếu mua đúng đáy, nhưng rủi ro timing lớn")
    w("4. **Rủi ro DCA Bot**: Bị \"kẹt\" trong bear market (tất cả SO filled, chờ recovery)")
    w(f"   - Longest cycle trong backtest: **{bs['longest']//24} ngày** ({bs['longest']//24//30:.0f} tháng)")
    w("5. **Kết hợp tối ưu**: Dùng DCA Bot cho ~30% vốn (active), Simple DCA cho ~70% (passive)")
    w()
    w("---")
    w()
    w(f"*Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}*")

    report = "\n".join(lines)
    with open(path, "w") as f:
        f.write(report)
    return report


# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    SEP = "═" * 80
    print(f"\n{SEP}")
    print("  BINANCE DCA SPOT BOT  –  BACKTEST & COMPARISON")
    print(f"  BTC/USDT │ 2017 → 03/2026 │ Projection → 03/2027, 12/2027")
    print(SEP)

    # ── Load data ────────────────────────────────────────
    print("\n▸ Loading data…")
    ts_1h, op_1h, hi_1h, lo_1h, cl_1h = load_candles("1h")
    ts_1d, op_1d, hi_1d, lo_1d, cl_1d = load_candles("1d")
    print(f"  1h: {len(cl_1h):,} candles  │  1d: {len(cl_1d):,} candles")

    start_date = datetime.utcfromtimestamp(ts_1h[0] / 1000).strftime("%Y-%m-%d")
    end_date = datetime.utcfromtimestamp(ts_1h[-1] / 1000).strftime("%Y-%m-%d")
    start_price = cl_1h[0]
    current_price = cl_1h[-1]
    print(f"  Period: {start_date} → {end_date}")
    print(f"  BTC: ${start_price:,.0f} → ${current_price:,.0f}")

    CAPITAL = 350  # As in screenshot

    # ── 1. Bot with screenshot settings ──────────────────
    print(f"\n{'─'*80}")
    print("  1. BINANCE DCA SPOT BOT  (Screenshot: dev=1%, TP=1.5%, 8 SO)")
    print(f"{'─'*80}")

    sett = {"dev": 0.01, "tp": 0.015, "mso": 8, "vs": 1.0, "ss": 1.0}
    io, so = calc_order_sizes(CAPITAL, sett["mso"], sett["vs"])
    sett["io"] = io
    sett["so"] = so

    bot_default = run_bot(hi_1h, lo_1h, cl_1h, CAPITAL, io, so,
                          sett["mso"], sett["dev"], sett["tp"],
                          sett["vs"], sett["ss"], earn_apr=0.0121)
    bs = bot_default.stats()
    bs["tot_profit"] = bot_default.tot_profit
    bs["tot_loss"] = bot_default.tot_loss

    print(f"  Capital: ${CAPITAL}  │  Init order: ${io:.0f}  │  SO: ${so:.0f}")
    print(f"  Final value:   ${bs['final']:>12,.2f}")
    print(f"  ROI:           {bs['roi']:>+11.1f}%")
    print(f"  Cycles:        {bs['cycles']:>11,}")
    print(f"  Win rate:      {bs['wr']:>11.1f}%")
    print(f"  Profit factor: {bs['pf']:>11.2f}")
    print(f"  Max drawdown:  {bs['dd']:>11.1f}%")
    print(f"  Longest cycle: {bs['longest']:>11} bars ({bs['longest']//24} days)")
    if bs["in_pos"]:
        print(f"  ⚠ In position, unrealized: ${bs['unr']:+,.2f}")

    # ── 2. Simple DCA $10/day ────────────────────────────
    print(f"\n{'─'*80}")
    print("  2. SIMPLE DCA  ($10/ngày)")
    print(f"{'─'*80}")

    dca_final, dca_inv, dca_roi, dca_coins = simple_dca(ts_1h, cl_1h, 10.0)
    dca_s = {"final": dca_final, "invested": dca_inv, "roi": dca_roi, "coins": dca_coins}

    print(f"  Invested:      ${dca_inv:>12,.0f}")
    print(f"  Final value:   ${dca_final:>12,.2f}")
    print(f"  ROI:           {dca_roi:>+11.1f}%")
    print(f"  BTC held:      {dca_coins:>14.6f}")

    # ── 3. Buy & Hold $350 ───────────────────────────────
    print(f"\n{'─'*80}")
    print(f"  3. BUY & HOLD  (${CAPITAL})")
    print(f"{'─'*80}")

    hold_final, hold_roi = buy_hold(cl_1h, CAPITAL)
    hold_s = {"final": hold_final, "roi": hold_roi}

    print(f"  Invested:      ${CAPITAL:>12,}")
    print(f"  Final value:   ${hold_final:>12,.2f}")
    print(f"  ROI:           {hold_roi:>+11.1f}%")

    # ── 4. Bot with $10/day injection ────────────────────
    print(f"\n{'─'*80}")
    print("  4. DCA BOT + $10/ngày injection  (cùng ngân sách với Simple DCA)")
    print(f"{'─'*80}")

    bot_inj, inj_total = run_bot_daily_inject(
        ts_1h, hi_1h, lo_1h, cl_1h, 10.0,
        8, 0.01, 0.015)
    bis = bot_inj.stats()

    print(f"  Total injected: ${inj_total:>11,.0f}")
    print(f"  Final value:    ${bis['final']:>11,.2f}")
    print(f"  ROI:            {bis['roi']:>+10.1f}%")
    print(f"  Cycles:         {bis['cycles']:>10,}")

    # ── 5. Grid search ───────────────────────────────────
    print(f"\n{'─'*80}")
    print("  5. GRID SEARCH  (1d candles, optimal parameters)")
    print(f"{'─'*80}")

    grid = grid_search(hi_1d, lo_1d, cl_1d, CAPITAL)

    print(f"\n  TOP 10:")
    print(f"  {'#':>3} {'Dev':>5} {'TP':>5} {'MSO':>4} {'VS':>5} {'SS':>5} │ "
          f"{'ROI':>8} {'WR':>6} {'PF':>6} {'DD':>6} {'Cyc':>6} {'Score':>7}")
    print(f"  {'─'*72}")
    for i, r in enumerate(grid[:10]):
        print(f"  {i+1:>3} {r['dev']*100:>4.1f}% {r['tp']*100:>4.1f}% "
              f"{r['mso']:>4} {r['vs']:>4.1f}x {r['ss']:>4.1f}x │ "
              f"{r['roi']:>+7.1f}% {r['wr']:>5.1f}% {r['pf']:>5.1f} "
              f"{r['dd']:>5.1f}% {r['cycles']:>6} {r['score']:>6.1f}")

    # Verify top 20 on 1h data and pick the actual best
    print(f"\n  Verifying top 20 on 1h data…")
    best_1h_score = -999
    best_1h = None
    for r in grid[:20]:
        _io, _so = calc_order_sizes(CAPITAL, r["mso"], r["vs"])
        _bot = run_bot(hi_1h, lo_1h, cl_1h, CAPITAL, _io, _so,
                       r["mso"], r["dev"], r["tp"], r["vs"], r["ss"])
        _s = _bot.stats()
        _score = (_s["roi"] * 0.35 + (100 - min(_s["dd"], 100)) * 0.25
                  + min(_s["wr"], 99) * 0.2 + min(_s["pf"], 10) * 5 * 0.2)
        if _s["cycles"] < 10:
            _score -= 50
        if _score > best_1h_score:
            best_1h_score = _score
            best_1h = {**r, "io": _io, "so": _so, "_bot": _bot, "_stats": _s}

    best = best_1h or grid[0]
    print(f"\n  ★ BEST (verified 1h): dev={best['dev']*100:.1f}%  TP={best['tp']*100:.1f}%  "
          f"MSO={best['mso']}  VS={best['vs']}x  SS={best['ss']}x")

    bot_opt = best.get("_bot")
    if bot_opt is None:
        opt_io, opt_so = calc_order_sizes(CAPITAL, best["mso"], best["vs"])
        bot_opt = run_bot(hi_1h, lo_1h, cl_1h, CAPITAL, opt_io, opt_so,
                          best["mso"], best["dev"], best["tp"],
                          best["vs"], best["ss"])
    else:
        opt_io, opt_so = best["io"], best["so"]

    os_ = bot_opt.stats()
    os_["tot_profit"] = bot_opt.tot_profit
    os_["tot_loss"] = bot_opt.tot_loss

    print(f"  ROI: {os_['roi']:+.1f}%  │  Cycles {os_['cycles']}  │  "
          f"WR {os_['wr']:.1f}%  │  DD {os_['dd']:.1f}%")

    opt_cfg = {**best, "io": opt_io, "so": opt_so}
    # Remove non-serializable keys
    opt_cfg.pop("_bot", None)
    opt_cfg.pop("_stats", None)

    # ── 6. Projection ────────────────────────────────────
    print(f"\n{'─'*80}")
    print("  6. PROJECTION  (→ 03/2027, 12/2027)")
    print(f"{'─'*80}")

    mrets = calc_monthly_returns(ts_1h, cl_1h)
    proj12, mstats = project(current_price, mrets, 12)
    proj21, _ = project(current_price, mrets, 21)

    print(f"  BTC monthly return: avg={mstats['avg']*100:.1f}%, "
          f"median={mstats['med']*100:.1f}%, std={mstats['std']*100:.1f}%")
    print()
    for label, proj in [("03/2027 (12m)", proj12), ("12/2027 (21m)", proj21)]:
        print(f"  {label}:")
        for sc in ["bearish", "moderate", "bullish"]:
            p = proj[sc]
            print(f"    {sc:>10}: ${p['price']:>10,.0f}  ({p['mr']*100:+.1f}%/mo)")

    # ── Write report ─────────────────────────────────────
    rpt_path = REPORTS / "dca_bot_comparison.md"
    write_report(
        rpt_path,
        bot_stats=bs, opt_stats=os_, opt_cfg=opt_cfg,
        dca_stats=dca_s, hold_stats=hold_s,
        bot_inj=bot_inj, bot_inj_invested=inj_total,
        settings=sett,
        current_price=current_price, start_price=start_price,
        start_date=start_date, end_date=end_date,
        capital=CAPITAL,
        proj12=proj12, proj21=proj21, mstats=mstats,
        cl_1h=cl_1h,
    )
    print(f"\n  ✔ Report saved: {rpt_path}")

    # ── Summary ──────────────────────────────────────────
    print(f"\n{SEP}")
    print("  SUMMARY")
    print(SEP)
    print(f"  {'Strategy':<30} {'Invested':>12} {'Final':>12} {'ROI':>9}")
    print(f"  {'─'*65}")
    print(f"  {'DCA Bot (screenshot)':<30} {'$'+str(CAPITAL):>12} ${bs['final']:>11,.0f} {bs['roi']:>+8.1f}%")
    print(f"  {'DCA Bot (optimized)':<30} {'$'+str(CAPITAL):>12} ${os_['final']:>11,.0f} {os_['roi']:>+8.1f}%")
    print(f"  {'Buy & Hold':<30} {'$'+str(CAPITAL):>12} ${hold_final:>11,.0f} {hold_roi:>+8.1f}%")
    print(f"  {'Simple DCA $10/day':<30} ${dca_inv:>11,.0f} ${dca_final:>11,.0f} {dca_roi:>+8.1f}%")
    print(f"  {'Bot + $10/day inject':<30} ${inj_total:>11,.0f} ${bis['final']:>11,.0f} {bis['roi']:>+8.1f}%")
    print()


if __name__ == "__main__":
    main()
