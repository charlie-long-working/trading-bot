"""
Load Binance klines from crawler output: merged CSV or ZIPs.

Returns OHLCV + open_time as numpy arrays (oldest bar first) for regime, technical, and fusion.
"""

import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

import numpy as np


# Binance kline CSV: no header in raw files; merged CSV has this header.
KLINE_HEADER = (
    "open_time,open,high,low,close,volume,close_time,quote_asset_volume,"
    "num_trades,taker_buy_base_asset_volume,taker_buy_quote_asset_volume,ignore"
)


@dataclass
class KlineSeries:
    """OHLCV + open_time from one (market, symbol, interval). Oldest bar first."""

    open_time: np.ndarray   # int64 ms
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray
    # Optional extra columns if present
    quote_asset_volume: Optional[np.ndarray] = None
    num_trades: Optional[np.ndarray] = None

    def __len__(self) -> int:
        return len(self.close)


def _parse_row(line: str) -> Optional[list]:
    parts = line.strip().split(",")
    if len(parts) < 6:
        return None
    try:
        return [
            int(parts[0]),
            float(parts[1]),
            float(parts[2]),
            float(parts[3]),
            float(parts[4]),
            float(parts[5]),
            float(parts[7]) if len(parts) > 7 else 0.0,
            int(parts[8]) if len(parts) > 8 else 0,
        ]
    except (ValueError, IndexError):
        return None


def _load_merged_csv(path: Path) -> Optional[KlineSeries]:
    if not path.exists():
        return None
    rows: list = []
    with open(path) as f:
        for line in f:
            if line.strip() == "" or line.strip() == KLINE_HEADER:
                continue
            parsed = _parse_row(line)
            if parsed is not None:
                rows.append(parsed)
    if not rows:
        return None
    rows.sort(key=lambda r: r[0])
    # Dedupe by open_time
    seen = set()
    unique = []
    for r in rows:
        if r[0] in seen:
            continue
        seen.add(r[0])
        unique.append(r)
    arr = np.array(unique)
    return KlineSeries(
        open_time=arr[:, 0].astype(np.int64),
        open=arr[:, 1].astype(np.float64),
        high=arr[:, 2].astype(np.float64),
        low=arr[:, 3].astype(np.float64),
        close=arr[:, 4].astype(np.float64),
        volume=arr[:, 5].astype(np.float64),
        quote_asset_volume=arr[:, 6].astype(np.float64),
        num_trades=arr[:, 7].astype(np.int64),
    )


def _load_from_zips(data_dir: Union[str, Path], market_type: str, symbol: str, interval: str) -> Optional[KlineSeries]:
    base = Path(data_dir) / market_type / "klines" / symbol / interval
    if not base.is_dir():
        return None
    zips = sorted(base.glob("*.zip"))
    if not zips:
        return None
    rows: list = []
    for zp in zips:
        try:
            with zipfile.ZipFile(zp, "r") as zf:
                for name in zf.namelist():
                    if name.endswith(".csv"):
                        with zf.open(name) as f:
                            for line in f:
                                decoded = line.decode("utf-8").strip()
                                if not decoded:
                                    continue
                                parsed = _parse_row(decoded)
                                if parsed is not None:
                                    rows.append(parsed)
                        break
        except Exception:
            continue
    if not rows:
        return None
    rows.sort(key=lambda r: r[0])
    seen = set()
    unique = []
    for r in rows:
        if r[0] in seen:
            continue
        seen.add(r[0])
        unique.append(r)
    arr = np.array(unique)
    return KlineSeries(
        open_time=arr[:, 0].astype(np.int64),
        open=arr[:, 1].astype(np.float64),
        high=arr[:, 2].astype(np.float64),
        low=arr[:, 3].astype(np.float64),
        close=arr[:, 4].astype(np.float64),
        volume=arr[:, 5].astype(np.float64),
        quote_asset_volume=arr[:, 6].astype(np.float64),
        num_trades=arr[:, 7].astype(np.int64),
    )


def load_klines(
    data_dir: Union[str, Path],
    market_type: str,
    symbol: str,
    interval: str,
    *,
    prefer_merged: bool = True,
) -> Optional[KlineSeries]:
    """
    Load klines for (market_type, symbol, interval).

    - prefer_merged=True: look for merged CSV at
      data_dir/{market_type}/klines/{symbol}/{symbol}-{interval}.csv first.
    - If merged not found or prefer_merged=False: read all ZIPs in
      data_dir/{market_type}/klines/{symbol}/{interval}/ and merge in memory.

    Returns KlineSeries (open_time, OHLCV, optional quote_volume, num_trades) or None if no data.
    """
    data_dir = Path(data_dir)
    if prefer_merged:
        merged_path = data_dir / market_type / "klines" / symbol / f"{symbol}-{interval}.csv"
        out = _load_merged_csv(merged_path)
        if out is not None:
            return out
    return _load_from_zips(data_dir, market_type, symbol, interval)
