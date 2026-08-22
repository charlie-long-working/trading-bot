# BTC vs ETH — OI + USDT.D (2022-01-01 → 2026-08-22)

Cùng engine, cùng TP/SL theo khung, compound $1,000, 1 vị thế, fee RT 0.04%. Rank theo **win rate**.

## Best by WR

| TF | BTC | ETH |
|---|---|---|
| **1D** | `G` 44.8% · +$429 | `G` 42.3% · +$357 |
| **4H** | `I` 47.7% · +$4,735 | `I` 42.2% · +$2,896 |
| **1H** | `I` 41.3% · +$3,268 | `I` 40.2% · +$2,953 |

## G / K / I

| TF | Strat | BTC WR | BTC $1k | ETH WR | ETH $1k | Δ (BTC−ETH) |
|---|---|---:|---:|---:|---:|---:|
| 1D | G | 44.8 | +429 | 42.3 | +357 | +72 |
| 1D | K | 40.0 | +631 | 38.6 | +467 | +164 |
| 1D | I | 36.2 | +486 | 29.0 | +28 | +458 |
| 4H | G | 31.6 | +86 | 25.5 | −92 | +178 |
| 4H | K | 40.5 | +1,967 | 37.5 | +1,091 | +876 |
| 4H | I | 47.7 | +4,735 | 42.2 | +2,896 | +1,839 |
| 1H | G | 32.4 | +96 | 30.2 | −6 | +102 |
| 1H | K | 38.6 | +1,807 | 35.2 | +702 | +1,105 |
| 1H | I | 41.3 | +3,268 | 40.2 | +2,953 | +315 |

## Takeaways

1. **Thứ tự strategy giống BTC:** 1D → G/K; 4H/1H → I.
2. **BTC edge rõ trên 4H I và 1H K** (Δ profit +$1.8k / +$1.1k).
3. **ETH G yếu trên intraday** (4H −$92, 1H −$6) — không dùng G làm live play trên H1/H4 ETH.
4. **ETH I 1D gần hòa** (WR 29% ≈ BE, +$28) — filter USDT.D risk-off ít edge hơn trên ETH daily.

## Data

- ETH panel: `oi_panel_ethusdt_{daily,4h,1h}.csv`, `klines_ethusdt_*.csv`
- Reports: `oi_scenarios_ethusdt.md|_4h|_1h`

*Không phải tư vấn đầu tư.*
