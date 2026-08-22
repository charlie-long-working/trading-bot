# OI + USDT.D Scenarios — BTCUSDT **1h**

Window: **2022-01-01 → 2026-08-22 17:00** (40674 nến 1h).
Nguồn: Bybit OI · Binance funding/giá · **USDT.D** (DefiLlama USDT mcap / CMC total, proxy hiệu chỉnh trước ~2025-04).
Lookback OI/USDT.D/funding theo **lịch** (3 ngày / 30 ngày); EMA 20/50 trên nến khung.
Xếp hạng theo **win rate** (min 40 trades). Profit = compound 100% notional/trade, vốn gốc $1,000.
Exit: TP 1.5% / SL 0.6% → **R:R kế hoạch 2.50:1** / max hold 48 bars (~2.0d). Fee RT 0.04%.

## Bảng kịch bản (sort win rate ↓)

| # | Scenario | n | **Win%** | R:R kế hoạch | R:R thực | Exp R | Profit $1k | CAGR | MaxDD | PF |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | `I_usdtd_risk_off_short` | 615 | **41.3** | 2.50 | 2.35 | +0.40 | **$+3,268** | +37.5% | -7.0% | 1.65 |
| 2 | `K_oi_usdtd_confluence` | 609 | **38.6** | 2.50 | 2.30 | +0.29 | **$+1,807** | +25.4% | -11.6% | 1.45 |
| 3 | `J_usdtd_risk_on_long` | 493 | **34.1** | 2.50 | 2.27 | +0.12 | **$+406** | +7.8% | -15.8% | 1.18 |
| 4 | `G_regime_crowdfade` | 216 | **32.4** | 2.50 | 2.32 | +0.08 | **$+96** | +2.0% | -7.4% | 1.11 |
| 5 | `B_crowdfade_long` | 308 | **31.2** | 2.50 | 2.25 | +0.01 | **$+14** | +0.3% | -15.8% | 1.02 |
| 6 | `F_combined_ema` | 587 | **29.6** | 2.50 | 2.31 | -0.02 | **$-94** | -2.1% | -33.6% | 0.97 |
| 7 | `D_flush_short` | 149 | **29.5** | 2.50 | 2.35 | -0.01 | **$-17** | -0.4% | -11.6% | 0.98 |
| 8 | `E_oi_div_short` | 602 | **27.7** | 2.50 | 2.30 | -0.09 | **$-293** | -7.3% | -35.4% | 0.88 |
| 9 | `A_crowdfade_short` | 247 | **27.5** | 2.50 | 2.29 | -0.10 | **$-146** | -3.4% | -20.4% | 0.87 |
| 10 | `C_flush_long` | 176 | **23.3** | 2.50 | 2.25 | -0.26 | **$-245** | -6.0% | -30.6% | 0.68 |
| 11 | `H_bear_bounce_fade` * | 11 | **54.5** | 2.50 | 2.33 | +0.87 | **$+58** | +1.2% | -2.5% | 2.80 |

\* n thấp hơn ngưỡng rank. R:R thực = avg win / |avg loss| (gồm time/flip, nên khác kế hoạch). Profit compound trên $1,000, 1 position, không lev. BE WR ≈ 1/(1+R:R thực).

## `K_oi_usdtd_confluence` theo năm

| Year | n | Win% | R:R thực | Exp R | Profit $1k |
|---|---:|---:|---:|---:|---:|
| 2022 | 156 | **40.4** | 2.28 | +0.35 | $+371 |
| 2023 | 87 | **42.5** | 2.25 | +0.40 | $+229 |
| 2024 | 123 | **42.3** | 2.29 | +0.42 | $+352 |
| 2025 | 119 | **35.3** | 2.29 | +0.17 | $+124 |
| 2026 | 124 | **33.9** | 2.32 | +0.13 | $+96 |

## Playbook hiện tại

- Time / close: **2026-08-22 17:00** / `77288.9`
- OI Δ3d: -19.83% | z30: -2.75 | fund z: 1.53
- **USDT.D:** `6.939`% (Δ3d -0.999, z -3.53) | risk-off=False risk-on=True
- EMA regime (1h): **bull**

**Khuyến nghị:** `NONE` (conf=none) — No OI/USDT.D confluence; flat

### Liquidation map
- Vote: **none** (balanced_liq_map)
- Long cluster: `76979.79` | Short: `79687.63`

## Logic `K_oi_usdtd_confluence`

1. **SHORT:** EMA bear + OI↑3d >2% + **USDT.D** Δ3d>+0.2 (hoặc z>1) + fund z>0.3
2. **LONG:** EMA bull + OI↑3d >1.5% + **USDT.D** Δ3d<−0.2 (hoặc z<−1) + fund z<−0.5
3. USDT.D ↑ = tiền trú ẩn stable → áp lực BTC; USDT.D ↓ = risk-on.
4. USDT.D daily được ffill lên nến H1/H4 (bước ngày, không nội suy trong ngày).

Best by win rate: `I_usdtd_risk_off_short` — WR **41.3%** · R:R thực **2.35:1** (kế hoạch 2.50) · profit **$+3,268** / $1k (+326.8%, CAGR +37.5%) · n=615 → `oi_scenario_trades_I_usdtd_risk_off_short_btcusdt_1h.csv`

Panel: `oi_panel_btcusdt_1h.csv` · klines: `klines_btcusdt_1h.csv`

*Không phải tư vấn đầu tư.*