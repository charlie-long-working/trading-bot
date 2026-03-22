# Strategy Comparison: MACD+RSI vs Regime+Fusion vs Buy & Hold

## Tham số

| Strategy | Mô tả |
|----------|-------|
| **MACD+RSI** | MACD(12,26,9) + RSI(14), OB=70 / OS=30. SL = 1.5×ATR(14), TP = 2.5×ATR(14) |
| **Regime+Fusion** | Regime (MA20/50 + volatility) + Order Blocks + FVG + Supply/Demand |
| **Buy & Hold** | Mua tại bar đầu, giữ đến bar cuối |

## Kết quả tổng hợp

| Config | Hold | Regime+Fusion | MACD+RSI | #Tr (R) | WR (R) | PF (R) | Sharpe (R) | DD (R) | #Tr (M) | WR (M) | PF (M) | Sharpe (M) | DD (M) |
|--------|------|---------------|----------|---------|--------|--------|------------|--------|---------|--------|--------|------------|--------|
| spot BTC/USDT 1h | +1454.3% | +898.3% | -56.7% | 463 | 19.7% | 13.78 | 0.71 | 46.3% | 2104 | 38.4% | 0.99 | -0.07 | 87.0% |
| spot BTC/USDT 1d | +1462.9% | +1104.1% | +154.1% | 75 | 38.7% | 27.41 | 1.80 | 33.2% | 83 | 44.6% | 1.42 | 2.39 | 57.1% |
| spot ETH/USDT 1h | +551.3% | +460.9% | +18.1% | 703 | 21.8% | 7.51 | 0.56 | 68.7% | 2109 | 38.3% | 1.05 | 0.28 | 73.3% |
| spot ETH/USDT 1d | +550.5% | +653.9% | +130.4% | 136 | 48.5% | 12.12 | 1.31 | 38.2% | 89 | 44.9% | 1.35 | 2.12 | 58.6% |
| future BTC/USDT 1h | +833.4% | +1147.5% | -60.2% | 40 | 32.5% | 99.08 | 2.54 | 4.0% | 2258 | 37.4% | 0.98 | -0.15 | 73.7% |
| future BTC/USDT 1d | +830.0% | +558.4% | -33.7% | 43 | 39.5% | 24.27 | 2.40 | 15.2% | 101 | 38.6% | 1.02 | 0.11 | 59.6% |
| future ETH/USDT 1h | +1424.2% | +1509.9% | -57.7% | 91 | 22.0% | 76.77 | 1.67 | 11.0% | 2338 | 37.6% | 1.00 | 0.01 | 86.4% |
| future ETH/USDT 1d | +1403.2% | +708.2% | +79.4% | 41 | 48.8% | 21.54 | 2.43 | 33.6% | 99 | 42.4% | 1.27 | 1.72 | 67.8% |

## Winner (theo tổng lợi nhuận)

- **spot BTC/USDT 1h**: Buy & Hold (+1454.3%)
- **spot BTC/USDT 1d**: Buy & Hold (+1462.9%)
- **spot ETH/USDT 1h**: Buy & Hold (+551.3%)
- **spot ETH/USDT 1d**: Regime+Fusion (+653.9%)
- **future BTC/USDT 1h**: Regime+Fusion (+1147.5%)
- **future BTC/USDT 1d**: Buy & Hold (+830.0%)
- **future ETH/USDT 1h**: Regime+Fusion (+1509.9%)
- **future ETH/USDT 1d**: Buy & Hold (+1403.2%)

## Winner (theo Sharpe – risk-adjusted)

- **spot BTC/USDT 1h**: Regime+Fusion (Sharpe 0.71)
- **spot BTC/USDT 1d**: MACD+RSI (Sharpe 2.39)
- **spot ETH/USDT 1h**: Regime+Fusion (Sharpe 0.56)
- **spot ETH/USDT 1d**: MACD+RSI (Sharpe 2.12)
- **future BTC/USDT 1h**: Regime+Fusion (Sharpe 2.54)
- **future BTC/USDT 1d**: Regime+Fusion (Sharpe 2.40)
- **future ETH/USDT 1h**: Regime+Fusion (Sharpe 1.67)
- **future ETH/USDT 1d**: Regime+Fusion (Sharpe 2.43)

## Nhận xét

### MACD+RSI
- Đơn giản, dễ tái tạo, phù hợp làm baseline.
- Momentum-following: hoạt động tốt khi thị trường trending rõ ràng.
- Sinh nhiều false signal trong giai đoạn sideways / choppy.
- ATR-based SL/TP tự động điều chỉnh theo volatility.

### Regime+Fusion
- Phức tạp hơn, thích nghi theo market regime (bull/bear/ranging).
- Profit Factor cao (ít loss lớn), nhưng Win Rate thấp hơn trên 1h.
- Phù hợp futures (có short) hơn spot.

### Kết luận
- Cả hai strategy đều cần kết hợp với risk management chặt chẽ.
- **Hold portfolio (DCA)** vẫn là lựa chọn an toàn cho phần vốn dài hạn.
- **Trading portfolio**: chọn strategy phù hợp dựa trên Sharpe và Max DD, không chỉ total return.

## Files

- Regime+Fusion indicators: `reports/indicators/`
- MACD+RSI indicators: `reports/indicators_macd_rsi/`
