"""
OI + Funding + USDT.D scenario strategies for BTC perpetual (1d / 4h / 1h).

Đánh giá chính: **win rate** (min trades), không tối ưu ROI vs buy&hold.

Lookbacks OI / USDT.D / funding theo **lịch** (3 ngày, 30 ngày) trên mọi khung;
EMA 20/50/200 tính trên nến khung đó.

USDT.D ↑ = risk-off vào stable → thiên short BTC; USDT.D ↓ = risk-on → thiên long.

Not investment advice. Fees 0.04% round-trip assumed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

try:
    import numpy as np
    import pandas as pd
except ImportError:
    np = None
    pd = None


FEE_RT = 0.0004
DEFAULT_TP = 0.08
DEFAULT_SL = 0.03
MAX_HOLD = 10  # bars on 1d (= days)
MIN_TRADES_RANK = 8  # ignore tiny samples when ranking by win rate (1d)
MIN_TRADES_BY_TF = {"1d": 8, "4h": 20, "1h": 40}

# Default exits scaled down from daily 8%/3%/10d
TF_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "1d": {"tp": 0.08, "sl": 0.03, "max_hold": 10, "bars_per_day": 1},
    "4h": {"tp": 0.04, "sl": 0.015, "max_hold": 24, "bars_per_day": 6},
    "1h": {"tp": 0.015, "sl": 0.006, "max_hold": 48, "bars_per_day": 24},
}


@dataclass
class ScenarioResult:
    name: str
    description: str
    n_trades: int
    win_rate: float
    return_pct: float
    max_dd_pct: float
    avg_hold_days: float
    expectancy_pct: float
    profit_factor: float
    buy_hold_pct: float
    params: Dict[str, Any]
    planned_rr: float = 0.0
    realized_rr: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    n_wins: int = 0
    n_losses: int = 0
    be_win_rate: float = 0.0
    cagr_pct: float = 0.0
    expectancy_r: float = 0.0
    profit_usd_1k: float = 0.0
    years: float = 0.0
    exit_tp_pct: float = 0.0
    exit_sl_pct: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def enrich_features(panel: "pd.DataFrame", bars_per_day: int = 1) -> "pd.DataFrame":
    """
    Feature names keep daily meaning: oi_chg_3 = OI change over ~3 calendar days.
    EMA 20/50/200 stay native to the bar timeframe.
    """
    df = panel.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    b = max(int(bars_per_day), 1)
    d1, d3, d7, d30 = b, 3 * b, 7 * b, 30 * b
    hh = 20  # native TF swing

    df["ret_1"] = df["close"].pct_change(d1)
    df["ret_3"] = df["close"].pct_change(d3)
    df["ret_7"] = df["close"].pct_change(d7)

    df["oi_chg_1"] = df["oi_btc"].pct_change(d1)
    df["oi_chg_3"] = df["oi_btc"].pct_change(d3)
    df["oi_chg_7"] = df["oi_btc"].pct_change(d7)
    df["oi_z_30"] = (df["oi_btc"] - df["oi_btc"].rolling(d30).mean()) / df["oi_btc"].rolling(d30).std()
    if b == 1:
        df["oi_pctile_90"] = df["oi_btc"].rolling(90).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1] if len(x) == 90 else np.nan,
            raw=False,
        )

    df["fund"] = df["funding_mean"].fillna(0.0)
    df["fund_z_30"] = (df["fund"] - df["fund"].rolling(d30).mean()) / df["fund"].rolling(d30).std()
    df["fund_sum_3"] = df["fund"].rolling(d3).sum()

    df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()
    df["bull"] = (df["ema20"] > df["ema50"]) & (df["close"] > df["ema50"])
    df["bear"] = (df["ema20"] < df["ema50"]) & (df["close"] < df["ema50"])

    df["price_hh"] = df["close"] >= df["close"].rolling(hh).max().shift(1)
    df["price_ll"] = df["close"] <= df["close"].rolling(hh).min().shift(1)
    df["oi_hh"] = df["oi_btc"] >= df["oi_btc"].rolling(hh).max().shift(1)
    df["oi_ll"] = df["oi_btc"] <= df["oi_btc"].rolling(hh).min().shift(1)
    df["oi_flush"] = (df["oi_chg_1"] < -0.04) & (df["oi_z_30"].shift(1) > 0.5)

    if "usdt_d" in df.columns:
        df["usdt_d"] = pd.to_numeric(df["usdt_d"], errors="coerce")
        df["usdt_d_chg_3"] = df["usdt_d"].diff(d3)
        df["usdt_d_chg_7"] = df["usdt_d"].diff(d7)
        df["usdt_d_z_30"] = (df["usdt_d"] - df["usdt_d"].rolling(d30).mean()) / df["usdt_d"].rolling(d30).std()
        df["usdt_d_hh"] = df["usdt_d"] >= df["usdt_d"].rolling(hh).max().shift(1)
        df["usdt_d_ll"] = df["usdt_d"] <= df["usdt_d"].rolling(hh).min().shift(1)
        df["usdtd_risk_off"] = (df["usdt_d_chg_3"] > 0.15) | (df["usdt_d_z_30"] > 1.0)
        df["usdtd_risk_on"] = (df["usdt_d_chg_3"] < -0.15) | (df["usdt_d_z_30"] < -1.0)
    else:
        df["usdt_d"] = np.nan
        df["usdt_d_chg_3"] = np.nan
        df["usdt_d_z_30"] = np.nan
        df["usdtd_risk_off"] = False
        df["usdtd_risk_on"] = False

    df.attrs["bars_per_day"] = b
    return df


def _fmt_bar_time(ts, interval: str) -> str:
    t = pd.Timestamp(ts)
    if interval == "1d":
        return str(t.date())
    return t.strftime("%Y-%m-%d %H:%M")


def _simulate(
    df: "pd.DataFrame",
    signals: "pd.Series",
    tp: float = DEFAULT_TP,
    sl: float = DEFAULT_SL,
    max_hold: int = MAX_HOLD,
    fee: float = FEE_RT,
    interval: str = "1d",
    bars_per_day: int = 1,
) -> Tuple[List[dict], Dict[str, float]]:
    trades: List[dict] = []
    i = 0
    n = len(df)
    opens = df["open"].values
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    dates = df["date"].values
    sig = signals.fillna(0).astype(int).values

    while i < n - 2:
        side = int(sig[i])
        if side == 0:
            i += 1
            continue
        entry_i = i + 1
        entry = float(opens[entry_i])
        if entry <= 0:
            i += 1
            continue
        if side > 0:
            tp_px, sl_px = entry * (1 + tp), entry * (1 - sl)
        else:
            tp_px, sl_px = entry * (1 - tp), entry * (1 + sl)

        exit_i = None
        exit_px = None
        reason = "time"
        for j in range(entry_i, min(entry_i + max_hold, n)):
            hi, lo = float(highs[j]), float(lows[j])
            if side > 0:
                if lo <= sl_px:
                    exit_i, exit_px, reason = j, sl_px, "sl"
                    break
                if hi >= tp_px:
                    exit_i, exit_px, reason = j, tp_px, "tp"
                    break
            else:
                if hi >= sl_px:
                    exit_i, exit_px, reason = j, sl_px, "sl"
                    break
                if lo <= tp_px:
                    exit_i, exit_px, reason = j, tp_px, "tp"
                    break
            if j > entry_i and int(sig[j]) == -side:
                exit_i, exit_px, reason = j, float(closes[j]), "flip"
                break
        if exit_i is None:
            exit_i = min(entry_i + max_hold - 1, n - 1)
            exit_px = float(closes[exit_i])
            reason = "time"

        if side > 0:
            pnl = (exit_px / entry - 1.0) - fee
        else:
            pnl = (entry / exit_px - 1.0) - fee

        hold_bars = int(exit_i - entry_i + 1)
        pnl_pct = 100 * pnl
        r_mult = pnl_pct / (sl * 100.0) if sl else 0.0
        trades.append(
            {
                "entry_date": _fmt_bar_time(dates[entry_i], interval),
                "exit_date": _fmt_bar_time(dates[exit_i], interval),
                "side": "long" if side > 0 else "short",
                "entry": round(entry, 2),
                "exit": round(exit_px, 2),
                "pnl_pct": round(pnl_pct, 3),
                "r_multiple": round(r_mult, 3),
                "hold_bars": hold_bars,
                "hold_days": round(hold_bars / max(bars_per_day, 1), 3),
                "reason": reason,
            }
        )
        i = exit_i + 1

    t0 = pd.Timestamp(dates[0]) if n else None
    t1 = pd.Timestamp(dates[-1]) if n else None
    years = (
        max((t1 - t0).total_seconds() / (365.25 * 86400.0), 1e-6)
        if t0 is not None and t1 is not None
        else 0.0
    )
    planned_rr = (tp / sl) if sl else 0.0
    be_planned = 100.0 / (1.0 + planned_rr) if planned_rr else 0.0
    bh = float(closes[-1] / closes[0] - 1.0) if n > 1 else 0.0

    if not trades:
        return [], {
            "n_trades": 0,
            "win_rate": 0.0,
            "return_pct": 0.0,
            "max_dd_pct": 0.0,
            "avg_hold_days": 0.0,
            "avg_hold_bars": 0.0,
            "expectancy_pct": 0.0,
            "profit_factor": 0.0,
            "buy_hold_pct": round(100 * bh, 2),
            "planned_rr": round(planned_rr, 2),
            "realized_rr": 0.0,
            "avg_win_pct": 0.0,
            "avg_loss_pct": 0.0,
            "n_wins": 0,
            "n_losses": 0,
            "be_win_rate": round(be_planned, 1),
            "cagr_pct": 0.0,
            "expectancy_r": 0.0,
            "profit_usd_1k": 0.0,
            "years": round(years, 2),
            "exit_tp_pct": 0.0,
            "exit_sl_pct": 0.0,
            "exit_time_pct": 0.0,
            "exit_flip_pct": 0.0,
        }

    pnls = np.array([t["pnl_pct"] for t in trades], dtype=float)
    rs = np.array([t["r_multiple"] for t in trades], dtype=float)
    wins = pnls[pnls > 0]
    losses = pnls[pnls <= 0]
    eq = np.cumprod(1.0 + pnls / 100.0)
    peak = np.maximum.accumulate(eq)
    dd = (eq / peak - 1.0) * 100.0
    pf = float(wins.sum() / abs(losses.sum())) if len(losses) and losses.sum() != 0 else float("inf") if len(wins) else 0.0
    realized_rr = float(wins.mean() / abs(losses.mean())) if len(wins) and len(losses) and losses.mean() != 0 else 0.0
    be_real = 100.0 / (1.0 + realized_rr) if realized_rr > 0 else be_planned
    reasons = [t["reason"] for t in trades]
    n_t = len(trades)
    def _pct_reason(tag: str) -> float:
        return round(100.0 * reasons.count(tag) / n_t, 1)
    cagr = (float(eq[-1]) ** (1.0 / years) - 1.0) * 100.0 if years > 0 and eq[-1] > 0 else 0.0
    return trades, {
        "n_trades": n_t,
        "win_rate": round(100.0 * float((pnls > 0).mean()), 2),
        "return_pct": round(100.0 * float(eq[-1] - 1.0), 2),
        "max_dd_pct": round(float(dd.min()), 2),
        "avg_hold_days": round(float(np.mean([t["hold_days"] for t in trades])), 3),
        "avg_hold_bars": round(float(np.mean([t["hold_bars"] for t in trades])), 2),
        "expectancy_pct": round(float(pnls.mean()), 3),
        "profit_factor": round(pf, 3) if pf != float("inf") else 999.0,
        "buy_hold_pct": round(100 * bh, 2),
        "planned_rr": round(planned_rr, 2),
        "realized_rr": round(realized_rr, 2),
        "avg_win_pct": round(float(wins.mean()), 3) if len(wins) else 0.0,
        "avg_loss_pct": round(float(losses.mean()), 3) if len(losses) else 0.0,
        "n_wins": int(len(wins)),
        "n_losses": int(len(losses)),
        "be_win_rate": round(be_real, 1),
        "cagr_pct": round(cagr, 2),
        "expectancy_r": round(float(rs.mean()), 3),
        "profit_usd_1k": round(1000.0 * float(eq[-1] - 1.0), 2),
        "years": round(years, 2),
        "exit_tp_pct": _pct_reason("tp"),
        "exit_sl_pct": _pct_reason("sl"),
        "exit_time_pct": _pct_reason("time"),
        "exit_flip_pct": _pct_reason("flip"),
    }


def signal_crowdfade_short(df: "pd.DataFrame", oi_chg: float = 0.03, fund_z: float = 1.2) -> "pd.Series":
    cond = (df["oi_chg_3"] > oi_chg) & (df["fund_z_30"] > fund_z) & (df["oi_z_30"] > 0)
    return pd.Series(np.where(cond, -1, 0), index=df.index)


def signal_crowdfade_long(df: "pd.DataFrame", oi_chg: float = 0.03, fund_z: float = -1.2) -> "pd.Series":
    cond = (df["oi_chg_3"] > oi_chg) & (df["fund_z_30"] < fund_z) & (df["oi_z_30"] > 0)
    return pd.Series(np.where(cond, 1, 0), index=df.index)


def signal_flush_long(df: "pd.DataFrame") -> "pd.Series":
    cond = df["oi_flush"] & (df["close"] > df["ema20"]) & df["bull"]
    return pd.Series(np.where(cond, 1, 0), index=df.index)


def signal_flush_short(df: "pd.DataFrame") -> "pd.Series":
    cond = df["oi_flush"] & (df["close"] < df["ema20"]) & df["bear"]
    return pd.Series(np.where(cond, -1, 0), index=df.index)


def signal_oi_div_short(df: "pd.DataFrame") -> "pd.Series":
    cond = df["price_hh"] & (~df["oi_hh"]) & (df["fund_z_30"] > 0.5)
    return pd.Series(np.where(cond, -1, 0), index=df.index)


def signal_combined(df: "pd.DataFrame") -> "pd.Series":
    long_c = signal_crowdfade_long(df)
    short_c = signal_crowdfade_short(df)
    out = np.zeros(len(df), dtype=int)
    for i in range(len(df)):
        if int(long_c.iloc[i]) == 1 and not bool(df["bear"].iloc[i]):
            out[i] = 1
        elif int(short_c.iloc[i]) == -1 and not bool(df["bull"].iloc[i]):
            out[i] = -1
    fl = signal_flush_long(df)
    fs = signal_flush_short(df)
    for i in range(len(df)):
        if out[i] == 0:
            if int(fl.iloc[i]) == 1:
                out[i] = 1
            elif int(fs.iloc[i]) == -1:
                out[i] = -1
    return pd.Series(out, index=df.index)


def signal_regime_crowdfade(df: "pd.DataFrame") -> "pd.Series":
    short_c = (df["bear"] & (df["oi_chg_3"] > 0.05) & (df["fund_z_30"] > 1.0) & (df["oi_z_30"] > 0))
    long_c = (df["bull"] & (df["oi_chg_3"] > 0.02) & (df["fund_z_30"] < -1.5) & (df["oi_z_30"] > 0))
    return pd.Series(np.where(long_c, 1, np.where(short_c, -1, 0)), index=df.index)


def signal_bear_bounce_fade(df: "pd.DataFrame") -> "pd.Series":
    cond = df["bear"] & (df["oi_chg_3"] > 0.025) & (df["ret_3"] > 0.02) & (df["fund_z_30"] > 0.5)
    return pd.Series(np.where(cond, -1, 0), index=df.index)


def signal_usdtd_risk_off_short(df: "pd.DataFrame") -> "pd.Series":
    """USDT.D rising (risk-off) + funding hot → SHORT."""
    cond = df["usdtd_risk_off"] & (df["fund_z_30"] > 0.5) & (df["oi_z_30"] > -0.5)
    return pd.Series(np.where(cond, -1, 0), index=df.index)


def signal_usdtd_risk_on_long(df: "pd.DataFrame") -> "pd.Series":
    """USDT.D falling (risk-on) + funding cold → LONG."""
    cond = df["usdtd_risk_on"] & (df["fund_z_30"] < -0.5) & df["bull"]
    return pd.Series(np.where(cond, 1, 0), index=df.index)


def signal_oi_usdtd_confluence(df: "pd.DataFrame") -> "pd.Series":
    """
    OI + USDT.D + EMA (grid for win rate ~40%, n≈50):
      SHORT: bear + OI↑>2% + USDT.D Δ3d>+0.2 (or z>1) + fund z>0.3
      LONG:  bull + OI↑>1.5% + USDT.D Δ3d<-0.2 (or z<-1) + fund z<-0.5
    """
    short_c = (
        df["bear"]
        & (df["oi_chg_3"] > 0.02)
        & ((df["usdt_d_chg_3"] > 0.2) | (df["usdt_d_z_30"] > 1.0))
        & (df["fund_z_30"] > 0.3)
    )
    long_c = (
        df["bull"]
        & (df["oi_chg_3"] > 0.015)
        & ((df["usdt_d_chg_3"] < -0.2) | (df["usdt_d_z_30"] < -1.0))
        & (df["fund_z_30"] < -0.5)
    )
    return pd.Series(np.where(long_c, 1, np.where(short_c, -1, 0)), index=df.index)


SCENARIOS = [
    ("A_crowdfade_short", "OI↑3d>3% + funding z>1.2 → SHORT", signal_crowdfade_short),
    ("B_crowdfade_long", "OI↑3d>3% + funding z<-1.2 → LONG", signal_crowdfade_long),
    ("C_flush_long", "OI flush −4% + bull reclaim EMA → LONG", signal_flush_long),
    ("D_flush_short", "OI flush −4% + bear lose EMA → SHORT", signal_flush_short),
    ("E_oi_div_short", "Price HH không xác nhận OI + fund+ → SHORT", signal_oi_div_short),
    ("F_combined_ema", "Crowdfade lỏng ± flush + EMA", signal_combined),
    ("G_regime_crowdfade", "SHORT bear OI↑5%+fund+ | LONG bull OI↑2%+fund−", signal_regime_crowdfade),
    ("H_bear_bounce_fade", "Bear bounce + OI↑ + fund+ → SHORT", signal_bear_bounce_fade),
    ("I_usdtd_risk_off_short", "USDT.D↑ risk-off + fund+ → SHORT", signal_usdtd_risk_off_short),
    ("J_usdtd_risk_on_long", "USDT.D↓ risk-on + fund− + bull → LONG", signal_usdtd_risk_on_long),
    ("K_oi_usdtd_confluence", "★ OI + USDT.D + EMA confluence", signal_oi_usdtd_confluence),
]


def min_trades_for(interval: str) -> int:
    return int(MIN_TRADES_BY_TF.get(interval, MIN_TRADES_RANK))


def rank_key_winrate(r: ScenarioResult) -> Tuple[float, float, int]:
    """Primary: win rate (with min trades); tie-break expectancy then n."""
    min_n = int((r.params or {}).get("min_trades_rank", MIN_TRADES_RANK))
    if r.n_trades < min_n:
        return (-1.0, r.expectancy_pct, r.n_trades)
    return (r.win_rate, r.expectancy_pct, r.n_trades)


def run_all_scenarios(
    panel: "pd.DataFrame",
    tp: float = DEFAULT_TP,
    sl: float = DEFAULT_SL,
    max_hold: int = MAX_HOLD,
    interval: str = "1d",
    bars_per_day: Optional[int] = None,
) -> Tuple[List[ScenarioResult], Dict[str, List[dict]], "pd.DataFrame"]:
    cfg = TF_DEFAULTS.get(interval, TF_DEFAULTS["1d"])
    bpd = int(bars_per_day if bars_per_day is not None else cfg["bars_per_day"])
    min_n = min_trades_for(interval)
    df = enrich_features(panel, bars_per_day=bpd)
    need = ["oi_z_30", "fund_z_30", "ema50"]
    if "usdt_d" in df.columns and df["usdt_d"].notna().sum() > 50:
        need.append("usdt_d_z_30")
    df = df.dropna(subset=need).reset_index(drop=True)
    results: List[ScenarioResult] = []
    trade_books: Dict[str, List[dict]] = {}

    for name, desc, fn in SCENARIOS:
        sig = fn(df)
        trades, m = _simulate(
            df, sig, tp=tp, sl=sl, max_hold=max_hold, interval=interval, bars_per_day=bpd
        )
        trade_books[name] = trades
        results.append(
            ScenarioResult(
                name=name,
                description=desc,
                n_trades=m["n_trades"],
                win_rate=m["win_rate"],
                return_pct=m["return_pct"],
                max_dd_pct=m["max_dd_pct"],
                avg_hold_days=m["avg_hold_days"],
                expectancy_pct=m["expectancy_pct"],
                profit_factor=m["profit_factor"],
                buy_hold_pct=m["buy_hold_pct"],
                planned_rr=m["planned_rr"],
                realized_rr=m["realized_rr"],
                avg_win_pct=m["avg_win_pct"],
                avg_loss_pct=m["avg_loss_pct"],
                n_wins=m["n_wins"],
                n_losses=m["n_losses"],
                be_win_rate=m["be_win_rate"],
                cagr_pct=m["cagr_pct"],
                expectancy_r=m["expectancy_r"],
                profit_usd_1k=m["profit_usd_1k"],
                years=m["years"],
                exit_tp_pct=m["exit_tp_pct"],
                exit_sl_pct=m["exit_sl_pct"],
                params={
                    "tp": tp,
                    "sl": sl,
                    "max_hold": max_hold,
                    "fee_rt": FEE_RT,
                    "interval": interval,
                    "bars_per_day": bpd,
                    "min_trades_rank": min_n,
                    "avg_hold_bars": m.get("avg_hold_bars"),
                    "exit_time_pct": m.get("exit_time_pct"),
                    "exit_flip_pct": m.get("exit_flip_pct"),
                },
            )
        )
    results.sort(key=rank_key_winrate, reverse=True)
    return results, trade_books, df


def current_scenario_state(df: "pd.DataFrame", liq_summary: Optional[dict] = None) -> Dict[str, Any]:
    row = df.iloc[-1]
    ts = pd.Timestamp(row["date"])
    date = str(ts.date()) if ts.hour == 0 and ts.minute == 0 and ts.second == 0 else ts.strftime("%Y-%m-%d %H:%M")
    active = []
    for name, desc, fn in SCENARIOS:
        sig = fn(df)
        v = int(sig.iloc[-1])
        if v != 0:
            active.append({"scenario": name, "side": "long" if v > 0 else "short", "desc": desc})

    regime = "bull" if bool(row["bull"]) else ("bear" if bool(row["bear"]) else "neutral")
    play = {
        "date": date,
        "close": round(float(row["close"]), 2),
        "oi_btc": round(float(row["oi_btc"]), 2),
        "oi_usd": round(float(row["oi_usd"]), 0),
        "oi_chg_3_pct": round(100 * float(row["oi_chg_3"]), 2) if pd.notna(row["oi_chg_3"]) else None,
        "oi_z_30": round(float(row["oi_z_30"]), 2) if pd.notna(row["oi_z_30"]) else None,
        "funding_mean": float(row["fund"]),
        "funding_z_30": round(float(row["fund_z_30"]), 2) if pd.notna(row["fund_z_30"]) else None,
        "usdt_d": round(float(row["usdt_d"]), 3) if pd.notna(row.get("usdt_d")) else None,
        "usdt_d_chg_3": round(float(row["usdt_d_chg_3"]), 3) if pd.notna(row.get("usdt_d_chg_3")) else None,
        "usdt_d_z_30": round(float(row["usdt_d_z_30"]), 2) if pd.notna(row.get("usdt_d_z_30")) else None,
        "usdtd_risk_off": bool(row["usdtd_risk_off"]) if "usdtd_risk_off" in df.columns else False,
        "usdtd_risk_on": bool(row["usdtd_risk_on"]) if "usdtd_risk_on" in df.columns else False,
        "regime_ema": regime,
        "active_signals": active,
    }

    preferred = [a for a in active if a["scenario"].startswith("K_")]
    focus = preferred or [a for a in active if a["scenario"].startswith(("I_", "J_", "G_"))] or active

    if liq_summary and not liq_summary.get("error"):
        play["liq_vote"] = liq_summary.get("vote_side")
        play["liq_reason"] = liq_summary.get("vote_reason")
        play["liq_long_cluster"] = (liq_summary.get("nearest_long_cluster") or {}).get("mid")
        play["liq_short_cluster"] = (liq_summary.get("nearest_short_cluster") or {}).get("mid")

        sides = {a["side"] for a in focus}
        liq = liq_summary.get("vote_side")
        if "short" in sides and liq == "short":
            play["recommended"] = {
                "side": "short",
                "confidence": "high",
                "thesis": "OI/USDT.D short confluence + liq cascade",
                "entry": play["close"],
                "stop": play["liq_short_cluster"],
                "target": play["liq_long_cluster"],
            }
        elif "long" in sides and liq == "long":
            play["recommended"] = {
                "side": "long",
                "confidence": "high",
                "thesis": "OI/USDT.D long confluence + short squeeze cluster",
                "entry": play["close"],
                "stop": play["liq_long_cluster"],
                "target": play["liq_short_cluster"],
            }
        elif focus:
            side = focus[0]["side"]
            play["recommended"] = {
                "side": side,
                "confidence": "medium",
                "thesis": focus[0]["desc"],
                "entry": play["close"],
                "stop": play["liq_short_cluster"] if side == "short" else play["liq_long_cluster"],
                "target": play["liq_long_cluster"] if side == "short" else play["liq_short_cluster"],
            }
        elif liq in ("long", "short"):
            play["recommended"] = {
                "side": liq,
                "confidence": "low",
                "thesis": "Only liquidation map — chờ OI/USDT.D confirm",
                "entry": None,
                "stop": play["liq_long_cluster"] if liq == "short" else play["liq_short_cluster"],
                "target": play["liq_short_cluster"] if liq == "long" else play["liq_long_cluster"],
            }
        else:
            play["recommended"] = {
                "side": "none",
                "confidence": "none",
                "thesis": "No OI/USDT.D confluence; flat",
            }
    else:
        play["recommended"] = {
            "side": focus[0]["side"] if focus else "none",
            "confidence": "medium" if focus else "none",
            "thesis": focus[0]["desc"] if focus else "No active scenario",
        }
    return play
