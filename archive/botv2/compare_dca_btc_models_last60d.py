"""
Compare OKX-style DCA Futures models on BTC (last ~2 months)
===============================================================
Goal
 - Create a BTC DCA bot configuration (direction chosen by MA200(1D))
 - Compare multiple DCA parameter "models" on:
     1) highest PnL/ROI
     2) highest number of winning TP cycles ("cycles ăn được")

Notes
 - Uses the same simplified engine as `botv2/simulate_dca_bot.py` but adds `direction`
   support (long/short) and runs on the last ~60 days.
 - It is a simulation/approximation for relative comparison.

Output
 - Markdown report saved to `botv2/reports/dca_btc_model_compare_last60d.md`

Usage
   python -m botv2.compare_dca_btc_models_last60d
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

from botv2.config import CACHE_DIR, BOTV2_ROOT


REPORTS = BOTV2_ROOT / "reports"

EFFECTIVE_FEE = 0.0005 * 0.60  # taker 0.05% after rebate => 0.03%
FUNDING_RATE_8H = 0.0001
TF_HOURS = 1.0


def _read_ohlcv_1d(path: Path) -> Tuple[np.ndarray, np.ndarray]:
    ts = []
    cl = []
    with open(path) as f:
        r = csv.reader(f)
        next(r)
        for row in r:
            if len(row) < 6:
                continue
            ts.append(int(row[0]))
            cl.append(float(row[4]))
    return np.asarray(ts, dtype=np.int64), np.asarray(cl, dtype=float)


def _read_ohlcv_1h(path: Path) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    ts = []
    hi = []
    lo = []
    cl = []
    with open(path) as f:
        r = csv.reader(f)
        next(r)
        for row in r:
            if len(row) < 6:
                continue
            ts.append(int(row[0]))
            hi.append(float(row[2]))
            lo.append(float(row[3]))
            cl.append(float(row[4]))
    return (
        np.asarray(ts, dtype=np.int64),
        np.asarray(hi, dtype=float),
        np.asarray(lo, dtype=float),
        np.asarray(cl, dtype=float),
    )


def _ts_to_dt(ts: int) -> str:
    # ts in seconds or ms
    v = int(ts)
    if v < 1e12:
        v *= 1000
    return datetime.fromtimestamp(v / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def _choose_direction_by_ma200_1d(btc_1d_cl: np.ndarray) -> Tuple[str, float]:
    if btc_1d_cl.size < 200:
        return "short", 0.0
    ma200 = float(np.mean(btc_1d_cl[-200:]))
    last = float(btc_1d_cl[-1])
    pct = (last - ma200) / ma200 * 100.0
    direction = "short" if pct < 0 else "long"
    return direction, pct


@dataclass(frozen=True)
class Cfg:
    direction: str  # "long" | "short"
    lev: int
    ps: float  # price deviation (%) per step
    tp: float  # take profit per cycle (%)
    max_so: int
    init_m: float
    so_m: float
    vs: float  # vol scale
    ss: float  # step scale

    def so_drop_fracs(self) -> np.ndarray:
        step = self.ps / 100.0
        cum = 0.0
        drops = []
        for _ in range(self.max_so):
            cum += step
            drops.append(cum)
            step *= self.ss
        return np.asarray(drops, dtype=float)

    def total_margin(self) -> float:
        # init + SO sequence
        t = self.init_m
        m = self.so_m
        for _ in range(self.max_so):
            t += m
            m *= self.vs
        return float(t)


def simulate(cfg: Cfg, capital: float, hi: np.ndarray, lo: np.ndarray, cl: np.ndarray) -> Dict:
    """
    Return:
      final, ret_pct, n_cycles, n_tp, n_liq, win_rate, max_dd
    """
    n = len(cl)
    balance = float(capital)
    peak_balance = balance
    max_dd = 0.0

    so_drop_fracs = cfg.so_drop_fracs()
    so_margins = np.asarray([cfg.so_m * (cfg.vs ** i) for i in range(cfg.max_so)], dtype=float)

    cycles = 0
    tp_cycles = 0
    liq_cycles = 0

    i = 0
    funding_per_bar = FUNDING_RATE_8H * (TF_HOURS / 8.0)

    while i < n and balance > cfg.init_m:
        entry_price = float(cl[i])
        entry_i = i

        # open position
        init_notional = cfg.init_m * cfg.lev
        init_coins = init_notional / entry_price
        fee = init_notional * EFFECTIVE_FEE
        balance -= fee

        total_coins = init_coins
        total_cost = init_notional  # keep "cost" as notional basis (for avg)
        total_margin = float(cfg.init_m)
        avg_entry = entry_price

        # Safety order triggers
        if cfg.direction == "long":
            so_trigger_prices = entry_price * (1.0 - so_drop_fracs)
            tp_price = avg_entry * (1.0 + cfg.tp / 100.0)
        else:
            so_trigger_prices = entry_price * (1.0 + so_drop_fracs)
            tp_price = avg_entry * (1.0 - cfg.tp / 100.0)

        next_so = 0
        exit_i = i
        exit_reason = "end"
        exit_price = entry_price

        for j in range(i + 1, n):
            bar_lo = float(lo[j])
            bar_hi = float(hi[j])

            # funding cost on current notional basis
            fc = total_cost * funding_per_bar
            balance -= fc

            # fill SOs while adverse move reaches next trigger
            while next_so < cfg.max_so:
                trig = float(so_trigger_prices[next_so])
                if cfg.direction == "long":
                    cond = bar_lo <= trig
                else:
                    cond = bar_hi >= trig

                if not cond:
                    break

                sm = float(so_margins[next_so])
                if balance < sm:
                    break

                fill_price = trig
                so_notional = sm * cfg.lev
                so_coins = so_notional / fill_price
                sfee = so_notional * EFFECTIVE_FEE
                balance -= sfee

                total_coins += so_coins
                total_cost += so_notional
                total_margin += sm
                avg_entry = total_cost / total_coins

                # update tp_price after avg changes
                if cfg.direction == "long":
                    tp_price = avg_entry * (1.0 + cfg.tp / 100.0)
                else:
                    tp_price = avg_entry * (1.0 - cfg.tp / 100.0)

                next_so += 1

            # TP check
            tp_hit = (bar_hi >= tp_price) if cfg.direction == "long" else (bar_lo <= tp_price)
            if tp_hit:
                exit_reason = "tp"
                exit_i = j
                exit_price = tp_price

                pnl = (total_coins * (exit_price - avg_entry)) if cfg.direction == "long" else (
                    total_coins * (avg_entry - exit_price)
                )
                cfee = total_coins * exit_price * EFFECTIVE_FEE
                balance -= cfee
                balance += pnl
                break

            # liquidation check (simplified)
            # long liquidation when loss >= 95% margin => (avg - bar_lo) * coins >= 0.95*margin
            # short liquidation => (bar_hi - avg) * coins >= 0.95*margin
            if cfg.direction == "long":
                unrealised_loss = total_coins * (avg_entry - bar_lo)
            else:
                unrealised_loss = total_coins * (bar_hi - avg_entry)

            if unrealised_loss >= total_margin * 0.95:
                exit_reason = "liquidation"
                exit_i = j
                exit_price = bar_hi if cfg.direction == "short" else bar_lo
                liq_cycles += 1
                balance = max(0.0, balance - total_margin)
                break
        else:
            # end of data
            exit_reason = "end"
            exit_i = n - 1
            exit_price = float(cl[-1])
            if cfg.direction == "long":
                pnl = total_coins * (exit_price - avg_entry)
            else:
                pnl = total_coins * (avg_entry - exit_price)
            cfee = total_coins * exit_price * EFFECTIVE_FEE
            balance -= cfee
            balance += pnl

        cycles += 1

        if exit_reason == "tp":
            tp_cycles += 1

        peak_balance = max(peak_balance, balance)
        dd = (peak_balance - balance) / peak_balance * 100.0 if peak_balance > 0 else 0.0
        max_dd = max(max_dd, dd)

        i = exit_i + 1

    ret_pct = (balance / capital - 1.0) * 100.0 if capital > 0 else 0.0
    win_rate = tp_cycles / max(cycles, 1) * 100.0

    return {
        "final": balance,
        "ret_pct": ret_pct,
        "max_dd": max_dd,
        "n_cycles": cycles,
        "n_tp": tp_cycles,
        "n_liq": liq_cycles,
        "win_rate": win_rate,
    }


def main() -> None:
    # Data paths
    btc_1h_path = Path(CACHE_DIR) / "binance" / "spot" / "BTC_USDT_1h.csv"
    btc_1d_path = Path(CACHE_DIR) / "binance" / "spot" / "BTC_USDT_1d.csv"

    ts_1h, hi_1h, lo_1h, cl_1h = _read_ohlcv_1h(btc_1h_path)
    ts_1d, cl_1d = _read_ohlcv_1d(btc_1d_path)

    last_ts = int(ts_1h[-1])
    cutoff = last_ts - int(60 * 86400 * 1000)  # ~60 days in ms
    start_idx = int(np.searchsorted(ts_1h, cutoff, side="left"))

    hi = hi_1h[start_idx:]
    lo = lo_1h[start_idx:]
    cl = cl_1h[start_idx:]
    ts_win = ts_1h[start_idx:]

    direction, pct_dev = _choose_direction_by_ma200_1d(cl_1d)

    entry = float(cl[0])
    end = float(cl[-1])
    window_start = _ts_to_dt(ts_win[0])
    window_end = _ts_to_dt(ts_win[-1])

    # Screenshot-like base (from your ETH screenshot)
    init_m = 5.0
    so_m = 5.0
    vs = 1.0
    ss = 1.1

    levs = [5, 8]
    ps_list = [0.45, 0.53, 0.75, 1.0]
    tps = [1.0, 1.5, 1.7, 2.0]
    max_sos = [8, 10, 15]

    # Ensure evaluation includes your ETH-like take profit 1.7
    # (already in tp list)
    candidates: List[Cfg] = []
    for lev, ps, tp, mso in product(levs, ps_list, tps, max_sos):
        candidates.append(Cfg(direction=direction, lev=lev, ps=ps, tp=tp, max_so=mso,
                                init_m=init_m, so_m=so_m, vs=vs, ss=ss))

    print(f"BTC window: {window_start} → {window_end} | direction chosen: {direction} | MA200 dev={pct_dev:.2f}%")
    print(f"Candidates: {len(candidates)}")

    results = []
    for idx, cfg in enumerate(candidates, start=1):
        tm = cfg.total_margin()
        # give a small buffer to reduce forced partial-fills due to balance < SO margin
        capital = tm * 1.05
        r = simulate(cfg, capital, hi, lo, cl)
        results.append((cfg, r, tm))
        if idx % 20 == 0:
            print(f"  tested {idx}/{len(candidates)}")

    # Filter configs without liquidation events (prefer safety)
    safe = [x for x in results if x[1]["n_liq"] == 0]
    if not safe:
        safe = results

    # Best by PnL/ROI
    safe.sort(key=lambda x: x[1]["ret_pct"], reverse=True)
    best_roi_cfg, best_roi_r, best_roi_tm = safe[0]

    # Most winning cycles
    safe.sort(key=lambda x: (x[1]["n_tp"], x[1]["ret_pct"]), reverse=True)
    best_tp_cfg, best_tp_r, best_tp_tm = safe[0]

    # Top 10 for report
    safe_sorted = sorted(safe, key=lambda x: x[1]["ret_pct"], reverse=True)[:10]

    report_path = REPORTS / "dca_btc_model_compare_last60d.md"
    REPORTS.mkdir(parents=True, exist_ok=True)

    # Markdown writer
    lines: List[str] = []
    lines.append("# DCA BTC Models Compare (last ~2 months)")
    lines.append("")
    lines.append(f"**Window**: {window_start} → {window_end}")
    lines.append(f"**BTC change**: {entry:,.2f} → {end:,.2f} ({(end/entry-1)*100:+.1f}%)")
    lines.append(f"**MA200(1D) dev**: {pct_dev:+.2f}% → choose direction **{direction}**")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 1) Best by ROI (PnL)")
    lines.append("")
    lines.append("| Direction | Leverage | Price deviation | Take profit | Max SO | Vol scale | Step scale | ROI | TP cycles | Max DD |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    lines.append(
        f"| {best_roi_cfg.direction} | {best_roi_cfg.lev}x | {best_roi_cfg.ps:.2f}% | {best_roi_cfg.tp:.2f}% | {best_roi_cfg.max_so} | {best_roi_cfg.vs:.2f}x | {best_roi_cfg.ss:.2f}x | "
        f"{best_roi_r['ret_pct']:+.1f}% | {best_roi_r['n_tp']} | {best_roi_r['max_dd']:.1f}% |"
    )
    lines.append("")
    lines.append("## 2) Best by TP cycles (cycles ăn được nhiều nhất)")
    lines.append("")
    lines.append("| Direction | Leverage | Price deviation | Take profit | Max SO | TP cycles | Cycles | ROI | Max DD |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    lines.append(
        f"| {best_tp_cfg.direction} | {best_tp_cfg.lev}x | {best_tp_cfg.ps:.2f}% | {best_tp_cfg.tp:.2f}% | {best_tp_cfg.max_so} | "
        f"{best_tp_r['n_tp']} | {best_tp_r['n_cycles']} | {best_tp_r['ret_pct']:+.1f}% | {best_tp_r['max_dd']:.1f}% |"
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 3) Top 10 by ROI (no liquidation)")
    lines.append("")
    lines.append("| # | Lev | dev | TP | MaxSO | ROI | TP cycles | Liq | Max DD |")
    lines.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for i, (cfg, r, tm) in enumerate(safe_sorted, start=1):
        lines.append(f"| {i} | {cfg.lev}x | {cfg.ps:.2f}% | {cfg.tp:.2f}% | {cfg.max_so} | {r['ret_pct']:+.1f}% | {r['n_tp']} | {r['n_liq']} | {r['max_dd']:.1f}% |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 4) Recommended OKX setup (parameter-only)")
    lines.append("")
    lines.append(f"- Direction: **{best_roi_cfg.direction}**")
    lines.append(f"- Leverage: **{best_roi_cfg.lev}x**")
    lines.append(f"- Price deviation: **{best_roi_cfg.ps:.2f}%**")
    lines.append(f"- Take profit: **{best_roi_cfg.tp:.2f}%**")
    lines.append(f"- Max safety orders: **{best_roi_cfg.max_so}**")
    lines.append(f"- Vol scale: **{best_roi_cfg.vs:.2f}x**")
    lines.append(f"- Step scale: **{best_roi_cfg.ss:.2f}x**")
    lines.append("")
    lines.append("**Important**: bạn đang cần cả điều kiện Start/Stop và số tiền cho Initial/Safety order để đảm bảo đủ margin fill SO; thông số amount không có trong report này.")
    lines.append("")
    lines.append(f"*Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport saved: {report_path}")
    print(f"Best ROI: {best_roi_cfg} => ROI {best_roi_r['ret_pct']:+.1f}% | TP cycles {best_roi_r['n_tp']}")
    print(f"Most TP cycles: {best_tp_cfg} => TP cycles {best_tp_r['n_tp']} | ROI {best_tp_r['ret_pct']:+.1f}%")


if __name__ == "__main__":
    main()

