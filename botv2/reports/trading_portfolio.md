# Danh mục Trading (Strategy)

## Mô tả

Danh mục **Trading** dùng chiến lược **Regime + OB/FVG/Supply-Demand** – vào lệnh khi có tín hiệu kỹ thuật, có SL và TP rõ ràng.

## Cấu hình đề xuất (từ backtest)

| Cấu hình | Vs Hold | Max DD | Ghi chú |
|----------|---------|--------|---------|
| future BTC/USDT 1h | +314% | 4% | Ưu tiên số 1 |
| future ETH/USDT 1h | +86% | 11% | Cân bằng |
| spot ETH/USDT 1d | +103% | 38% | Spot dài hạn |

## Entry, SL, TP

Mỗi tín hiệu có:
- **Entry**: Giá đóng cửa nến tại thời điểm signal
- **Stop Loss**: Từ zone (OB/FVG/zone) hoặc % theo regime
- **Take Profit**: % theo regime (Bear 3%, Sideways 2%, Bull trend-follow)

## Indicator export

Chạy `python -m botv2.run_indicators` để xuất CSV/JSON với entry, SL, TP cho từng cấu hình. File nằm tại `botv2/reports/indicators/`.

## Pine Script

Có thể dùng `tradingview/Regime_Fusion_Signals.pine` (parent repo) – logic tương đương, vẽ label + SL/TP trên chart.

## Cách sử dụng

1. Chạy backtest: `python -m botv2.run_backtest`
2. Xuất indicator: `python -m botv2.run_indicators`
3. Chọn cấu hình (ưu tiên future BTC 1h hoặc ETH 1h)
4. Theo dõi signal và đặt lệnh với SL/TP từ indicator

## Phù hợp

- Nhà đầu tư active, có thời gian theo dõi
- Chấp nhận rủi ro trading (stop loss)
- Có thể trade futures (long/short)
