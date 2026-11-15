# Reference — OI / USDT.D baselines

Refresh by re-running `python3 -m botdown.run_oi_scenarios`. Numbers below are **in-sample** snapshots (approx window 2022-01-01 → 2026-08-22).

## Data retention notes

| Source | Span available publicly |
|--------|-------------------------|
| Bybit OI 1d / 4h / 1h | 2022 → now (chunked startTime/endTime) |
| Binance funding | 2022 → now |
| Binance OI / L-S ratios | ~30 days only |
| CMC global mcap (for true USDT.D) | ~last 500 days |
| DefiLlama USDT circulating | ~2017 → now |
| USDT.D older than CMC | `proxy_calibrated` in `usdt_d_source` |

## Default simulate params

- **1d:** TP 8%, SL 3%, max hold 10d
- **4h:** TP 4%, SL 1.5%, max hold 24 bars (~4d)
- **1h:** TP 1.5%, SL 0.6%, max hold 48 bars (~2d)
- Fee RT 0.04%. Entry next bar open; exits TP/SL/time/flip.

## Leaderboard snapshot (win rate + R:R + profit / $1k compound)

Planned R:R **2.67** (1d/4h) and **2.50** (1h). Realized ~2.3–2.6 (time exits). BE WR ~28–31%.

**1d** (min n=8): G WR 44.8% RR 2.25 profit **+$429** CAGR 8.2% · K 40.0% RR 2.45 **+$631** CAGR 11.3% · I 36.2% **+$486**

**4h** (min n=20): I WR 47.7% RR 2.57 profit **+$4,735** CAGR 46.7% · K 40.5% **+$1,967** CAGR 27%

**1h** (min n=40): I WR 41.3% RR 2.35 profit **+$3,268** CAGR 37.5% · K 38.6% **+$1,807** CAGR 25.4%

Avoid as primary: E_oi_div_short. H_bear_bounce_fade has too few trades on H1/H4. Do not add profits across TFs.

## G exit mix (typical)

- SL ~55%, TP ~31%, time ~14%
- Side mix often short-heavy in bear windows

## K by year (WR focus)

| Year | n | WR% | Note |
|------|--:|----:|------|
| 2022 | ~14 | ~21% | Weak |
| 2023 | ~8 | ~38% | |
| 2024 | ~8 | ~62% | Strong |
| 2025 | ~11 | ~36% | |
| 2026 YTD | ~9 | ~56% | |

## Money example @ $1000 compound

**A — margin 5% × 20x** (notional ≈ equity):

| | G | K |
|--|--:|--:|
| Final | ~$1429 | ~$1631 |
| CAGR ~4.64y | ~8%/y | ~11%/y |
| Avg win / loss $ | ~+$79 / −$35 | similar |

**B — risk 5% of equity at SL 3%**:

| | G | K |
|--|--:|--:|
| Final | ~$1740 | ~$2104 |
| Max DD | steeper (~21–31%) | |

## Live playbook fields

From `playbook_now` in JSON:

- `usdt_d`, `usdt_d_chg_3`, `usdt_d_z_30`, `usdtd_risk_off/on`
- `oi_chg_3_pct`, `oi_z_30`, `funding_z_30`, `regime_ema`
- `recommended.side|confidence|thesis|entry|stop|target`
- Liq: `nearest_long_cluster` (below), `nearest_short_cluster` (above)

## Env (optional)

```
COINGLASS_API_KEY=   # else reconstructed liq map
FRED_API_KEY=        # M2 YoY cho run_okx_bot (regime); không dùng cho OI
```
