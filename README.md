# Trading-bot

Binance historical klines crawler and macro/regime-based trading strategy (design + scaffolding).

**Version:** see [VERSION](VERSION). Lưu version bằng Git: `git tag v1.0.0` và `git push --tags`.

---

## Docker (chạy đóng gói)

```bash
# Build và chạy dashboard tại http://localhost:5000
docker compose up -d

# Crawl dữ liệu (volume ./data được mount vào /app/data)
docker compose run --rm bot python crawl_binance_klines.py --market-type spot,um --symbols BTCUSDT,ETHUSDT --interval 1h --start 2024-01-01 --end 2025-03-15 --out-dir /app/data

# Gửi tín hiệu Telegram (cần .env với TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
docker compose run --rm bot python run_telegram_signal.py

# Chạy backtest
docker compose run --rm bot python run_backtest.py
```

Tạo file `.env` từ `.env.example` (Glassnode, Telegram) trước khi dùng Telegram hoặc on-chain. Build đơn lẻ: `docker build -t trading-bot:latest .`

---

## Part 1: Binance data.binance.vision crawler

### What the data is

- **Futures (USD-M):** [data.binance.vision – futures UM daily klines](https://data.binance.vision/?prefix=data/futures/um/daily/klines/)
- **Spot:** [data.binance.vision – spot daily klines](https://data.binance.vision/?prefix=data/spot/daily/klines/)

Both provide **daily** and **monthly** kline (candlestick) ZIPs. Use **monthly** for history and **daily** for the most recent days not yet in the latest monthly file.

### URL patterns

| Market               | Base path                                             | File pattern                           |
| -------------------- | ----------------------------------------------------- | -------------------------------------- |
| Spot                 | `data/spot/daily/klines/{SYMBOL}/{INTERVAL}/`         | `{SYMBOL}-{INTERVAL}-{YYYY-MM-DD}.zip` |
| Spot (monthly)       | `data/spot/monthly/klines/{SYMBOL}/{INTERVAL}/`       | `{SYMBOL}-{INTERVAL}-{YYYY-MM}.zip`    |
| Futures UM           | `data/futures/um/daily/klines/{SYMBOL}/{INTERVAL}/`   | Same (symbol, interval, date)          |
| Futures UM (monthly) | `data/futures/um/monthly/klines/{SYMBOL}/{INTERVAL}/` | `{SYMBOL}-{INTERVAL}-{YYYY-MM}.zip`    |

**Intervals:** `1m`, `3m`, `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `6h`, `8h`, `12h`, `1d`, `3d`, `1w`, `1mo`.

**Example URLs:**

- Spot 1h BTC:  
  `https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1h/BTCUSDT-1h-2025-03-14.zip`
- Futures 1d ETH:  
  `https://data.binance.vision/data/futures/um/daily/klines/ETHUSDT/1d/ETHUSDT-1d-2025-03-14.zip`

### Kline CSV format

Each ZIP contains a CSV (no header). Each row is one candle. Columns:

| Index | Field                        | Description              |
| ----- | ---------------------------- | ------------------------ |
| 0     | open_time                    | Candle start (ms)        |
| 1     | open                         | Open price               |
| 2     | high                         | High price               |
| 3     | low                          | Low price                |
| 4     | close                        | Close price              |
| 5     | volume                       | Base-asset volume        |
| 6     | close_time                   | Candle end (ms)          |
| 7     | quote_asset_volume           | Quote volume             |
| 8     | num_trades                   | Number of trades         |
| 9     | taker_buy_base_asset_volume  | Taker buy (base) volume  |
| 10    | taker_buy_quote_asset_volume | Taker buy (quote) volume |
| 11    | ignore                       | Unused                   |

For most price/volume work you only need columns 0–5 (time, O, H, L, C, V).

### How to run the crawler

1. **Create a virtual environment and install dependencies:**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Download klines (examples):**

   **Why only one ZIP?** You get one file per (market, symbol, interval, date/month). So a single month + one symbol + one interval = 1 ZIP. To get many files, use a **wider date range**, **multiple intervals** (`--intervals 1h,1d`), **multiple symbols**, and/or **both markets** (`spot,um`).

   ```bash
   # Crawl more data: spot + futures, BTC + ETH, 1h and 1d, monthly Jan 2024 – Mar 2025 (~120 ZIPs)
   python crawl_binance_klines.py --market-type spot,um --symbols BTCUSDT,ETHUSDT \
     --intervals 1h,1d --start 2024-01-01 --end 2025-03-15 --frequency monthly --out-dir data

   # Spot + futures, BTC and ETH, single interval 1h, monthly from 2020 to now
   python crawl_binance_klines.py --market-type spot,um --symbols BTCUSDT,ETHUSDT \
     --interval 1h --start 2020-01-01 --end 2025-03-15 --frequency monthly --out-dir data

   # Daily files only, spot, last 7 days
   python crawl_binance_klines.py --market-type spot --symbols BTCUSDT \
     --interval 1d --start 2025-03-08 --end 2025-03-15 --frequency daily --out-dir data

   # After download: unzip and merge into one CSV per (market, symbol, interval)
   python crawl_binance_klines.py --market-type spot,um --symbols BTCUSDT,ETHUSDT \
     --intervals 1h,1d --start 2024-01-01 --frequency monthly --out-dir data --merge-csv
   ```

3. **CLI options:**

   | Option               | Description |
   | -------------------- | ----------- |
   | `--market-type`      | `spot`, `um`, or `spot,um` |
   | `--symbols`          | Comma-separated, e.g. `BTCUSDT,ETHUSDT` |
   | `--interval`         | Single interval (e.g. `1h`, `1d`); used if `--intervals` not set |
| `--intervals`        | Comma-separated intervals (e.g. `1h,1d`) to fetch multiple at once |
   | `--start` / `--end`  | Date range `YYYY-MM-DD` (default end: today) |
   | `--frequency`       | `daily` or `monthly` |
   | `--out-dir`         | Output directory (default: `data`) |
   | `--workers`         | Parallel downloads 1–4 (default: 2) |
   | `--merge-csv`       | Unzip and merge into one CSV per (market, symbol, interval) |
   | `--no-skip-existing`| Re-download even if file exists |

4. **Output layout:**

   - ZIPs: `{out_dir}/{market_type}/klines/{symbol}/{interval}/{symbol}-{interval}-{date}.zip`
   - Merged CSV (with `--merge-csv`): `{out_dir}/{market_type}/klines/{symbol}/{symbol}-{interval}.csv`

The script skips existing files by default (incremental/delta). It uses throttling and exponential backoff on HTTP 429.

---

## Part 2: Macro/regime + technical strategy

Strategy combines **timeline factors** (on-chain, M2, halving, seasonal), **market regime** (bear, bull, sideways), and **technical** (smart money, supply/demand, volume). See:

- **[docs/STRATEGY.md](docs/STRATEGY.md)** – macro/regime narrative, regime rules, and **technical strategy** (order blocks, FVG, liquidity, supply/demand, volume).
- **[docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md)** – phased implementation plan (data → regime → technical → fusion → backtest → execution).
- **`strategy/`** – Regime classifier, rule sets, timeline (halving, seasonal), **order blocks**, **fair value gaps**, **supply/demand zones**, **volume** filters.
- **`signals/`** – Signal fusion: regime + technical zones → long/short/none with optional volume confirmation.

### On-chain data (Glassnode)

SOPR and MVRV are loaded from the **Glassnode API** (or from cached CSV) and passed into the regime classifier.

1. **API key (optional):** Create a key at [glassnode.com](https://glassnode.com). Copy `.env.example` to `.env` and set `GLASSNODE_API_KEY=your_key`. Without a key, the bot uses cached files in `data/onchain/{BTC|ETH}/` when present.
2. **Cache:** First run with API key saves `data/onchain/BTC/sopr.csv`, `mvrv.csv` (and same for ETH). Later runs can use cache only.
3. **Symbols:** Only **BTCUSDT** and **ETHUSDT** are mapped to Glassnode assets (BTC, ETH). Other pairs run without on-chain.

---

## Dashboard GUI (tracking and view)

A web dashboard makes it easier to track market context, backtest results, and charts.

**Run the dashboard:**

```bash
pip install -r requirements.txt   # includes flask
python run_dashboard.py
```

Then open **http://127.0.0.1:5000** in your browser.

**Features:**

- **Market context** – Regime, favor (long/short/neutral), halving phase, seasonal flag, last close for the selected market/symbol/interval.
- **Backtest summary** – Trades, return %, max drawdown, win rate, profit factor for the selected pair.
- **All-pairs backtest table** – Summary of backtest metrics for spot/um × BTCUSDT/ETHUSDT × 1d/1h.
- **Price & regime chart** – Close price and regime (bull/bear) over the last 500 bars for the selected pair.

Use the dropdowns to switch market (spot/um), symbol (BTCUSDT/ETHUSDT), and interval (1d/1h), then click **Refresh** to update.
