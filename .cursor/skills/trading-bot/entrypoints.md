# Entrypoints

All from repo root with `PYTHONPATH=.` (`.venv/bin/python`).

## Live / production

| Command | Role |
|---------|------|
| `python -m botdown.run_oi_telegram [--symbols BTCUSDT,ETHUSDT] [--interval 1h\|4h\|auto] [--dry-run] [--force] [--no-liq] [--no-dedupe]` | Live I+K → Telegram (GHA dùng `--interval auto --no-liq`) |
| `python run_strategy_dashboard.py` | Streamlit OI playbook dashboard (:8501) |
| `python run_okx_bot.py [--symbols] [--market spot\|swap\|um] [--interval 1h] [--size-usdt 100] [--paper\|--dry-run] [--interval-minutes N]` | OKX Regime Fusion (systemd mẫu: `deploy/okx-bot.service.example`) |
| `python run_okx_signal_only.py [--symbols] [--market] [--interval]` | Fusion signal, không đặt lệnh |
| `python -m botdown.bot_macd_rsi --once` / `--loop SEC` | MACD live ccxt (bắt buộc một trong hai; mặc định dry-run qua `MACD_RSI_DRY_RUN`) |
| `python -m botdown.tradingview_okx_webhook` | Flask `POST /tv/okx`, `GET /health`, port `TV_WEBHOOK_PORT` (8787) |
| `python -m botdown.bot --once` | Downtrend short MTF (Binance USD-M), sau khi đóng nến D1 |

## Research

| Command | Role |
|---------|------|
| `python -m botdown.run_oi_scenarios [--symbol] [--start 2022-01-01] [--interval 1d,4h,1h] [--refresh] [--tp] [--sl] [--max-hold]` | Leaderboard A–K theo win rate → `botdown/reports/` |
| `python -m botdown.run_liquidation_map [--symbol BTCUSDT] [--hours 72]` | Liquidation buckets |
| `python -m botdown.run_consensus_crypto [--min-votes 2] [--update-registry] [--dry-run]` | Vote đa mô hình |
| `python -m botdown.run_backtest_macd_rsi [--interval 1d\|1h] [--exit pct\|atr] [--tp-pct] [--sl-pct] [--ema-trend]` | MACD % TP/SL trên 2 cửa sổ bear |
| `python -m botdown.compare_macd_smc_three_windows` | MACD vs SMC |
| `python -m botdown.compare_macd_fusion_windows` | MACD vs Fusion |
| `python -m botdown.search_stable_macd_rsi_btc [--start] [--end] [--fee]` | Grid MACD+RSI |
| `python -m botdown.run_backtest` | Backtest downtrend MTF |
| `python crawl_binance_klines.py [--market-type spot,um] [--symbols] [--intervals] [--start] [--merge-csv]` | Binance Vision ZIP → `data/` |
| `python run_backtest.py [...]` | Fusion backtest cũ trên CSV đã crawl |

## Secrets (`.env`, xem `.env.example`)

- Telegram: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
- OKX (Fusion bot): `OKX_API_KEY`, `OKX_SECRET_KEY`, `OKX_PASSPHRASE`, `OKX_DEMO`.
- OKX (ccxt: MACD bot, webhook): `OKX_API_KEY`, `OKX_API_SECRET`, `OKX_API_PASSPHRASE` (hoặc `OKX_PASSWORD`), `OKX_SANDBOX`.
- Binance (ccxt): `BINANCE_API_KEY`, `BINANCE_API_SECRET`.
- MACD bot: `MACD_RSI_EXCHANGE`, `MACD_RSI_DRY_RUN`, `MACD_RSI_NOTIONAL_USD`, `MACD_RSI_SYMBOL`, `MACD_RSI_LEVERAGE`, `MACD_RSI_TIMEFRAME`, `MACD_RSI_TP_PCT`, `MACD_RSI_SL_PCT`, `MACD_RSI_EMA_*`, `MACD_RSI_OKX_TDMODE`.
- Downtrend bot: `BOTDOWN_DRY_RUN`, `BOTDOWN_NOTIONAL_USD`, `BOTDOWN_SYMBOL`, `BOTDOWN_LEVERAGE`.
- Webhook: `TRADINGVIEW_WEBHOOK_SECRET`, `TV_OKX_SYMBOL`, `TV_OKX_NOTIONAL_USD`, `TV_OKX_LEVERAGE`, `TV_WEBHOOK_PORT`.
- Dữ liệu: `FRED_API_KEY` (M2 YoY cho OKX regime), `COINGLASS_API_KEY` / `CG_API_KEY`, `GLASSNODE_API_KEY`.

GHA secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (`FRED_API_KEY` có nhưng không workflow nào dùng).
