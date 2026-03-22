# Lấy dữ liệu realtime cho Trading Bot

Hướng dẫn các nguồn dữ liệu realtime (giá, klines) phục vụ signal và dashboard.

---

## 1. Binance REST API (Khuyến nghị – miễn phí, chính thức)

**Ưu điểm:** Miễn phí, không cần API key, chính thức từ Binance, độ trễ thấp.

### Endpoints

| Market   | Base URL                 | Klines path      | Ticker price      |
| -------- | ------------------------ | ---------------- | ----------------- |
| Spot     | `https://api.binance.com`| `/api/v3/klines` | `/api/v3/ticker/price` |
| Futures  | `https://fapi.binance.com`| `/fapi/v1/klines`| `/fapi/v1/ticker/price` |

### Sử dụng trong project

```python
from data_loaders.realtime import fetch_binance_klines, fetch_binance_ticker_price

# Lấy 500 nến 1h mới nhất (spot BTCUSDT)
open_time, open_, high, low, close, volume = fetch_binance_klines(
    symbol="BTCUSDT",
    interval="1h",
    market_type="spot",
    limit=500,
)

# Lấy giá hiện tại
price = fetch_binance_ticker_price("BTCUSDT", market_type="spot")
```

Format trả về tương thích `load_merged_klines`: `(open_time, open, high, low, close, volume)`.

### Intervals hỗ trợ

`1m`, `3m`, `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `6h`, `8h`, `12h`, `1d`, `3d`, `1w`, `1M`

### Rate limit

- Klines: ~1200 requests/phút (weight-based).
- Khuyến nghị: throttle 1–2 req/s khi gọi nhiều symbol.

---

## 2. Binance WebSocket (Streaming thời gian thực)

**Ưu điểm:** Cập nhật liên tục, không cần poll REST.

### Streams

| Stream        | URL pattern (spot)                    | Mô tả              |
| ------------- | ------------------------------------- | ------------------ |
| Kline/Candlestick | `wss://stream.binance.com:9443/ws/btcusdt@kline_1h` | Nến theo interval |
| Mini ticker   | `wss://stream.binance.com:9443/ws/btcusdt@miniTicker` | Giá 24h mini      |
| Trade         | `wss://stream.binance.com:9443/ws/btcusdt@trade`     | Giao dịch         |

Futures: `wss://fstream.binance.com/ws/btcusdt@kline_1h`

### Thư viện Python

- **python-binance**: `pip install python-binance` – có sẵn WebSocket.
- **websockets**: `pip install websockets` – tự implement.

```python
# Ví dụ python-binance
from binance import BinanceSocketManager
from binance.client import Client

client = Client()
bm = BinanceSocketManager(client)
ts = bm.kline_socket("BTCUSDT", interval=Client.KLINE_INTERVAL_1HOUR)
async for msg in ts:
    # msg chứa k, o, h, l, c, v, ...
    print(msg)
```

---

## 3. TradingView

TradingView **không có API public chính thức** cho Python. Các lựa chọn:

### 3.1. tvkit (Python, WebSocket)

```bash
pip install tvkit
```

- Realtime OHLCV qua WebSocket.
- Hỗ trợ 69 thị trường, 4800+ crypto.
- Cần Python 3.11+.

```python
import asyncio
from tvkit import TvClient

async def main():
    async with TvClient() as client:
        async for bar in client.stream_klines("BINANCE:BTCUSDT", "60"):
            print(bar)

asyncio.run(main())
```

### 3.2. TradingView Data API (RapidAPI)

- **URL:** https://rapidapi.com/hypier/api/tradingview-data1
- **Phí:** Có gói miễn phí giới hạn, gói trả phí cho realtime.
- **Dữ liệu:** 160K+ symbols, 4800+ crypto, sub-150ms latency qua WebSocket.

### 3.3. tradingview-datafeed (GitHub)

```bash
pip install --upgrade git+https://github.com/StreamAlpha/tvdatafeed.git
```

- Tải historical (tối đa ~5000 nến).
- Có thể dùng username/password TradingView (giới hạn khi không login).
- Không phải realtime streaming thuần.

### 3.4. Charting Library Datafeed (JavaScript)

- Dành cho web app dùng TradingView Charting Library.
- Cần tự implement Datafeed API + backend WebSocket.
- Không dùng trực tiếp từ Python.

---

## 4. Các nguồn khác

### 4.1. OKX (đã có trong project)

```python
from data_loaders.okx_klines import fetch_okx_klines
from exchange.okx_client import OKXClient

client = OKXClient()  # Public candles không cần API key
out = fetch_okx_klines(client, "BTCUSDT", "spot", "1h", limit=300)
```

### 4.2. CoinGecko

- REST API miễn phí: `https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd`
- Chủ yếu giá spot, không có klines chi tiết.
- Rate limit: ~10–30 req/phút (free).

### 4.3. Yahoo Finance (yfinance)

```bash
pip install yfinance
```

- Chủ yếu chứng khoán, crypto hạn chế.
- Symbol: `BTC-USD`, `ETH-USD`.

---

## 5. So sánh nhanh

| Nguồn           | Realtime | Klines | Miễn phí | API key | Ghi chú                    |
| --------------- | -------- | ------ | -------- | ------- | -------------------------- |
| Binance REST    | ✅       | ✅     | ✅       | Không   | Khuyến nghị cho Binance    |
| Binance WebSocket | ✅     | ✅     | ✅       | Không   | Streaming liên tục         |
| OKX REST        | ✅       | ✅     | ✅       | Không*  | Đã tích hợp trong project  |
| tvkit (TradingView) | ✅   | ✅     | ✅       | Không   | Cần Python 3.11+           |
| TradingView RapidAPI | ✅  | ✅     | Trả phí  | Có      | Sub-150ms, nhiều symbol    |
| CoinGecko       | ✅       | ❌     | ✅       | Không   | Chỉ giá, không klines      |

\* OKX candles public không cần key; trade/account cần key.

---

## 6. Tích hợp vào signal realtime

Để chạy signal với dữ liệu realtime thay vì file:

```python
from data_loaders.realtime import fetch_binance_klines
from signals.current_signal import get_current_signal_with_tp_sl

# Thay vì load_merged_klines, dùng fetch_binance_klines
# Cần adapter vì get_current_signal_with_tp_sl nhận data_dir...
# Hoặc tạo hàm mới nhận trực tiếp arrays:

def get_realtime_signal(symbol="BTCUSDT", market_type="spot", interval="1h"):
    out = fetch_binance_klines(symbol, interval, market_type, limit=500)
    if out is None:
        return None
    open_time, open_, high, low, close, volume = out
    # ... gọi get_signal với arrays ...
```

Module `data_loaders.realtime` trả về cùng format `(open_time, open, high, low, close, volume)` nên có thể dùng trực tiếp với `get_signal` trong `signals.fusion`.
