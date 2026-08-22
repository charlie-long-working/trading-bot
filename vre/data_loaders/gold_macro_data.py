"""
Daily / weekly gold and ICE DXY proxy via Yahoo Finance (yfinance).

Cache: vre/data/external/{name}.csv — columns: date, (optional OHLC for gold).

FRED broad USD (DTWEXBGS) stays in fred.py; DX-Y.NYB is the common DXY futures proxy.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    import pandas as pd
except ImportError:
    pd = None

ROOT = Path(__file__).resolve().parent.parent
EXTERNAL_DIR = ROOT / "data" / "external"

YF_GOLD_DEFAULT = "GC=F"  # COMEX gold front; spot alternative: no perfect free Yahoo symbol
YF_DXY_DEFAULT = "DX-Y.NYB"


def _ensure_dir() -> None:
    EXTERNAL_DIR.mkdir(parents=True, exist_ok=True)


def fetch_yfinance_daily(
    ticker: str,
    *,
    period: str = "max",
    auto_adjust: bool = True,
) -> Optional["pd.DataFrame"]:
    """Download daily OHLCV from Yahoo. Returns DataFrame indexed by date."""
    if pd is None:
        return None
    try:
        import yfinance as yf
    except ImportError:
        print("[gold_macro_data] pip install yfinance")
        return None
    t = yf.Ticker(ticker)
    df = t.history(period=period, auto_adjust=auto_adjust, interval="1d")
    if df is None or df.empty:
        return None
    df = df.reset_index()
    # Yahoo column may be Date or Datetime
    col = "Date" if "Date" in df.columns else df.columns[0]
    df = df.rename(columns={col: "date"})
    df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_localize(None).dt.normalize()
    return df


def save_external_csv(name: str, df: "pd.DataFrame") -> Path:
    _ensure_dir()
    path = EXTERNAL_DIR / f"{name}.csv"
    df.to_csv(path, index=False)
    return path


def load_external_csv(name: str) -> Optional["pd.DataFrame"]:
    if pd is None:
        return None
    path = EXTERNAL_DIR / f"{name}.csv"
    if not path.exists():
        return None
    try:
        return pd.read_csv(path, parse_dates=["date"])
    except Exception:
        return None


def get_gold_futures_daily(
    ticker: str = YF_GOLD_DEFAULT,
    force_refresh: bool = False,
) -> Optional["pd.DataFrame"]:
    """
    Daily gold (COMEX front default). Cache: external/gc_f_daily.csv
    Columns: date, open, high, low, close, volume (if present).
    """
    cache_name = "gc_f_daily"
    if not force_refresh:
        cached = load_external_csv(cache_name)
        if cached is not None and len(cached) > 0:
            return cached
    raw = fetch_yfinance_daily(ticker)
    if raw is None:
        return load_external_csv(cache_name)
    cols = [c for c in ["date", "Open", "High", "Low", "Close", "Volume"] if c in raw.columns]
    out = raw[cols].copy()
    rename = {"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
    out = out.rename(columns=rename)
    save_external_csv(cache_name, out)
    return out


def get_dxy_daily(
    ticker: str = YF_DXY_DEFAULT,
    force_refresh: bool = False,
) -> Optional["pd.DataFrame"]:
    """ICE DXY proxy (Yahoo). Cache: external/dxy_daily.csv — date, close."""
    cache_name = "dxy_daily"
    if not force_refresh:
        cached = load_external_csv(cache_name)
        if cached is not None and len(cached) > 0:
            return cached
    raw = fetch_yfinance_daily(ticker)
    if raw is None:
        return load_external_csv(cache_name)
    out = raw[["date", "Close"]].rename(columns={"Close": "close"})
    save_external_csv(cache_name, out)
    return out


def resample_ohlc_weekly(daily: "pd.DataFrame") -> "pd.DataFrame":
    """Last close of week (W-FRI) from daily with columns date, open, high, low, close."""
    if pd is None or daily is None or daily.empty:
        return pd.DataFrame()
    d = daily.copy()
    d = d.set_index("date").sort_index()
    ohlc = {}
    if "open" in d.columns:
        ohlc["open"] = "first"
    if "high" in d.columns:
        ohlc["high"] = "max"
    if "low" in d.columns:
        ohlc["low"] = "min"
    if "close" in d.columns:
        ohlc["close"] = "last"
    w = d.resample("W-FRI").agg(ohlc)
    w = w.dropna(how="all")
    return w.reset_index()
