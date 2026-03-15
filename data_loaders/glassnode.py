"""
Load on-chain metrics (SOPR, MVRV) from Glassnode API or cached CSV.

- API: https://api.glassnode.com/v1/metrics/...
- Requires GLASSNODE_API_KEY (env or .env). Free tier has rate limits.
- Cache: save to data/onchain/{asset}/sopr.csv and mvrv.csv (columns: t, v) for offline use.
"""

from pathlib import Path
from typing import Optional, Tuple, Union

import numpy as np

# Optional: load .env for GLASSNODE_API_KEY
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import os
import time

try:
    import requests
except ImportError:
    requests = None


BASE_URL = "https://api.glassnode.com/v1/metrics"
# SOPR: Spent Output Profit Ratio. MVRV: Market Value to Realized Value.
SOPR_PATH = "indicators/sopr"
MVRV_PATH = "market/mvrv"

# Symbol (e.g. BTCUSDT) -> Glassnode asset (BTC, ETH)
SYMBOL_TO_ASSET = {
    "BTCUSDT": "BTC",
    "BTC": "BTC",
    "ETHUSDT": "ETH",
    "ETH": "ETH",
}


def _asset_for_symbol(symbol: str) -> Optional[str]:
    """Return Glassnode asset (BTC, ETH) for symbol, or None if not supported."""
    return SYMBOL_TO_ASSET.get(symbol.upper())


def _get_api_key() -> Optional[str]:
    return os.environ.get("GLASSNODE_API_KEY")


def _fetch_metric(
    asset: str,
    metric_path: str,
    api_key: str,
    since_ts: int,
    until_ts: int,
    interval: str = "24h",
) -> Optional[list]:
    """Fetch one metric from Glassnode API. since/until in seconds. Returns list of {t, v} or None."""
    if requests is None:
        return None
    url = f"{BASE_URL}/{metric_path}"
    params = {
        "a": asset,
        "api_key": api_key,
        "i": interval,
        "s": since_ts,
        "u": until_ts,
    }
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            return data
        return None
    except Exception:
        return None


def fetch_sopr(
    asset: str,
    since_ts: int,
    until_ts: int,
    api_key: Optional[str] = None,
    interval: str = "24h",
) -> Optional[list]:
    """Fetch SOPR time series. since_ts/until_ts in Unix seconds. Returns list of dicts with t, v."""
    key = api_key or _get_api_key()
    if not key:
        return None
    return _fetch_metric(asset, SOPR_PATH, key, since_ts, until_ts, interval)


def fetch_mvrv(
    asset: str,
    since_ts: int,
    until_ts: int,
    api_key: Optional[str] = None,
    interval: str = "24h",
) -> Optional[list]:
    """Fetch MVRV time series. since_ts/until_ts in Unix seconds. Returns list of dicts with t, v."""
    key = api_key or _get_api_key()
    if not key:
        return None
    return _fetch_metric(asset, MVRV_PATH, key, since_ts, until_ts, interval)


def _ts_to_day(ts_ms: int) -> int:
    """Convert timestamp (ms) to day bucket (Unix seconds at 00:00 UTC)."""
    if ts_ms > 1e15:
        ts_ms = int(ts_ms / 1000)
    return int(ts_ms // (24 * 3600 * 1000)) * (24 * 3600)


def _build_series_by_day(points: list) -> dict:
    """Convert list of {t, v} to dict day_ts -> value. t is in seconds."""
    out = {}
    for p in points:
        t = int(p.get("t", 0))
        v = p.get("v")
        if v is None:
            continue
        day = _ts_to_day(t * 1000)
        out[day] = float(v)
    return out


def load_sopr_mvrv_for_klines(
    open_time: np.ndarray,
    symbol: str,
    data_dir: Union[str, Path],
    api_key: Optional[str] = None,
    use_cache: bool = True,
    save_cache: bool = True,
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """
    Load SOPR and MVRV aligned to kline open_time (same length, index i = value for bar i).

    - open_time: array of candle open timestamps (ms).
    - symbol: e.g. BTCUSDT, ETHUSDT (maps to BTC, ETH on Glassnode).
    - data_dir: base dir for cache, e.g. data/onchain/{asset}/sopr.csv.
    - use_cache: if True, read from CSV when available.
    - save_cache: if True, save API response to CSV.

    Returns (sopr_array, mvrv_array) or (None, None) if asset unsupported or no data.
    Values are forward-filled from previous day when exact date missing.
    """
    asset = _asset_for_symbol(symbol)
    if asset is None:
        return None, None

    data_dir = Path(data_dir)
    cache_dir = data_dir / "onchain" / asset
    cache_dir.mkdir(parents=True, exist_ok=True)
    sopr_csv = cache_dir / "sopr.csv"
    mvrv_csv = cache_dir / "mvrv.csv"

    n = len(open_time)
    sopr_arr = np.full(n, np.nan)
    mvrv_arr = np.full(n, np.nan)

    # Normalize to ms
    ot = np.asarray(open_time, dtype=np.int64)
    if ot.size and ot[0] < 1e12:
        ot = ot * 1000
    since_ts = int(ot[0] / 1000) if n else 0
    until_ts = int(ot[-1] / 1000) if n else 0

    def _read_csv(path: Path) -> dict:
        """Read t,v CSV; key by day (start of day UTC in seconds) for alignment."""
        day_to_val = {}
        if not path.exists():
            return day_to_val
        with open(path) as f:
            next(f, None)  # skip header
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(",")
                if len(parts) < 2:
                    continue
                try:
                    t = int(parts[0])
                    v = float(parts[1])
                    day = (t // 86400) * 86400  # normalize to 00:00 UTC
                    day_to_val[day] = v
                except (ValueError, IndexError):
                    continue
        return day_to_val

    def _write_csv(path: Path, points: list) -> None:
        with open(path, "w") as f:
            f.write("t,v\n")
            for p in sorted(points, key=lambda x: x["t"]):
                f.write(f"{p['t']},{p['v']}\n")

    sopr_by_day = {}
    mvrv_by_day = {}

    if use_cache and sopr_csv.exists() and mvrv_csv.exists():
        sopr_by_day = _read_csv(sopr_csv)
        mvrv_by_day = _read_csv(mvrv_csv)
    else:
        key = api_key or _get_api_key()
        if key:
            # Fetch with a bit of padding
            since_ts = max(0, since_ts - 86400 * 2)
            until_ts = until_ts + 86400 * 2
            sopr_data = fetch_sopr(asset, since_ts, until_ts, key)
            if sopr_data:
                sopr_by_day = _build_series_by_day(sopr_data)
                if save_cache:
                    _write_csv(sopr_csv, sopr_data)
            time.sleep(0.3)  # rate limit
            mvrv_data = fetch_mvrv(asset, since_ts, until_ts, key)
            if mvrv_data:
                mvrv_by_day = _build_series_by_day(mvrv_data)
                if save_cache:
                    _write_csv(mvrv_csv, mvrv_data)
        else:
            # No API key: try cache only
            if sopr_csv.exists():
                sopr_by_day = _read_csv(sopr_csv)
            if mvrv_csv.exists():
                mvrv_by_day = _read_csv(mvrv_csv)

    if not sopr_by_day and not mvrv_by_day:
        return None, None

    # Align to each bar: bar's day -> value (forward-fill from previous if missing)
    sorted_sopr_days = sorted(sopr_by_day.keys()) if sopr_by_day else []
    sorted_mvrv_days = sorted(mvrv_by_day.keys()) if mvrv_by_day else []

    last_sopr = None
    last_mvrv = None
    sidx = 0
    midx = 0
    for i in range(n):
        day = _ts_to_day(int(ot[i]))
        while sidx < len(sorted_sopr_days) and sorted_sopr_days[sidx] <= day:
            last_sopr = sopr_by_day[sorted_sopr_days[sidx]]
            sidx += 1
        while midx < len(sorted_mvrv_days) and sorted_mvrv_days[midx] <= day:
            last_mvrv = mvrv_by_day[sorted_mvrv_days[midx]]
            midx += 1
        if last_sopr is not None:
            sopr_arr[i] = last_sopr
        if last_mvrv is not None:
            mvrv_arr[i] = last_mvrv

    return sopr_arr, mvrv_arr


def get_onchain_for_bar(
    sopr_array: Optional[np.ndarray],
    mvrv_array: Optional[np.ndarray],
    bar_index: int,
) -> Tuple[Optional[float], Optional[float]]:
    """Return (sopr, mvrv) for bar_index; None if not available or NaN."""
    sopr = None
    mvrv = None
    if sopr_array is not None and bar_index < len(sopr_array):
        v = sopr_array[bar_index]
        if np.isfinite(v):
            sopr = float(v)
    if mvrv_array is not None and bar_index < len(mvrv_array):
        v = mvrv_array[bar_index]
        if np.isfinite(v):
            mvrv = float(v)
    return sopr, mvrv
