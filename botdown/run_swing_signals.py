#!/usr/bin/env python3
"""
Crypto swing signals on CLOSED daily candles + weekly trend bulletin → Telegram.

Runs locally (launchd com.cursor.swing-crypto, daily ~07:10 VN = after the 00:00 UTC close).
Intraday H1/H4 alerts stay on GitHub Actions (run_oi_telegram).

1D strategies (best saved backtests, see skill crypto-oi-usdtd):
  - OI scenarios G_regime_crowdfade, K_oi_usdtd_confluence, I_usdtd_risk_off_short
    TP 8% / SL 3% / max hold 10 bars (TF_DEFAULTS['1d'])
  - MACD+RSI (botdown engine) pct TP 10% / SL 4% + EMA20/50 filter, long+short
1W: weekly trend read-out (EMA20/50, Ichimoku cloud, MACD, RSI) — context only, sent once
    per closed week (Mon–Sun UTC). Also appended to every 1D signal.

Dedupe by closed-bar key → re-running after sleep never double-sends.

  PYTHONPATH=. python -m botdown.run_swing_signals --dry-run
  PYTHONPATH=. python -m botdown.run_swing_signals --weekly-only --dry-run
  PYTHONPATH=. python -m botdown.run_swing_signals --heartbeat
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from botdown.engine_macd_rsi_bt import MacdRsiParams, macd_rsi_entry_snapshot
from botdown.oi_liq_strategy import (
    TF_DEFAULTS,
    enrich_features,
    signal_oi_usdtd_confluence,
    signal_regime_crowdfade,
    signal_usdtd_risk_off_short,
)
from botdown.oi_live_signal import _drop_forming_bar
from botdown.swing_common import (
    SentStore,
    Signal,
    deliver,
    format_signal,
    format_weekly,
    h,
    now_vn,
    resample_ohlc,
    split_messages,
    trend_line,
    weekly_trend,
)
from data_loaders.oi_history import build_oi_panel_recent, fetch_klines_resilient

STORE = ROOT / "data" / "swing" / "swing_sent.json"

SCENARIOS_1D = [
    ("G_regime_crowdfade", "Bear + OI↑3d>5% + funding z>1 → SHORT | Bull + OI↑3d>2% + funding z<−1.5 → LONG",
     signal_regime_crowdfade),
    ("K_oi_usdtd_confluence", "OI + USDT.D + EMA cùng hướng", signal_oi_usdtd_confluence),
    ("I_usdtd_risk_off_short", "USDT.D risk-off + funding dương → SHORT", signal_usdtd_risk_off_short),
]

# In-sample 2022-01 → 2026-08, TP8/SL3/10d, fee 0.04% (botdown/reports/oi_scenarios_*.md)
EVIDENCE = {
    ("BTCUSDT", "G_regime_crowdfade"): "in-sample 2022–08/2026: 29 lệnh, win 45%, PF 1,83 (p≈0,08)",
    ("BTCUSDT", "K_oi_usdtd_confluence"): "in-sample: 50 lệnh, win 40%, PF 1,63 — chỉ tốt từ 2024 (PF 0,93 → 2,45)",
    ("BTCUSDT", "I_usdtd_risk_off_short"): "in-sample: 69 lệnh, win 36%, PF 1,38 — yếu",
    ("ETHUSDT", "G_regime_crowdfade"): "in-sample: 26 lệnh, win 42%, PF 1,77 (p≈0,11)",
    ("ETHUSDT", "K_oi_usdtd_confluence"): "in-sample: 44 lệnh, win 39%, PF 1,55",
    ("ETHUSDT", "I_usdtd_risk_off_short"): "in-sample: 62 lệnh, win 29%, PF 1,08 — gần hoà vốn",
    ("BTCUSDT", "macd_rsi_pct_ema"): "ngoài mẫu 2024–08/2026: 22 lệnh, +0,84%/lệnh (mẫu nhỏ)",
    ("ETHUSDT", "macd_rsi_pct_ema"): "chưa backtest riêng cho ETH",
}

CFG_1D = TF_DEFAULTS["1d"]


def _panel_1d(symbol: str) -> pd.DataFrame:
    panel = build_oi_panel_recent(symbol, interval="1d", lookback_bars=400)
    df = enrich_features(panel, bars_per_day=1)
    need = [c for c in ("oi_z_30", "fund_z_30", "ema50") if c in df.columns]
    if "usdt_d" in df.columns and df["usdt_d"].notna().sum() > 50:
        need.append("usdt_d_z_30")
    df = df.dropna(subset=need).reset_index(drop=True)
    return _drop_forming_bar(df, "1d")


def _snapshot_notes(row: pd.Series) -> List[str]:
    def f(x, nd=2, mul=1.0):
        return "—" if x is None or pd.isna(x) else f"{float(x) * mul:.{nd}f}"

    return [
        f"OI Δ3d {f(row.get('oi_chg_3'), 2, 100)}% · OI z30 {f(row.get('oi_z_30'))} · funding z {f(row.get('fund_z_30'))}",
        f"USDT.D {f(row.get('usdt_d'), 3)}% (Δ3d {f(row.get('usdt_d_chg_3'), 3)}, z {f(row.get('usdt_d_z_30'))})",
        f"EMA50 regime: {'bull' if bool(row.get('bull')) else ('bear' if bool(row.get('bear')) else 'neutral')}",
    ]


def _levels(entry: float, side: str, tp: float, sl: float):
    if side == "long":
        return entry * (1 - sl), entry * (1 + tp)
    return entry * (1 + sl), entry * (1 - tp)


def scan_daily(symbol: str, df: pd.DataFrame) -> List[Signal]:
    out: List[Signal] = []
    if len(df) < 60:
        print(f"  {symbol}: chỉ {len(df)} nến 1D sạch — bỏ qua")
        return out
    row = df.iloc[-1]
    bar = pd.Timestamp(row["date"]).strftime("%Y-%m-%d")
    close = float(row["close"])
    notes = _snapshot_notes(row)

    for name, rule, fn in SCENARIOS_1D:
        sig = fn(df)
        v, v_prev = int(sig.iloc[-1]), int(sig.iloc[-2])
        # Edge-trigger: scenarios are persistent states (I stays on for weeks) → alert only when it turns on/flips
        if v == 0 or v == v_prev:
            continue
        side = "long" if v > 0 else "short"
        stop, target = _levels(close, side, float(CFG_1D["tp"]), float(CFG_1D["sl"]))
        out.append(Signal(
            asset="crypto", symbol=symbol, tf="1D", side=side, strategy=name, rule=rule,
            bar_time=bar, entry=close, stop=stop, target=target,
            max_hold=f"{CFG_1D['max_hold']} nến ngày", evidence=EVIDENCE.get((symbol, name)),
            notes=notes,
        ))

    ot = (pd.to_datetime(df["date"]).astype("int64") // 10**6).to_numpy()
    p = MacdRsiParams(exit_mode="pct", take_profit_pct=0.10, stop_loss_pct=0.04, use_ema_trend_filter=True)
    snap = macd_rsi_entry_snapshot(ot, df["high"].to_numpy(float), df["low"].to_numpy(float),
                                   df["close"].to_numpy(float), params=p, allow_short=True)
    if snap and snap.get("side") in ("long", "short"):
        out.append(Signal(
            asset="crypto", symbol=symbol, tf="1D", side=str(snap["side"]), strategy="macd_rsi_pct_ema",
            rule="MACD hist cắt 0 + RSI (70/30) + EMA20/50 cùng hướng",
            bar_time=bar, entry=float(snap.get("entry_ref", close)),
            stop=float(snap["stop"]) if snap.get("stop") is not None else None,
            target=float(snap["tp"]) if snap.get("tp") is not None else None,
            max_hold="tới khi hist MACD đảo chiều hoặc chạm SL/TP",
            evidence=EVIDENCE.get((symbol, "macd_rsi_pct_ema")),
        ))
    return out


def weekly_for(symbol: str) -> tuple[Optional[Dict], Optional[str]]:
    """Trend of the last closed Mon–Sun (UTC) week + its week-end date."""
    start = (datetime.now(timezone.utc) - timedelta(days=3 * 365)).strftime("%Y-%m-%d")
    d = fetch_klines_resilient(symbol, interval="1d", start=start)
    d = d.rename(columns={c: c.lower() for c in d.columns})
    tcol = "date" if "date" in d.columns else ("open_time" if "open_time" in d.columns else d.columns[0])
    d = d.rename(columns={tcol: "date"})
    d["date"] = pd.to_datetime(d["date"])
    if getattr(d["date"].dt, "tz", None) is not None:
        d["date"] = d["date"].dt.tz_convert("UTC").dt.tz_localize(None)
    today = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
    d = d[d["date"] < today]                                  # drop forming daily bar
    w = resample_ohlc(d, "W-SUN")
    w = w[w["week_end"] < today]                               # week ends Sunday; closed after Sun 24:00 UTC
    if len(w) == 0:
        return None, None
    t = weekly_trend(w["high"].to_numpy(), w["low"].to_numpy(), w["close"].to_numpy())
    return t, pd.Timestamp(w["week_end"].iloc[-1]).strftime("%Y-%m-%d")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbols", default="BTCUSDT,ETHUSDT")
    ap.add_argument("--dry-run", action="store_true", help="in ra, không gửi, không ghi dedupe")
    ap.add_argument("--no-dedupe", action="store_true")
    ap.add_argument("--heartbeat", action="store_true", help="gửi 1 dòng tóm tắt khi không có tín hiệu 1D")
    ap.add_argument("--weekly-only", action="store_true")
    ap.add_argument("--daily-only", action="store_true")
    args = ap.parse_args()

    from notify.telegram import send_message

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    store = SentStore(STORE)
    seen = (lambda k: False) if args.no_dedupe else (lambda k: k in store)
    print(f"=== Crypto swing {now_vn():%Y-%m-%d %H:%M} VN | {symbols} ===")

    weekly: Dict[str, Optional[Dict]] = {}
    week_end: Optional[str] = None
    for s in symbols:
        try:
            weekly[s], we = weekly_for(s)
            week_end = week_end or we
            print(f"  {s} 1W {we}: {trend_line(weekly[s])}")
        except Exception as e:
            weekly[s] = None
            print(f"  {s} 1W ERR {e}", file=sys.stderr)

    blocks: List[str] = []
    sent_keys: List[str] = []
    errors = 0

    if not args.daily_only and week_end:
        wkey = f"WEEKLY|crypto|{week_end}"
        if not seen(wkey):
            blocks.append(format_weekly(f"Crypto — xu hướng tuần kết thúc {week_end} (UTC)",
                                        [(s, weekly.get(s), None) for s in symbols],
                                        "Tuần Binance: T2 00:00 → CN 24:00 UTC."))
            sent_keys.append(wkey)

    if not args.weekly_only:
        bars = {}
        sigs: List[Signal] = []
        for s in symbols:
            try:
                df = _panel_1d(s)
                bars[s] = pd.Timestamp(df.iloc[-1]["date"]).strftime("%Y-%m-%d") if len(df) else "?"
                found = scan_daily(s, df)
                print(f"  {s} 1D {bars[s]}: {[(x.strategy, x.side) for x in found] or 'không có tín hiệu'}")
                sigs.extend(found)
            except Exception as e:
                errors += 1
                print(f"  {s} 1D ERR {e}", file=sys.stderr)
        new = [x for x in sigs if not seen(x.key)]
        for x in new:
            blocks.append(format_signal(x, weekly.get(x.symbol)))
            sent_keys.append(x.key)
        if not sigs and args.heartbeat and bars:
            day = max(bars.values())
            hkey = f"HEARTBEAT|crypto|{day}"
            if not seen(hkey):
                wk = " · ".join(f"{s} tuần {weekly[s]['bias']}" for s in symbols if weekly.get(s))
                blocks.append(f"📭 Crypto 1D {h(day)}: không có tín hiệu G/K/I/MACD. {h(wk)}")
                sent_keys.append(hkey)

    if not blocks:
        print("Không có gì mới để gửi.")
        return 1 if errors and errors == len(symbols) else 0

    ok = deliver(split_messages(blocks), send_message, args.dry_run)
    if ok and not args.dry_run:
        for k in sent_keys:
            store.add(k)
        store.save()
    print(f"{'DRY ' if args.dry_run else ''}blocks={len(blocks)} ok={ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
