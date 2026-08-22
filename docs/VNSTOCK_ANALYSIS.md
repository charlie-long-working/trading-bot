# Phân tích Vnstock và hướng tái sử dụng

> Tham khảo: [github.com/thinh-vu/vnstock](https://github.com/thinh-vu/vnstock)

## 1. Tổng quan Vnstock

**Vnstock** là bộ toolkit Python mã nguồn mở cho phân tích chứng khoán Việt Nam, hỗ trợ:

| Tính năng | Mô tả | API / Class |
|-----------|-------|-------------|
| Giá lịch sử | OHLC theo ngày/1h/15m... | `Quote.history()` |
| Intraday | Tick giao dịch từng lệnh | `Quote.intraday()` |
| Bảng giá | Bid/ask nhiều mã | `Trading.price_board()` |
| Thông tin công ty | Overview, sector | `Company.overview()` |
| Báo cáo tài chính | CĐKT, KQKD, LCTT, chỉ số | `Finance.balance_sheet()`, `ratio()` |
| Danh sách mã | All symbols, indices | `Listing.all_symbols()` |
| Chỉ số | VNIndex, HNXIndex, VN30F... | `Quote` (symbol=VNINDEX) |
| FX | Tỷ giá VCB | `vcb_exchange_rate()` |
| Vàng | Giá vàng SJC | `sjc_gold_price()` |
| Quỹ mở | Danh mục, hiệu suất | `Fund.listing()` |

### Nguồn dữ liệu (source)

- **KBS** – KB Securities (cổ phiếu, chỉ số, phái sinh)
- **VCI** – VCI Securities
- **MSN** – Microsoft (thị trường quốc tế: FX, chỉ số nước ngoài)

---

## 2. Cấu trúc mã nguồn

```
vnstock/
├── api/           # Adapter thống nhất (Quote, Company, Finance, Trading, Listing)
├── explorer/      # Implement theo từng nguồn
│   ├── kbs/       # KB Securities
│   ├── vci/       # VCI Securities
│   ├── msn/       # Microsoft (FX, global indices)
│   ├── fmarket/   # Quỹ mở
│   └── misc/      # VCB tỷ giá, SJC vàng
├── core/          # Utils, client HTTP, transform, auth
└── connector/     # Đăng ký provider
```

### Ví dụ sử dụng cơ bản

```python
# Cách 1: Giao diện chính (Vnstock)
from vnstock import Vnstock
stock = Vnstock().stock(symbol='VCI', source='KBS')
df = stock.quote.history(start='2020-01-01', end='2024-05-25')

# Cách 2: Import trực tiếp
from vnstock import Quote, Company, Finance, Trading, Listing

quote = Quote(symbol='VNINDEX', source='KBS')
df = quote.history(start='2024-01-01', end='2025-03-22', interval='d')

# Tỷ giá & vàng
from vnstock.explorer.misc import vcb_exchange_rate, sjc_gold_price
fx = vcb_exchange_rate(date='2024-03-21')
gold = sjc_gold_price(date='2024-03-21')
```

---

## 3. Khả năng tái sử dụng trong Trading-bot

### Hiện trạng

- **botv2**: Crypto (CCXT/Binance), DCA, backtest
- **vre**: Vietnam macro từ CSV local (lãi suất, BĐS) + FRED (demographics)
- **vnstock** đã được cài (3.5.0) nhưng chưa dùng

### Gợi ý tái sử dụng

| Mục đích | Vnstock API | Ứng dụng |
|----------|-------------|----------|
| Chỉ số thị trường | `Quote(symbol='VNINDEX', source='KBS').history()` | Tương quan VNIndex vs BĐS, lãi suất trong vre |
| Giá vàng SJC | `sjc_gold_price(date)` | So sánh vàng–BĐS, risk-off |
| Tỷ giá VCB | `vcb_exchange_rate(date)` | Series tỷ giá cho macro model |
| Báo cáo tài chính | `Finance.ratio(period='year')` | Phân tích sector, chỉ số P/E, ROE |
| Danh sách mã | `Listing(source='KBS').all_symbols()` | Batch lấy dữ liệu nhiều cổ phiếu |
| Bảng giá | `Trading().price_board(['VCB','ACB'])` | Realtime hoặc snapshot |

---

## 4. Lưu ý khi tích hợp

### Giấy phép (License)

- Vnstock dùng license tùy chỉnh: **cá nhân, phi thương mại**.
- Dùng thương mại cần liên hệ tác giả để xin phép.

### Xác thực (v3.4.0+)

- Đăng ký API key tại [vnstocks.com/login](https://vnstocks.com/login) để tăng giới hạn.
- Guest: 20 req/phút; Community: 60 req/phút (đăng ký miễn phí).

```python
from vnstock import register_user
register_user(api_key='YOUR_KEY')  # hoặc register_user() để nhập interactively
```

### Tuyên bố miễn trừ

- Chỉ phục vụ **nghiên cứu và sử dụng cá nhân**.
- Không khuyến nghị dùng cho giao dịch thực tế hoặc quyết định tài chính.

---

## 5. Tài liệu & tài nguyên

- Docs: [vnstocks.com/docs](https://vnstocks.com/docs)
- Agent guide (AI viết code vnstock): [vnstock-agent-guide](https://github.com/vnstock-hq/vnstock-agent-guide)
- Cursor rules: `.cursor/rules/instructions.md` (copy từ agent guide)
