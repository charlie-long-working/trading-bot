# botv2 – CCXT Strategy + DCA

Project con trong Trading-bot, dùng [CCXT](https://github.com/ccxt/ccxt) để lấy dữ liệu và thực hiện backtest + DCA.

## Cấu trúc

```
botv2/
├── config.py          # Cấu hình symbols, timeframes, cache
├── data/              # CCXT fetch + cache OHLCV
├── backtest/          # Engine backtest (dùng strategy từ parent)
├── indicators/        # Xuất entry/SL/TP (CSV, JSON)
├── dca/               # DCA simulate + optimize
├── reports/           # backtest_summary, dca_results, hold/trading
├── run_data.py        # Fetch klines 2017–nay
├── run_backtest.py    # Backtest spot/future 1h/1d
├── run_indicators.py  # Export signals
├── run_dca.py         # Tối ưu DCA
└── run_all.py         # Chạy full pipeline
```

## Cài đặt

```bash
pip install ccxt pandas numpy
```

## Chạy

Từ thư mục gốc `Trading-bot`:

```bash
# Lấy dữ liệu (cần network)
python -m botv2.run_data

# Backtest (dùng data/ nếu chưa có cache)
python -m botv2.run_backtest

# Xuất indicator
python -m botv2.run_indicators

# Tối ưu DCA
python -m botv2.run_dca

# Hoặc chạy tất cả (--skip-data để bỏ qua fetch)
python -m botv2.run_all --skip-data
```

## Hai danh mục

- **Hold**: DCA $10/ngày hoặc $100/tuần, tỷ lệ BTC/ETH tối ưu
- **Trading**: Regime + OB/FVG/Supply-Demand, có SL/TP

Xem `reports/SUMMARY.md` để so sánh.
