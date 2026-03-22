# Hướng dẫn tạo bot giao dịch tự động trên OKX

Bot dùng **chiến lược regime + fusion** (theo plan Binance Data Crawl + Macro/Regime): phân loại thị trường (bull/bear/sideways), kết hợp order block, FVG, supply/demand và volume để ra tín hiệu Long/Short, sau đó **tự động đặt lệnh trên OKX**.

---

## 1. Tổng quan luồng bot

```
OKX API (candles) → Klines 1h
       ↓
Regime classifier (MA, volatility, optional M2/on-chain)
       ↓
Fusion signal (OB / FVG / supply-demand + volume)
       ↓
Signal Long/Short + Entry, SL, TP
       ↓
OKX API (place order) → Lệnh thị trường + SL/TP
```

- **Dữ liệu nến:** lấy trực tiếp từ OKX (`/api/v5/market/candles` hoặc `history-candles`), không cần crawler Binance.
- **Tín hiệu:** module `signals/okx_signal.py` — regime + fusion (order blocks, FVG, zones, volume) + **timeline** (halving phase, seasonal tháng yếu) để điều chỉnh position size. Cùng logic với Telegram/backtest, thêm modifier theo plan macro/regime.
- **Khớp lệnh:** chỉ khi có tín hiệu; có chế độ **paper** (chỉ in, không gửi lệnh thật).

---

## 2. Chuẩn bị

### 2.1. Môi trường

- Python 3.10+ (đã có trong project).
- Cài thêm dependency (nếu chưa): `requests` (đã có trong `requirements.txt`).

### 2.2. API key OKX

1. Đăng nhập [OKX](https://www.okx.com) → **Account** → **API** ([My API](https://www.okx.com/account/my-api)).
2. Tạo API key mới:
   - **Permissions:** bật ít nhất **Trade** (đặt lệnh) và **Read** (số dư, lệnh).
   - **Passphrase:** OKX không “cấp” passphrase — khi tạo key, màn hình có ô **Passphrase**: bạn **tự đặt** một mật khẩu (vd. `myOkxBot2024`) và **nhớ lưu** vào biến môi trường `OKX_PASSPHRASE`. Nếu quên, phải tạo API key mới.
   - Lưu **Secret Key** (OKX chỉ hiển thị một lần).
   - Lưu **API Key** (public).
3. (Khuyến nghị) Giới hạn IP hoặc chỉ dùng sub-account để hạn chế rủi ro.

### 2.3. Cấu hình .env

Sao chép `.env.example` thành `.env` và điền:

```env
OKX_API_KEY=...        # OKX cấp khi tạo key
OKX_SECRET_KEY=...     # OKX cấp khi tạo key (chỉ hiện 1 lần)
OKX_PASSPHRASE=...     # Mật khẩu BẠN TỰ ĐẶT khi tạo key (ô "Passphrase" trên trang OKX)
```

- **Tài khoản Demo:** thêm `OKX_DEMO=1` trong `.env` và dùng API key tạo từ **tài khoản Demo OKX** (xem mục 3.0 bên dưới).

---

## 3. Chạy bot

### 3.0. Chạy với tài khoản Demo OKX

OKX có **tài khoản Demo** (số dư ảo, không mất tiền thật). Cách dùng:

1. **Lấy API key từ tài khoản Demo**
   - Đăng nhập [OKX](https://www.okx.com) → chuyển sang **Demo Trading** (trên app: vào Cài đặt / Profile → chọn Tài khoản Demo; trên web thường có nút chuyển góc trên).
   - Trong **Demo**, vào **Account** → **API** ([My API](https://www.okx.com/account/my-api)) → tạo API key (Trade + Read), đặt Passphrase, lưu API Key và Secret Key.

2. **Cấu hình .env**
   - Điền `OKX_API_KEY`, `OKX_SECRET_KEY`, `OKX_PASSPHRASE` (đúng key vừa tạo từ **Demo**).
   - Thêm dòng: **`OKX_DEMO=1`** (để bot in dòng nhắc đang chạy demo).

3. **Chạy bot**
   - Chỉ xem tín hiệu, không gửi lệnh:
     ```bash
     python run_okx_bot.py --symbols BTCUSDT,ETHUSDT --market swap --paper
     ```
   - Gửi lệnh thật **trên số dư Demo** (không tốn tiền thật):
     ```bash
     python run_okx_bot.py --symbols BTCUSDT --market swap --size-usdt 100
     ```
   - Khi chạy với `OKX_DEMO=1`, bot sẽ in: `(Chế độ DEMO: API key từ tài khoản Demo OKX — lệnh dùng số dư demo)`.

**Lưu ý:** API key tạo từ **tài khoản Demo** chỉ giao dịch trên số dư demo. Khi muốn chạy tiền thật, tạo key mới từ **tài khoản chính** và đổi trong `.env` (có thể bỏ hoặc đặt `OKX_DEMO=0`).

### 3.1. Chế độ paper (chỉ in, không đặt lệnh)

An toàn để kiểm tra tín hiệu và logic:

```bash
python run_okx_bot.py --symbols BTCUSDT,ETHUSDT --market swap --paper
```

- Lấy nến 1h từ OKX cho BTC-USDT-SWAP, ETH-USDT-SWAP.
- Chạy regime + fusion → in ra Long/Short kèm entry, SL, TP, **không gửi lệnh**.

### 3.2. Chạy thật (perpetual swap)

Sau khi đã kiểm tra kỹ với `--paper`:

```bash
python run_okx_bot.py --symbols BTCUSDT --market swap --size-usdt 100
```

- `--market swap`: perpetual (BTC-USDT-SWAP).
- `--size-usdt 100`: mỗi lệnh tương đương 100 USDT (sẽ quy đổi sang số contract theo giá hiện tại).

### 3.3. Spot (tuỳ chọn)

```bash
python run_okx_bot.py --symbols BTCUSDT --market spot --size-usdt 50 --paper
```

### 3.4. Tham số thường dùng

| Tham số        | Mặc định        | Ý nghĩa |
|----------------|-----------------|--------|
| `--symbols`    | BTCUSDT,ETHUSDT | Cặp giao dịch, cách nhau dấu phẩy |
| `--market`     | swap            | `spot` hoặc `swap` (perpetual) |
| `--interval`   | 1h              | Khung nến (khuyến nghị 1h) |
| `--size-usdt`  | 100             | Size mỗi lệnh (USDT) |
| `--paper`      | -               | Chỉ in lệnh, không gửi OKX |
| `--dry-run`    | -               | Giống `--paper` |

---

## 4. Cấu trúc code liên quan

| Thành phần | Mô tả |
|------------|--------|
| `exchange/okx_client.py` | Client REST OKX: lấy candles, đặt lệnh, max-avail-size. |
| `data_loaders/okx_klines.py` | Gọi OKX candles, trả về format (open_time, o, h, l, c, volume) giống `load_merged_klines`. |
| `signals/okx_signal.py` | `get_okx_signal`: tín hiệu OKX từ OHLCV + timeline (halving, seasonal) → entry/SL/TP + position_size_modifier. |
| `signals/current_signal.py` | `get_current_signal_with_tp_sl_from_arrays`: signal từ mảng OHLCV (dùng khi không cần timeline). |
| `run_okx_bot.py` | Script chính: đọc .env → lấy nến OKX → signal → đặt lệnh (hoặc paper). |
| `run_okx_signal_only.py` | Chỉ in tín hiệu OKX (candles public, không cần API key). |

---

## 5. Lưu ý an toàn

1. **Luôn thử `--paper`** trước khi bật lệnh thật.
2. **Size nhỏ** khi chạy thật (`--size-usdt` nhỏ) để kiểm tra end-to-end.
3. **API key:** không commit `.env`; chỉ cấp quyền Trade/Read, không cần Withdraw cho bot.
4. **Rate limit:** OKX giới hạn số lệnh/giây; bot hiện đặt tuần tự từng symbol, tránh spam.
5. **SL/TP:** Bot gửi kèm stop-loss và take-profit khi đặt lệnh; kiểm tra trên OKX sau khi đặt.

---

## 6. Mở rộng theo plan (timeline + macro)

Plan gốc gồm **timeline** (on-chain, M2, halving, seasonal) và **regime**. Hiện tại:

- **Regime:** đã dùng trong bot (MA, volatility; có thể bổ sung M2, SOPR/MVRV).
- **Chỉ xem tín hiệu (không đặt lệnh):** `python run_okx_signal_only.py --symbols BTCUSDT,ETHUSDT --market swap` — dùng candles public OKX, không cần API key.
- **On-chain (SOPR/MVRV):** Telegram signal đã dùng Glassnode; bot OKX có thể bật on-chain sau nếu bạn thêm logic lấy SOPR/MVRV và truyền vào `get_okx_signal(sopr=..., mvrv=...)`.
- **Halving / seasonal:** đã dùng trong `signals/okx_signal.py` — `position_size_modifier` giảm khi tháng yếu (6–8) hoặc halving phase neutral; bot nhân `size_usdt * position_size_modifier`. M2 có thể truyền vào `get_okx_signal(m2_yoy=...)` khi đã có nguồn dữ liệu.

Khi đã có dữ liệu M2 và halving (theo plan), chỉ cần mở rộng `RegimeInputs` và `get_rules_for_regime` rồi bot OKX sẽ tự dùng logic mới vì cùng pipeline signal.

---

## 7. Tài liệu OKX

- [OKX API v5](https://www.okx.com/docs-v5/en/)
- [REST Authentication](https://www.okx.com/docs-v5/en/#overview-rest-api) (OK-ACCESS-KEY, SIGN, TIMESTAMP, PASSPHRASE)
- [Place order](https://www.okx.com/docs-v5/en/#order-book-trading-trade-post-place-order)
- [Candles](https://www.okx.com/docs-v5/en/#market-data-get-candlesticks)

Nếu bạn muốn thêm chế độ lệnh limit, đặt từng bước SL/TP riêng, hoặc tích hợp Telegram khi có lệnh OKX, có thể mở rộng `run_okx_bot.py` và module `exchange` tương ứng.

---

## 8. Chạy bot tự động 24/7 (deploy lên VPS)

OKX **không** host code bot; bot chạy trên máy hoặc VPS của bạn và gọi API OKX. Để bot chạy tự động:

- Chạy lặp mỗi N phút: `python run_okx_bot.py ... --interval-minutes 60`
- Deploy lên VPS (Ubuntu) và dùng **systemd** để giữ process chạy 24/7, tự restart khi lỗi.

Chi tiết: **[docs/DEPLOY_OKX_BOT.md](DEPLOY_OKX_BOT.md)**. File systemd mẫu: `deploy/okx-bot.service.example`.
