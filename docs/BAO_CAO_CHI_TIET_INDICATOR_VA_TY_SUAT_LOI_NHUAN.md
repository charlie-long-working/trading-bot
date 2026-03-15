# Báo cáo chi tiết: Indicator, cách thực hiện và tỷ suất lợi nhuận

**Dự án:** Trading-bot — Chiến lược Macro/Regime + Smart Money  
**Tham chiếu:** Plan Binance Data Crawl + Macro/Regime Strategy

---

## 1. Tổng quan kiến trúc

Chiến lược kết hợp **yếu tố timeline** (on-chain, M2, halving, seasonal) và **market regime** (bear, bull, sideways) để điều chỉnh quy tắc vào/ra lệnh và sizing.

```
Inputs (On-chain, M2, Halving, Seasonal) → Regime Classifier → Bear / Bull / Sideways
                                                                        ↓
                                                    Rule sets (entry, exit, size)
                                                                        ↓
                                                    Signals (OB, FVG, Supply/Demand + Volume)
                                                                        ↓
                                                    Backtest / Execution
```

---

## 2. Các indicator và cách sử dụng

### 2.1 Regime (phân loại thị trường)

**Mục đích:** Gán nhãn thị trường là **bear**, **bull** hoặc **sideways** để chọn bộ quy tắc phù hợp.

**Cách thực hiện trong code (`strategy/regime.py`):**

| Thành phần | Mô tả | Tham số mặc định |
|------------|--------|-------------------|
| **Trend (MA)** | MA ngắn (20) vs MA dài (50) trên `close` | `short_period=20`, `long_period=50` |
| **Volatility** | So sánh độ lệch chuẩn gần đây vs trước đó; co lại → sideways | `vol_period=20`, co lại nếu `recent_std < 0.8 * prev_std` |
| **M2 YoY** (tùy chọn) | M2 &lt; ngưỡng bear → ủng hộ bear | `m2_bear_threshold=0.0` |
| **SOPR** (tùy chọn) | SOPR &lt; 1 → capitulation, ủng hộ bear | `sopr_capitulation_threshold=1.0` |
| **MVRV** (tùy chọn) | MVRV ≥ 3.5 → FOMO, chuyển sang sideways (giảm size) | `mvrv_fomo_threshold=3.5` |

**Logic phân loại:**

- **Bull:** MA ngắn &gt; MA dài, volatility không co mạnh; nếu có MVRV cao thì vẫn có thể bị chuyển sang sideways.
- **Bear:** MA ngắn &lt; MA dài; nếu có M2 &lt; 0 hoặc SOPR &lt; 1 thì càng củng cố bear.
- **Sideways:** Range / volatility co lại, hoặc tín hiệu lẫn lộn.

**Dữ liệu cần:** Chuỗi `close` (bắt buộc), `high`/`low` (tùy chọn). M2, SOPR, MVRV cung cấp ngoài (FRED, Glassnode, CSV).

---

### 2.2 Timeline (Halving + Seasonal)

**Mục đích:** Bối cảnh theo chu kỳ halving và mùa vụ để điều chỉnh tâm lý (accumulation / discovery) và filter theo tháng.

**Cách thực hiện (`strategy/timeline.py`):**

| Indicator | Mô tả | Giá trị trả về |
|-----------|--------|-----------------|
| **Halving phase** | Khoảng cách tới halving gần nhất | `"pre"` (trước halving), `"post"` (sau halving ≤ 24 tháng), `"neutral"` |
| **Seasonal (tháng yếu)** | Tháng lịch sử thường yếu (ví dụ mùa hè) | `is_weak_seasonal_month(month)` → True cho 6, 7, 8 |

**Halving dates dùng trong code:** 2012-11-28, 2016-07-09, 2020-05-11, 2024-04-19.

**Cách dùng trong chiến lược:**

- **Pre-halving:** Ưu tiên accumulation / scale in; vẫn áp dụng sizing theo regime (bear/sideways = size nhỏ).
- **Post-halving:** Thường bull/sideways; kết hợp M2 và on-chain để xác nhận trend, tránh FOMO cuối chu kỳ.
- **Seasonal:** Dùng làm filter (giảm size trong tháng yếu) hoặc điều chỉnh nhẹ entry/exit.

---

### 2.3 On-chain (SOPR, MVRV) — đã tích hợp Glassnode

**Đã tích hợp:** `data_loaders/glassnode.py` lấy SOPR và MVRV từ **Glassnode API** (hoặc đọc từ cache CSV), align theo ngày với klines và đưa vào `RegimeInputs(sopr=..., mvrv=...)` trong backtest và `make_decision`.

| Chỉ báo | Ý nghĩa | Ngưỡng trong RegimeClassifier |
|---------|----------|-------------------------------|
| **SOPR** | Lãi/lỗ thực hiện; &lt; 1 = bán lỗ (capitulation) | &lt; 1 → củng cố bear |
| **MVRV** | Market Value / Realized Value; cao = FOMO | ≥ 3.5 → chuyển sideways, giảm size |
| **Exchange reserves, active addresses, hash rate, funding** | Plan đề cập; dùng cho overbought/oversold và xác nhận trend | Mở rộng sau khi có nguồn dữ liệu |

**Cách dùng:** Đặt `GLASSNODE_API_KEY` trong file `.env` (xem `.env.example`). Cache lưu tại `data/onchain/{BTC|ETH}/sopr.csv` và `mvrv.csv`. Chỉ hỗ trợ symbol **BTCUSDT** (→ BTC) và **ETHUSDT** (→ ETH).

---

### 2.4 M2 (cung tiền)

**Mục đích:** M2 YoY tăng (&gt; 0%) thường tương quan risk-on/bull; co (&lt; 0%) với bear. Dùng làm override/context cho regime.

**Cách thực hiện:**

- Nguồn: FRED (US M2), có thể thêm lag (ví dụ 90 ngày) nếu cần.
- Trong code: truyền một giá trị `m2_yoy` vào `RegimeInputs(m2_yoy=...)`; classifier dùng `m2_bear_threshold` (mặc định 0) để ủng hộ bear khi M2 &lt; ngưỡng.

**Chưa có loader M2 trong repo;** cần module load FRED (hoặc CSV) và merge theo ngày với klines.

---

### 2.5 Technical (Smart Money): Order Block, FVG, Supply/Demand

**Mục đích:** Xác định vùng giá có khả năng phản ứng (entry zones) và kết hợp với regime để sinh tín hiệu.

**Cách thực hiện (`strategy/technical.py`):**

| Indicator | Mô tả ngắn | Tham số chính |
|-----------|------------|----------------|
| **Order Block (OB)** | Nến cuối cùng trước một đợt di chuyển mạnh; bullish OB = nến bearish/doji trước cú tăng, bearish OB ngược lại | `lookback=50`, `move_bars=5`, `min_move_pct=0.5` |
| **Fair Value Gap (FVG)** | Khoảng trống 3 nến: bullish FVG = high[1] &lt; low[3], bearish = low[1] &gt; high[3] | `lookback=30` |
| **Supply/Demand zones** | Vùng base (vài nến) sau đó giá bứt phá mạnh; demand = close vượt trên base high, supply = close dưới base low | `lookback=50`, `expansion_pct=0.3`, `base_bars=3` |
| **Swing high/low** | Đỉnh/đáy local (left/right bars) dùng cho liquidity và structure | `left=2`, `right=2` |
| **Liquidity sweep** | Giá quét qua level (swing high/low) rồi đóng lại — có thể dùng cho entry | `lookback=5` |

**Entry logic trong fusion:** Chỉ vào lệnh khi giá hiện tại (close bar cuối) nằm trong hoặc sát vùng OB/FVG/zone (với `tolerance_pct`) và regime cho phép hướng đó (long/short).

---

### 2.6 Volume

**Mục đích:** Lọc tín hiệu (chỉ vào lệnh khi volume đủ mạnh) và nhận diện trạng thái volume (cao/thấp/climactic).

**Cách thực hiện (`strategy/volume.py`):**

| Hàm / Khái niệm | Mô tả |
|-----------------|--------|
| **volume_sma(volume, period=20)** | SMA volume theo chu kỳ |
| **get_volume_context(...)** | Trạng thái: HIGH / NEUTRAL / LOW / CLIMACTIC theo tỷ lệ volume/SMA; `climactic_ratio=2.0` |
| **volume_confirmation(volume, idx, period, min_ratio=1.0)** | True nếu volume tại bar ≥ min_ratio × SMA (mặc định ≥ trung bình) |

**Trong fusion (`signals/fusion.py`):** Nếu `require_volume_confirmation=True` thì signal LONG/SHORT chỉ được chấp nhận khi `volume_confirmation(...)` = True.

---

### 2.7 Rule set theo regime

**Mục đích:** Ánh xạ regime → quy tắc sizing, leverage, cho phép long/short, stop và take profit.

**Cách thực hiện (`strategy/rules.py`):**

| Regime | max_leverage | position_size_pct | allow_long | allow_short | stop_pct | take_profit_pct |
|--------|----------------|-------------------|------------|-------------|---------|------------------|
| **Bear** | 1.0 | 0.25 | ✓ | ✓ | 2% | 3% |
| **Bull** | 2.0 | 1.0 | ✓ | ✗ | 3% | None (trend-follow) |
| **Sideways** | 1.0 | 0.5 | ✓ | ✓ | 1.5% | 2% |

- **Bear:** Bảo vệ vốn; size nhỏ (25%), stop chặt (2%), TP 3%.
- **Bull:** Long bias, size đầy đủ, không TP cố định.
- **Sideways:** Mean reversion; size 50%, stop/TP chặt.

---

## 3. Cách thực hiện luồng tín hiệu và backtest

### 3.1 Luồng tín hiệu (fusion)

1. **Load dữ liệu:** Klines (open, high, low, close, volume) từ thư mục `data/` (spot hoặc um, symbol, interval).
2. **Regime:** Tại mỗi bar, `RegimeClassifier.classify(RegimeInputs(close=..., high=..., low=..., m2_yoy=..., sopr=..., mvrv=...))` → Bear/Bull/Sideways.
3. **Rule set:** `get_rules_for_regime(regime)` → RuleSet (size, stop, TP, allow long/short).
4. **Technical zones:** Tính `order_blocks`, `fair_value_gaps`, `supply_demand_zones` trên lookback (50, 30, 50).
5. **Volume:** Nếu bật, kiểm tra `volume_confirmation` tại bar hiện tại.
6. **Signal:**  
   - **Long:** regime cho phép long + giá tại bullish OB hoặc bullish FVG hoặc demand zone + (volume ok nếu bật).  
   - **Short:** tương tự với bearish OB/FVG/supply và allow_short.  
   - Trả về `SignalResult(signal, regime, reason, stop_below/stop_above)`.

### 3.2 Backtest (`backtest/engine.py`)

- **Dữ liệu:** `load_merged_klines(data_dir, market_type, symbol, interval)`.
- **Walk:** Từ bar `lookback` đến hết; tại mỗi bar chỉ dùng dữ liệu quá khứ để tính regime + signal (không look-ahead).
- **Exit:** Kiểm tra stop (chạm low với long, chạm high với short) và target (nếu có) trước khi xử lý entry mới.
- **Entry:** Nếu không có position và có signal LONG/SHORT phù hợp rule → mở position với `entry_price=close[i]`, stop từ zone hoặc % (stop_pct), target từ take_profit_pct (nếu có), size = `position_size_pct * base_size`.
- **Equity:** Bắt đầu 1.0; mỗi lần đóng lệnh: `equity *= 1 + pnl_pct/100` (pnl_pct đã nhân với size_pct).
- **Position đang mở cuối dữ liệu:** Đóng tại close cuối cùng, exit_reason="end".

---

## 4. Tỷ suất lợi nhuận và các chỉ số đánh giá

### 4.1 Các metric được tính trong backtest

| Chỉ số | Công thức / Cách tính |
|--------|------------------------|
| **Total return %** | `(equity_final - 1.0) * 100` với equity bắt đầu = 1.0 |
| **Win rate %** | `(số lệnh thắng / tổng số lệnh) * 100` |
| **Profit factor** | `gross_profit / |gross_loss|` (tổng lãi / tổng lỗ tuyệt đối) |
| **Sharpe ratio** | `mean(returns) / std(returns) * sqrt(252)` — annualized xấp xỉ từ chuỗi lợi nhuận mỗi lệnh |
| **Max drawdown %** | Trên equity curve: `max((peak - equity) / peak) * 100` với peak = running maximum |

**Lưu ý:** PnL mỗi lệnh đã được nhân với `position_size_pct` (0.25 / 0.5 / 1.0 theo regime), nên tổng return phản ánh sizing theo regime.

### 4.2 Cách xem kết quả

- **Dashboard:** Chạy `python -m dashboard.app`, mở `http://127.0.0.1:5050`.  
  - API `/api/backtest?market=...&symbol=...&interval=...` trả về: `num_trades`, `total_return_pct`, `max_drawdown_pct`, `win_rate`, `profit_factor`, `sharpe_ratio`, `equity_curve`.
- **Gọi trực tiếp:** `run_backtest(data_dir, market_type, symbol, interval, lookback=100, base_size=1.0, require_volume_confirmation=False)` → `BacktestResult`.

### 4.3 Ý nghĩa và kỳ vọng

- **Tỷ suất lợi nhuận:** Phụ thuộc vào symbol, interval, khoảng thời gian trong data và chất lượng zone/regime. Không có con số cố định trong plan; cần chạy backtest trên từng cặp (ví dụ spot BTCUSDT 1d, 1h) và so sánh.
- **Bear regime:** Size nhỏ (25%) nên return tuyệt đối thấp hơn bull nhưng giảm rủi ro.
- **Bull regime:** Full size, không TP cố định → có thể lợi nhuận cao hơn nếu trend kéo dài, nhưng drawdown cũng có thể lớn hơn.
- **Sharpe &gt; 0.5–1.0** thường được xem ổn cho chiến lược; **profit factor &gt; 1** nghĩa là tổng lãi &gt; tổng lỗ.
- **Max drawdown:** Cần đặt ngưỡng chấp nhận được (ví dụ &lt; 20–30%) tùy risk tolerance.

### 4.4 Cải thiện tỷ suất lợi nhuận (theo plan và code)

1. **Bổ sung M2 và on-chain:** Load M2 (FRED), SOPR/MVRV (Glassnode/CSV), đưa vào `RegimeInputs` để regime chính xác hơn và tránh vào lệnh sai phase.
2. **Tinh chỉnh rule set:** Điều chỉnh `position_size_pct`, `stop_pct`, `take_profit_pct` theo backtest từng regime.
3. **Timeline filter:** Giảm size hoặc tắt long trong tháng seasonal yếu; tăng dần size trong post-halving khi M2 expansion.
4. **Volume:** Bật `require_volume_confirmation=True` để giảm tín hiệu nhiễu (có thể giảm số lệnh nhưng tăng chất lượng).
5. **Crawler và data:** Đảm bảo đủ lịch sử (spot + futures, nhiều interval) theo plan Part 1 để backtest đại diện và tránh overfitting.

---

## 5. Tóm tắt

| Hạng mục | Nội dung |
|----------|----------|
| **Indicator** | Regime (MA + volatility + M2/SOPR/MVRV tùy chọn), Timeline (halving phase, seasonal), Technical (OB, FVG, supply/demand), Volume (SMA, confirmation). |
| **Cách thực hiện** | Regime classifier → rule set → fusion (regime + zone + volume) → signal; backtest walk bar-by-bar, exit stop/target/end, equity compound theo size_pct. |
| **Tỷ suất lợi nhuận** | Đo bằng total_return_pct, win_rate, profit_factor, sharpe_ratio, max_drawdown_pct; không có mức cố định — cần backtest từng cấu hình và cải thiện bằng M2, on-chain, timeline và volume. |

Báo cáo này căn cứ trên plan đính kèm và code hiện tại trong repo (regime, rules, technical, volume, timeline, fusion, backtest, dashboard).
