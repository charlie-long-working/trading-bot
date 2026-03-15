# Crawled Data: Understanding and Usage

After running the Binance klines crawler, data lives under `data/`. This doc describes schema, layout, coverage, and how it feeds into the strategy.

---

## 1. Data layout

| Path pattern | Description |
|--------------|-------------|
| `data/{market_type}/klines/{symbol}/{interval}/*.zip` | Raw monthly (or daily) kline ZIPs from data.binance.vision |
| `data/{market_type}/klines/{symbol}/{symbol}-{interval}.csv` | Merged CSV (created when running crawler with `--merge-csv`) |

- **market_type:** `spot` or `um` (USD-M futures).
- **symbol:** e.g. `BTCUSDT`, `ETHUSDT`.
- **interval:** e.g. `1h`, `1d`, `1mo`.

**Example paths:**
- Zips: `data/um/klines/BTCUSDT/1h/BTCUSDT-1h-2024-03.zip`
- Merged: `data/um/klines/BTCUSDT/BTCUSDT-1h.csv`

---

## 2. Kline CSV schema

Each ZIP contains one CSV (no header in raw files). Merged CSV has a header. Columns match Binance REST `/api/v3/klines`:

| Index | Column name | Description | Strategy use |
|-------|-------------|-------------|--------------|
| 0 | open_time | Candle start (ms, UTC) | Index / datetime for alignment |
| 1 | open | Open price | OHLCV, technical (OB, FVG, zones) |
| 2 | high | High price | OHLCV, swing highs, liquidity |
| 3 | low | Low price | OHLCV, swing lows, liquidity |
| 4 | close | Close price | OHLCV, regime (MA trend), signals |
| 5 | volume | Base-asset volume | Volume filters, confirmation |
| 6 | close_time | Candle end (ms) | Optional alignment |
| 7 | quote_asset_volume | Quote volume | Optional analytics |
| 8 | num_trades | Number of trades | Optional |
| 9 | taker_buy_base_asset_volume | Taker buy (base) | Optional |
| 10 | taker_buy_quote_asset_volume | Taker buy (quote) | Optional |
| 11 | ignore | Unused | Ignore |

For **regime**, **technical** (order blocks, FVG, supply/demand, liquidity), and **signal fusion**, the minimal needed series are:

- **Time:** `open_time` (or derived datetime).
- **OHLCV:** `open`, `high`, `low`, `close`, `volume`.

Optional: `quote_asset_volume`, `num_trades` for deeper volume/flow analysis.

---

## 3. Coverage (what you have)

Current crawl typically includes:

- **Markets:** `spot`, `um`.
- **Symbols:** e.g. `BTCUSDT`, `ETHUSDT`.
- **Intervals:** e.g. `1h`, `1d` (and optionally `1mo`).
- **Date range:** From crawler `--start` / `--end` (e.g. 2020-01-01 to 2025-03-15).
- **Frequency:** Monthly ZIPs for history; daily for recent gaps.

Check what exists:

```bash
ls data/um/klines/BTCUSDT/1h/   # list monthly zips
ls data/spot/klines/ETHUSDT/1d/
```

If merged CSVs were generated (`--merge-csv`):

```bash
ls data/um/klines/BTCUSDT/*.csv
ls data/spot/klines/ETHUSDT/*.csv
```

---

## 4. Loading data for the strategy

### Option A: Merged CSV (recommended for backtest)

If you ran the crawler with `--merge-csv`, load one series per (market, symbol, interval):

- Path: `data/{market_type}/klines/{symbol}/{symbol}-{interval}.csv`
- Parse `open_time` as integer (ms) or convert to datetime; use columns 1–5 as `open`, `high`, `low`, `close`, `volume` (and 7–10 if needed).

**Loader:** Use `data_loaders.load_klines(data_dir, market_type, symbol, interval)` — it prefers this merged file when present.

### Option B: Zips only

Without merged CSV, either:

1. Run the crawler again with `--merge-csv` to generate merged CSVs, or  
2. Use the same loader: `data_loaders.load_klines(...)` will fall back to reading all ZIPs in `data/{market_type}/klines/{symbol}/{interval}/`, then sort and merge in memory.

### Output shape for strategy

The regime classifier and technical layer expect **numpy arrays** (or list), **oldest bar first, newest last**:

- `open`, `high`, `low`, `close`, `volume`: 1D arrays, same length.
- Regime: `RegimeInputs(close=close, high=high, low=low)`.
- Technical / fusion: same OHLCV + volume; optional `open_time` for date alignment (e.g. M2, halving, seasonal).

So after loading:

- Sort rows by `open_time` ascending.
- Extract columns into `open_time`, `open`, `high`, `low`, `close`, `volume` (and optionally quote_volume, num_trades).
- Pass arrays to `RegimeClassifier`, `order_blocks`, `fair_value_gaps`, `supply_demand_zones`, `volume_confirmation`, and `get_signal` in `signals.fusion`.

---

## 5. Mapping to strategy components

| Strategy piece | Data used | Notes |
|----------------|-----------|--------|
| **Regime** | close, high, low | Optional: M2 YoY, SOPR, MVRV (from other sources, aligned by date) |
| **Order blocks / FVG / zones** | open, high, low, close | Same OHLCV; volume optional for strength |
| **Volume** | volume | SMA, climax, confirmation vs average |
| **Fusion** | All above | regime + technical + volume → signal |
| **Timeline (halving, seasonal)** | open_time (date) | Align from external series (halving dates, calendar) |
| **M2 / on-chain** | open_time (date) | Align from FRED / Glassnode (or CSV) by date |

---

## 6. Gaps and next steps

- **Merged CSVs:** Generate with `--merge-csv` if you prefer a single file per (market, symbol, interval).
- **Kline loader:** Use `data_loaders` (or equivalent) to load from merged CSV or from ZIPs → single DataFrame or arrays for backtest.
- **M2 / halving / seasonal:** Load from external sources and align by date to `open_time` for regime and filters.
- **On-chain:** Optional; align SOPR/MVRV by date when available.

See **STRATEGY_PLAN_AFTER_DATA.md** for the concrete implementation order after data is understood and loadable.
