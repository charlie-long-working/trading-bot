# Indicator & Strategy TradingView

---

## OI + USDT.D (playbook live I+K) — `OI_USDTD_Signals.pine` / `OI_USDTD_Strategy.pine`

Khớp logic `botdown/oi_live_signal.py` + Telegram alerts (K ưu tiên, I secondary).

| Thành phần | Nguồn trên TradingView |
|------------|------------------------|
| **Open Interest** | `BINANCE:BTCUSDT.P_OI` (auto `_OI` suffix) |
| **Funding z** | Proxy từ `BINANCE:BTCUSDT_PREMIUM` (≠ funding thật 100%) |
| **USDT.D** | `CRYPTOCAP:USDT.D` (daily, ffill lên H1/H4) |
| **TP/SL** | 1h: 1.5%/0.6% · 4h: 4%/1.5% |

**Cách dùng**

1. Chart **`BINANCE:BTCUSDT.P`** hoặc **`BINANCE:ETHUSDT.P`** (perpetual).
2. Khung **1h** hoặc **4h** (khớp backtest Python).
3. Pine Editor → dán `OI_USDTD_Signals.pine` → Add to chart.
4. Bảng góc phải: OI Δ3d, fund z, USDT.D, signal. Alert: **OI+USDT.D LONG/SHORT**.
5. Backtest trên TV: dán `OI_USDTD_Strategy.pine` → Strategy Tester.

**Lưu ý:** WR/profit trên TV **không trùng** backtest Python (OI Bybit vs Binance, USDT.D DefiLlama vs CRYPTOCAP, funding proxy). Nguồn “chuẩn” vẫn là `run_oi_scenarios` + Telegram GHA.

---

**Chỉ giao dịch theo xu hướng:** LONG khi uptrend (price > EMA) + RSI oversold (mua dip). SHORT khi downtrend + RSI overbought (bán đỉnh). Tránh mean reversion ngược trend → giảm thua trong thị trường trending như BTC.

| Thành phần | Mặc định |
|------------|----------|
| EMA trend | 50 |
| RSI oversold / overbought | 38 / 62 |
| TP / SL | 2.5% / 1.5% (R:R > 1) |

**Files:** `RSI_Trend_Dip_Signals.pine` | `RSI_Trend_Dip_Strategy.pine`

---

## RSI BB Mean Reversion — `RSI_BB_MeanReversion_Signals.pine` / `RSI_BB_MeanReversion_Strategy.pine`

Strategy mean reversion. **BẬT "Chỉ giao dịch theo trend"** trong Settings để tránh thua trong trending market. Mặc định đã bật.

| Thành phần | Mặc định |
|------------|----------|
| RSI oversold / overbought | 32 / 68 |
| TP / SL | 2% / 1.5% |
| Chỉ theo trend | Bật (LONG khi price > EMA50, SHORT khi price < EMA50) |

---

## Regime Fusion: Thế mạnh khi thua Buy & Hold

Regime Fusion thường **thua Buy & Hold** trong bull dài hạn. Thế mạnh: **giảm drawdown**, **short trong bear**, **không mua đỉnh**, **SL/TP rõ ràng**. Chi tiết: [docs/REGIME_FUSION_STRENGTHS.md](../docs/REGIME_FUSION_STRENGTHS.md).

---

## MA200 & Chênh lệch % (`MA200_Price_Deviation.pine`)

Indicator đơn giản: **đường MA200** trên chart và **% chênh lệch giá so với MA200** (bảng góc màn hình).

- **MA200:** Simple Moving Average 200 nến.
- **Chênh lệch %:** `(giá - MA200) / MA200 × 100` — dương = giá trên MA200, âm = giá dưới MA200.

**Cách dùng:** Pine Editor → dán nội dung `MA200_Price_Deviation.pine` → Add to chart. Trong Settings có thể đổi chu kỳ MA, màu/độ dày đường, bật/tắt bảng và vị trí bảng.

---

## Regime Fusion (điểm mua/bán) — `Regime_Fusion_Signals.pine`

Indicator Pine Script v5 dùng **cùng logic strategy** với bot OKX và backtest: **Regime + Order Blocks + FVG + Supply/Demand + Volume**. Hiển thị **LONG (mua)** và **SHORT (bán)** kèm **SL (stop loss)** và **TP (take profit)** trên chart.

## Indicator đánh cả Long và Short

- **Long (Mua):** khi regime Bull hoặc Sideways + giá ở vùng Bull OB / Bull FVG / Demand + volume ok → **tam giác xanh hướng lên (▲)** dưới nến.
- **Short (Bán):** khi regime Bear hoặc Sideways + giá ở vùng Bear OB / Bear FVG / Supply + volume ok → **tam giác đỏ hướng xuống (▼)** trên nến.
- **Bull** chỉ cho phép Long (không Short). **Bear** và **Sideways** cho phép cả hai.

## Lệnh nào Long, lệnh nào Short — SL/TP ở đâu

| Tín hiệu | Nhận biết trên chart | Stop loss (SL) | Chốt lời (TP) |
|----------|----------------------|----------------|----------------|
| **LONG** | Tam giác **xanh ▲** dưới nến + label "LONG" + đường **đỏ nét đứt** | Đường **đỏ nét đứt** (dưới giá) = SL. Ưu tiên đáy vùng (OB/FVG/demand), không thì ~2–3% dưới entry. | Đường **xanh nét đứt** (trên giá) = TP. Bull: không TP cố định (giữ trend). Bear/Sideways: ~2–3% trên entry. |
| **SHORT** | Tam giác **đỏ ▼** trên nến + label "SHORT" + đường **đỏ nét đứt** | Đường **đỏ nét đứt** (trên giá) = SL. Ưu tiên đỉnh vùng (OB/FVG/supply), không thì ~2% trên entry. | Đường **xanh nét đứt** (dưới giá) = TP. ~2–3% dưới entry. |

Trong **Settings → Hiển thị** có thể bật/tắt **"Vẽ đường SL & TP"** và chỉnh **"SL/TP kéo dài (bars)"** để đường SL/TP hiển thị bao nhiêu nến. Label gần tín hiệu ghi rõ **LONG** hoặc **SHORT** và giá **SL**, **TP**.

## Cách dùng

1. Mở [TradingView](https://www.tradingview.com) → chart (vd: BTCUSDT). **Khuyến nghị khung 1h.** Trên khung 1D tín hiệu dễ trễ — xem mục "Tại sao tín hiệu trông sai trên 1D?" bên dưới.
2. Vào **Pine Editor** (bấm "Pine Editor" ở dưới hoặc **Indicators** → **Create**).
3. Xóa code mặc định, **dán toàn bộ nội dung** file `Regime_Fusion_Signals.pine`.
4. Bấm **Add to chart**. Indicator sẽ vẽ:
   - **MA ngắn (20)** và **MA dài (50)** — dùng cho regime.
   - **Tam giác xanh ▲** = **LONG (Mua)**; **Tam giác đỏ ▼** = **SHORT (Bán)**.
   - **Đường đỏ nét đứt** = SL; **Đường xanh nét đứt** = TP. **Label** bên cạnh ghi LONG/SHORT và giá SL, TP.
   - Nền xanh nhạt = Bull, nền đỏ nhạt = Bear.

## Tham số (Settings — nhóm: Regime, Order Block, Fair Value Gap, Supply/Demand, Bộ lọc, Hiển thị)

| Nhóm | Tham số | Mặc định | Ý nghĩa |
|------|--------|----------|--------|
| Regime | MA ngắn / MA dài | 20 / 50 | Phân loại Bull/Bear/Sideways. |
| Regime | Chu kỳ volatility | 20 | Để phát hiện co volatility (sideways). |
| Order Block | Lookback / Số nến xác nhận / Min move % | 50 / 5 / 0.5 | Tìm OB và move tối thiểu. |
| Fair Value Gap | Lookback | 30 | Số nến nhìn lại để tìm FVG. |
| Supply/Demand | Lookback / Số nến base / Expansion % | 50 / 3 / 0.3 | Vùng cung/cầu. |
| Bộ lọc | Max tuổi vùng (bars) | 20 | Chỉ xét vùng hình thành trong N nến gần nhất. Khung 1D nên 15–25. |
| Bộ lọc | Tolerance % | 0.1 | Độ rộng khi coi giá "ở trong" vùng. |
| Bộ lọc | Bắt buộc volume >= SMA(20) | Tắt | Bật để lọc theo volume. |
| Hiển thị | Vẽ MA / Nền regime | Bật | Có thể tắt MA hoặc nền xanh/đỏ. |

## Tại sao tín hiệu trông sai trên 1D?

- **Lookback 50 = 50 ngày:** vùng (OB/FVG/supply-demand) từ 1–2 tháng trước vẫn được dùng → tín hiệu xuất hiện khi giá quay lại vùng cũ, trông rất trễ.
- **Regime MA 20/50 trên 1D:** xu hướng rất dài, đổi Bull/Bear chậm → bán sau đỉnh, mua sau đáy.
- **Cách chỉnh:** (1) Dùng **Max tuổi vùng (bars)** = 15–25 (Settings) để chỉ xét vùng gần đây; hoặc (2) giảm **Order block / FVG / Supply-Demand lookback** xuống 20–25; hoặc (3) dùng khung **1h** như bot OKX.

## Kết nối webhook OKX (Tín hiệu TradingView → OKX)

1. Trên chart đã gắn indicator, bấm **Alerts** (biểu tượng đồng hồ).
2. Tạo alert: **Condition** chọn **Regime Fusion - Mua/Bán** → **Regime Fusion - Long** hoặc **Regime Fusion - Short**.
3. Trong **Notifications** bật **Webhook URL**, điền: `https://www.okx.com/algo/signal/trigger`.
4. **Message** dùng JSON theo hướng dẫn OKX (có `action`, `instrument`, `signalToken` từ tín hiệu OKX bạn tạo).
5. Khi điều kiện thỏa, TradingView gửi webhook → OKX nhận và thực thi lệnh theo cấu hình tín hiệu trên OKX.

Chi tiết tạo tín hiệu trên OKX và format message: xem [docs/HUONG_DAN_BOT_OKX.md](../docs/HUONG_DAN_BOT_OKX.md) và giao diện **Tín hiệu TradingView** trên OKX.

## So với bot Python

- **Logic giống nhau:** Regime (MA 20/50 + volatility), Order Block (nến bearish/bullish + move 0.5%), FVG (3 nến), Supply/Demand (base 3 nến + expansion 0.3%), volume tùy chọn.
- **Khác biệt:** TradingView không có on-chain (SOPR/MVRV) hay M2; chỉ dùng giá + volume. Có thể chỉnh tham số trong Settings để gần với backtest hoặc bot OKX.
