#!/usr/bin/env python3
"""
Simulate a DCA Futures Bot (Pionex/3Commas-style) on historical BTCUSDT data.

Bot parameters from screenshot:
  - BTCUSDT Perpetual, Long, 10x leverage
  - Price steps: 0.75%, Take profit: 1.50%
  - Initial order margin: 28 USDT, Safety order margin: 11 USDT
  - Max safety orders: 13
  - Volume scale: 1.00x, Price step scale: 1.10x
  - No stop loss

Run: python -m botv2.simulate_dca_bot
"""

import csv
import sys
import time as _time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from botv2.config import CACHE_DIR, REPO_ROOT, BOTV2_ROOT

REPORT_DIR = BOTV2_ROOT / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

EFFECTIVE_FEE = 0.0005 * 0.60  # taker 0.05% after 40% rebate = 0.03%
FUNDING_RATE_8H = 0.0001


def _ts_to_str(ts) -> str:
    ts_val = int(ts)
    if ts_val < 1e12:
        ts_val *= 1000
    return datetime.fromtimestamp(ts_val / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


# ── Data loading ─────────────────────────────────────────────────────────────

def _read_csv(path: Path) -> List[Tuple]:
    rows = []
    with open(path) as f:
        reader = csv.reader(f)
        next(reader)
        for line in reader:
            if len(line) < 6:
                continue
            try:
                rows.append((int(line[0]), float(line[1]), float(line[2]),
                             float(line[3]), float(line[4]), float(line[5])))
            except (ValueError, IndexError):
                continue
    return rows


def load_btc(timeframe: str):
    path = Path(CACHE_DIR) / "binance" / "spot" / f"BTC_USDT_{timeframe}.csv"
    if path.exists():
        rows = _read_csv(path)
        if rows:
            return tuple(np.array([r[i] for r in rows]) for i in range(6))
    return None


def resample_15m_to_4h(ot, op, hi, lo, cl, vol):
    bucket_ms = 4 * 3600 * 1000
    keys = (ot.astype(np.int64) // bucket_ms * bucket_ms)
    unique_keys = np.unique(keys)
    n = len(unique_keys)
    r_ot = unique_keys
    r_op = np.empty(n); r_hi = np.empty(n); r_lo = np.empty(n)
    r_cl = np.empty(n); r_vol = np.empty(n)
    for idx, k in enumerate(unique_keys):
        mask = keys == k
        r_op[idx] = op[mask][0]
        r_hi[idx] = hi[mask].max()
        r_lo[idx] = lo[mask].min()
        r_cl[idx] = cl[mask][-1]
        r_vol[idx] = vol[mask].sum()
    return r_ot, r_op, r_hi, r_lo, r_cl, r_vol


# ── DCA Bot config ───────────────────────────────────────────────────────────

class Cfg:
    __slots__ = ("lev", "ps", "tp", "init_m", "so_m", "max_so", "vs", "ss", "sl")

    def __init__(self, lev=10, ps=0.75, tp=1.5, init_m=28, so_m=11,
                 max_so=13, vs=1.0, ss=1.1, sl=0.0):
        self.lev = lev; self.ps = ps; self.tp = tp
        self.init_m = init_m; self.so_m = so_m; self.max_so = max_so
        self.vs = vs; self.ss = ss; self.sl = sl

    @property
    def total_margin(self):
        t = self.init_m
        m = self.so_m
        for _ in range(self.max_so):
            t += m; m *= self.vs
        return t

    def so_drop_fracs(self):
        """Cumulative drop fractions for each SO trigger from entry."""
        step = self.ps / 100.0
        cum = 0.0
        drops = []
        for i in range(self.max_so):
            cum += step
            drops.append(cum)
            step *= self.ss
        return drops

    def max_deviation_pct(self):
        d = self.so_drop_fracs()
        return d[-1] * 100 if d else 0


# ── Fast simulation (numpy-accelerated) ─────────────────────────────────────

def simulate_fast(cfg: Cfg, capital: float,
                  hi: np.ndarray, lo: np.ndarray, cl: np.ndarray,
                  tf_hours: float):
    """
    Simulate DCA bot. Returns dict with results.
    Uses numpy arrays and avoids per-bar Python overhead where possible.
    """
    n = len(cl)
    balance = capital
    peak_balance = capital

    so_drop_fracs = np.array(cfg.so_drop_fracs())
    so_margins_arr = np.array([cfg.so_m * (cfg.vs ** i) for i in range(cfg.max_so)])

    cycles = []
    liq_events = []
    balance_snapshots = []
    total_fees = 0.0
    total_funding = 0.0

    i = 0
    funding_per_bar = FUNDING_RATE_8H * (tf_hours / 8.0)

    while i < n and balance > cfg.init_m:
        entry_price = cl[i]
        entry_i = i

        if balance < cfg.init_m:
            break

        init_notional = cfg.init_m * cfg.lev
        init_coins = init_notional / entry_price
        fee = init_notional * EFFECTIVE_FEE
        balance -= fee
        total_fees += fee

        # Active orders: track total_coins, total_cost (for avg), total_margin
        total_coins = init_coins
        total_cost = init_notional
        total_margin = cfg.init_m
        avg_entry = entry_price

        # Pre-compute SO trigger prices
        so_trigger_prices = entry_price * (1 - so_drop_fracs)
        next_so = 0

        exit_reason = None
        exit_price = 0.0
        exit_i = i

        for j in range(i + 1, n):
            bar_lo = lo[j]
            bar_hi = hi[j]

            # Funding cost
            fc = total_cost * funding_per_bar  # funding on notional
            balance -= fc
            total_funding += fc

            # Fill safety orders (price went down)
            while next_so < cfg.max_so and bar_lo <= so_trigger_prices[next_so]:
                sm = so_margins_arr[next_so]
                if balance < sm:
                    break
                fill_price = so_trigger_prices[next_so]
                so_notional = sm * cfg.lev
                so_coins = so_notional / fill_price
                sfee = so_notional * EFFECTIVE_FEE
                balance -= sfee
                total_fees += sfee

                total_coins += so_coins
                total_cost += so_notional
                total_margin += sm
                avg_entry = total_cost / total_coins
                next_so += 1

            # TP check
            tp_price = avg_entry * (1 + cfg.tp / 100.0)
            if bar_hi >= tp_price:
                pnl = total_coins * (tp_price - avg_entry)
                cfee = total_coins * tp_price * EFFECTIVE_FEE
                balance -= cfee
                total_fees += cfee
                balance += pnl
                peak_balance = max(peak_balance, balance)
                exit_reason = "tp"
                exit_price = tp_price
                exit_i = j
                break

            # Liquidation check: unrealised loss vs margin
            unrealised = total_coins * (bar_lo - avg_entry)
            if (-unrealised) >= total_margin * 0.95:
                balance = max(0, balance - total_margin)
                exit_reason = "liquidation"
                exit_price = bar_lo
                exit_i = j
                liq_events.append({
                    "time": j,
                    "price": bar_lo,
                    "entry": entry_price,
                    "avg": round(avg_entry, 2),
                    "so": next_so,
                    "margin": round(total_margin, 2),
                    "bal_after": round(balance, 2),
                    "drop": round((entry_price - bar_lo) / entry_price * 100, 2),
                })
                break
        else:
            # End of data
            last_price = cl[-1]
            pnl = total_coins * (last_price - avg_entry)
            cfee = total_coins * last_price * EFFECTIVE_FEE
            balance -= cfee
            total_fees += cfee
            balance += pnl
            exit_reason = "end"
            exit_price = last_price
            exit_i = n - 1

        duration_h = (exit_i - entry_i) * tf_hours
        pnl_cycle = (total_coins * (exit_price - avg_entry)
                     if exit_reason != "liquidation" else -total_margin)

        cycles.append({
            "start": entry_i, "end": exit_i,
            "entry": entry_price, "avg": avg_entry,
            "exit": exit_price, "reason": exit_reason,
            "so": next_so, "margin": total_margin,
            "pnl": round(pnl_cycle, 2),
            "pnl_pct": round(pnl_cycle / total_margin * 100, 2) if total_margin else 0,
            "dur_h": round(duration_h, 1),
        })

        balance_snapshots.append(round(balance, 2))
        i = exit_i + 1

    # Stats
    tp_cycles = [c for c in cycles if c["reason"] == "tp"]
    liq_cycles_list = [c for c in cycles if c["reason"] == "liquidation"]
    total_pnl = sum(c["pnl"] for c in cycles)

    max_dd = 0
    pk = capital
    for b in balance_snapshots:
        pk = max(pk, b)
        dd = (pk - b) / pk if pk > 0 else 0
        max_dd = max(max_dd, dd)

    return {
        "initial": capital,
        "final": round(balance, 2),
        "ret_pct": round((balance / capital - 1) * 100, 2) if capital > 0 else 0,
        "n_cycles": len(cycles),
        "n_tp": len(tp_cycles),
        "n_liq": len(liq_cycles_list),
        "win_rate": round(len(tp_cycles) / len(cycles) * 100, 1) if cycles else 0,
        "avg_pnl_tp": round(np.mean([c["pnl"] for c in tp_cycles]), 2) if tp_cycles else 0,
        "avg_dur_tp": round(np.mean([c["dur_h"] for c in tp_cycles]), 1) if tp_cycles else 0,
        "avg_so": round(np.mean([c["so"] for c in tp_cycles]), 1) if tp_cycles else 0,
        "fees": round(total_fees, 2),
        "funding": round(total_funding, 2),
        "max_dd": round(max_dd * 100, 1),
        "liq_events": liq_events,
        "cycles": cycles,
        "bal_snaps": balance_snapshots,
    }


# ── Optimization ─────────────────────────────────────────────────────────────

def optimize(capital, hi, lo, cl, tf_h, tf_label):
    """Grid search for best DCA params."""
    best = None
    safest = None
    best_score = -1e9
    safest_ret = -1e9
    tested = 0

    if capital <= 300:
        init_ms = [5, 8, 10, 15]
        so_ms = [3, 4, 5, 6]
        max_sos = [4, 6, 8, 10, 13]
    else:
        init_ms = [8, 10, 15, 20, 28]
        so_ms = [4, 5, 8, 10]
        max_sos = [5, 8, 10, 13]

    levs = [3, 5, 8, 10]
    pss = [0.75, 1.0, 1.5, 2.0, 3.0]
    tps = [1.0, 1.5, 2.0, 3.0]
    sss = [1.0, 1.1, 1.2, 1.3]

    for lev in levs:
        for im in init_ms:
            for sm in so_ms:
                for mso in max_sos:
                    tm = im + sm * mso
                    if tm > capital * 0.95 or tm < capital * 0.2:
                        continue
                    for ps in pss:
                        for tp in tps:
                            for ss in sss:
                                c = Cfg(lev=lev, ps=ps, tp=tp, init_m=im,
                                        so_m=sm, max_so=mso, ss=ss)
                                r = simulate_fast(c, capital, hi, lo, cl, tf_h)
                                tested += 1
                                if r["n_cycles"] < 3:
                                    continue
                                score = r["ret_pct"] - r["n_liq"] * 50 - r["max_dd"] * 0.5
                                if score > best_score:
                                    best_score = score
                                    best = {"cfg": c, "r": r, "score": score}
                                if r["n_liq"] == 0 and r["ret_pct"] > safest_ret:
                                    safest_ret = r["ret_pct"]
                                    safest = {"cfg": c, "r": r, "score": score}

    return {"best": best, "safest": safest, "tested": tested,
            "capital": capital, "tf": tf_label}


# ── Report writer ────────────────────────────────────────────────────────────

def _cfg_table(cfg: Cfg) -> list:
    return [
        "| Parameter | Value |",
        "|-----------|-------|",
        f"| Leverage | {cfg.lev}x |",
        f"| Price step | {cfg.ps}% |",
        f"| Take profit | {cfg.tp}% |",
        f"| Initial margin | ${cfg.init_m} |",
        f"| SO margin | ${cfg.so_m} |",
        f"| Max SOs | {cfg.max_so} |",
        f"| Step scale | {cfg.ss}x |",
        f"| Total margin | ${cfg.total_margin:.0f} |",
    ]


def _res_row(r: dict) -> str:
    return (f"${r['final']:,.0f} | {r['ret_pct']:+.1f}% | {r['n_cycles']} | "
            f"{r['n_tp']} | **{r['n_liq']}** | {r['win_rate']:.0f}% | "
            f"{r['max_dd']:.1f}% | ${r['fees']:.0f} | ${r['funding']:.0f}")


def write_report(scr_results, opt300, opt500, ot_map):
    scr_cfg = Cfg()  # default = screenshot params
    md = []

    md.append("# Phân tích DCA Futures Bot — BTCUSDT Perpetual")
    md.append("")
    md.append("Period: 2017-08-17 → 2026-03-14 | Dữ liệu: BTC/USDT Spot (proxy)")
    md.append("")

    # ── 1. Screenshot bot ──
    md.append("## 1. Tham số Bot từ Screenshot")
    md.append("")
    md += _cfg_table(scr_cfg)
    md.append(f"| Max price deviation | {scr_cfg.max_deviation_pct():.2f}% |")
    md.append(f"| Stop loss | Không |")
    md.append("")

    # SO Grid
    md.append("### Safety Order Grid")
    md.append("")
    md.append("| SO# | Bước giảm | Tổng giảm từ entry | Margin |")
    md.append("|-----|-----------|---------------------|--------|")
    step = scr_cfg.ps / 100; cum = 0
    for i in range(scr_cfg.max_so):
        cum += step
        md.append(f"| SO{i+1} | {step*100:.3f}% | {cum*100:.2f}% | ${scr_cfg.so_m * scr_cfg.vs**i:.0f} |")
        step *= scr_cfg.ss
    md.append("")

    # ── 2. Results on each TF ──
    md.append("## 2. Kết quả Bot Screenshot (vốn $300)")
    md.append("")
    md.append("| TF | Final | Return | Cycles | TP | Liq | WR | Max DD | Fees | Funding |")
    md.append("|----|-------|--------|--------|----|-----|-----|--------|------|---------|")
    for tf in ["15m", "1h", "4h"]:
        if tf in scr_results:
            r = scr_results[tf]
            md.append(f"| {tf} | " + _res_row(r) + " |")
    md.append("")

    # Liq analysis
    md.append("### Thời điểm bị Liquidation")
    md.append("")
    for tf in ["15m", "1h", "4h"]:
        if tf in scr_results:
            evts = scr_results[tf]["liq_events"]
            ot = ot_map.get(tf)
            if evts:
                md.append(f"**{tf}:** {len(evts)} lần liquidation")
                for ev in evts[:10]:
                    t = _ts_to_str(ot[ev["time"]]) if ot is not None else f"bar {ev['time']}"
                    md.append(f"  - {t}: BTC ${ev['price']:,.0f} "
                              f"(entry ${ev['entry']:,.0f}, giảm {ev['drop']:.1f}%), "
                              f"SO filled: {ev['so']}/{scr_cfg.max_so}, "
                              f"Mất margin: ${ev['margin']:.0f}")
                if len(evts) > 10:
                    md.append(f"  - ... và {len(evts)-10} lần nữa")
                md.append("")
            else:
                md.append(f"**{tf}:** Không bị liquidation")
                md.append("")

    # Risk analysis
    md.append("### Phân tích rủi ro cháy tài khoản")
    md.append("")
    md.append(f"- Tổng margin cần: **${scr_cfg.total_margin:.0f}** / $300 = **{scr_cfg.total_margin/300*100:.0f}%** vốn")
    md.append(f"- Max deviation: **{scr_cfg.max_deviation_pct():.2f}%** — "
              f"sau khi fill hết SO, giá chỉ cần giảm thêm ~1-2% → **liquidation**")
    md.append("- **Không có stop loss** → 1 lần liquidation = mất **toàn bộ $171 margin**")
    md.append("- Với 10x leverage: Liquidation price ≈ avg_entry × (1 - margin/notional)")
    md.append("")

    # ── 3. Opt $300 ──
    md.append("## 3. Chiến lược tối ưu cho vốn $300")
    md.append("")
    _write_opt(md, opt300, "$300", 300)

    # ── 4. Opt $500 ──
    md.append("## 4. Chiến lược tối ưu cho vốn $500")
    md.append("")
    _write_opt(md, opt500, "$500", 500)

    # ── 5. Comparison ──
    md.append("## 5. So sánh tổng hợp với các chiến lược khác")
    md.append("")
    md.append("| Strategy | Vốn | Return | Max DD | Liq Risk | Loại |")
    md.append("|----------|-----|--------|--------|----------|------|")

    for tf in ["1h"]:
        if tf in scr_results:
            r = scr_results[tf]
            md.append(f"| DCA Bot screenshot ({tf}) | $300 | {r['ret_pct']:+.1f}% | {r['max_dd']:.1f}% | {r['n_liq']} lần | Auto |")

    if opt300.get("safest"):
        r = opt300["safest"]["r"]
        md.append(f"| DCA Bot tối ưu an toàn | $300 | {r['ret_pct']:+.1f}% | {r['max_dd']:.1f}% | 0 | Auto |")
    if opt500.get("safest"):
        r = opt500["safest"]["r"]
        md.append(f"| DCA Bot tối ưu an toàn | $500 | {r['ret_pct']:+.1f}% | {r['max_dd']:.1f}% | 0 | Auto |")

    md.append("| MACD+RSI Futures 1d | $500 | +11.2% | <20% | 0 | Active |")
    md.append("| Regime+Fusion BTC 1h | $500 | +1,147% | 4% | 0 | Active |")
    md.append("| Regime+Fusion ETH 1h | $500 | +1,510% | 11% | 0 | Active |")
    md.append("| Buy & Hold BTC spot | $500 | +1,454% | ~80% | 0 | Passive |")
    md.append("| DCA Spot $10/ngày | ~$33K | +336% | ~60% | 0 | Auto |")
    md.append("")

    md.append("### Nhận xét chính")
    md.append("")
    md.append("1. **DCA Bot Futures** sinh lời đều khi thị trường sideway/tăng nhẹ, "
              "nhưng **cực kỳ nguy hiểm khi crash**.")
    md.append("2. **10x leverage + Không SL** = chỉ cần 1 lần giá giảm >18% liên tục → mất toàn bộ margin ($171).")
    md.append("3. BTC từ 2017-2026 có **nhiều lần giảm >20%**: "
              "COVID 3/2020 (-50%), China ban 5/2021 (-55%), FTX 11/2022 (-25%), ...")
    md.append("4. So với **Regime+Fusion** (return +1,147%, DD chỉ 4%), DCA bot có risk/reward tệ hơn nhiều.")
    md.append("5. DCA bot phù hợp hơn khi: leverage thấp (3-5x), price step rộng (1.5%+), "
              "ít SO hơn nhưng margin lớn hơn.")
    md.append("")

    # ── 6. Recommendations ──
    md.append("## 6. Khuyến nghị & Khi nào cần bơm vốn")
    md.append("")
    md.append("### Khi nào bot sẽ bị liquidation?")
    md.append("")
    md.append("Các giai đoạn BTC giảm mạnh (từ data 2017-2026):")
    md.append("- **2018-01**: $20K → $6K (-70% trong 2 tháng)")
    md.append("- **2020-03** (COVID): $9K → $3.8K (-58% trong 1 tuần)")
    md.append("- **2021-05**: $64K → $29K (-55% trong 2 tuần)")
    md.append("- **2022-06** (LUNA/FTX): $47K → $15.5K (-67% trong 6 tháng)")
    md.append("")
    md.append("→ Bot với 10x leverage + 18% max deviation sẽ bị **liquidation** trong TẤT CẢ các giai đoạn trên.")
    md.append("")
    md.append("### Khi nào cần bơm thêm vốn (Add Margin)?")
    md.append("")
    md.append("| Tình huống | Hành động |")
    md.append("|------------|-----------|")
    md.append("| SO ≥ 8/13 đã fill | ⚠️ Chuẩn bị thêm margin |")
    md.append("| SO ≥ 11/13 đã fill | 🔴 Add margin ngay hoặc đóng lệnh chấp nhận lỗ |")
    md.append("| Margin ratio > 80% | 🔴 Nguy hiểm - thêm vốn hoặc giảm position |")
    md.append("| BTC weekly trend = downtrend | Tạm dừng bot, không mở cycle mới |")
    md.append("| Funding rate > 0.03%/8h | Chi phí giữ lệnh quá cao → xem xét đóng |")
    md.append("")
    md.append("### Quy tắc vàng")
    md.append("")
    md.append("1. **Giữ 30-50% vốn NGOÀI bot** làm quỹ dự phòng add margin")
    md.append("2. **Luôn đặt stop loss** (dù bot không yêu cầu) ở mức -25% từ entry")
    md.append("3. **Giảm leverage xuống 5x** nếu vốn < $500")
    md.append("4. **Tăng price step lên 1.5%+** để bot chịu được biến động lớn hơn")
    md.append("5. **Monitor Daily/Weekly RSI**: Nếu RSI > 80 trên Weekly → giảm size hoặc dừng bot")
    md.append("")

    out = REPORT_DIR / "dca_bot_analysis.md"
    with open(out, "w") as f:
        f.write("\n".join(md))
    return out


def _write_opt(md, opt, label, cap):
    if opt.get("best"):
        b = opt["best"]
        md.append(f"### Best Overall ({label})")
        md.append("")
        md += _cfg_table(b["cfg"])
        r = b["r"]
        md.append(f"| **Return** | **{r['ret_pct']:+.1f}%** (${cap} → ${r['final']:,.0f}) |")
        md.append(f"| Cycles | {r['n_cycles']} (TP: {r['n_tp']}, Liq: {r['n_liq']}) |")
        md.append(f"| Win rate | {r['win_rate']:.0f}% |")
        md.append(f"| Max DD | {r['max_dd']:.1f}% |")
        md.append(f"| Avg PnL/TP cycle | ${r['avg_pnl_tp']:.2f} |")
        md.append(f"| Avg SOs filled | {r['avg_so']:.1f} |")
        md.append("")

    if opt.get("safest"):
        s = opt["safest"]
        md.append(f"### Safest — 0 Liquidation ({label})")
        md.append("")
        md += _cfg_table(s["cfg"])
        r = s["r"]
        md.append(f"| **Return** | **{r['ret_pct']:+.1f}%** (${cap} → ${r['final']:,.0f}) |")
        md.append(f"| Cycles | {r['n_cycles']} (TP: {r['n_tp']}) |")
        md.append(f"| Win rate | {r['win_rate']:.0f}% |")
        md.append(f"| Max DD | {r['max_dd']:.1f}% |")
        md.append(f"| Avg PnL/TP cycle | ${r['avg_pnl_tp']:.2f} |")
        md.append("")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    t0 = _time.time()
    print("=" * 70)
    print("  DCA Futures Bot — Backtest & Optimization")
    print("=" * 70)

    # Load data
    datasets = {}
    ot_map = {}

    data_1h = load_btc("1h")
    if data_1h:
        ot1, _, hi1, lo1, cl1, _ = data_1h
        datasets["1h"] = (hi1, lo1, cl1, 1.0)
        ot_map["1h"] = ot1
        print(f"  1h: {len(cl1):,} candles ({_ts_to_str(ot1[0])} → {_ts_to_str(ot1[-1])})")

    data_15m = load_btc("15m")
    if data_15m:
        ot15, op15, hi15, lo15, cl15, vol15 = data_15m
        datasets["15m"] = (hi15, lo15, cl15, 0.25)
        ot_map["15m"] = ot15
        print(f" 15m: {len(cl15):,} candles ({_ts_to_str(ot15[0])} → {_ts_to_str(ot15[-1])})")

        ot4, _, hi4, lo4, cl4, _ = resample_15m_to_4h(ot15, op15, hi15, lo15, cl15, vol15)
        datasets["4h"] = (hi4, lo4, cl4, 4.0)
        ot_map["4h"] = ot4
        print(f"  4h: {len(cl4):,} candles (resampled)")

    if not datasets:
        print("ERROR: No data. Run python -m botv2.run_data")
        return

    scr_cfg = Cfg()

    # ── Part 1: Screenshot bot on all TFs with $300 ──
    print(f"\n  Screenshot bot: margin needed ${scr_cfg.total_margin:.0f}, "
          f"max dev {scr_cfg.max_deviation_pct():.2f}%")
    print("\n── Part 1: Screenshot bot ($300) ──")

    scr_results = {}
    for tf in ["1h", "4h"]:
        if tf not in datasets:
            continue
        hi, lo, cl, tf_h = datasets[tf]
        print(f"  Simulating {tf}...", end=" ", flush=True)
        r = simulate_fast(scr_cfg, 300, hi, lo, cl, tf_h)
        scr_results[tf] = r
        print(f"${r['final']:,.0f} ({r['ret_pct']:+.1f}%) | "
              f"Cycles {r['n_cycles']} TP {r['n_tp']} Liq {r['n_liq']} | "
              f"DD {r['max_dd']:.1f}%")

    # 15m is slow, run on subset if needed
    if "15m" in datasets:
        hi15, lo15, cl15, _ = datasets["15m"]
        # Use last ~2 years of 15m data for speed (enough for analysis)
        n_bars_2y = 2 * 365 * 24 * 4  # ~70K bars
        if len(cl15) > n_bars_2y:
            print(f"  Simulating 15m (last 2 years subset)...", end=" ", flush=True)
            r = simulate_fast(scr_cfg, 300,
                              hi15[-n_bars_2y:], lo15[-n_bars_2y:], cl15[-n_bars_2y:], 0.25)
            scr_results["15m"] = r
            ot_map["15m_sub"] = ot_map["15m"][-n_bars_2y:]
            print(f"${r['final']:,.0f} ({r['ret_pct']:+.1f}%) | "
                  f"Cycles {r['n_cycles']} TP {r['n_tp']} Liq {r['n_liq']} | "
                  f"DD {r['max_dd']:.1f}%")
        else:
            print(f"  Simulating 15m...", end=" ", flush=True)
            r = simulate_fast(scr_cfg, 300, hi15, lo15, cl15, 0.25)
            scr_results["15m"] = r
            print(f"${r['final']:,.0f} ({r['ret_pct']:+.1f}%) | "
                  f"Cycles {r['n_cycles']} TP {r['n_tp']} Liq {r['n_liq']} | "
                  f"DD {r['max_dd']:.1f}%")

    # ── Part 2: Optimize for $300 on 1h ──
    print("\n── Part 2: Optimize $300 (on 1h) ──")
    hi_opt, lo_opt, cl_opt, tfh_opt = datasets.get("1h", datasets[list(datasets.keys())[0]])
    opt300 = optimize(300, hi_opt, lo_opt, cl_opt, tfh_opt, "1h")
    print(f"  Tested: {opt300['tested']} configs")
    if opt300["best"]:
        r = opt300["best"]["r"]
        print(f"  Best: {r['ret_pct']:+.1f}%, Liq {r['n_liq']}, DD {r['max_dd']:.1f}%")
    if opt300["safest"]:
        r = opt300["safest"]["r"]
        print(f"  Safest: {r['ret_pct']:+.1f}%, DD {r['max_dd']:.1f}% (0 liq)")

    # ── Part 3: Optimize for $500 on 1h ──
    print("\n── Part 3: Optimize $500 (on 1h) ──")
    opt500 = optimize(500, hi_opt, lo_opt, cl_opt, tfh_opt, "1h")
    print(f"  Tested: {opt500['tested']} configs")
    if opt500["best"]:
        r = opt500["best"]["r"]
        print(f"  Best: {r['ret_pct']:+.1f}%, Liq {r['n_liq']}, DD {r['max_dd']:.1f}%")
    if opt500["safest"]:
        r = opt500["safest"]["r"]
        print(f"  Safest: {r['ret_pct']:+.1f}%, DD {r['max_dd']:.1f}% (0 liq)")

    # ── Write report ──
    out = write_report(scr_results, opt300, opt500, ot_map)
    elapsed = _time.time() - t0
    print(f"\n  Report: {out}")
    print(f"  Done in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
