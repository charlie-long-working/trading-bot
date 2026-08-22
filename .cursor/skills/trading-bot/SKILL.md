---
name: trading-bot
description: >-
  Navigate and change the Trading-bot crypto repo (OI Telegram, OKX Regime Fusion,
  MACD/RSI, data_loaders). Use when editing Trading-bot, botdown, OI alerts, OKX bot,
  Binance/Gate fallbacks, or when the user mentions crypto live alerts / GHA oi-telegram.
---

# Trading-bot (crypto)

**Read this first** instead of scanning the whole tree. Details: [architecture.md](architecture.md), [entrypoints.md](entrypoints.md). Workspace sibling: `stock/` (VN only). Related: skill `crypto-oi-usdtd` for OI playbook math.

## Agent rules (save context)

1. Prefer **re-run CLI / read `botdown/reports/`** over re-deriving strategy.
2. Default home: `botdown/` + `data_loaders/`. Ignore `archive/` unless user asks for DCA/legacy.
3. Do not invent a second Telegram/webhook/MACD engine.
4. GHA OI: never assume `fapi` works — use resilient loaders already in `oi_history.py`.
5. `PYTHONPATH=.` from repo root.

## Where to change what

| Task | Touch |
|------|--------|
| Live OI alert text / I+K | `botdown/oi_live_signal.py` |
| Live playbook dashboard | `botdown/dashboard_oi_playbook.py` (`python run_strategy_dashboard.py`) |
| OI scenario definitions | `botdown/oi_liq_strategy.py` |
| Fetch OI/klines/funding (GHA) | `data_loaders/oi_history.py` |
| USDT.D | `data_loaders/usdt_d.py` |
| Telegram send | `notify/telegram.py` + `botdown/run_oi_telegram.py` |
| Cron | `.github/workflows/oi-telegram-alerts.yml` |
| OKX live Fusion | `run_okx_bot.py`, `signals/okx_signal.py`, `exchange/okx_client.py` |
| MACD backtest | `botdown/engine_macd_rsi_bt.py`, `botdown/run_backtest_macd_rsi.py` |
| MACD live ccxt | `botdown/bot_macd_rsi.py`, `botdown/exchange_factory.py` |

## Quick commands

```bash
cd /Users/namnguyen/Documents/Cursor/Trading-bot
export PYTHONPATH=.

python -m botdown.run_oi_telegram --dry-run --interval 1h
python -m botdown.run_oi_scenarios --interval 1h,4h
python -m botdown.run_liquidation_map --symbol BTCUSDT
python -m botdown.run_backtest_macd_rsi --interval 1d --exit pct --tp-pct 0.10 --sl-pct 0.04
```

## Trace checklist

When debugging alerts: workflow SHA → `run_oi_telegram` → `build_oi_panel_recent` (source=gate/spot?) → `enrich_features` → I/K → `format_oi_telegram` → secrets.

When adding a feature: update [architecture.md](architecture.md) one line if you add a new entrypoint or SoT file.
