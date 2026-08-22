# Regime & Decision Chart Dashboard

Web UI to view price, **regime** (bull / bear / sideways), **signals** (long/short), and **trades** on one chart. Deploy locally and use the sidebar to pick symbol and interval.

## Run on localhost

From the project root:

```bash
pip install -r requirements.txt
streamlit run dashboard/app.py
```

Then open **http://localhost:8501** in your browser.

## What you see

- **Candlestick chart** — OHLC for the selected symbol/interval (last N bars).
- **Regime background** — Green tint = bull, red tint = bear, gray = sideways.
- **Signal markers** — Green triangle up = long signal, red triangle down = short signal (from order blocks, FVG, supply/demand + regime).
- **Trade markers** — Blue circle = entry, orange X = exit (from the same backtest logic).
- **Regime strip** — Second panel shows regime over time (Bear / Sideways / Bull).
- **Summary** — Current regime, favor (long/short/neutral), halving phase, seasonal, and a table of trades in view.

## Data

Uses merged klines under `data/{market_type}/klines/{symbol}/{symbol}-{interval}.csv`. Set **Data directory** in the sidebar if your data lives elsewhere.
