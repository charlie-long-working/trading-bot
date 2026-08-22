"""
Grid search for optimal DCA bot parameters on BTC 15m + 1h data.
Capital: $500, Full period: 2017-08 to 2026-03
"""
import csv
import numpy as np
from pathlib import Path
from datetime import datetime
from itertools import product
import time

CACHE = Path("data/cache/binance/spot")


def load_candles(filename):
    rows = []
    with open(CACHE / filename) as f:
        reader = csv.reader(f)
        next(reader)
        for line in reader:
            if len(line) < 6:
                continue
            rows.append((int(line[0]), float(line[2]), float(line[3]), float(line[4])))
    return rows


class DCABot:
    __slots__ = (
        "capital", "init_cap", "leverage", "is_long",
        "init_margin", "so_margin", "max_so",
        "price_step", "tp_pct", "sl_pct",
        "step_scale", "vol_scale", "cooldown_bars",
        "in_pos", "avg_entry", "tot_margin", "tot_notional", "tot_coins",
        "so_triggers", "so_margins", "so_filled", "cd_counter",
        "wins", "losses", "tot_profit", "tot_loss",
        "max_dd", "peak_cap", "cycles", "liqs",
    )

    def __init__(self, capital, leverage, is_long, init_margin, so_margin,
                 max_so, price_step, tp_pct, sl_pct, step_scale, vol_scale, cooldown_bars):
        self.capital = capital
        self.init_cap = capital
        self.leverage = leverage
        self.is_long = is_long
        self.init_margin = init_margin
        self.so_margin = so_margin
        self.max_so = max_so
        self.price_step = price_step
        self.tp_pct = tp_pct
        self.sl_pct = sl_pct
        self.step_scale = step_scale
        self.vol_scale = vol_scale
        self.cooldown_bars = cooldown_bars

        self.so_triggers = np.zeros(max_so)
        self.so_margins = np.zeros(max_so)
        self.so_filled = np.zeros(max_so, dtype=bool)

        self.in_pos = False
        self.avg_entry = 0.0
        self.tot_margin = 0.0
        self.tot_notional = 0.0
        self.tot_coins = 0.0
        self.cd_counter = 0
        self.wins = 0
        self.losses = 0
        self.tot_profit = 0.0
        self.tot_loss = 0.0
        self.max_dd = 0.0
        self.peak_cap = capital
        self.cycles = 0
        self.liqs = 0

    def _build_so(self, ep):
        cum = 0.0
        step = self.price_step
        for i in range(self.max_so):
            cum += step
            self.so_triggers[i] = ep * (1 - cum) if self.is_long else ep * (1 + cum)
            self.so_margins[i] = self.so_margin * (self.vol_scale ** i)
            self.so_filled[i] = False
            step *= self.step_scale

    def _open(self, price):
        if self.capital < self.init_margin:
            return
        self.in_pos = True
        m = min(self.init_margin, self.capital)
        n = m * self.leverage
        self.tot_margin = m
        self.tot_notional = n
        self.tot_coins = n / price
        self.avg_entry = price
        self.capital -= m
        self._build_so(price)

    def _close(self, pnl):
        fee = self.tot_notional * 0.0004 * 2
        net = pnl - fee
        self.capital += self.tot_margin + net
        self.cycles += 1
        if net > 0:
            self.wins += 1
            self.tot_profit += net
        else:
            self.losses += 1
            self.tot_loss += abs(net)
        self.peak_cap = max(self.peak_cap, self.capital)
        dd = (self.peak_cap - self.capital) / self.peak_cap * 100
        if dd > self.max_dd:
            self.max_dd = dd
        self.in_pos = False
        self.cd_counter = self.cooldown_bars

    def process(self, high, low, close):
        if self.cd_counter > 0:
            self.cd_counter -= 1
            return
        if not self.in_pos:
            self._open(close)
            return

        ae = self.avg_entry
        tc = self.tot_coins
        tm = self.tot_margin

        for i in range(self.max_so):
            if self.so_filled[i]:
                continue
            trig = self.so_triggers[i]
            hit = (low <= trig) if self.is_long else (high >= trig)
            if hit:
                m = min(self.so_margins[i], self.capital)
                if m > 0:
                    n = m * self.leverage
                    c = n / trig
                    self.tot_margin += m
                    self.tot_notional += n
                    self.tot_coins += c
                    self.avg_entry = self.tot_notional / self.tot_coins
                    self.capital -= m
                    tm = self.tot_margin
                    tc = self.tot_coins
                    ae = self.avg_entry
                self.so_filled[i] = True

        if self.is_long:
            tp_p = ae * (1 + self.tp_pct)
            if high >= tp_p:
                self._close(tc * (tp_p - ae))
                return
            if self.sl_pct:
                sl_p = ae * (1 - self.sl_pct)
                if low <= sl_p:
                    self._close(tc * (sl_p - ae))
                    return
            liq_p = ae - tm * 0.996 / tc
            if low <= liq_p:
                self.liqs += 1
                self._close(-tm)
                return
        else:
            tp_p = ae * (1 - self.tp_pct)
            if low <= tp_p:
                self._close(tc * (ae - tp_p))
                return
            if self.sl_pct:
                sl_p = ae * (1 + self.sl_pct)
                if high >= sl_p:
                    self._close(tc * (ae - sl_p))
                    return
            liq_p = ae + tm * 0.996 / tc
            if high >= liq_p:
                self.liqs += 1
                self._close(-tm)
                return


def run_grid(candles, capital, is_long):
    leverages = [3, 5]
    price_steps = [0.01, 0.015, 0.02, 0.025, 0.03]
    tp_pcts = [0.015, 0.02, 0.025, 0.03]
    sl_pcts = [0.10, 0.15, 0.20]
    step_scales = [1.1, 1.2, 1.3]
    max_sos = [6, 8, 10]
    cooldowns = [2, 4, 8]

    results = []
    total = (len(leverages) * len(price_steps) * len(tp_pcts) *
             len(sl_pcts) * len(step_scales) * len(max_sos) * len(cooldowns))
    print(f"    Grid: {total} combinations...")

    best_score = -999
    count = 0
    t0 = time.time()

    for lev, ps, tp, sl, ss, mso, cd in product(
        leverages, price_steps, tp_pcts, sl_pcts, step_scales, max_sos, cooldowns
    ):
        init_m = capital * 0.06 if lev == 3 else capital * 0.05
        so_m = capital * 0.045 if lev == 3 else capital * 0.04

        bot = DCABot(capital, lev, is_long, init_m, so_m,
                     mso, ps, tp, sl, ss, 1.05, cd)

        for _, h, l, c in candles:
            bot.process(h, l, c)

        roi = (bot.capital / bot.init_cap - 1) * 100
        wr = bot.wins / max(bot.cycles, 1) * 100
        pf = bot.tot_profit / max(bot.tot_loss, 0.01)

        score = roi * 0.4 + (100 - bot.max_dd) * 0.3 + min(wr, 99) * 0.2 + min(pf, 5) * 10 * 0.1
        if bot.liqs > 0:
            score -= bot.liqs * 50
        if bot.max_dd > 50:
            score -= (bot.max_dd - 50) * 2

        results.append({
            "lev": lev, "ps": ps, "tp": tp, "sl": sl,
            "ss": ss, "mso": mso, "cd": cd,
            "roi": roi, "wr": wr, "pf": pf,
            "dd": bot.max_dd, "cycles": bot.cycles,
            "liqs": bot.liqs, "capital": bot.capital,
            "score": score,
        })

        count += 1
        if count % 500 == 0:
            elapsed = time.time() - t0
            eta = elapsed / count * (total - count)
            print(f"      {count}/{total} ({elapsed:.0f}s, ETA {eta:.0f}s)...")

    results.sort(key=lambda x: -x["score"])
    return results


def main():
    CAPITAL = 500

    print("Loading candles...")
    candles_15m = load_candles("BTC_USDT_15m.csv")
    candles_1h = load_candles("BTC_USDT_1h.csv")
    print(f"  15m: {len(candles_15m)} candles")
    print(f"   1h: {len(candles_1h)} candles")

    for tf_name, candles in [("1h", candles_1h), ("15m", candles_15m)]:
        for direction, is_long in [("LONG", True), ("SHORT", False)]:
            print(f"\n{'='*120}")
            print(f"  GRID SEARCH: {direction} | {tf_name} | ${CAPITAL} | 2017-2026")
            print(f"{'='*120}")

            results = run_grid(candles, CAPITAL, is_long)

            print(f"\n  TOP 10 {direction} ({tf_name}):")
            print(f"  {'#':>3} {'Lev':>4} {'Step':>6} {'TP':>6} {'SL':>6} {'SScale':>7} {'MaxSO':>6} {'CD':>4} │"
                  f" {'ROI':>8} {'WR':>6} {'PF':>6} {'MaxDD':>7} {'Cycles':>7} {'LIQ':>4} {'Capital':>10} {'Score':>7}")
            print(f"  {'─'*110}")

            for i, r in enumerate(results[:10]):
                m = " ⚠" if r['liqs'] > 0 else ""
                print(f"  {i+1:>3} {r['lev']:>4}x {r['ps']*100:>5.1f}% {r['tp']*100:>5.1f}% {r['sl']*100:>5.0f}% {r['ss']:>6.1f}x {r['mso']:>6} {r['cd']:>4} │"
                      f" {r['roi']:>+7.0f}% {r['wr']:>5.1f}% {r['pf']:>5.1f} {r['dd']:>6.1f}% {r['cycles']:>7} {r['liqs']:>4} ${r['capital']:>8,.0f} {r['score']:>6.1f}{m}")

            if results:
                best = results[0]
                print(f"\n  ★ BEST {direction} ({tf_name}):")
                print(f"    Leverage: {best['lev']}x | Price step: {best['ps']*100:.1f}% | TP: {best['tp']*100:.1f}% | SL: {best['sl']*100:.0f}%")
                print(f"    Step scale: {best['ss']}x | Max SO: {best['mso']} | Cooldown: {best['cd']} bars")
                init_m = CAPITAL * 0.06 if best['lev'] == 3 else CAPITAL * 0.05
                so_m = CAPITAL * 0.045 if best['lev'] == 3 else CAPITAL * 0.04
                print(f"    Init margin: ${init_m:.0f} | SO margin: ${so_m:.0f}")
                print(f"    ROI: {best['roi']:+.0f}% | WR: {best['wr']:.1f}% | PF: {best['pf']:.1f} | MaxDD: {best['dd']:.1f}% | LIQ: {best['liqs']}")


if __name__ == "__main__":
    main()
