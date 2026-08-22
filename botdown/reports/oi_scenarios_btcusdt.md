# OI + USDT.D Scenarios — BTCUSDT **1d**

Window: **2022-01-01 → 2026-08-22** (1695 nến 1d).
Nguồn: Bybit OI · Binance funding/giá · **USDT.D** (DefiLlama USDT mcap / CMC total, proxy hiệu chỉnh trước ~2025-04).
Lookback OI/USDT.D/funding theo **lịch** (3 ngày / 30 ngày); EMA 20/50 trên nến khung.
Xếp hạng theo **win rate** (min 8 trades). Profit = compound 100% notional/trade, vốn gốc $1,000.
Exit: TP 8.0% / SL 3.0% → **R:R kế hoạch 2.67:1** / max hold 10d. Fee RT 0.04%.

## Bảng kịch bản (sort win rate ↓)

| # | Scenario | n | **Win%** | R:R kế hoạch | R:R thực | Exp R | Profit $1k | CAGR | MaxDD | PF |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | `G_regime_crowdfade` | 29 | **44.8** | 2.67 | 2.25 | +0.46 | **$+429** | +8.2% | -12.6% | 1.83 |
| 2 | `K_oi_usdtd_confluence` | 50 | **40.0** | 2.67 | 2.45 | +0.37 | **$+631** | +11.3% | -18.4% | 1.63 |
| 3 | `C_flush_long` | 29 | **37.9** | 2.67 | 2.10 | +0.17 | **$+123** | +2.6% | -10.9% | 1.28 |
| 4 | `A_crowdfade_short` | 33 | **36.4** | 2.67 | 2.38 | +0.23 | **$+198** | +4.0% | -18.4% | 1.36 |
| 5 | `I_usdtd_risk_off_short` | 69 | **36.2** | 2.67 | 2.43 | +0.23 | **$+486** | +9.1% | -25.0% | 1.38 |
| 6 | `B_crowdfade_long` | 41 | **34.1** | 2.67 | 2.23 | +0.10 | **$+83** | +1.8% | -20.7% | 1.15 |
| 7 | `F_combined_ema` | 102 | **31.4** | 2.67 | 2.49 | +0.09 | **$+175** | +3.6% | -27.5% | 1.14 |
| 8 | `H_bear_bounce_fade` | 16 | **31.2** | 2.67 | 2.71 | +0.16 | **$+56** | +1.2% | -18.9% | 1.23 |
| 9 | `J_usdtd_risk_on_long` | 32 | **31.2** | 2.67 | 1.74 | -0.14 | **$-148** | -3.4% | -22.1% | 0.79 |
| 10 | `D_flush_short` | 43 | **25.6** | 2.67 | 2.89 | -0.01 | **$-53** | -1.2% | -17.2% | 0.99 |
| 11 | `E_oi_div_short` | 53 | **22.6** | 2.67 | 2.36 | -0.23 | **$-335** | -8.6% | -44.4% | 0.69 |

\* n thấp hơn ngưỡng rank. R:R thực = avg win / |avg loss| (gồm time/flip, nên khác kế hoạch). Profit compound trên $1,000, 1 position, không lev. BE WR ≈ 1/(1+R:R thực).

## `K_oi_usdtd_confluence` theo năm

| Year | n | Win% | R:R thực | Exp R | Profit $1k |
|---|---:|---:|---:|---:|---:|
| 2022 | 14 | **21.4** | 3.20 | -0.09 | $-51 |
| 2023 | 8 | **37.5** | 1.97 | +0.12 | $+19 |
| 2024 | 8 | **62.5** | 2.34 | +1.10 | $+283 |
| 2025 | 11 | **36.4** | 2.22 | +0.17 | $+43 |
| 2026 | 9 | **55.6** | 2.76 | +1.01 | $+292 |

## Playbook hiện tại

- Time / close: **2026-08-22** / `77181.5`
- OI Δ3d: -21.52% | z30: -2.72 | fund z: 2.07
- **USDT.D:** `6.939`% (Δ3d -0.999, z -3.28) | risk-off=False risk-on=True
- EMA regime (1d): **bull**

**Khuyến nghị:** `NONE` (conf=none) — No OI/USDT.D confluence; flat

### Liquidation map
- Vote: **none** (balanced_liq_map)
- Long cluster: `76979.83` | Short: `79687.66`

## Logic `K_oi_usdtd_confluence`

1. **SHORT:** EMA bear + OI↑3d >2% + **USDT.D** Δ3d>+0.2 (hoặc z>1) + fund z>0.3
2. **LONG:** EMA bull + OI↑3d >1.5% + **USDT.D** Δ3d<−0.2 (hoặc z<−1) + fund z<−0.5
3. USDT.D ↑ = tiền trú ẩn stable → áp lực BTC; USDT.D ↓ = risk-on.
4. USDT.D daily được ffill lên nến H1/H4 (bước ngày, không nội suy trong ngày).

Best by win rate: `G_regime_crowdfade` — WR **44.8%** · R:R thực **2.25:1** (kế hoạch 2.67) · profit **$+429** / $1k (+42.9%, CAGR +8.2%) · n=29 → `oi_scenario_trades_G_regime_crowdfade_btcusdt.csv`

Panel: `oi_panel_btcusdt_daily.csv` · klines: `klines_btcusdt_daily.csv`

*Không phải tư vấn đầu tư.*