#!/usr/bin/env python3
"""
Gold + macro panel: FRED (Fed funds, yields, broad USD, NBER recession, VIX)
+ Yahoo Finance (COMEX GC=F daily -> monthly + weekly; ICE DXY daily -> monthly).

Outputs under vre/data/reports/:
  - gold_macro_panel_monthly.csv (full FRED history joined)
  - gold_macro_panel_monthly_trimmed.csv (từ tháng đầu có giá COMEX)
  - gold_macro_correlation_matrix_levels.csv
  - gold_macro_correlation_matrix_yoy.csv
  - gold_macro_rolling_corr.csv
  - gold_gc_f_weekly_from_daily.csv
  - gold_macro_summary.csv

Requires: FRED_API_KEY, pandas, fredapi, yfinance.

Run from repo root:
  python vre/scripts/gold_macro_analysis.py
  python vre/scripts/gold_macro_analysis.py --refresh

Nếu Python báo PEP 668: tạo venv rồi pip install -r requirements.txt
  python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

import numpy as np
import pandas as pd

from vre.data_loaders.fred import get_series, CACHE_DIR
from vre.data_loaders.gold_macro_data import (
    get_gold_futures_daily,
    get_dxy_daily,
    resample_ohlc_weekly,
    EXTERNAL_DIR,
)

REPORTS_DIR = ROOT / "vre" / "data" / "reports"
EVENTS_CSV = ROOT / "vre" / "data" / "events" / "war_episodes.csv"

# London PM gold FRED ids were retired from the API; monthly gold = COMEX front (Yahoo) resampled in this script.
FRED_MACRO_FOR_GOLD = [
    "FEDFUNDS",
    "GS10",
    "GS2",
    "DTWEXBGS",
    "USREC",
    "VIXCLS",
]


def _fred_to_monthly(df: pd.DataFrame, col: str) -> pd.DataFrame:
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").rename(columns={"value": col})
    return df.resample("MS").last()


def build_monthly_panel(
    api_key: str | None,
    force_refresh_fred: bool,
    force_refresh_yf: bool,
) -> pd.DataFrame:
    merged = None
    for sid in FRED_MACRO_FOR_GOLD:
        df = get_series(sid, force_refresh=force_refresh_fred, api_key=api_key)
        if df is None or df.empty:
            print(f"[warn] missing FRED series: {sid} (cache dir: {CACHE_DIR})")
            continue
        m = _fred_to_monthly(df, sid)
        merged = m if merged is None else merged.join(m, how="outer")

    gold_d = get_gold_futures_daily(force_refresh=force_refresh_yf)
    if gold_d is not None and not gold_d.empty:
        gold_d = gold_d.copy()
        gold_d["date"] = pd.to_datetime(gold_d["date"])
        g = gold_d.set_index("date")[["close"]].rename(columns={"close": "GOLD_COMEX_M_close"})
        g_m = g.resample("MS").last()
        merged = g_m if merged is None else merged.join(g_m, how="outer")

    dxy_d = get_dxy_daily(force_refresh=force_refresh_yf)
    if dxy_d is not None and not dxy_d.empty:
        dxy_d = dxy_d.copy()
        dxy_d["date"] = pd.to_datetime(dxy_d["date"])
        dx = dxy_d.set_index("date")[["close"]].rename(columns={"close": "DXY_YF_close_m"})
        dx_m = dx.resample("MS").last()
        merged = dx_m if merged is None else merged.join(dx_m, how="outer")

    if merged is None:
        return pd.DataFrame()

    merged = merged.sort_index().ffill()
    merged = merged.reset_index().rename(columns={"index": "date"})
    return merged


def add_yoy_and_log_diff(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.copy()
    out["date"] = pd.to_datetime(out["date"])
    out = out.sort_values("date").set_index("date")
    skip_yoy = {"USREC"}
    numeric = [c for c in out.columns if c not in skip_yoy and pd.api.types.is_numeric_dtype(out[c])]
    for c in numeric:
        out[f"{c}_yoy"] = out[c].pct_change(periods=12) * 100.0
        le = out[c].clip(lower=1e-9)
        ratio = le / le.shift(12)
        out[f"{c}_logdiff12"] = np.where(ratio.notna() & (ratio > 0), np.log(ratio), np.nan)
    return out.reset_index()


def correlation_matrices(panel_levels: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    cols_levels = [
        c
        for c in panel_levels.columns
        if c != "date"
        and not c.endswith("_yoy")
        and not c.endswith("_logdiff12")
        and panel_levels[c].dtype != object
    ]
    sub_l = panel_levels[cols_levels].dropna(how="all")
    corr_l = sub_l.corr(method="pearson", min_periods=24)

    yoy_cols = [c for c in panel_levels.columns if c.endswith("_yoy")]
    if yoy_cols:
        sub_y = panel_levels[["date"] + yoy_cols].dropna(how="all")
        corr_y = sub_y[yoy_cols].corr(method="pearson", min_periods=24)
    else:
        corr_y = pd.DataFrame()

    return corr_l, corr_y


def rolling_correlations(
    panel: pd.DataFrame,
    gold_col: str,
    others: list[str],
    window_months: int = 24,
) -> pd.DataFrame:
    d = panel.copy()
    d["date"] = pd.to_datetime(d["date"])
    d = d.sort_values("date").set_index("date")
    rows = []
    for o in others:
        if o not in d.columns or gold_col not in d.columns:
            continue
        pair = d[[gold_col, o]].dropna()
        if len(pair) < window_months + 2:
            continue
        roll = pair[gold_col].rolling(window_months).corr(pair[o])
        tmp = roll.reset_index()
        tmp.columns = ["date", "corr"]
        tmp["pair"] = f"{gold_col}_vs_{o}"
        rows.append(tmp)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def load_war_episodes() -> pd.DataFrame | None:
    if not EVENTS_CSV.exists():
        return None
    return pd.read_csv(EVENTS_CSV, parse_dates=["start", "end"])


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--refresh", action="store_true", help="Force FRED + yfinance refresh")
    p.add_argument("--window", type=int, default=24, help="Rolling correlation window (months)")
    args = p.parse_args()

    key = os.environ.get("FRED_API_KEY")
    if not key and not args.refresh:
        # allow running on cache-only if files exist
        pass

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    panel = build_monthly_panel(
        api_key=key,
        force_refresh_fred=args.refresh,
        force_refresh_yf=args.refresh,
    )
    if panel.empty:
        print("No panel data. Set FRED_API_KEY and run with --refresh, or populate vre/data/fred/*.csv")
        return 1

    panel_path = REPORTS_DIR / "gold_macro_panel_monthly.csv"
    panel.to_csv(panel_path, index=False)
    print(f"Wrote {panel_path} rows={len(panel)}")

    gold_m = "GOLD_COMEX_M_close"
    if gold_m in panel.columns:
        first_gold = panel[gold_m].first_valid_index()
        if first_gold is not None:
            trimmed = panel.loc[first_gold:].reset_index(drop=True)
            trim_path = REPORTS_DIR / "gold_macro_panel_monthly_trimmed.csv"
            trimmed.to_csv(trim_path, index=False)
            print(f"Wrote {trim_path} rows={len(trimmed)} (from first COMEX month)")

    panel_ext = add_yoy_and_log_diff(panel)
    corr_l, corr_y = correlation_matrices(panel_ext)
    corr_l.to_csv(REPORTS_DIR / "gold_macro_correlation_matrix_levels.csv")
    if not corr_y.empty:
        corr_y.to_csv(REPORTS_DIR / "gold_macro_correlation_matrix_yoy.csv")
    print(f"Wrote correlation matrices to {REPORTS_DIR}")

    others = [
        c
        for c in ["DXY_YF_close_m", "DTWEXBGS", "FEDFUNDS", "GS10", "GS2", "VIXCLS"]
        if c in panel.columns
    ]
    roll = rolling_correlations(panel, gold_m, others, window_months=args.window)
    if not roll.empty:
        roll.to_csv(REPORTS_DIR / "gold_macro_rolling_corr.csv", index=False)
        print(f"Wrote gold_macro_rolling_corr.csv rows={len(roll)}")

    # Weekly gold from daily cache (summary file for reference)
    gold_d = get_gold_futures_daily(force_refresh=False)
    if gold_d is not None and not gold_d.empty:
        wk = resample_ohlc_weekly(gold_d)
        wk_path = REPORTS_DIR / "gold_gc_f_weekly_from_daily.csv"
        wk.to_csv(wk_path, index=False)
        print(f"Wrote {wk_path} rows={len(wk)}")

    wars = load_war_episodes()
    if wars is not None:
        print("War episodes CSV loaded for reference:", EVENTS_CSV)

    summary_row = panel.iloc[[-1]].copy()
    summary_row.insert(0, "panel_rows", len(panel))
    summary_row.to_csv(REPORTS_DIR / "gold_macro_summary.csv", index=False)
    print(f"Wrote {REPORTS_DIR / 'gold_macro_summary.csv'}")

    try:
        from data_loaders.liquidation_map import fetch_liquidation_map, save_liquidation_reports
        xau = fetch_liquidation_map("XAUUSDT")
        liq_paths = save_liquidation_reports(xau, reports_dir=REPORTS_DIR)
        s = xau.summary()
        print(
            f"XAU liq map source={s.get('source')} mark={s.get('mark')} "
            f"vote={s.get('vote_side')} nearby L ${s.get('nearby_long_usd', 0):,.0f} "
            f"S ${s.get('nearby_short_usd', 0):,.0f}"
        )
        print(f"Wrote {liq_paths['json']} and {liq_paths['csv']}")
        if pd is not None and xau.buckets:
            extra = {
                "xau_mark": s.get("mark"),
                "xau_liq_vote": s.get("vote_side"),
                "xau_nearby_long_usd": s.get("nearby_long_usd"),
                "xau_nearby_short_usd": s.get("nearby_short_usd"),
                "xau_long_frac": s.get("long_frac"),
            }
            for k, v in extra.items():
                summary_row[k] = v
            summary_row.to_csv(REPORTS_DIR / "gold_macro_summary.csv", index=False)
    except Exception as e:
        print(f"[warn] XAU liquidation map skipped: {e}")

    print("\n--- Pearson (levels) gold row ---")
    if gold_m in corr_l.index:
        print(corr_l[gold_m].dropna().sort_values(ascending=False).to_string())
    elif gold_m not in panel.columns:
        print(f"[warn] Column {gold_m} missing (install yfinance and run with --refresh for Yahoo gold).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
