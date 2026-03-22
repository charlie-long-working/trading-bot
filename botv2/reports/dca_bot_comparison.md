# DCA Spot Bot vs Simple DCA – Backtest & Dự phóng

**Period**: 2017-08-17 → 2026-03-14  
**BTC**: $4,309 → $70,673  

---

## 1. Binance DCA Spot Bot (Cài đặt Screenshot)

| Tham số | Giá trị |
|---------|---------|
| Bước giá (Price Dev) | 1.0% |
| TP mỗi kỳ | 1.5% |
| Lệnh an toàn max | 8 |
| Volume Scale | 1.00x |
| Step Scale | 1.00x |
| Vốn ban đầu | $350 |
| Lệnh ban đầu | $37 |
| Lệnh an toàn | $37 |

### Kết quả

| Metric | Giá trị |
|--------|---------|
| Final Value | $1,394.93 |
| ROI | +298.6% |
| Total PnL | $961.00 |
| Cycles | 811 |
| Win Rate | 100.0% |
| Profit Factor | 109930.07 |
| Max Drawdown | 0.0% |
| Longest Cycle | 24972 bars (~1040 ngày) |
| Unrealized PnL | $-138.30 |

---

## 2. DCA Bot Tối ưu (Grid Search)

| Tham số | Giá trị |
|---------|---------|
| Bước giá | 0.8% |
| TP mỗi kỳ | 1.5% |
| Lệnh an toàn max | 4 |
| Volume Scale | 1.30x |
| Step Scale | 1.20x |
| Lệnh ban đầu | $46 |
| Lệnh an toàn | $46 |

### Kết quả (1h data)

| Metric | Giá trị |
|--------|---------|
| Final Value | $1,457.50 |
| ROI | +316.4% |
| Cycles | 674 |
| Win Rate | 100.0% |
| Profit Factor | 124902.35 |
| Max Drawdown | 0.0% |

---

## 3. So sánh tổng hợp

### A. Vốn cố định $350

| Chiến lược | Vốn đầu | Final Value | ROI | Ghi chú |
|------------|---------|-------------|-----|---------|
| DCA Bot (screenshot) | $350 | $1,395 | +298.6% | 811 cycles, WR 100% |
| DCA Bot (tối ưu) | $350 | $1,457 | +316.4% | 674 cycles, WR 100% |
| Buy & Hold | $350 | $5,741 | +1540.2% | Mua 1 lần, giữ |

### B. Đầu tư $10/ngày (so sánh cùng ngân sách)

| Chiến lược | Tổng đầu tư | Final Value | ROI | Ghi chú |
|------------|-------------|-------------|-----|---------|
| Simple DCA | $31,320 | $153,910 | +391.4% | Mua mỗi ngày, không bán |
| DCA Bot + $10/ngày | $31,320 | $66,743 | +113.1% | Bot trade + nạp $10/ngày |

---

## 4. Dự phóng (Projection)

BTC monthly return: avg=4.6%, median=0.7%, std=20.5%

### BTC Price Forecast

| Kịch bản | Monthly Return | BTC 03/2027 | BTC 12/2027 |
|----------|---------------|-------------|-------------|
| Bearish | -7.9%/tháng | $26,210 | $12,456 |
| Moderate | +0.7%/tháng | $76,852 | $81,839 |
| Bullish | +14.2%/tháng | $349,448 | $1,158,729 |

### Simple DCA $10/ngày – Dự phóng (tiếp tục từ hiện tại)

Hiện tại: 2.177788 BTC, portfolio $153,910  
Tiếp tục $10/ngày → thêm $3,650 (12 tháng) / $6,388 (21 tháng)

| Kịch bản | BTC 03/2027 | Portfolio 03/2027 | Portfolio 12/2027 |
|----------|-------------|-------------------|-------------------|
| Bearish | $26,210 | $58,490 | $28,335 |
| Moderate | $76,852 | $171,324 | $185,581 |
| Bullish | $349,448 | $777,894 | $2,616,442 |

### DCA Bot – Dự phóng

Historical: 7.9 cycles/tháng, avg PnL/cycle: $1.36

| Kịch bản | Cycle adj. | Monthly gain | Bot 03/2027 | Bot 12/2027 |
|----------|-----------|-------------|-------------|-------------|
| Bearish | 0.5x (3.9/mo) | +0.38%/mo | $1,461 | $1,512 |
| Moderate | 0.8x (6.3/mo) | +0.61%/mo | $1,501 | $1,586 |
| Bullish | 1.2x (9.5/mo) | +0.92%/mo | $1,557 | $1,691 |

### DCA Bot Tối ưu – Dự phóng

Historical: 6.6 cycles/tháng, avg PnL/cycle: $1.85

| Kịch bản | Cycle adj. | Monthly gain | Bot 03/2027 | Bot 12/2027 |
|----------|-----------|-------------|-------------|-------------|
| Bearish | 0.5x (3.3/mo) | +0.42%/mo | $1,532 | $1,591 |
| Moderate | 0.8x (5.3/mo) | +0.67%/mo | $1,579 | $1,676 |
| Bullish | 1.2x (7.9/mo) | +1.00%/mo | $1,643 | $1,797 |

---

## 5. Khuyến nghị thông số tối ưu cho DCA Bot BTC

### Cài đặt Binance DCA Spot:

| Tham số | Khuyến nghị | Screenshot | Lý do |
|---------|-------------|-----------|-------|
| Bước giá | **0.8%** | 1.0% | Cover correction ~3% tổng |
| TP mỗi kỳ | **1.5%** | 1.5% | Cân bằng tần suất cycle & lợi nhuận |
| Lệnh an toàn max | **4** | 8 | Đủ buffer cho dip |
| Volume Scale | **1.30x** | 1.00x | Tăng size khi giá giảm sâu |
| Step Scale | **1.20x** | 1.00x | Giãn khoảng cách safety order |

### Phân tích

1. **DCA Bot** phù hợp thị trường **sideways/ranging** – kiếm lợi nhuận nhỏ mỗi cycle
2. **Simple DCA** phù hợp **long-term accumulation** – hưởng lợi khi BTC tăng dài hạn
3. **Buy & Hold** ROI cao nhất nếu mua đúng đáy, nhưng rủi ro timing lớn
4. **Rủi ro DCA Bot**: Bị "kẹt" trong bear market (tất cả SO filled, chờ recovery)
   - Longest cycle trong backtest: **1040 ngày** (34 tháng)
5. **Kết hợp tối ưu**: Dùng DCA Bot cho ~30% vốn (active), Simple DCA cho ~70% (passive)

---

*Generated: 2026-03-16 15:45 UTC*