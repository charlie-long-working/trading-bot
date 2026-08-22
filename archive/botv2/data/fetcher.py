"""
Fetch OHLCV via CCXT and cache to CSV.

Uses Binance (spot) and Binance USD-M (futures). Loops fetch_ohlcv with since/limit
to get full history from 2017 to now.
"""

import csv
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import ccxt
import numpy as np


_exchange_cache: dict = {}


def _get_exchange(exchange_id: str):
    """Create CCXT exchange instance (cached, with markets loaded)."""
    if exchange_id in _exchange_cache:
        return _exchange_cache[exchange_id]
    if exchange_id == "binance":
        ex = ccxt.binance({"enableRateLimit": True})
    elif exchange_id == "binanceusdm":
        ex = ccxt.binanceusdm({"enableRateLimit": True})
    else:
        raise ValueError(f"Unsupported exchange: {exchange_id}")
    ex.load_markets()
    _exchange_cache[exchange_id] = ex
    return ex


def _market_type_to_exchange(market_type: str) -> str:
    if market_type == "spot":
        return "binance"
    if market_type == "future":
        return "binanceusdm"
    raise ValueError(f"Unknown market_type: {market_type}")


def _ms_to_date(ms: int) -> str:
    return datetime.utcfromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M:%S")


def fetch_and_save_klines(
    exchange_id: str,
    market_type: str,
    symbol: str,
    timeframe: str,
    start_date: str,
    end_date: Optional[str] = None,
    cache_dir: str = "data/cache",
    limit_per_request: int = 1000,
) -> Path:
    """
    Fetch OHLCV from exchange and save to CSV.

    Args:
        exchange_id: e.g. binance, binanceusdm
        market_type: spot or future
        symbol: CCXT symbol (e.g. BTC/USDT)
        timeframe: 1h, 1d
        start_date: YYYY-MM-DD
        end_date: YYYY-MM-DD or None for today
        cache_dir: base dir for cache
        limit_per_request: max candles per API call

    Returns:
        Path to saved CSV
    """
    exchange = _get_exchange(exchange_id)
    since = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
    if end_date:
        until = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp() * 1000)
    else:
        until = int(datetime.utcnow().timestamp() * 1000)

    # Build cache path: cache_dir/exchange_id/market_type/symbol_timeframe.csv
    safe_symbol = symbol.replace("/", "_")
    out_dir = Path(cache_dir) / exchange_id / market_type
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{safe_symbol}_{timeframe}.csv"

    all_rows = []
    current_since = since

    while current_since < until:
        try:
            ohlcv = exchange.fetch_ohlcv(
                symbol, timeframe, since=current_since, limit=limit_per_request
            )
        except ccxt.BadSymbol as e:
            print(f"  Symbol not available on {exchange_id}: {e}")
            break
        except ccxt.ExchangeNotAvailable:
            print(f"  Exchange not available, retrying in 5s...")
            time.sleep(5)
            continue
        except Exception as e:
            err_msg = str(e)
            if "does not have market symbol" in err_msg or "not found" in err_msg.lower():
                print(f"  Symbol not found on {exchange_id}: {e}")
                break
            print(f"  Fetch error at {_ms_to_date(current_since)}: {e}")
            time.sleep(2)
            continue

        if not ohlcv:
            break

        for row in ohlcv:
            ts, o, h, l, c, v = row[0], row[1], row[2], row[3], row[4], row[5]
            if ts >= until:
                break
            all_rows.append((int(ts), float(o), float(h), float(l), float(c), float(v)))

        last_ts = ohlcv[-1][0]
        if last_ts <= current_since:
            break
        current_since = last_ts + 1
        time.sleep(exchange.rateLimit / 1000 if exchange.rateLimit else 0.2)

    # Deduplicate by open_time
    seen = set()
    unique_rows = []
    for r in all_rows:
        if r[0] not in seen:
            seen.add(r[0])
            unique_rows.append(r)
    unique_rows.sort(key=lambda x: x[0])

    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["open_time", "open", "high", "low", "close", "volume"])
        w.writerows(unique_rows)

    print(f"  Saved {len(unique_rows)} rows to {out_path}")
    return out_path


def _read_csv_rows(path: Path) -> list:
    """Read OHLCV rows from a CSV file, returning list of tuples or empty list."""
    rows = []
    with open(path) as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for line in reader:
            if len(line) < 6:
                continue
            try:
                rows.append((
                    int(line[0]),
                    float(line[1]),
                    float(line[2]),
                    float(line[3]),
                    float(line[4]),
                    float(line[5]),
                ))
            except (ValueError, IndexError):
                continue
    return rows


def load_klines(
    market_type: str,
    symbol: str,
    timeframe: str,
    cache_dir: str = "data/cache",
    fallback_data_dir: Optional[str] = None,
) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    """
    Load cached klines from CSV.

    Returns (open_time, open, high, low, close, volume) as numpy arrays, or None if missing.
    If fallback_data_dir is set (e.g. parent repo data/), tries POC layout: {dir}/{market}/klines/{symbol}/{symbol}-{tf}.csv
    """
    exchange_id = _market_type_to_exchange(market_type)
    safe_symbol = symbol.replace("/", "_")
    candidates = [Path(cache_dir) / exchange_id / market_type / f"{safe_symbol}_{timeframe}.csv"]
    if fallback_data_dir:
        poc_symbol = symbol.replace("/", "")
        poc_market = "um" if market_type == "future" else "spot"
        candidates.append(
            Path(fallback_data_dir) / poc_market / "klines" / poc_symbol / f"{poc_symbol}-{timeframe}.csv"
        )

    rows = []
    for path in candidates:
        if not path.exists():
            continue
        rows = _read_csv_rows(path)
        if rows:
            break

    if not rows:
        return None

    return (
        np.array([r[0] for r in rows]),
        np.array([r[1] for r in rows]),
        np.array([r[2] for r in rows]),
        np.array([r[3] for r in rows]),
        np.array([r[4] for r in rows]),
        np.array([r[5] for r in rows]),
    )
