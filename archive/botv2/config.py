"""botv2 configuration: symbols, timeframes, market types, date range."""

from datetime import date
from pathlib import Path

# Resolve botv2 root (parent of this file)
BOTV2_ROOT = Path(__file__).resolve().parent
REPO_ROOT = BOTV2_ROOT.parent

# CCXT symbols (standard format)
SYMBOLS = ["BTC/USDT", "ETH/USDT"]

# Timeframes for backtest and DCA
TIMEFRAMES = ["1h", "1d"]

# Market types: spot (Binance spot), future (Binance USD-M)
MARKET_TYPES = ("spot", "future")

# Data range: 2017 to today
START_DATE = date(2017, 1, 1)
END_DATE = date.today()

# Exchange config
EXCHANGE_SPOT = "binance"
EXCHANGE_FUTURE = "binanceusdm"

# Cache path: botv2/data/cache/{exchange_id}/{market_type}/{symbol}_{timeframe}.csv
CACHE_DIR = str(BOTV2_ROOT / "data" / "cache")

# Backtest config
LOOKBACK = 100
BASE_SIZE = 1.0
USE_ONCHAIN = False  # Skip Glassnode for botv2 initial setup
