# DCA Bot — Phân tích theo giai đoạn thị trường

Mục tiêu: Tìm config tốt nhất cho **03/2026 → 03/2027** | TF: 1h

## Các giai đoạn thị trường đã test

| Giai đoạn | Thời gian | BTC | Đặc điểm |
|-----------|-----------|-----|----------|
| Bull run | 10/2020 → 04/2021 | $10K → $64K | Tăng mạnh, ít pullback sâu |
| Crash | 11/2021 → 06/2022 | $69K → $17K | Giảm -75%, bear market |
| Bear bottom | 06/2022 → 12/2022 | $17K → $16K | Sideway đáy, accumulation |
| Recovery | 01/2023 → 03/2024 | $16K → $73K | Hồi phục mạnh |
| Recent | 03/2024 → 03/2026 | $60K → $73K | Volatile sideway/up |

## Kết quả với vốn $300

| Config | Bull 2020-2021 | Crash 2021 | Bear bottom 2022 | Recovery 2023-24 | Recent 2024-26 | Score |
|--------|-----|-----|-----|-----|-----|-------|
| Safe 300 (3x, 2.5%, TP2%) | +30% | -28% ⚠3 | -10% ⚠1 | +22% | +4% ⚠1 | -63 |
| Wide Grid (3x, 3%, TP3%) | +66% | -55% ⚠3 | -28% ⚠1 | +49% | +16% ⚠1 | -66 |
| Conservative (3x, 2%, TP2%) | +54% | -47% ⚠3 | -25% ⚠1 | +41% | +7% ⚠1 | -66 |
| Moderate (5x, 1.5%, TP1.5%) | +113% | -55% ⚠4 | +16% ⚠1 | +72% | +31% ⚠3 | -97 |
| Balanced 300 (5x, 1.5%, TP1.5%) | +78% | -41% ⚠4 | -5% ⚠1 | +59% | +19% ⚠3 | -103 |
| Scalper (5x, 1%, TP0.8%) | +62% ⚠3 | -46% ⚠9 | -18% ⚠4 | +53% | +11% ⚠7 | -287 |
| Screenshot (10x, 0.75%, TP1.5%) | +289% ⚠10 | -100% ⚠4 | -100% ⚠3 | +280% ⚠4 | -100% ⚠5 | -297 |
| Aggressive SW (8x, 0.75%, TP1%) | +116% ⚠10 | -38% ⚠11 | -20% ⚠5 | +113% ⚠4 | -18% ⚠16 | -579 |

### Chi tiết từng giai đoạn ($300)

**Bull 2020-2021:**

| Config | Final | Return | Cycles | TP | Liq | WR | DD | Avg PnL/TP |
|--------|-------|--------|--------|----|-----|----|----|------------|
| Safe 300 (3x, 2.5%, TP2%) | $389 | +29.6% | 142 | 141 | 0 | 99% | 0.1% | $0.67 |
| Wide Grid (3x, 3%, TP3%) | $497 | +65.5% | 95 | 94 | 0 | 99% | 0.3% | $2.21 |
| Conservative (3x, 2%, TP2%) | $462 | +54.0% | 139 | 138 | 0 | 99% | 0.2% | $1.25 |
| Moderate (5x, 1.5%, TP1.5%) | $640 | +113.4% | 255 | 254 | 0 | 100% | 0.2% | $1.43 |
| Balanced 300 (5x, 1.5%, TP1.5%) | $534 | +77.9% | 217 | 216 | 0 | 100% | 0.3% | $1.17 |
| Scalper (5x, 1%, TP0.8%) | $485 | +61.6% | 600 | 597 | 3 | 100% | 11.0% | $0.52 |
| Screenshot (10x, 0.75%, TP1.5%) | $1,166 | +288.8% | 348 | 337 | 10 | 97% | 26.9% | $7.54 |
| Aggressive SW (8x, 0.75%, TP1%) | $647 | +115.7% | 521 | 510 | 10 | 98% | 25.7% | $2.14 |

**Crash 2021:**

| Config | Final | Return | Cycles | TP | Liq | WR | DD | Avg PnL/TP |
|--------|-------|--------|--------|----|-----|----|----|------------|
| Safe 300 (3x, 2.5%, TP2%) | $216 | -27.9% | 52 | 48 | 3 | 92% | 30.2% | $0.68 |
| Wide Grid (3x, 3%, TP3%) | $134 | -55.2% | 34 | 30 | 3 | 88% | 58.6% | $2.19 |
| Conservative (3x, 2%, TP2%) | $160 | -46.6% | 52 | 48 | 3 | 92% | 50.5% | $1.34 |
| Moderate (5x, 1.5%, TP1.5%) | $136 | -54.6% | 102 | 97 | 4 | 95% | 63.0% | $1.57 |
| Balanced 300 (5x, 1.5%, TP1.5%) | $176 | -41.4% | 96 | 91 | 4 | 95% | 48.1% | $1.30 |
| Scalper (5x, 1%, TP0.8%) | $162 | -45.9% | 364 | 354 | 9 | 97% | 49.9% | $0.53 |
| Screenshot (10x, 0.75%, TP1.5%) | $1 | -99.6% | 45 | 41 | 4 | 91% | 99.6% | $8.67 |
| Aggressive SW (8x, 0.75%, TP1%) | $187 | -37.8% | 321 | 309 | 11 | 96% | 67.2% | $2.27 |

**Bear bottom 2022:**

| Config | Final | Return | Cycles | TP | Liq | WR | DD | Avg PnL/TP |
|--------|-------|--------|--------|----|-----|----|----|------------|
| Safe 300 (3x, 2.5%, TP2%) | $269 | -10.2% | 40 | 38 | 1 | 95% | 13.5% | $0.73 |
| Wide Grid (3x, 3%, TP3%) | $216 | -28.1% | 21 | 19 | 1 | 90% | 28.1% | $2.34 |
| Conservative (3x, 2%, TP2%) | $226 | -24.7% | 35 | 33 | 1 | 94% | 25.6% | $1.34 |
| Moderate (5x, 1.5%, TP1.5%) | $348 | +16.1% | 85 | 83 | 1 | 98% | 23.6% | $1.75 |
| Balanced 300 (5x, 1.5%, TP1.5%) | $285 | -5.1% | 67 | 65 | 1 | 97% | 18.1% | $1.39 |
| Scalper (5x, 1%, TP0.8%) | $245 | -18.2% | 188 | 183 | 4 | 97% | 20.1% | $0.55 |
| Screenshot (10x, 0.75%, TP1.5%) | $0 | -100.0% | 17 | 14 | 3 | 82% | 100.0% | $9.03 |
| Aggressive SW (8x, 0.75%, TP1%) | $240 | -19.9% | 153 | 147 | 5 | 96% | 37.8% | $2.30 |

**Recovery 2023-24:**

| Config | Final | Return | Cycles | TP | Liq | WR | DD | Avg PnL/TP |
|--------|-------|--------|--------|----|-----|----|----|------------|
| Safe 300 (3x, 2.5%, TP2%) | $367 | +22.4% | 122 | 121 | 0 | 99% | 0.1% | $0.63 |
| Wide Grid (3x, 3%, TP3%) | $447 | +48.9% | 80 | 79 | 0 | 99% | 0.1% | $2.07 |
| Conservative (3x, 2%, TP2%) | $422 | +40.8% | 119 | 118 | 0 | 99% | 0.2% | $1.18 |
| Moderate (5x, 1.5%, TP1.5%) | $517 | +72.4% | 191 | 190 | 0 | 100% | 0.8% | $1.31 |
| Balanced 300 (5x, 1.5%, TP1.5%) | $476 | +58.6% | 188 | 187 | 0 | 100% | 0.6% | $1.07 |
| Scalper (5x, 1%, TP0.8%) | $458 | +52.5% | 359 | 359 | 0 | 100% | 1.0% | $0.52 |
| Screenshot (10x, 0.75%, TP1.5%) | $1,140 | +279.9% | 231 | 226 | 4 | 98% | 31.5% | $7.07 |
| Aggressive SW (8x, 0.75%, TP1%) | $639 | +113.2% | 333 | 328 | 4 | 98% | 17.6% | $2.10 |

**Recent 2024-26:**

| Config | Final | Return | Cycles | TP | Liq | WR | DD | Avg PnL/TP |
|--------|-------|--------|--------|----|-----|----|----|------------|
| Safe 300 (3x, 2.5%, TP2%) | $313 | +4.2% | 97 | 95 | 1 | 98% | 12.5% | $0.73 |
| Wide Grid (3x, 3%, TP3%) | $349 | +16.2% | 62 | 60 | 1 | 97% | 18.8% | $2.55 |
| Conservative (3x, 2%, TP2%) | $321 | +6.9% | 91 | 89 | 1 | 98% | 18.7% | $1.32 |
| Moderate (5x, 1.5%, TP1.5%) | $394 | +31.2% | 244 | 240 | 3 | 98% | 25.5% | $1.52 |
| Balanced 300 (5x, 1.5%, TP1.5%) | $358 | +19.4% | 217 | 213 | 3 | 98% | 22.3% | $1.25 |
| Scalper (5x, 1%, TP0.8%) | $334 | +11.5% | 590 | 582 | 7 | 99% | 24.4% | $0.54 |
| Screenshot (10x, 0.75%, TP1.5%) | $0 | -100.0% | 71 | 66 | 5 | 93% | 100.0% | $7.32 |
| Aggressive SW (8x, 0.75%, TP1%) | $246 | -18.1% | 555 | 538 | 16 | 97% | 68.8% | $2.15 |

### Khuyến nghị #1 cho $300: **Safe 300 (3x, 2.5%, TP2%)**

| Parameter | Value |
|-----------|-------|
| Leverage | 3x |
| Price step | 2.5% |
| Take profit | 2.0% |
| Initial margin | $8 |
| SO margin | $4 |
| Max SOs | 10 |
| Step scale | 1.2x |
| Total margin | $48 (16% vốn) |

- **Giai đoạn gần nhất (2024-26):** +4.2%, 1 liq, DD 12.5%
- **Crash test (2021-22):** -27.9%, 3 liq, DD 30.2%

### Khuyến nghị #2 cho $300: **Wide Grid (3x, 3%, TP3%)**

- Leverage: 3x, PS: 3.0%, TP: 3.0%
- Init: $18, SO: $9, Max SO: 8, SS: 1.3x
- Total margin: $90
- Recent: +16.2%, Liq: 1
- Crash: -55.2%, Liq: 3

## Kết quả với vốn $500

| Config | Bull 2020-2021 | Crash 2021 | Bear bottom 2022 | Recovery 2023-24 | Recent 2024-26 | Score |
|--------|-----|-----|-----|-----|-----|-------|
| Safe 500 (3x, 2.5%, TP2%) | +34% | -35% ⚠3 | -12% ⚠1 | +26% | +4% ⚠1 | -64 |
| Wide Grid (3x, 3%, TP3%) | +66% | -55% ⚠3 | -28% ⚠1 | +49% | +16% ⚠1 | -66 |
| Conservative (3x, 2%, TP2%) | +54% | -47% ⚠3 | -25% ⚠1 | +41% | +7% ⚠1 | -66 |
| Moderate (5x, 1.5%, TP1.5%) | +113% | -55% ⚠4 | +16% ⚠1 | +72% | +31% ⚠3 | -97 |
| Balanced 500 (5x, 1.5%, TP1.5%) | +82% | -37% ⚠4 | -4% ⚠1 | +54% | +18% ⚠3 | -102 |
| Scalper (5x, 1%, TP0.8%) | +84% ⚠2 | -48% ⚠9 | -18% ⚠4 | +53% | +11% ⚠6 | -262 |
| Aggressive SW (8x, 0.75%, TP1%) | +116% ⚠10 | -38% ⚠11 | -20% ⚠5 | +113% ⚠4 | -18% ⚠16 | -579 |
| Screenshot (10x, 0.75%, TP1.5%) | +173% ⚠10 | -97% ⚠9 | -23% ⚠7 | +168% ⚠4 | -40% ⚠16 | -587 |

### Chi tiết từng giai đoạn ($500)

**Bull 2020-2021:**

| Config | Final | Return | Cycles | TP | Liq | WR | DD | Avg PnL/TP |
|--------|-------|--------|--------|----|-----|----|----|------------|
| Safe 500 (3x, 2.5%, TP2%) | $672 | +34.3% | 143 | 142 | 0 | 99% | 0.1% | $1.29 |
| Wide Grid (3x, 3%, TP3%) | $828 | +65.5% | 95 | 94 | 0 | 99% | 0.2% | $3.68 |
| Conservative (3x, 2%, TP2%) | $770 | +54.0% | 139 | 138 | 0 | 99% | 0.2% | $2.09 |
| Moderate (5x, 1.5%, TP1.5%) | $1,067 | +113.4% | 255 | 254 | 0 | 100% | 0.2% | $2.39 |
| Balanced 500 (5x, 1.5%, TP1.5%) | $908 | +81.5% | 243 | 242 | 0 | 100% | 0.3% | $1.80 |
| Scalper (5x, 1%, TP0.8%) | $920 | +84.0% | 659 | 657 | 2 | 100% | 7.2% | $0.89 |
| Aggressive SW (8x, 0.75%, TP1%) | $1,078 | +115.7% | 521 | 510 | 10 | 98% | 25.7% | $3.57 |
| Screenshot (10x, 0.75%, TP1.5%) | $1,366 | +173.3% | 348 | 337 | 10 | 97% | 23.3% | $7.54 |

**Crash 2021:**

| Config | Final | Return | Cycles | TP | Liq | WR | DD | Avg PnL/TP |
|--------|-------|--------|--------|----|-----|----|----|------------|
| Safe 500 (3x, 2.5%, TP2%) | $324 | -35.3% | 58 | 54 | 3 | 93% | 37.7% | $1.27 |
| Wide Grid (3x, 3%, TP3%) | $224 | -55.2% | 34 | 30 | 3 | 88% | 58.6% | $3.64 |
| Conservative (3x, 2%, TP2%) | $267 | -46.6% | 52 | 48 | 3 | 92% | 50.5% | $2.22 |
| Moderate (5x, 1.5%, TP1.5%) | $227 | -54.6% | 102 | 97 | 4 | 95% | 63.0% | $2.62 |
| Balanced 500 (5x, 1.5%, TP1.5%) | $313 | -37.5% | 104 | 99 | 4 | 95% | 44.5% | $1.97 |
| Scalper (5x, 1%, TP0.8%) | $258 | -48.5% | 366 | 356 | 9 | 97% | 52.6% | $0.90 |
| Aggressive SW (8x, 0.75%, TP1%) | $311 | -37.8% | 321 | 309 | 11 | 96% | 67.2% | $3.78 |
| Screenshot (10x, 0.75%, TP1.5%) | $16 | -96.7% | 126 | 117 | 9 | 93% | 97.0% | $8.16 |

**Bear bottom 2022:**

| Config | Final | Return | Cycles | TP | Liq | WR | DD | Avg PnL/TP |
|--------|-------|--------|--------|----|-----|----|----|------------|
| Safe 500 (3x, 2.5%, TP2%) | $441 | -11.8% | 42 | 40 | 1 | 95% | 16.0% | $1.39 |
| Wide Grid (3x, 3%, TP3%) | $359 | -28.1% | 21 | 19 | 1 | 90% | 28.1% | $3.91 |
| Conservative (3x, 2%, TP2%) | $377 | -24.7% | 35 | 33 | 1 | 94% | 25.6% | $2.23 |
| Moderate (5x, 1.5%, TP1.5%) | $580 | +16.1% | 85 | 83 | 1 | 98% | 23.6% | $2.91 |
| Balanced 500 (5x, 1.5%, TP1.5%) | $478 | -4.3% | 71 | 69 | 1 | 97% | 17.2% | $2.10 |
| Scalper (5x, 1%, TP0.8%) | $409 | -18.3% | 196 | 191 | 4 | 97% | 20.8% | $0.93 |
| Aggressive SW (8x, 0.75%, TP1%) | $401 | -19.9% | 153 | 147 | 5 | 96% | 37.8% | $3.84 |
| Screenshot (10x, 0.75%, TP1.5%) | $385 | -23.1% | 142 | 134 | 7 | 94% | 70.7% | $8.14 |

**Recovery 2023-24:**

| Config | Final | Return | Cycles | TP | Liq | WR | DD | Avg PnL/TP |
|--------|-------|--------|--------|----|-----|----|----|------------|
| Safe 500 (3x, 2.5%, TP2%) | $629 | +25.9% | 124 | 123 | 0 | 99% | 0.1% | $1.19 |
| Wide Grid (3x, 3%, TP3%) | $745 | +48.9% | 80 | 79 | 0 | 99% | 0.1% | $3.45 |
| Conservative (3x, 2%, TP2%) | $704 | +40.8% | 119 | 118 | 0 | 99% | 0.2% | $1.97 |
| Moderate (5x, 1.5%, TP1.5%) | $862 | +72.4% | 191 | 190 | 0 | 100% | 0.8% | $2.18 |
| Balanced 500 (5x, 1.5%, TP1.5%) | $772 | +54.4% | 190 | 189 | 0 | 100% | 0.5% | $1.64 |
| Scalper (5x, 1%, TP0.8%) | $766 | +53.2% | 359 | 359 | 0 | 100% | 1.0% | $0.88 |
| Aggressive SW (8x, 0.75%, TP1%) | $1,066 | +113.2% | 333 | 328 | 4 | 98% | 17.6% | $3.50 |
| Screenshot (10x, 0.75%, TP1.5%) | $1,340 | +167.9% | 231 | 226 | 4 | 98% | 24.2% | $7.07 |

**Recent 2024-26:**

| Config | Final | Return | Cycles | TP | Liq | WR | DD | Avg PnL/TP |
|--------|-------|--------|--------|----|-----|----|----|------------|
| Safe 500 (3x, 2.5%, TP2%) | $520 | +4.0% | 97 | 95 | 1 | 98% | 14.5% | $1.39 |
| Wide Grid (3x, 3%, TP3%) | $581 | +16.2% | 62 | 60 | 1 | 97% | 18.8% | $4.25 |
| Conservative (3x, 2%, TP2%) | $535 | +6.9% | 91 | 89 | 1 | 98% | 18.7% | $2.21 |
| Moderate (5x, 1.5%, TP1.5%) | $656 | +31.2% | 244 | 240 | 3 | 98% | 25.5% | $2.53 |
| Balanced 500 (5x, 1.5%, TP1.5%) | $588 | +17.7% | 222 | 218 | 3 | 98% | 21.7% | $1.91 |
| Scalper (5x, 1%, TP0.8%) | $554 | +10.8% | 527 | 520 | 6 | 99% | 25.1% | $0.92 |
| Aggressive SW (8x, 0.75%, TP1%) | $410 | -18.1% | 555 | 538 | 16 | 97% | 68.8% | $3.58 |
| Screenshot (10x, 0.75%, TP1.5%) | $298 | -40.3% | 332 | 315 | 16 | 95% | 93.1% | $7.86 |

### Khuyến nghị #1 cho $500: **Safe 500 (3x, 2.5%, TP2%)**

| Parameter | Value |
|-----------|-------|
| Leverage | 3x |
| Price step | 2.5% |
| Take profit | 2.0% |
| Initial margin | $15 |
| SO margin | $8 |
| Max SOs | 13 |
| Step scale | 1.2x |
| Total margin | $119 (24% vốn) |

- **Giai đoạn gần nhất (2024-26):** +4.0%, 1 liq, DD 14.5%
- **Crash test (2021-22):** -35.3%, 3 liq, DD 37.7%

### Khuyến nghị #2 cho $500: **Wide Grid (3x, 3%, TP3%)**

- Leverage: 3x, PS: 3.0%, TP: 3.0%
- Init: $30, SO: $15, Max SO: 8, SS: 1.3x
- Total margin: $150
- Recent: +16.2%, Liq: 1
- Crash: -55.2%, Liq: 3

## Kịch bản 03/2026 → 03/2027

Không ai biết trước thị trường, nhưng dựa trên cycle BTC:

### Kịch bản 1: Tiếp tục tăng (xác suất ~30%)
- BTC $73K → $100K+
- DCA bot Long hoạt động tốt, ít kích hoạt SO
- **Config tốt:** Aggressive hoặc Scalper (nhiều cycle nhanh)

### Kịch bản 2: Sideway $60K-$85K (xác suất ~35%)
- Lý tưởng nhất cho DCA bot
- **Config tốt:** Moderate hoặc Balanced (đủ SO để catch dip, TP đều)

### Kịch bản 3: Correction -30-50% (xác suất ~25%)
- Post-halving cycle top → correction
- **Config tốt:** Wide Grid hoặc Conservative (chịu được giảm sâu)
- ⚠️ Screenshot config (10x) sẽ bị liquidation!

### Kịch bản 4: Black swan crash >50% (xác suất ~10%)
- Mọi DCA futures bot đều cháy
- **Giải pháp duy nhất:** Stop loss thủ công hoặc tắt bot khi BTC break support lớn

## Chiến lược phòng thủ

Dù chọn config nào, **luôn áp dụng:**

1. **Chỉ dùng 50-60% vốn cho bot**, giữ 40-50% dự phòng
2. **Đặt alert khi SO >= 8** → chuẩn bị add margin hoặc đóng lệnh
3. **Tắt bot khi BTC break dưới MA200 Daily** (trend bearish)
4. **Không chạy bot trong tuần có FOMC, CPI, NFP** nếu vốn nhỏ
5. **Review hàng tuần:** Nếu lỗ >15% trong 1 tuần → dừng 1 tuần

## So sánh: DCA Bot vs Regime+Fusion

| Tiêu chí | DCA Bot (best config) | Regime+Fusion |
|----------|----------------------|---------------|
| Tự động | ✅ 100% auto | ❌ Cần theo dõi signal |
| Rủi ro cháy | ⚠️ Có (leverage) | ✅ Có SL, DD thấp |
| Return dài hạn | Trung bình-Cao | Cao |
| Phù hợp | Sideway market | Mọi market |
| Vốn nhỏ ($300-500) | ⚠️ Rủi ro cao | ✅ Phù hợp hơn |

**Kết luận:** Với vốn $300-$500, **Regime+Fusion** an toàn hơn nhiều. DCA bot chỉ nên dùng khi bạn chấp nhận rủi ro cháy tài khoản và có quỹ dự phòng để add margin.
