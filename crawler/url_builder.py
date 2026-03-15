"""Build data.binance.vision URLs for spot and futures UM klines."""

from datetime import date
from typing import Union

BASE_URL = "https://data.binance.vision/data"


def _interval_path(market_type: str, interval: str) -> str:
    """Spot uses 1mo, futures often 1M; Binance Vision uses 1m for minute. Keep as-is for month."""
    if interval == "1mo" and market_type == "um":
        return "1M"  # futures monthly interval in path
    return interval


def kline_url(
    symbol: str,
    interval: str,
    date_or_month: Union[date, str],
    market_type: str,
    frequency: str,
) -> str:
    """
    Build exact download URL for one kline file.

    - symbol: e.g. BTCUSDT
    - interval: e.g. 1h, 1d, 1mo
    - date_or_month: for daily use date(2025, 3, 14); for monthly use "2025-03"
    - market_type: "spot" or "um"
    - frequency: "daily" or "monthly"
    """
    path_interval = _interval_path(market_type, interval)
    if frequency == "daily":
        d = date_or_month if isinstance(date_or_month, date) else date.fromisoformat(str(date_or_month))
        date_str = d.strftime("%Y-%m-%d")
        filename = f"{symbol}-{path_interval}-{date_str}.zip"
    else:
        month_str = date_or_month if isinstance(date_or_month, str) else date_or_month.strftime("%Y-%m")
        filename = f"{symbol}-{path_interval}-{month_str}.zip"
    if market_type == "spot":
        path = f"spot/{frequency}/klines/{symbol}/{path_interval}/{filename}"
    else:
        path = f"futures/um/{frequency}/klines/{symbol}/{path_interval}/{filename}"
    return f"{BASE_URL}/{path}"
