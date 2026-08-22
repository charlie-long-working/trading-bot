# Architecture (skill annex)

See also repo `docs/ARCHITECTURE.md` (same map).

## Live stacks

- **OI Telegram (ops):** `oi_history` → `oi_live_signal` → `run_oi_telegram` → GHA
- **OKX Fusion:** `strategy` + `signals.okx_signal` → `run_okx_bot`
- **MACD:** `engine_macd_rsi_bt` (BT SoT) / `bot_macd_rsi` (live)

## Layout

- Keep: `botdown`, `data_loaders`, `strategy`, `signals`, `exchange`, `notify`, `data`, `tradingview`, `deploy`
- Archive: `archive/botv2`, dashboard, old Telegram/webhook/lambda
- Offline optional: `crawler`, root `backtest/`

## GHA OI fallbacks

Klines: Binance spot/vision → Bybit → fapi. OI: Bybit → Binance hist → Gate. Funding: Bybit → fapi → Gate. USDT.D: llama/CMC + spot closes (not fapi-only).
