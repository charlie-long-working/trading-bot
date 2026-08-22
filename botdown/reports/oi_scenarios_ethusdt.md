# OI + USDT.D Scenarios — ETHUSDT **1d**

Window: **2022-01-01 → 2026-08-22** (1695 nến 1d).
Nguồn: Bybit OI · Binance funding/giá · **USDT.D** (DefiLlama USDT mcap / CMC total, proxy hiệu chỉnh trước ~2025-04).
Lookback OI/USDT.D/funding theo **lịch** (3 ngày / 30 ngày); EMA 20/50 trên nến khung.
Xếp hạng theo **win rate** (min 8 trades). Profit = compound 100% notional/trade, vốn gốc $1,000.
Exit: TP 8.0% / SL 3.0% → **R:R kế hoạch 2.67:1** / max hold 10d. Fee RT 0.04%.

## Bảng kịch bản (sort win rate ↓)

| # | Scenario | n | **Win%** | R:R kế hoạch | R:R thực | Exp R | Profit $1k | CAGR | MaxDD | PF |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | `G_regime_crowdfade` | 26 | **42.3** | 2.67 | 2.41 | +0.44 | **$+357** | +6.9% | -11.0% | 1.77 |
| 2 | `K_oi_usdtd_confluence` | 44 | **38.6** | 2.67 | 2.47 | +0.34 | **$+467** | +8.8% | -11.3% | 1.55 |
| 3 | `H_bear_bounce_fade` | 27 | **37.0** | 2.67 | 2.46 | +0.28 | **$+209** | +4.2% | -16.0% | 1.45 |
| 4 | `D_flush_short` | 46 | **32.6** | 2.67 | 2.68 | +0.20 | **$+236** | +4.8% | -17.0% | 1.30 |
| 5 | `F_combined_ema` | 120 | **30.0** | 2.67 | 2.60 | +0.08 | **$+144** | +3.0% | -35.1% | 1.11 |
| 6 | `E_oi_div_short` | 54 | **29.6** | 2.67 | 2.78 | +0.12 | **$+129** | +2.7% | -35.6% | 1.17 |
| 7 | `I_usdtd_risk_off_short` | 62 | **29.0** | 2.67 | 2.64 | +0.06 | **$+28** | +0.6% | -26.4% | 1.08 |
| 8 | `A_crowdfade_short` | 42 | **28.6** | 2.67 | 2.82 | +0.09 | **$+60** | +1.3% | -32.1% | 1.13 |
| 9 | `B_crowdfade_long` | 39 | **28.2** | 2.67 | 2.44 | -0.03 | **$-75** | -1.7% | -29.9% | 0.96 |
| 10 | `J_usdtd_risk_on_long` | 26 | **26.9** | 2.67 | 2.62 | -0.03 | **$-49** | -1.1% | -18.4% | 0.96 |
| 11 | `C_flush_long` | 45 | **26.7** | 2.67 | 2.77 | +0.01 | **$-41** | -0.9% | -27.8% | 1.01 |

\* n thấp hơn ngưỡng rank. R:R thực = avg win / |avg loss| (gồm time/flip, nên khác kế hoạch). Profit compound trên $1,000, 1 position, không lev. BE WR ≈ 1/(1+R:R thực).

## `K_oi_usdtd_confluence` theo năm

| Year | n | Win% | R:R thực | Exp R | Profit $1k |
|---|---:|---:|---:|---:|---:|
| 2022 | 14 | **35.7** | 2.30 | +0.18 | $+59 |
| 2023 | 7 | **42.9** | 1.90 | +0.24 | $+43 |
| 2024 | 11 | **45.5** | 2.23 | +0.47 | $+149 |
| 2025 | 7 | **28.6** | 2.93 | +0.12 | $+16 |
| 2026 | 5 | **60.0** | 2.55 | +1.15 | $+176 |

## Playbook hiện tại

- Time / close: **2026-08-22** / `2427.37`
- OI Δ3d: -7.1% | z30: -0.03 | fund z: 2.11
- **USDT.D:** `6.939`% (Δ3d -0.999, z -3.28) | risk-off=False risk-on=True
- EMA regime (1d): **bull**

**Khuyến nghị:** `NONE` (conf=none) — No OI/USDT.D confluence; flat

### Liquidation map
- Vote: **none** (balanced_liq_map)
- Long cluster: `2403.24` | Short: `2463.93`

## Logic `K_oi_usdtd_confluence`

1. **SHORT:** EMA bear + OI↑3d >2% + **USDT.D** Δ3d>+0.2 (hoặc z>1) + fund z>0.3
2. **LONG:** EMA bull + OI↑3d >1.5% + **USDT.D** Δ3d<−0.2 (hoặc z<−1) + fund z<−0.5
3. USDT.D ↑ = tiền trú ẩn stable → áp lực BTC; USDT.D ↓ = risk-on.
4. USDT.D daily được ffill lên nến H1/H4 (bước ngày, không nội suy trong ngày).

Best by win rate: `G_regime_crowdfade` — WR **42.3%** · R:R thực **2.41:1** (kế hoạch 2.67) · profit **$+357** / $1k (+35.7%, CAGR +6.9%) · n=26 → `oi_scenario_trades_G_regime_crowdfade_ethusdt.csv`

Panel: `oi_panel_ethusdt_daily.csv` · klines: `klines_ethusdt_daily.csv`

*Không phải tư vấn đầu tư.*