# Trading-bot architecture

Crypto-only. VN equities → `../stock`. VRE / property → `../real-estate`.

## Mental model (3 live stacks)

```
┌─────────────────────────────────────────────────────────────┐
│ A. OI + USDT.D alerts (primary ops)                         │
│    data_loaders/oi_history + usdt_d                          │
│    → botdown/oi_liq_strategy + oi_live_signal                │
│    → botdown/run_oi_telegram  ← GHA oi-telegram-alerts.yml  │
├─────────────────────────────────────────────────────────────┤
│ B. Regime Fusion OKX bot                                    │
│    strategy/ + signals/okx_signal → exchange/okx_client      │
│    → run_okx_bot.py                                         │
├─────────────────────────────────────────────────────────────┤
│ C. MACD+RSI (backtest + optional live ccxt)                 │
│    botdown/engine_macd_rsi_bt.py  (SoT for % TP/SL)         │
│    botdown/bot_macd_rsi.py + exchange_factory               │
└─────────────────────────────────────────────────────────────┘
```

## Package map

| Dir | Own | Do not |
|-----|-----|--------|
| `botdown/` | Engines, OI live/scenarios, consensus, MACD bot, TV webhook | Dump one-off scripts without CLI |
| `data_loaders/` | All external I/O (klines, OI, USDT.D, liq, FRED M2) | Strategy math |
| `strategy/` + `signals/` | Regime Fusion primitives + OKX signal | OI scenarios |
| `exchange/` + `notify/` | OKX REST (Fusion bot), Telegram | Second Telegram client |
| `data/` | Caches (oi, macro, klines, liquidation) | Commit secrets |
| `tradingview/` | Pine mirrors | Runtime Python |
| `archive/` | Legacy botv2/dashboard/old webhooks | New production code |
| `crawler/` + `backtest/` | Offline vision ZIP + old fusion BT | Prefer botdown for new BT |

## Data flow — OI Telegram (hourly)

1. GHA cron `:05` UTC → `python -m botdown.run_oi_telegram --interval auto --no-liq`
2. `build_oi_panel_recent` — klines: spot/vision → Bybit → fapi; OI: Bybit → BN → Gate
3. `enrich_features` + live I/K only (`oi_live_signal`)
4. Format entry/SL/TP from TF table → `notify.telegram`
5. Dedupe: `botdown/reports/oi_telegram_sent.json` (Actions cache)

## Sources of truth

| Concern | File |
|---------|------|
| MACD % TP/SL BT | `botdown/engine_macd_rsi_bt.py` |
| OI scenarios A–K | `botdown/oi_liq_strategy.py` |
| Live I/K message | `botdown/oi_live_signal.py` |
| GHA-safe OI panel | `data_loaders/oi_history.py` |
| USDT.D | `data_loaders/usdt_d.py` |
| Agent playbook | `.cursor/skills/trading-bot/SKILL.md` |

## Anti-debt rules

1. **One kline facade for new code** — call `data_loaders` helpers; do not add inline Binance URLs in CLIs.
2. **One Telegram product for cron** — OI alerts; regime Telegram is archived.
3. **One MACD engine** — `botdown/engine_macd_rsi_bt.py`; do not revive `archive/botv2` MACD.
4. **One TV→OKX webhook** — `botdown/tradingview_okx_webhook.py`.
5. **Reports** — write under `botdown/reports/`; caches under `data/`.
6. **VN / VRE code** — never reintroduce under this repo; use `stock/` (equities) or `real-estate/` (property).
