"""
Load Vietnam-specific economic data from local CSV files.

Expected CSV files in vre/data/vietnam/:
  - interest_rates.csv  (columns: date, refinancing_rate, deposit_rate)
  - property_prices.csv (columns: date, region, price_per_m2, yoy_change)

SBV does not provide a public API, so data is maintained manually.
"""

from pathlib import Path
from typing import Optional

try:
    import pandas as pd
except ImportError:
    pd = None

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "vietnam"


def load_interest_rates() -> Optional["pd.DataFrame"]:
    """Load Vietnam interest rate history from CSV."""
    if pd is None:
        return None
    path = DATA_DIR / "interest_rates.csv"
    if not path.exists():
        print(f"[VN] Interest rate CSV not found: {path}")
        return None
    try:
        df = pd.read_csv(path, parse_dates=["date"])
        return df.sort_values("date").reset_index(drop=True)
    except Exception as e:
        print(f"[VN] Error reading interest rates: {e}")
        return None


def load_property_prices() -> Optional["pd.DataFrame"]:
    """Load Vietnam property price history from CSV."""
    if pd is None:
        return None
    path = DATA_DIR / "property_prices.csv"
    if not path.exists():
        print(f"[VN] Property price CSV not found: {path}")
        return None
    try:
        df = pd.read_csv(path, parse_dates=["date"])
        return df.sort_values("date").reset_index(drop=True)
    except Exception as e:
        print(f"[VN] Error reading property prices: {e}")
        return None


def load_property_national_avg() -> Optional["pd.DataFrame"]:
    """
    Load and aggregate property prices to national monthly average.
    Returns DataFrame [date, price_per_m2, yoy_change].
    """
    df = load_property_prices()
    if df is None:
        return None
    agg = df.groupby("date").agg({
        "price_per_m2": "mean",
        "yoy_change": "mean",
    }).reset_index()
    agg["date"] = pd.to_datetime(agg["date"])
    return agg.sort_values("date").reset_index(drop=True)


def build_property_index() -> Optional["pd.DataFrame"]:
    """
    Build a property price index (base 2015-01 = 100) from local CSV data.
    Uses national average price_per_m2, resampled monthly.
    Returns DataFrame [date, value] compatible with BIS format.
    """
    avg = load_property_national_avg()
    if avg is None or len(avg) == 0:
        return None

    avg = avg.copy()
    avg["date"] = pd.to_datetime(avg["date"])
    avg = avg.set_index("date").resample("6MS").last().reset_index()

    base_rows = avg[avg["date"].dt.year == 2015]
    if len(base_rows) > 0:
        base_val = base_rows["price_per_m2"].iloc[0]
    else:
        base_val = avg["price_per_m2"].iloc[0]

    if base_val == 0:
        base_val = 1.0

    avg["value"] = (avg["price_per_m2"] / base_val) * 100.0
    return avg[["date", "value"]].dropna().reset_index(drop=True)


def get_all_vietnam_data() -> dict:
    """Load all Vietnam local datasets. Returns dict of DataFrames."""
    result = {}
    rates = load_interest_rates()
    if rates is not None:
        result["interest_rates"] = rates
    prices = load_property_prices()
    if prices is not None:
        result["property_prices"] = prices
    avg = load_property_national_avg()
    if avg is not None:
        result["property_national_avg"] = avg
    prop_index = build_property_index()
    if prop_index is not None:
        result["property_index"] = prop_index
    return result
