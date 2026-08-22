# Archive — legacy / research (not production)

Code here is **kept for reference**, not the agent default path.

| Path | Was | Prefer instead |
|------|-----|----------------|
| `botv2/` | DCA + duplicate MACD + CCXT cache | `botdown/engine_macd_rsi_bt.py`, `data/` |
| `dashboard/` + `run_dashboard.py` | Streamlit decision UI | OI reports / Telegram |
| `run_telegram_signal.py` | Regime 1h Telegram | `python -m botdown.run_oi_telegram` |
| `webhook_tv_to_okx_server.py` | TV→OKX v1 | `botdown/tradingview_okx_webhook.py` |
| `lambda_tv_okx/` | AWS Lambda TV→OKX | same webhook module |

Run archived scripts only if needed:

```bash
cd /Users/namnguyen/Documents/Cursor/Trading-bot
PYTHONPATH=archive:. python -m botv2.run_all   # if you still need DCA research
```

Do **not** add new features under `archive/`. Promote to `botdown/` / `data_loaders/` if revived.
