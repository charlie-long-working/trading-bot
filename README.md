# Trading-bot

Crypto trading: **OI + USDT.D Telegram alerts**, OKX Regime Fusion bot, MACD/RSI backtests.

VN stocks → [`stock/`](../stock). VRE / BĐS → [`real-estate/`](../real-estate).  
**Agents:** read `.cursor/skills/trading-bot/SKILL.md` (also under workspace `.cursor/skills/`).  
**Architecture:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Setup

```bash
cd /Users/namnguyen/Documents/Cursor/Trading-bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Telegram / OKX / optional FRED
export PYTHONPATH=.
```

## Most-used commands

```bash
# Live playbook dashboard (I+K, TP/SL, scan BTC/ETH)
python run_strategy_dashboard.py
# hoặc: PYTHONPATH=. streamlit run botdown/dashboard_oi_playbook.py

# Live OI alerts (same as GitHub Actions)
python -m botdown.run_oi_telegram --dry-run --interval auto

# OI scenario research
python -m botdown.run_oi_scenarios --interval 1h,4h

# OKX Fusion bot
python run_okx_bot.py

# MACD backtest
python -m botdown.run_backtest_macd_rsi --interval 1d --exit pct --tp-pct 0.10 --sl-pct 0.04
```

## Layout (short)

| Path | Role |
|------|------|
| `botdown/` | Engines, OI live/scenarios, MACD bot |
| `data_loaders/` | Exchange/API I/O |
| `strategy/` `signals/` `exchange/` | Regime Fusion + OKX |
| `notify/` | Telegram |
| `data/` | Caches |
| `archive/` | Legacy (botv2, old dashboard/webhooks) — do not extend |
| `.github/workflows/oi-telegram-alerts.yml` | Hourly OI → Telegram |

## Secrets (GHA)

`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` only for OI alerts. OKX keys stay local/VPS.
