# OI + USDT.D Scenarios — BTCUSDT **4h**

Window: **2022-01-01 → 2026-08-22 16:00** (10169 nến 4h).
Nguồn: Bybit OI · Binance funding/giá · **USDT.D** (DefiLlama USDT mcap / CMC total, proxy hiệu chỉnh trước ~2025-04).
Lookback OI/USDT.D/funding theo **lịch** (3 ngày / 30 ngày); EMA 20/50 trên nến khung.
Xếp hạng theo **win rate** (min 20 trades). Profit = compound 100% notional/trade, vốn gốc $1,000.
Exit: TP 4.0% / SL 1.5% → **R:R kế hoạch 2.67:1** / max hold 24 bars (~4.0d). Fee RT 0.04%.

## Bảng kịch bản (sort win rate ↓)

| # | Scenario | n | **Win%** | R:R kế hoạch | R:R thực | Exp R | Profit $1k | CAGR | MaxDD | PF |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | `I_usdtd_risk_off_short` | 176 | **47.7** | 2.67 | 2.57 | +0.69 | **$+4,735** | +46.7% | -10.2% | 2.35 |
| 2 | `D_flush_short` | 65 | **41.5** | 2.67 | 2.53 | +0.46 | **$+531** | +9.8% | -11.7% | 1.80 |
| 3 | `K_oi_usdtd_confluence` | 195 | **40.5** | 2.67 | 2.43 | +0.40 | **$+1,967** | +26.9% | -15.6% | 1.66 |
| 4 | `J_usdtd_risk_on_long` | 142 | **40.1** | 2.67 | 2.38 | +0.36 | **$+1,061** | +17.2% | -11.4% | 1.59 |
| 5 | `B_crowdfade_long` | 122 | **39.3** | 2.67 | 2.42 | +0.35 | **$+812** | +13.9% | -13.0% | 1.57 |
| 6 | `F_combined_ema` | 218 | **37.6** | 2.67 | 2.41 | +0.28 | **$+1,316** | +20.2% | -11.8% | 1.45 |
| 7 | `C_flush_long` | 74 | **32.4** | 2.67 | 2.30 | +0.07 | **$+59** | +1.3% | -12.6% | 1.10 |
| 8 | `G_regime_crowdfade` | 76 | **31.6** | 2.67 | 2.47 | +0.09 | **$+86** | +1.8% | -13.0% | 1.14 |
| 9 | `A_crowdfade_short` | 94 | **29.8** | 2.67 | 2.46 | +0.03 | **$+16** | +0.3% | -18.1% | 1.04 |
| 10 | `E_oi_div_short` | 203 | **26.1** | 2.67 | 2.53 | -0.08 | **$-256** | -6.3% | -43.7% | 0.89 |
| 11 | `H_bear_bounce_fade` * | 6 | **0.0** | 2.67 | 0.00 | -0.91 | **$-79** | -1.8% | -6.5% | 0.00 |

\* n thấp hơn ngưỡng rank. R:R thực = avg win / |avg loss| (gồm time/flip, nên khác kế hoạch). Profit compound trên $1,000, 1 position, không lev. BE WR ≈ 1/(1+R:R thực).

## `K_oi_usdtd_confluence` theo năm

| Year | n | Win% | R:R thực | Exp R | Profit $1k |
|---|---:|---:|---:|---:|---:|
| 2022 | 46 | **41.3** | 2.57 | +0.48 | $+372 |
| 2023 | 34 | **55.9** | 2.13 | +0.77 | $+458 |
| 2024 | 33 | **33.3** | 2.45 | +0.15 | $+68 |
| 2025 | 42 | **33.3** | 2.51 | +0.17 | $+99 |
| 2026 | 40 | **40.0** | 2.56 | +0.42 | $+266 |

## Playbook hiện tại

- Time / close: **2026-08-22 16:00** / `77310.0`
- OI Δ3d: -17.4% | z30: -2.71 | fund z: 1.52
- **USDT.D:** `6.939`% (Δ3d -0.999, z -3.46) | risk-off=False risk-on=True
- EMA regime (4h): **bull**

**Khuyến nghị:** `NONE` (conf=none) — No OI/USDT.D confluence; flat

### Liquidation map
- Vote: **none** (balanced_liq_map)
- Long cluster: `76979.8` | Short: `79687.63`

## Logic `K_oi_usdtd_confluence`

1. **SHORT:** EMA bear + OI↑3d >2% + **USDT.D** Δ3d>+0.2 (hoặc z>1) + fund z>0.3
2. **LONG:** EMA bull + OI↑3d >1.5% + **USDT.D** Δ3d<−0.2 (hoặc z<−1) + fund z<−0.5
3. USDT.D ↑ = tiền trú ẩn stable → áp lực BTC; USDT.D ↓ = risk-on.
4. USDT.D daily được ffill lên nến H1/H4 (bước ngày, không nội suy trong ngày).

Best by win rate: `I_usdtd_risk_off_short` — WR **47.7%** · R:R thực **2.57:1** (kế hoạch 2.67) · profit **$+4,735** / $1k (+473.5%, CAGR +46.7%) · n=176 → `oi_scenario_trades_I_usdtd_risk_off_short_btcusdt_4h.csv`

Panel: `oi_panel_btcusdt_4h.csv` · klines: `klines_btcusdt_4h.csv`

*Không phải tư vấn đầu tư.*