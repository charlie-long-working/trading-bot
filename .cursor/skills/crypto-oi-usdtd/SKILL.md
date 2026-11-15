---
name: crypto-oi-usdtd
description: >-
  BTC futures OI + funding + USDT.D scenarios, liquidation-price buckets, and
  win-rate-ranked playbooks in Trading-bot. Use when the user asks about OI,
  open interest, USDT.D, liquidation map/heatmap, crowdfade, G_regime,
  K_oi_usdtd_confluence, R:R sizing, or margin×leverage P&L on these strategies.
---

# Crypto OI + USDT.D + Liquidation

Repo map / anti-debt: skill **`trading-bot`**. This skill is the **OI strategy playbook** (scenarios, exits, live I+K).

Workspace: `Documents/Cursor/Trading-bot`. Run with `PYTHONPATH=.` from that root. Prefer **re-running scripts / reading reports** over re-deriving logic.

## Rank metric (user preference)

- Primary: **win rate** (min 8 trades on 1d; 20 on 4h; 40 on 1h). Do **not** optimize vs buy&hold ROI.
- Return / CAGR only when asked for money sizing.
- Default exit: **1d** TP 8%/SL 3%/hold 10d; **4h** 4%/1.5%/24 bars; **1h** 1.5%/0.6%/48 bars.

## Commands (copy-paste)

```bash
cd /Users/namnguyen/Documents/Cursor/Trading-bot
export PYTHONPATH=.

# Live long/short by liquidation price buckets → reports/liquidation_map_btcusdt.*
python3 -m botdown.run_liquidation_map --symbol BTCUSDT

# OI panel 2022→now + USDT.D + nến + scenario leaderboard (win rate)
python3 -m botdown.run_oi_scenarios                  # BTC 1d
python3 -m botdown.run_oi_scenarios --interval 1h,4h
python3 -m botdown.run_oi_scenarios --symbol ETHUSDT --interval 1d,4h,1h
python3 -m botdown.run_oi_scenarios --refresh        # force re-crawl

# Live H1/H4 alerts (I + K only) → Telegram
python3 -m botdown.run_oi_telegram --dry-run --interval 1h
python3 -m botdown.run_oi_telegram --interval auto   # 1h always; 4h if UTC hour % 4 == 0
python3 -m botdown.run_oi_telegram --interval 4h --force

# Consensus (MACD/SMC/Fusion + liquidation_map vote)
python3 -m botdown.run_consensus_crypto --dry-run
```

### Live playbook H1/H4 (Telegram)

- Strategies: **`K_oi_usdtd_confluence`** (primary) + **`I_usdtd_risk_off_short`**. No `G` on H1/H4 live.
- Symbols: BTCUSDT, ETHUSDT. Exits: H4 TP 4%/SL 1.5%; H1 TP 1.5%/SL 0.6%.
- Module: `botdown/oi_live_signal.py` (recent panel) + `botdown/run_oi_telegram.py`.
- Dedupe: `botdown/reports/oi_telegram_sent.json`.

**GitHub Actions** (no VPS needed for alerts): workflow `.github/workflows/oi-telegram-alerts.yml`

- Cron: `45 * * * *` UTC (= :45 giờ VN). GitHub giãn lịch → thực tế ~5 lần/ngày, nhiều nến 1h không được quét; 4h chỉ chạy khi lần chạy rơi vào giờ UTC chia hết cho 4.
- Workflow bị `disabled_inactivity` 22/10–15/11/2026, đã bật lại. Repo public 60 ngày không push sẽ bị tắt nữa → `gh workflow enable oi-telegram-alerts.yml`.
- Đã sửa 15/11/2026: `format_oi_telegram` escape HTML (trước đó cảnh báo có K bị Telegram từ chối vì `<` thô trong `SCENARIO_WHY`).
- GHA chạy với `--no-liq`.
- Secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
- `workflow_dispatch` for manual / dry-run.
- Job uses recent OI fetch (not full 2022 crawl). VPS only if later auto-trade / websocket.

HTTP: loaders use **urllib + ProxyHandler({})** (avoid env proxy 403). Live `build_oi_panel_recent` fallbacks for GHA: **klines** spot/Bybit (fapi often 451); **OI** Bybit → Binance hist → **Gate** contract_stats; **funding** Bybit → Binance → Gate. Full backtests still prefer Bybit OI + Binance fapi. USDT.D daily, ffill onto H1/H4.

## Key modules

| Module | Role |
|--------|------|
| `data_loaders/oi_history.py` | OI/price/funding panel; GHA-safe spot+Gate fallbacks |
| `data_loaders/usdt_d.py` | USDT.D = USDT mcap (DefiLlama) / total (CMC ~500d; older = calibrated proxy) |
| `data_loaders/liquidation_map.py` | Live buckets; CoinGlass if `COINGLASS_API_KEY` else OI×leverage reconstruct |
| `botdown/oi_liq_strategy.py` | Features, scenarios A–K, simulate, playbook |
| `botdown/oi_live_signal.py` | Live I+K scan on recent H1/H4 panel |
| `botdown/run_oi_scenarios.py` | CLI + markdown/json reports |
| `botdown/run_oi_telegram.py` | Telegram alerts + dedupe |
| `botdown/crypto_consensus.py` | Adds vote `liquidation_map` (not kill-registry) |
| `.github/workflows/oi-telegram-alerts.yml` | Cron :45 UTC → Telegram |

## Reports (read these first)

```
botdown/reports/
  oi_panel_{btc,eth}usdt_daily.csv|_4h.csv|_1h.csv
  klines_{btc,eth}usdt_*.csv
  oi_scenarios_btcusdt*.md|.json
  oi_scenarios_ethusdt*.md|.json
  oi_btc_eth_compare.md
  oi_scenario_trades_<name>_{btc,eth}usdt[_4h|_1h].csv
  oi_telegram_sent.json                 # dedupe cache for live alerts
  liquidation_map_btcusdt.csv|.json
data/macro/usdt_d_daily.csv
data/oi/{btc,eth}usdt_oi_panel_{daily,4h,1h}.csv
```

## Scenario cheat-sheet

| ID | Idea |
|----|------|
| **G_regime_crowdfade** | Best WR on **1d**: bear+OI↑5%+fund+ → short; bull+OI↑2%+fund− → long |
| **I_usdtd_risk_off_short** | Best WR on **4h/1h** (enough trades): USDT.D↑ + fund+ → short · **live H1/H4** |
| **K_oi_usdtd_confluence** | G-style + USDT.D filters · **live H1/H4 primary** |
| **I / J** | USDT.D-only risk-off short / risk-on long |
| Liq vote | Nearby long buckets below mark → cascade/short; short buckets above → squeeze/long |

USDT.D ↑ (Δ3d >0.15 or z>1) = risk-off; ↓ = risk-on.

## Playbook workflow

1. **Live H1/H4:** `run_oi_telegram` / GHA cron — I+K only; Telegram when side ≠ none.
2. Backtest reports: `oi_scenarios_*_{1h,4h}.md` / `oi_btc_eth_compare.md`.
3. Answer with: side, scenario, USDT.D, OI Δ3d, TP/SL — **not investment advice**.

## Sizing answers (when asked)

Assume compound unless user says otherwise.

- **Margin 5% × lev 20x** → notional ≈ 100% equity. @ $1000: margin $50, notional $1000; TP +$80 / SL −$30.
- **Risk 5% on SL 3%** → notional = risk/0.03; @ $1000: notional ~$1667, TP +$133 / SL −$50.

Baseline totals (in-sample 2022-01→2026-08, ~4.64y) — re-run to refresh:

| Setup | G final | K final | G CAGR | K CAGR |
|-------|---------|---------|--------|--------|
| margin 5%×20x | ~+$429 (~8%/y) | ~+$631 (~11%/y) | ~8% | ~11% |

Details / year splits: [reference.md](reference.md).

## Agent rules (token savers)

1. **Do not** re-probe Bybit/CMC/Llama APIs unless `--refresh` or cache missing.
2. **Do not** rebuild strategy from scratch — edit `oi_liq_strategy.py` scenarios.
3. Rank tables by **win rate**, not return.
4. Cross-link only: sibling skill `trading-vn-crypto` for MACD/VN/bots.
