# OI + USDT.D Scenarios — ETHUSDT **4h**

Window: **2022-01-01 → 2026-08-22 16:00** (10169 nến 4h).
Nguồn: Bybit OI · Binance funding/giá · **USDT.D** (DefiLlama USDT mcap / CMC total, proxy hiệu chỉnh trước ~2025-04).
Lookback OI/USDT.D/funding theo **lịch** (3 ngày / 30 ngày); EMA 20/50 trên nến khung.
Xếp hạng theo **win rate** (min 20 trades). Profit = compound 100% notional/trade, vốn gốc $1,000.
Exit: TP 4.0% / SL 1.5% → **R:R kế hoạch 2.67:1** / max hold 24 bars (~4.0d). Fee RT 0.04%.

## Bảng kịch bản (sort win rate ↓)

| # | Scenario | n | **Win%** | R:R kế hoạch | R:R thực | Exp R | Profit $1k | CAGR | MaxDD | PF |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | `I_usdtd_risk_off_short` | 199 | **42.2** | 2.67 | 2.50 | +0.48 | **$+2,896** | +34.8% | -12.0% | 1.83 |
| 2 | `J_usdtd_risk_on_long` | 117 | **37.6** | 2.67 | 2.57 | +0.35 | **$+779** | +13.5% | -17.0% | 1.55 |
| 3 | `K_oi_usdtd_confluence` | 176 | **37.5** | 2.67 | 2.46 | +0.30 | **$+1,091** | +17.6% | -16.9% | 1.48 |
| 4 | `A_crowdfade_short` | 113 | **33.6** | 2.67 | 2.40 | +0.14 | **$+233** | +4.7% | -27.6% | 1.22 |
| 5 | `D_flush_short` | 84 | **27.4** | 2.67 | 2.43 | -0.06 | **$-98** | -2.2% | -16.5% | 0.92 |
| 6 | `H_bear_bounce_fade` | 22 | **27.3** | 2.67 | 2.72 | +0.01 | **$-2** | -0.1% | -7.4% | 1.02 |
| 7 | `B_crowdfade_long` | 119 | **26.9** | 2.67 | 2.51 | -0.06 | **$-130** | -3.0% | -26.1% | 0.92 |
| 8 | `F_combined_ema` | 246 | **26.4** | 2.67 | 2.47 | -0.08 | **$-316** | -8.0% | -43.4% | 0.89 |
| 9 | `G_regime_crowdfade` | 47 | **25.5** | 2.67 | 2.46 | -0.12 | **$-92** | -2.1% | -14.3% | 0.84 |
| 10 | `E_oi_div_short` | 249 | **25.3** | 2.67 | 2.57 | -0.10 | **$-350** | -9.0% | -36.9% | 0.87 |
| 11 | `C_flush_long` | 93 | **23.7** | 2.67 | 2.57 | -0.16 | **$-219** | -5.3% | -31.6% | 0.80 |

\* n thấp hơn ngưỡng rank. R:R thực = avg win / |avg loss| (gồm time/flip, nên khác kế hoạch). Profit compound trên $1,000, 1 position, không lev. BE WR ≈ 1/(1+R:R thực).

## `K_oi_usdtd_confluence` theo năm

| Year | n | Win% | R:R thực | Exp R | Profit $1k |
|---|---:|---:|---:|---:|---:|
| 2022 | 54 | **35.2** | 2.54 | +0.25 | $+202 |
| 2023 | 24 | **62.5** | 2.02 | +0.91 | $+372 |
| 2024 | 32 | **37.5** | 2.62 | +0.37 | $+178 |
| 2025 | 39 | **33.3** | 2.57 | +0.19 | $+105 |
| 2026 | 27 | **25.9** | 2.67 | -0.05 | $-28 |

## Playbook hiện tại

- Time / close: **2026-08-22 16:00** / `2427.37`
- OI Δ3d: -0.27% | z30: 0.62 | fund z: 1.71
- **USDT.D:** `6.939`% (Δ3d -0.999, z -3.46) | risk-off=False risk-on=True
- EMA regime (4h): **bull**

**Khuyến nghị:** `NONE` (conf=none) — No OI/USDT.D confluence; flat

### Liquidation map
- Vote: **none** (balanced_liq_map)
- Long cluster: `2403.77` | Short: `2464.47`

## Logic `K_oi_usdtd_confluence`

1. **SHORT:** EMA bear + OI↑3d >2% + **USDT.D** Δ3d>+0.2 (hoặc z>1) + fund z>0.3
2. **LONG:** EMA bull + OI↑3d >1.5% + **USDT.D** Δ3d<−0.2 (hoặc z<−1) + fund z<−0.5
3. USDT.D ↑ = tiền trú ẩn stable → áp lực BTC; USDT.D ↓ = risk-on.
4. USDT.D daily được ffill lên nến H1/H4 (bước ngày, không nội suy trong ngày).

Best by win rate: `I_usdtd_risk_off_short` — WR **42.2%** · R:R thực **2.50:1** (kế hoạch 2.67) · profit **$+2,896** / $1k (+289.6%, CAGR +34.8%) · n=199 → `oi_scenario_trades_I_usdtd_risk_off_short_ethusdt_4h.csv`

Panel: `oi_panel_ethusdt_4h.csv` · klines: `klines_ethusdt_4h.csv`

*Không phải tư vấn đầu tư.*