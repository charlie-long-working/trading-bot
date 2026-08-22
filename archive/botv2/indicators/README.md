# botv2 Indicators

## Export format (Entry, SL, TP)

Chạy `python -m botv2.run_indicators` để xuất CSV/JSON với mỗi signal:

| Cột | Mô tả |
|-----|-------|
| open_time | Thời điểm entry (UTC) |
| symbol | BTC/USDT, ETH/USDT |
| timeframe | 1h, 1d |
| side | long, short |
| entry | Giá entry |
| stop_loss | Giá SL |
| take_profit | Giá TP |
| exit_price | Giá thoát |
| exit_reason | stop, target, signal, end |
| pnl_pct | Lợi nhuận % |

## Pine Script

Dùng indicator tương đương từ parent repo: `../tradingview/Regime_Fusion_Signals.pine`

- Logic: Regime (MA 20/50) + Order Blocks + FVG + Supply/Demand + Volume
- Vẽ label LONG/SHORT với đường SL và TP
- Khuyến nghị khung 1h
