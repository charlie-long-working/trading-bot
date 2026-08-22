# OI + USDT.D Scenarios — ETHUSDT **1h**

Window: **2022-01-01 → 2026-08-22 18:00** (40675 nến 1h).
Nguồn: Bybit OI · Binance funding/giá · **USDT.D** (DefiLlama USDT mcap / CMC total, proxy hiệu chỉnh trước ~2025-04).
Lookback OI/USDT.D/funding theo **lịch** (3 ngày / 30 ngày); EMA 20/50 trên nến khung.
Xếp hạng theo **win rate** (min 40 trades). Profit = compound 100% notional/trade, vốn gốc $1,000.
Exit: TP 1.5% / SL 0.6% → **R:R kế hoạch 2.50:1** / max hold 48 bars (~2.0d). Fee RT 0.04%.

## Bảng kịch bản (sort win rate ↓)

| # | Scenario | n | **Win%** | R:R kế hoạch | R:R thực | Exp R | Profit $1k | CAGR | MaxDD | PF |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | `I_usdtd_risk_off_short` | 651 | **40.2** | 2.50 | 2.33 | +0.36 | **$+2,953** | +35.2% | -11.6% | 1.57 |
| 2 | `J_usdtd_risk_on_long` | 468 | **35.7** | 2.50 | 2.29 | +0.18 | **$+638** | +11.4% | -22.7% | 1.27 |
| 3 | `K_oi_usdtd_confluence` | 526 | **35.2** | 2.50 | 2.32 | +0.18 | **$+702** | +12.4% | -15.4% | 1.26 |
| 4 | `D_flush_short` | 242 | **31.8** | 2.50 | 2.30 | +0.05 | **$+70** | +1.5% | -14.3% | 1.07 |
| 5 | `B_crowdfade_long` | 347 | **30.3** | 2.50 | 2.28 | -0.01 | **$-31** | -0.7% | -14.0% | 0.99 |
| 6 | `G_regime_crowdfade` | 116 | **30.2** | 2.50 | 2.31 | -0.00 | **$-6** | -0.1% | -13.3% | 1.00 |
| 7 | `F_combined_ema` | 634 | **30.1** | 2.50 | 2.29 | -0.01 | **$-66** | -1.5% | -26.5% | 0.99 |
| 8 | `A_crowdfade_short` | 326 | **29.1** | 2.50 | 2.33 | -0.03 | **$-73** | -1.6% | -20.4% | 0.96 |
| 9 | `C_flush_long` | 210 | **28.6** | 2.50 | 2.28 | -0.07 | **$-89** | -2.0% | -18.1% | 0.91 |
| 10 | `E_oi_div_short` | 749 | **27.2** | 2.50 | 2.31 | -0.10 | **$-395** | -10.4% | -45.9% | 0.86 |
| 11 | `H_bear_bounce_fade` * | 25 | **20.0** | 2.50 | 2.33 | -0.35 | **$-53** | -1.2% | -7.2% | 0.58 |

\* n thấp hơn ngưỡng rank. R:R thực = avg win / |avg loss| (gồm time/flip, nên khác kế hoạch). Profit compound trên $1,000, 1 position, không lev. BE WR ≈ 1/(1+R:R thực).

## `K_oi_usdtd_confluence` theo năm

| Year | n | Win% | R:R thực | Exp R | Profit $1k |
|---|---:|---:|---:|---:|---:|
| 2022 | 176 | **35.2** | 2.32 | +0.18 | $+200 |
| 2023 | 65 | **38.5** | 2.30 | +0.29 | $+115 |
| 2024 | 127 | **39.4** | 2.30 | +0.32 | $+265 |
| 2025 | 96 | **26.0** | 2.32 | -0.14 | $-83 |
| 2026 | 62 | **37.1** | 2.36 | +0.26 | $+97 |

## Playbook hiện tại

- Time / close: **2026-08-22 18:00** / `2428.06`
- OI Δ3d: -2.51% | z30: 0.76 | fund z: 1.72
- **USDT.D:** `6.939`% (Δ3d -0.999, z -3.5) | risk-off=False risk-on=True
- EMA regime (1h): **bull**

**Khuyến nghị:** `NONE` (conf=none) — No OI/USDT.D confluence; flat

### Liquidation map
- Vote: **none** (balanced_liq_map)
- Long cluster: `2402.96` | Short: `2463.64`

## Logic `K_oi_usdtd_confluence`

1. **SHORT:** EMA bear + OI↑3d >2% + **USDT.D** Δ3d>+0.2 (hoặc z>1) + fund z>0.3
2. **LONG:** EMA bull + OI↑3d >1.5% + **USDT.D** Δ3d<−0.2 (hoặc z<−1) + fund z<−0.5
3. USDT.D ↑ = tiền trú ẩn stable → áp lực BTC; USDT.D ↓ = risk-on.
4. USDT.D daily được ffill lên nến H1/H4 (bước ngày, không nội suy trong ngày).

Best by win rate: `I_usdtd_risk_off_short` — WR **40.2%** · R:R thực **2.33:1** (kế hoạch 2.50) · profit **$+2,953** / $1k (+295.3%, CAGR +35.2%) · n=651 → `oi_scenario_trades_I_usdtd_risk_off_short_ethusdt_1h.csv`

Panel: `oi_panel_ethusdt_1h.csv` · klines: `klines_ethusdt_1h.csv`

*Không phải tư vấn đầu tư.*