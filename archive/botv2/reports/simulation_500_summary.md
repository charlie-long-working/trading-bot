# Simulation: $500 Futures Portfolio

Strategy: MACD+RSI | Futures 1d | Max Leverage 3.0x | Risk/trade 2.0%

## Risk Management

| Rule | Value | Purpose |
|------|-------|---------|
| Max risk/trade | 2.0% equity | Mất tối đa $10 per trade |
| Max leverage | 3.0x | Giá thanh lý cách entry ~33% |
| Max position | 30.0% equity margin | Không all-in |
| Circuit breaker | 20.0% DD | Tự dừng khi thua nhiều |
| Daily loss limit | 5.0% | Không revenge trade |
| Fee rebate | 40% | Hoàn phí giao dịch |
| Stop-loss | 1.5x ATR | Luôn có SL, tự động |

## Results

### BTC/USDT
- Starting: $250
- Final equity: **$249.18** (-0.3%)
- Trades: 101 (Win 39/101)
- Fees + Funding: $7.47
- Circuit breakers triggered: 0

### ETH/USDT
- Starting: $250
- Final equity: **$306.86** (+22.7%)
- Trades: 99 (Win 42/99)
- Fees + Funding: $6.14
- Circuit breakers triggered: 0

### Combined
- **$500 → $556.04** (+11.2%)

## Tại sao không cháy tài khoản?

1. **Luôn có SL**: Mỗi lệnh đặt SL = 1.5x ATR. Nếu SL hit → mất tối đa 2% equity.
2. **Leverage thấp**: 3x = giá thanh lý cách entry ~33%. Với SL thường ~3-5%, không bao giờ chạm liquidation.
3. **Position sizing tự thu nhỏ**: Khi equity giảm, size lệnh giảm theo → thua ít hơn → phục hồi dễ hơn.
4. **Circuit breaker**: Nếu DD > 20%, tự tắt bot. Không trade khi đang thua streak.
5. **Daily loss limit**: Mất >5% trong ngày → dừng. Ngăn revenge trading.
6. **Không all-in**: Max 30% equity làm margin cho 1 lệnh.

## Chi tiết

Xem full trade log tại: `reports/simulation_500.log`
