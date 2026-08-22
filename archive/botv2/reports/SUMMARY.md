# botv2 – Tổng hợp Hold vs Trading

## Hai danh mục

| Danh mục | Chiến lược | Phù hợp |
|----------|------------|---------|
| **Hold** | DCA định kỳ ($10/ngày hoặc $100/tuần) | Dài hạn, ít thời gian |
| **Trading** | Regime + OB/FVG/Supply-Demand, có SL/TP | Active, có thời gian theo dõi |

## So sánh ngắn

- **Hold (DCA)**: Đơn giản, không cần timing; lợi nhuận phụ thuộc thời điểm DCA (ngày/giờ) và tỷ lệ BTC/ETH. Chạy `run_dca` để tối ưu.
- **Trading**: Có thể vượt hold (vd future BTC 1h +314%) nhưng cần theo dõi, chấp nhận drawdown. Cấu hình tốt: future 1h.

## Hướng dẫn chạy

```bash
# Từ thư mục gốc Trading-bot
source .venv/bin/activate  # nếu dùng venv

# 1. Lấy dữ liệu (2017–nay) qua CCXT
python -m botv2.run_data

# 2. Backtest (dùng data/ nếu chưa có cache)
python -m botv2.run_backtest

# 3. Xuất indicator (entry, SL, TP)
python -m botv2.run_indicators

# 4. Tối ưu DCA
python -m botv2.run_dca
```

## Reports

- `backtest_summary.md` – Bảng so sánh strategy vs hold
- `dca_results.md` – Giờ/ngày và tỷ lệ BTC/ETH tối ưu
- `hold_portfolio.md` – Mô tả danh mục Hold
- `trading_portfolio.md` – Mô tả danh mục Trading
- `indicators/` – CSV/JSON với entry, SL, TP
