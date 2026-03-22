# botv2 Backtest Summary: Strategy vs Buy-and-Hold

## Data & Setup

- **Data source**: CCXT (Binance spot, Binance USD-M futures) hoặc fallback từ `data/` (POC)
- **Period**: 2017 – nay
- **Symbols**: BTC/USDT, ETH/USDT
- **Timeframes**: 1h, 1d
- **Strategy**: Regime (MA 20/50 + volatility) + Order Blocks + Fair Value Gaps + Supply/Demand zones + Volume

## Kết quả tổng hợp

| Market | Symbol | TF | Trades | Strategy % | Hold % | Vs Hold | Max DD % | Win % | PF | Sharpe |
|--------|--------|-----|--------|------------|--------|---------|----------|------|-----|--------|
| spot | BTC/USDT | 1h | 463 | +898.3 | +1454.3 | -556.0 | 46.3 | 19.7 | 13.78 | 0.71 |
| spot | BTC/USDT | 1d | 75 | +1104.1 | +1462.9 | -358.8 | 33.2 | 38.7 | 27.41 | 1.80 |
| spot | ETH/USDT | 1h | 703 | +460.9 | +551.3 | -90.4 | 68.7 | 21.8 | 7.51 | 0.56 |
| spot | ETH/USDT | 1d | 136 | +653.9 | +550.5 | **+103.4** | 38.2 | 48.5 | 12.12 | 1.31 |
| future | BTC/USDT | 1h | 40 | +1147.5 | +833.4 | **+314.1** | 4.0 | 32.5 | 99.08 | 2.54 |
| future | BTC/USDT | 1d | 43 | +558.4 | +830.0 | -271.6 | 15.2 | 39.5 | 24.27 | 2.40 |
| future | ETH/USDT | 1h | 91 | +1509.9 | +1424.2 | **+85.7** | 11.0 | 22.0 | 76.77 | 1.67 |
| future | ETH/USDT | 1d | 41 | +708.2 | +1403.2 | -695.0 | 33.6 | 48.8 | 21.54 | 2.43 |

## Nhận xét định tính

### Cấu hình vượt Hold (Vs Hold > 0)

1. **spot ETH/USDT 1d**: +103.4% vs hold, Win 48.5%, Max DD 38.2% – phù hợp spot dài hạn.
2. **future BTC/USDT 1h**: +314.1% vs hold, Max DD chỉ 4%, Sharpe 2.54 – rủi ro thấp, lợi nhuận cao.
3. **future ETH/USDT 1h**: +85.7% vs hold, Max DD 11% – cân bằng risk/return.

### Cấu hình thua Hold

- **spot BTC 1h/1d**: Hold mạnh hơn do trend dài; strategy vào/ra nhiều, bỏ lỡ phần tăng mạnh.
- **future ETH 1d**: Hold +1403%, strategy +708% – khung 1d ít tín hiệu, hold phù hợp hơn.

### Khung thời gian

- **1h**: Nhiều tín hiệu hơn, phù hợp futures (có short) và scalping.
- **1d**: Ít tín hiệu, phù hợp spot hold hoặc swing dài.

### Market type

- **Futures**: Có short, tận dụng bear; Max DD thường thấp hơn khi có hedge.
- **Spot**: Chỉ long; trong bull dài hold thường tốt hơn.

## Kết luận

- **Trading portfolio** nên ưu tiên: **future BTC/USDT 1h** (vs hold +314%, Max DD 4%) hoặc **future ETH/USDT 1h** (+85.7%, DD 11%).
- **Spot** nếu trade: **ETH/USDT 1d** (+103% vs hold); BTC spot nên **hold** thay vì trade.
- **Hold portfolio** (DCA) phù hợp cho phần vốn dài hạn; xem `dca_results.md` và `hold_portfolio.md`.
