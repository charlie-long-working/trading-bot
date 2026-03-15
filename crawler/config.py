"""Crawler configuration: symbols, intervals, date range, market types, frequency, output dir."""

from dataclasses import dataclass, field
from datetime import date
from typing import List


# Intervals: spot uses 1mo, futures use 1M in some endpoints; we use lowercase for URL.
VALID_INTERVALS = (
    "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h",
    "1d", "3d", "1w", "1mo",
)

# Market type: spot or um (USD-M futures).
MARKET_TYPES = ("spot", "um")

# Frequency: daily or monthly.
FREQUENCIES = ("daily", "monthly")


@dataclass
class CrawlConfig:
    """Configuration for Binance klines crawl."""

    symbols: List[str] = field(default_factory=lambda: ["BTCUSDT", "ETHUSDT"])
    intervals: List[str] = field(default_factory=lambda: ["1h", "1d"])
    start_date: date = field(default_factory=lambda: date(2020, 1, 1))
    end_date: date = field(default_factory=date.today)
    market_types: List[str] = field(default_factory=lambda: ["spot", "um"])
    frequency: str = "monthly"
    out_dir: str = "data"
    workers: int = 2
    merge_csv: bool = False
    skip_existing: bool = True

    def __post_init__(self) -> None:
        for it in self.intervals:
            if it not in VALID_INTERVALS:
                raise ValueError(f"Invalid interval: {it}. Use one of {VALID_INTERVALS}")
        for mt in self.market_types:
            if mt not in MARKET_TYPES:
                raise ValueError(f"Invalid market_type: {mt}. Use one of {MARKET_TYPES}")
        if self.frequency not in FREQUENCIES:
            raise ValueError(f"Invalid frequency: {self.frequency}. Use one of {FREQUENCIES}")
        if self.start_date > self.end_date:
            raise ValueError("start_date must be <= end_date")
