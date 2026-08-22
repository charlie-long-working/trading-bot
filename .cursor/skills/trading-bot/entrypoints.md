# Entrypoints

All from repo root with `PYTHONPATH=.`.

## Production / frequent

| Command | Role |
|---------|------|
| `python -m botdown.run_oi_telegram` | Live I+K → Telegram (GHA) |
| `python -m botdown.run_oi_scenarios` | Scenario leaderboard → `botdown/reports/` |
| `python run_okx_bot.py` | OKX Regime Fusion live |
| `python run_okx_signal_only.py` | Fusion signal, no orders |
| `python -m botdown.bot_macd_rsi` | MACD live (ccxt) |

## Research

| Command | Role |
|---------|------|
| `python -m botdown.run_backtest_macd_rsi` | MACD % TP/SL windows |
| `python -m botdown.run_liquidation_map` | Liq buckets |
| `python -m botdown.run_consensus_crypto` | Multi-model vote |
| `python -m botdown.compare_macd_smc_three_windows` | Compare engines |
| `python crawl_binance_klines.py` | Vision ZIP → `data/` |
| `python run_backtest.py` | Legacy fusion on crawled CSV |

## Prefer webhook

`python -m botdown.tradingview_okx_webhook` (archived v1 under `archive/`).

## Secrets (`.env`)

`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `OKX_API_KEY`, `OKX_SECRET_KEY`, `OKX_PASSPHRASE`, optional `FRED_API_KEY`, `COINGLASS_API_KEY`.
