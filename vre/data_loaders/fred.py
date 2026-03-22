"""
Fetch economic indicators from FRED (Federal Reserve Economic Data).

Series: M2SL, FEDFUNDS, CPIAUCSL, FPCPITOTLZGVNM, DCOILWTICO, DTWEXBGS
Requires FRED_API_KEY env var (free at https://fred.stlouisfed.org/docs/api/api_key.html).
Cache: vre/data/fred/{series_id}.csv (columns: date,value).
"""

from pathlib import Path
from typing import Optional

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    from fredapi import Fred
except ImportError:
    Fred = None

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "fred"

SERIES = {
    "M2SL": "M2 Money Supply (Billions USD, Monthly)",
    "FEDFUNDS": "Fed Funds Rate (%, Monthly)",
    "CPIAUCSL": "CPI US All Urban Consumers (Index, Monthly)",
    "FPCPITOTLZGVNM": "CPI Vietnam Inflation (% YoY, Annual)",
    "DCOILWTICO": "Oil WTI Spot Price (USD/barrel, Daily)",
    "DTWEXBGS": "Trade-Weighted US Dollar Index (Broad, Daily)",
}


def _get_api_key() -> Optional[str]:
    return os.environ.get("FRED_API_KEY")


def _cache_path(series_id: str) -> Path:
    return CACHE_DIR / f"{series_id}.csv"


def fetch_series(series_id: str, api_key: Optional[str] = None) -> Optional["pd.DataFrame"]:
    """Fetch a FRED series via fredapi. Returns DataFrame with columns [date, value]."""
    if Fred is None or pd is None:
        print(f"[FRED] fredapi or pandas not installed. pip install fredapi pandas")
        return None
    key = api_key or _get_api_key()
    if not key:
        print("[FRED] FRED_API_KEY not set. Get free key at https://fred.stlouisfed.org/docs/api/api_key.html")
        return None
    try:
        fred = Fred(api_key=key)
        s = fred.get_series(series_id)
        df = pd.DataFrame({"date": s.index, "value": s.values})
        df["date"] = pd.to_datetime(df["date"])
        df = df.dropna(subset=["value"])
        return df
    except Exception as e:
        print(f"[FRED] Error fetching {series_id}: {e}")
        return None


def save_cache(series_id: str, df: "pd.DataFrame") -> Path:
    """Save DataFrame to CSV cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(series_id)
    df.to_csv(path, index=False)
    return path


def load_cache(series_id: str) -> Optional["pd.DataFrame"]:
    """Load from CSV cache if it exists."""
    if pd is None:
        return None
    path = _cache_path(series_id)
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path, parse_dates=["date"])
        return df
    except Exception:
        return None


def get_series(series_id: str, force_refresh: bool = False,
               api_key: Optional[str] = None) -> Optional["pd.DataFrame"]:
    """
    Load FRED series: try cache first, fetch from API if missing or forced.
    Returns DataFrame with columns [date, value].
    """
    if not force_refresh:
        cached = load_cache(series_id)
        if cached is not None and len(cached) > 0:
            return cached

    df = fetch_series(series_id, api_key=api_key)
    if df is not None and len(df) > 0:
        save_cache(series_id, df)
        return df

    return load_cache(series_id)


def get_all_series(force_refresh: bool = False,
                   api_key: Optional[str] = None) -> dict:
    """Fetch/load all configured FRED series. Returns {series_id: DataFrame}."""
    result = {}
    for sid in SERIES:
        df = get_series(sid, force_refresh=force_refresh, api_key=api_key)
        if df is not None:
            result[sid] = df
    return result


def get_merged_monthly(force_refresh: bool = False,
                       api_key: Optional[str] = None) -> Optional["pd.DataFrame"]:
    """
    Merge all series into a single monthly DataFrame.
    Resamples daily/annual series to monthly, forward-fills gaps.
    Columns: date, M2SL, FEDFUNDS, CPIAUCSL, FPCPITOTLZGVNM, DCOILWTICO, DTWEXBGS
    """
    if pd is None:
        return None
    all_data = get_all_series(force_refresh=force_refresh, api_key=api_key)
    if not all_data:
        return None

    merged = None
    for sid, df in all_data.items():
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").rename(columns={"value": sid})
        monthly = df.resample("MS").last()
        if merged is None:
            merged = monthly
        else:
            merged = merged.join(monthly, how="outer")

    if merged is not None:
        merged = merged.ffill()
        merged = merged.reset_index()
    return merged
