"""
Fetch Vietnam residential property price index from BIS (Bank for International Settlements).

API: https://stats.bis.org/api/v2/ (SDMX RESTful API)
Dataset: WS_SPP (Selected Property Prices)
Cache: vre/data/bis/vn_property.csv
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
    import requests
except ImportError:
    requests = None

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "bis"
CACHE_FILE = CACHE_DIR / "vn_property.csv"

BIS_API_BASE = "https://stats.bis.org/api/v2"
DATAFLOW = "WS_SPP"
# VN = Vietnam, Q:5:628 = Residential property, real, s.a.
# Key structure: freq.reference_area.value
BIS_KEY = "Q.VN.N.628"


def fetch_bis_property() -> Optional["pd.DataFrame"]:
    """
    Fetch Vietnam residential property price index from BIS SDMX API.
    Returns DataFrame with columns [date, value].
    """
    if requests is None or pd is None:
        print("[BIS] requests or pandas not installed")
        return None

    url = f"{BIS_API_BASE}/data/{DATAFLOW}/{BIS_KEY}"
    params = {"format": "csv", "detail": "dataonly"}

    try:
        r = requests.get(url, params=params, timeout=60,
                         headers={"Accept": "text/csv"})
        if r.status_code != 200:
            alt_keys = [
                "Q.VN.R.628",
                "Q.VN.N.771",
                "Q.VN.R.771",
            ]
            for alt_key in alt_keys:
                alt_url = f"{BIS_API_BASE}/data/{DATAFLOW}/{alt_key}"
                r = requests.get(alt_url, params=params, timeout=60,
                                 headers={"Accept": "text/csv"})
                if r.status_code == 200:
                    break

        if r.status_code != 200:
            print(f"[BIS] API returned {r.status_code}. Using fallback sample data.")
            return None

        from io import StringIO
        df = pd.read_csv(StringIO(r.text))

        date_col = None
        value_col = None
        for col in df.columns:
            cl = col.lower()
            if "period" in cl or "time" in cl or "date" in cl:
                date_col = col
            if "obs_value" in cl or "value" in cl:
                value_col = col

        if date_col is None or value_col is None:
            print(f"[BIS] Could not identify date/value columns: {df.columns.tolist()}")
            return None

        result = pd.DataFrame({
            "date": pd.to_datetime(df[date_col].astype(str).str.replace("Q1", "03")
                                   .str.replace("Q2", "06")
                                   .str.replace("Q3", "09")
                                   .str.replace("Q4", "12")
                                   .apply(lambda x: x + "-01" if len(x) <= 7 else x),
                                   errors="coerce"),
            "value": pd.to_numeric(df[value_col], errors="coerce"),
        })
        result = result.dropna()
        return result

    except Exception as e:
        print(f"[BIS] Error fetching property data: {e}")
        return None


def save_cache(df: "pd.DataFrame") -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(CACHE_FILE, index=False)
    return CACHE_FILE


def load_cache() -> Optional["pd.DataFrame"]:
    if pd is None:
        return None
    if not CACHE_FILE.exists():
        return None
    try:
        return pd.read_csv(CACHE_FILE, parse_dates=["date"])
    except Exception:
        return None


def get_property_index(force_refresh: bool = False) -> Optional["pd.DataFrame"]:
    """
    Load VN property index: cache first, API if missing.
    Returns DataFrame [date, value].
    """
    if not force_refresh:
        cached = load_cache()
        if cached is not None and len(cached) > 0:
            return cached

    df = fetch_bis_property()
    if df is not None and len(df) > 0:
        save_cache(df)
        return df

    return load_cache()
