"""
DCA simulation: buy fixed amount at fixed (day, hour) UTC.

Uses 1h klines for spot BTC and ETH. Price = close of the 1h bar at (date, hour).
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple

import numpy as np

from botv2.data.fetcher import load_klines
from botv2.config import CACHE_DIR, REPO_ROOT

# Cache to avoid reloading klines in tight optimization loops
_price_cache: Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]] = None
_price_map_cache: Optional[dict] = None


def _load_prices_aligned(market_type: str = "spot") -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load aligned (open_time, close_btc, close_eth) from 1h klines. Cached."""
    global _price_cache
    if _price_cache is not None:
        return _price_cache
    fallback = str(REPO_ROOT / "data") if (REPO_ROOT / "data").exists() else None
    btc = load_klines(market_type, "BTC/USDT", "1h", cache_dir=CACHE_DIR, fallback_data_dir=fallback)
    eth = load_klines(market_type, "ETH/USDT", "1h", cache_dir=CACHE_DIR, fallback_data_dir=fallback)
    if btc is None or eth is None:
        raise FileNotFoundError("Need 1h klines for BTC and ETH (spot)")
    ot_btc, _, _, _, close_btc, _ = btc
    ot_eth, _, _, _, close_eth, _ = eth
    _price_cache = _align_btc_eth(ot_btc, close_btc, ot_eth, close_eth)
    return _price_cache


def _get_price_map(ot: np.ndarray, c_btc: np.ndarray, c_eth: np.ndarray) -> dict:
    """Build (date, hour) -> (btc_price, eth_price). Cached."""
    global _price_map_cache
    if _price_map_cache is not None:
        return _price_map_cache
    m = {}
    for i in range(len(ot)):
        t = int(ot[i])
        if t < 1e12:
            t *= 1000
        # Skip invalid timestamps (e.g. from misaligned data)
        if t < 1e11 or t > 2e12:
            continue
        try:
            dt = datetime.utcfromtimestamp(t / 1000)
        except (ValueError, OSError):
            continue
        key = (dt.strftime("%Y-%m-%d"), dt.hour)
        m[key] = (float(c_btc[i]), float(c_eth[i]))
    _price_map_cache = m
    return m


def _align_btc_eth(
    ot_btc: np.ndarray,
    close_btc: np.ndarray,
    ot_eth: np.ndarray,
    close_eth: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Align BTC and ETH to common timestamps. Use BTC timestamps; for ETH interpolate if needed.
    Returns (open_time, close_btc, close_eth).
    """
    btc_map = {}
    for i in range(len(ot_btc)):
        ts = int(ot_btc[i])
        if ts < 1e12:
            ts *= 1000
        btc_map[ts] = float(close_btc[i])

    eth_map = {}
    for i in range(len(ot_eth)):
        ts = int(ot_eth[i])
        if ts < 1e12:
            ts *= 1000
        eth_map[ts] = float(close_eth[i])

    times = sorted(btc_map.keys())
    close_btc_arr = np.array([btc_map[t] for t in times])
    close_eth_arr = []
    for t in times:
        if t in eth_map:
            close_eth_arr.append(eth_map[t])
        else:
            # nearest
            closest = min(eth_map.keys(), key=lambda x: abs(x - t))
            close_eth_arr.append(eth_map[closest])
    close_eth_arr = np.array(close_eth_arr)
    return np.array(times), close_btc_arr, np.array(close_eth_arr)


def dca_daily(
    amount_per_day: float,
    start_date: str,
    end_date: str,
    btc_ratio: float,
    hour_utc: int,
    market_type: str = "spot",
) -> Tuple[float, float, float]:
    """
    Simulate DCA: buy $amount_per_day every day at hour_utc (0-23) UTC.
    btc_ratio: fraction to BTC (0-1), rest to ETH.
    Returns (final_portfolio_value, total_invested, total_return_pct).
    """
    ot, c_btc, c_eth = _load_prices_aligned(market_type)
    price_map = _get_price_map(ot, c_btc, c_eth)

    qty_btc = 0.0
    qty_eth = 0.0
    total_invested = 0.0
    current = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    while current <= end_dt:
        key = (current.strftime("%Y-%m-%d"), hour_utc)
        if key in price_map:
            btc_p, eth_p = price_map[key]
            amt_btc = amount_per_day * btc_ratio / btc_p if btc_p > 0 else 0
            amt_eth = amount_per_day * (1 - btc_ratio) / eth_p if eth_p > 0 else 0
            qty_btc += amt_btc
            qty_eth += amt_eth
            total_invested += amount_per_day
        current += timedelta(days=1)

    # Final value at last available price
    last_btc = float(c_btc[-1])
    last_eth = float(c_eth[-1])
    final_value = qty_btc * last_btc + qty_eth * last_eth
    total_return_pct = (final_value / total_invested - 1) * 100 if total_invested > 0 else 0
    return final_value, total_invested, total_return_pct


def dca_weekly(
    amount_per_week: float,
    start_date: str,
    end_date: str,
    btc_ratio: float,
    day_of_week: int,
    hour_utc: int,
    market_type: str = "spot",
) -> Tuple[float, float, float]:
    """
    Simulate DCA: buy $amount_per_week every week on day_of_week (0=Mon, 6=Sun) at hour_utc UTC.
    Returns (final_portfolio_value, total_invested, total_return_pct).
    """
    ot, c_btc, c_eth = _load_prices_aligned(market_type)
    price_map = _get_price_map(ot, c_btc, c_eth)

    qty_btc = 0.0
    qty_eth = 0.0
    total_invested = 0.0
    current = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    while current <= end_dt:
        if current.weekday() == day_of_week:
            key = (current.strftime("%Y-%m-%d"), hour_utc)
            if key in price_map:
                btc_p, eth_p = price_map[key]
                amt_btc = amount_per_week * btc_ratio / btc_p if btc_p > 0 else 0
                amt_eth = amount_per_week * (1 - btc_ratio) / eth_p if eth_p > 0 else 0
                qty_btc += amt_btc
                qty_eth += amt_eth
                total_invested += amount_per_week
        current += timedelta(days=1)

    last_btc = float(c_btc[-1])
    last_eth = float(c_eth[-1])
    final_value = qty_btc * last_btc + qty_eth * last_eth
    total_return_pct = (final_value / total_invested - 1) * 100 if total_invested > 0 else 0
    return final_value, total_invested, total_return_pct
