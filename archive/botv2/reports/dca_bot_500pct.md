# DCA Bot TP=500% – Tối ưu cho OKX

**Chiến lược**: DCA Bot mua vào, chỉ chốt khi lời **500%** (giá = avg cost × 6)  
**Vốn**: $3,000 ban đầu + $400/tháng × 12 tháng = **$7,800**  
**Data**: BTC/USDT daily, 2017-08-17 → 2026-03-14  
**BTC hiện tại**: $71,212

---

## 1. Thông số tối ưu (Grid Search)

Grid search qua 432 combinations × 12 windows thời kỳ khác nhau.

### TOP 5

| # | Dev | Max SO | Vol Scale | Step Scale | Coverage | Score |
|---|-----|--------|-----------|------------|----------|-------|
| 1 | 8% | 8 | 1.3x | 1.0x | 64% | 239.5 |
| 2 | 8% | 8 | 1.5x | 1.0x | 64% | 239.0 |
| 3 | 5% | 6 | 1.0x | 1.3x | 64% | 232.0 |
| 4 | 8% | 8 | 1.2x | 1.0x | 64% | 228.9 |
| 5 | 5% | 6 | 1.5x | 1.3x | 64% | 228.6 |

---

## 2. So sánh Bot vs Simple DCA qua từng mùa

| Giai đoạn | BTC Range | Bot BTC | Bot Avg | Bot ROI | DCA BTC | DCA Avg | DCA ROI | Winner |
|-----------|-----------|---------|---------|---------|---------|---------|---------|--------|
| Bear start 2018-01 | $3,156-$17,176 | 0.9987 | $6,718 | -40.7% | 1.1444 | $6,816 | -45.7% | **Bot** |
| Deep bear 2018-06 | $3,156-$9,074 | 1.2233 | $4,414 | +68.5% | 1.5223 | $5,124 | +67.0% | **Bot** |
| Recovery 2019-01 | $3,350-$13,970 | 0.1637 | $3,643 | +7.9% | 1.2409 | $6,286 | +14.5% | **DCA** |
| Cycle2 equiv 2019-07 | $3,782-$13,147 | 1.0683 | $5,804 | +48.9% | 0.9106 | $8,566 | +7.3% | **Bot** |
| Pre-bull 2020-03 | $3,782-$58,353 | 0.0430 | $34,603 | +208.3% | 0.6739 | $11,575 | +290.0% | **DCA** |
| Bull 2021-01 | $28,130-$69,000 | 0.0102 | $29,361 | +2.3% | 0.1722 | $45,299 | +2.0% | **Bot** |
| Bear start 2022-01 | $15,476-$48,190 | 0.2825 | $24,317 | -29.7% | 0.3134 | $24,888 | -33.5% | **Bot** |
| Cycle3 equiv 2022-04 | $15,476-$47,444 | 0.2347 | $24,158 | +13.7% | 0.3524 | $22,137 | +28.6% | **DCA** |
| Deep bear 2022-06 | $15,476-$31,983 | 0.2097 | $19,554 | +21.7% | 0.3621 | $21,542 | +26.3% | **DCA** |
| Recovery 2023-01 | $16,499-$44,700 | 0.0179 | $16,633 | +6.2% | 0.2813 | $27,733 | +52.5% | **DCA** |
| Bull 2024-01 | $38,555-$108,353 | 0.0141 | $42,381 | +9.6% | 0.1240 | $62,896 | +47.5% | **DCA** |
| Post-ATH 2025-01 | $74,508-$126,200 | 0.0114 | $85,970 | +0.3% | 0.0778 | $100,250 | -12.6% | **Bot** |

**Bot thắng 6/12 windows** | **DCA thắng 6/12 windows**

---

## 3. Full Backtest 2017-2026 ($3,000 + $400/tháng)

| Metric | DCA Bot TP=500% | Simple DCA |
|--------|----------------|------------|
| Tổng nạp | $44,200 | $41,156 |
| Final Value | $65,510 | $203,628 |
| ROI | +48.2% | +394.8% |
| BTC held | 0.041159 | 2.859460 |
| Avg cost | $72,738 | $14,393 |
| Cycles hoàn thành | 2 | — |
| Realized PnL | $21,373 | — |
| Capital idle | $62,579 | $0 |
| Max Drawdown | 47.4% | — |

**Đang giữ position**: avg cost $72,738, TP tại $435,990

### Timeline (monthly snapshots)

| Tháng | BTC Price | Bot Value | BTC Held | Avg Cost | Cycles | Tổng nạp |
|-------|-----------|-----------|----------|----------|--------|---------|
| 2017-08 | $4,285 | $3,000 | 0.0000 | $0 | 0 | $3,000 |
| 2018-02 | $9,225 | $9,754 | 0.6317 | $3,392 | 0 | $5,400 |
| 2018-08 | $7,605 | $10,541 | 0.6317 | $3,392 | 0 | $7,800 |
| 2019-02 | $3,462 | $10,227 | 0.6317 | $3,392 | 0 | $10,200 |
| 2019-08 | $10,375 | $16,825 | 0.6317 | $3,392 | 0 | $12,600 |
| 2020-02 | $9,385 | $18,765 | 0.6317 | $3,392 | 0 | $15,000 |
| 2020-08 | $11,801 | $22,418 | 0.6317 | $3,392 | 0 | $17,400 |
| 2021-02 | $33,526 | $30,621 | 0.0131 | $22,820 | 1 | $19,800 |
| 2021-08 | $39,845 | $33,130 | 0.0131 | $22,820 | 1 | $22,200 |
| 2022-02 | $38,695 | $35,491 | 0.0131 | $22,820 | 1 | $24,600 |
| 2022-08 | $23,268 | $37,809 | 0.0475 | $20,719 | 1 | $27,000 |
| 2023-02 | $23,733 | $40,690 | 0.1187 | $18,044 | 1 | $29,400 |
| 2023-08 | $29,706 | $43,815 | 0.1187 | $18,044 | 1 | $31,800 |
| 2024-02 | $43,083 | $47,800 | 0.1187 | $18,044 | 1 | $34,200 |
| 2024-08 | $65,354 | $52,817 | 0.1187 | $18,044 | 1 | $36,600 |
| 2025-02 | $100,636 | $60,412 | 0.0062 | $96,125 | 2 | $39,000 |
| 2025-08 | $113,298 | $63,301 | 0.0174 | $85,438 | 2 | $41,400 |
| 2026-02 | $76,968 | $65,056 | 0.0174 | $85,438 | 2 | $43,800 |
| 2026-03 | $65,776 | $65,336 | 0.0412 | $72,738 | 2 | $44,200 |

---

## 4. Dự phóng 03/2026 → 03/2027

BTC hiện tại: $71,212, drawdown ~43% từ ATH.  
Vị trí: ~23 tháng sau Halving 4 → tương đương mid-2019 hoặc 04/2022.

### Kịch bản dựa trên cycle tương đương

**Cycle2 equiv (2019-07)**
- BTC lúc đó: $10,625 → $9,193 (Low $3,782, High $13,147)
- Projected BTC: $71,212 → ~$61,612 (Low ~$25,349, High ~$88,116)
- Bot avg cost (projected): ~$38,898
- Bot ROI 12m: +48.9%
- Bot cycles completed: 0
- x5 target: ~$194,492
- x10 target: ~$388,984

**Cycle3 equiv (2022-04)**
- BTC lúc đó: $46,283 → $28,465 (Low $15,476, High $47,444)
- Projected BTC: $71,212 → ~$43,797 (Low ~$23,811, High ~$72,998)
- Bot avg cost (projected): ~$37,170
- Bot ROI 12m: +13.7%
- Bot cycles completed: 0
- x5 target: ~$185,851
- x10 target: ~$371,701

---

## 5. Hướng dẫn cài đặt OKX

### Đường dẫn: Trade → Trading Bots → DCA (Spot)

| Tham số OKX | Giá trị | Ghi chú |
|-------------|---------|---------|
| **Pair** | BTC/USDT | — |
| **Direction** | Buy Low (Long) | — |
| **Price deviation** | **8%** | Bước giá mỗi SO |
| **Take profit** | **500%** | Chốt khi avg × 6 |
| **Max safety orders** | **8** | — |
| **Vol. scale** | **1.3x** | Mua nhiều hơn ở giá thấp |
| **Step scale** | **1.0x** | Giãn khoảng cách SO |
| **Initial order** | **$298** | — |
| **Safety order** | **$298** | Base amount |
| **Stop loss** | **Không** | Tích lũy dài hạn |
| **Vốn ban đầu** | **$3,000** | — |
| **Nạp thêm** | **$400/tháng** | Thêm vào bot mỗi tháng |

### Chi tiết Safety Orders (giả sử entry tại BTC = $71,212)

| SO # | Drop từ entry | Trigger Price | Amount | Tổng tích lũy |
|------|-------------|---------------|--------|---------------|
| Init | 0% | $71,212 | $298 | $298 |
| SO 1 | -8.0% | $65,515 | $298 | $596 |
| SO 2 | -16.0% | $59,818 | $388 | $984 |
| SO 3 | -24.0% | $54,121 | $504 | $1,488 |
| SO 4 | -32.0% | $48,424 | $655 | $2,142 |
| SO 5 | -40.0% | $42,727 | $851 | $2,994 |
| SO 6 | -48.0% | $37,030 | $1,107 | $4,101 |
| SO 7 | -56.0% | $31,333 | $1,439 | $5,539 |
| SO 8 | -64.0% | $25,636 | $1,871 | $7,410 |

**Tổng vốn cần nếu tất cả SO filled**: $7,410
  → Vốn ban đầu $3,000 cover đến ~SO 0
  → Monthly injection $400 fund thêm các SO sâu hơn

### Lịch nạp vốn

| Tháng | Nạp | Tổng nạp | Ghi chú |
|-------|-----|---------|---------|
| 03/2026 | $3,000 | $3,000 | Khởi tạo bot |
| 04/2026 | $400 | $3,400 | Fund thêm SO sâu |
| 05/2026 | $400 | $3,800 | Fund thêm SO sâu |
| 06/2026 | $400 | $4,200 | Fund thêm SO sâu |
| 07/2026 | $400 | $4,600 | Reserve cho dip |
| 08/2026 | $400 | $5,000 | Reserve cho dip |
| 09/2026 | $400 | $5,400 | Reserve cho dip |
| 10/2026 | $400 | $5,800 | Tích lũy thêm |
| 11/2026 | $400 | $6,200 | Tích lũy thêm |
| 12/2026 | $400 | $6,600 | Tích lũy thêm |
| 01/2027 | $400 | $7,000 | Tích lũy thêm |
| 02/2027 | $400 | $7,400 | Tích lũy thêm |
| 03/2027 | $400 | $7,800 | Tích lũy thêm |

---

## 6. Mục tiêu chốt lời

Avg cost dự kiến: **$35,757** – **$288,813** (median ~$55,719)

| Mục tiêu | BTC cần đạt (từ median) | Thời gian dự kiến |
|----------|------------------------|-------------------|
| **x2** | $111,439 | 1-2 năm |
| **x3** | $167,158 | 2-3 năm |
| **x5** | $278,597 | 3-5 năm (next bull) |
| **x6 (TP 500%)** | $334,316 | Bot tự chốt |
| **x10** | $557,193 | 5-8 năm |

### So sánh nhanh

| | DCA Bot TP=500% | Simple DCA |
|---|---|---|
| Cách hoạt động | Tự mua nhiều khi giá giảm, chốt khi x6 | Mua đều mỗi ngày |
| Ưu điểm | Avg cost thấp hơn (mua mạnh lúc dip) | Đơn giản, deploy 100% vốn |
| Nhược điểm | Vốn nhàn rỗi khi thị trường ổn | Không tận dụng dip |
| Phù hợp | Bear/sideways market | Mọi market condition |
| Chốt lời | Tự động khi x6 | Phải chốt thủ công |

### Khuyến nghị kết hợp

- **$3,000** → OKX DCA Bot TP=500% (thông số ở trên)
- **$400/tháng**: Chia đôi
  - **$200** → Nạp thêm vào Bot (fund SO sâu)
  - **$200** → Simple DCA (Recurring Buy) để deploy ngay
- Cách này đảm bảo **100% vốn luôn làm việc** thay vì idle trong bot

---

*Generated: 2026-03-16 16:22 UTC*