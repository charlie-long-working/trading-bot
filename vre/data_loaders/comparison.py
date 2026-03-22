"""
Load property price and demographic data for international comparison.

Uses FRED (fredapi) to fetch BIS property indices and World Bank demographics
for developed countries: US, UK, Japan, Germany, France, Korea.
Vietnam uses local property index + FRED demographics (when available).
"""

from pathlib import Path
from typing import Optional, Dict, Any

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

# BIS Real Residential Property Price Index (2010=100) - FRED series
PROPERTY_SERIES = {
    "US": "QUSR628BIS",
    "UK": "QGBR628BIS",
    "Japan": "QJPR628BIS",
    "Germany": "QDER628BIS",
    "France": "QFRR628BIS",
    "Korea": "QKRR628BIS",
    "China": "QCNR628BIS",
    "Advanced (avg)": "Q5RR628BIS",
}

# World Bank demographics - FRED series
DEMO_POPULATION = {
    "Vietnam": "POPTOTVNA647NWDB",
    "China": "POPTOTCHA647NWDB",
    "US": "POPTOTUSA647NWDB",
    "Japan": "POPTOTJPA647NWDB",
    "UK": "POPTOTGBA647NWDB",
    "Germany": "POPTOTDEA647NWDB",
    "France": "POPTOTFRA647NWDB",
}

DEMO_OLD_AGE_DEPENDENCY = {
    "Vietnam": "SPPOPDPNDOLVNM",
    "China": "SPPOPDPNDOLCHN",
    "US": "SPPOPDPNDOLUSA",
    "Japan": "SPPOPDPNDOLJPN",
    "UK": "SPPOPDPNDOLGBR",
    "Germany": "SPPOPDPNDOLDEU",
    "France": "SPPOPDPNDOLFRA",
}

DEMO_WORKING_AGE_PCT = {
    "Vietnam": "SPPOP1564TOZSVNM",
    "China": "SPPOP1564TOZSCHN",
    "US": "SPPOP1564TOZSUSA",
    "Japan": "SPPOP1564TOZSJPN",
    "UK": "SPPOP1564TOZSGBR",
    "Germany": "SPPOP1564TOZSDEU",
    "France": "SPPOP1564TOZSFRA",
}

# Fertility rate (births per woman) - World Bank
DEMO_FERTILITY = {
    "Vietnam": "SPDYNTFRTINVNM",
    "China": "SPDYNTFRTINCHN",
    "US": "SPDYNTFRTINUSA",
    "Japan": "SPDYNTFRTINJPN",
    "UK": "SPDYNTFRTINGBR",
    "Germany": "SPDYNTFRTINDEU",
    "France": "SPDYNTFRTINFRA",
    "Korea": "SPDYNTFRTINKOR",
}


def _get_fred() -> Optional["Fred"]:
    key = os.environ.get("FRED_API_KEY")
    if not key or Fred is None:
        return None
    return Fred(api_key=key)


def _fetch_and_cache(series_id: str, fred: "Fred") -> Optional["pd.DataFrame"]:
    if pd is None:
        return None
    cache_path = CACHE_DIR / f"{series_id}.csv"
    if cache_path.exists():
        try:
            return pd.read_csv(cache_path, parse_dates=["date"])
        except Exception:
            pass
    try:
        s = fred.get_series(series_id)
        df = pd.DataFrame({"date": s.index, "value": s.values})
        df["date"] = pd.to_datetime(df["date"])
        df = df.dropna(subset=["value"])
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        df.to_csv(cache_path, index=False)
        return df
    except Exception:
        return None


def load_property_comparison(force_refresh: bool = False) -> Optional["pd.DataFrame"]:
    """
    Load property price indices for developed countries (BIS 2010=100).
    Returns wide DataFrame with columns: date, US, UK, Japan, Germany, France, Korea, Advanced (avg).
    """
    if pd is None:
        return None
    fred = _get_fred()
    if fred is None:
        return None

    dfs = []
    for country, sid in PROPERTY_SERIES.items():
        df = _fetch_and_cache(sid, fred)
        if df is not None and len(df) > 0:
            df = df.rename(columns={"value": country})
            dfs.append(df)

    if not dfs:
        return None

    merged = dfs[0]
    for df in dfs[1:]:
        merged = merged.merge(df, on="date", how="outer")
    merged = merged.sort_values("date").reset_index(drop=True)
    return merged


def load_demographics(force_refresh: bool = False) -> Dict[str, Optional["pd.DataFrame"]]:
    """
    Load demographic data: population, old-age dependency, working-age %.
    Returns dict: {population: df, old_dependency: df, working_age: df}
    """
    if pd is None:
        return {}
    fred = _get_fred()
    if fred is None:
        return {}

    def _load_category(mapping: dict) -> Optional["pd.DataFrame"]:
        dfs = []
        for country, sid in mapping.items():
            df = _fetch_and_cache(sid, fred)
            if df is not None and len(df) > 0:
                df = df.rename(columns={"value": country})
                dfs.append(df)
        if not dfs:
            return None
        merged = dfs[0]
        for df in dfs[1:]:
            merged = merged.merge(df, on="date", how="outer")
        return merged.sort_values("date").reset_index(drop=True)

    return {
        "population": _load_category(DEMO_POPULATION),
        "old_age_dependency": _load_category(DEMO_OLD_AGE_DEPENDENCY),
        "working_age_pct": _load_category(DEMO_WORKING_AGE_PCT),
        "fertility": _load_category(DEMO_FERTILITY),
    }


def merge_property_with_vietnam(
    intl_property: Optional["pd.DataFrame"],
    vn_property: Optional["pd.DataFrame"],
) -> Optional["pd.DataFrame"]:
    """
    Merge international BIS property (2010=100) with Vietnam local index (2015=100).
    Normalizes VN to 2010=100 for comparable scale: VN_norm = VN_value * (100 / VN_at_2010).
    """
    if pd is None or vn_property is None:
        return intl_property
    if intl_property is None:
        return None

    vn = vn_property.copy()
    vn["date"] = pd.to_datetime(vn["date"])
    vn = vn.set_index("date")

    intl = intl_property.copy()
    intl["date"] = pd.to_datetime(intl["date"])
    intl = intl.set_index("date")

    vn_2010 = vn[vn.index.year == 2010]
    if len(vn_2010) > 0:
        base = float(vn_2010["value"].iloc[0])
        vn_norm = (vn["value"] / base * 100) if base != 0 else vn["value"]
    else:
        vn_norm = vn["value"]

    vn_norm = vn_norm.to_frame(name="Vietnam")
    merged = intl.join(vn_norm, how="outer")
    return merged.sort_index().reset_index()


def build_fertility_property_correlation(
    prop_df: Optional["pd.DataFrame"],
    fertility_df: Optional["pd.DataFrame"],
) -> Optional["pd.DataFrame"]:
    """
    Merge property (quarterly) and fertility (annual), compute correlation by country.
    Returns DataFrame: country, correlation, n_obs.
    """
    if pd is None or prop_df is None or fertility_df is None:
        return None

    prop = prop_df.copy()
    prop["date"] = pd.to_datetime(prop["date"])
    prop["year"] = prop["date"].dt.year

    fert = fertility_df.copy()
    fert["date"] = pd.to_datetime(fert["date"])
    fert["year"] = fert["date"].dt.year

    prop_cols = [c for c in prop.columns if c not in ("date", "year")]
    fert_cols = [c for c in fert.columns if c not in ("date", "year")]
    common = set(prop_cols) & set(fert_cols)

    rows = []
    for country in common:
        prop_y = prop.groupby("year")[country].mean().reset_index()
        fert_y = fert[["year", country]].drop_duplicates("year")
        merged = prop_y.merge(fert_y, on="year", suffixes=("_prop", "_fert"))
        merged = merged.dropna()
        if len(merged) >= 5:
            corr = merged[country + "_prop"].corr(merged[country + "_fert"])
            rows.append({"country": country, "correlation": round(corr, 4), "n_obs": len(merged)})

    if not rows:
        return None
    return pd.DataFrame(rows).sort_values("correlation", ascending=False).reset_index(drop=True)


def build_fertility_property_merged(
    prop_df: Optional["pd.DataFrame"],
    fertility_df: Optional["pd.DataFrame"],
) -> Optional["pd.DataFrame"]:
    """Merge property and fertility at annual level for scatter/regression."""
    if pd is None or prop_df is None or fertility_df is None:
        return None

    prop = prop_df.copy()
    prop["date"] = pd.to_datetime(prop["date"])
    prop_annual = prop.set_index("date").resample("YS").mean().reset_index()
    prop_annual["year"] = prop_annual["date"].dt.year

    fert = fertility_df.copy()
    fert["date"] = pd.to_datetime(fert["date"])
    fert["year"] = fert["date"].dt.year

    prop_cols = [c for c in prop_annual.columns if c not in ("date", "year")]
    fert_cols = [c for c in fert.columns if c not in ("date", "year")]
    common = set(prop_cols) & set(fert_cols)

    all_data = []
    for country in common:
        p = prop_annual[["year", country]].rename(columns={country: "property"})
        f = fert[["year", country]].rename(columns={country: "fertility"})
        m = p.merge(f, on="year").dropna()
        m["country"] = country
        all_data.append(m)

    if not all_data:
        return None
    return pd.concat(all_data, ignore_index=True)


def compute_demographic_outlook(fertility_df: Optional["pd.DataFrame"]) -> dict:
    """
    Simple demographic outlook: fertility implies long-term property demand.
    Returns dict with country scores and narrative.
    """
    if pd is None or fertility_df is None or len(fertility_df) == 0:
        return {}

    fert = fertility_df.copy()
    fert["date"] = pd.to_datetime(fert["date"])
    latest_row = fert.sort_values("date").iloc[-1]

    fert_cols = [c for c in fert.columns if c != "date"]
    scores = []
    for c in fert_cols:
        v = latest_row.get(c)
        if pd.isna(v):
            continue
        v = float(v)
        if v >= 1.8:
            outlook = "Thuận lợi"
            score = 1
        elif v >= 1.2:
            outlook = "Trung lập"
            score = 0
        else:
            outlook = "Áp lực dài hạn"
            score = -1
        scores.append({"country": c, "fertility": round(v, 2), "outlook": outlook, "score": score})

    return {
        "scores": pd.DataFrame(scores).sort_values("fertility", ascending=False),
        "narrative": (
            "Tỷ lệ sinh cao (≥1.8) thường hỗ trợ nhu cầu BĐS dài hạn; "
            "tỷ lệ sinh thấp (<1.2) gắn với áp lực nhân khẩu học (Nhật, Hàn, Trung Quốc)."
        ),
    }
