# Position sizing: vốn $1000 và sizing theo volatility

## 1. Backtest đang tính thế nào?

- Backtest dùng **equity ảo = 1**, mỗi lệnh “đặt” **size_pct** (theo regime):
  - **Bear:** 25% vốn
  - **Bull:** 100% vốn
  - **Sideways:** 50% vốn
- PnL mỗi lệnh = **return giá × size_pct** → cộng dồn: `equity *= 1 + pnl_pct/100`.
- **Tỷ suất lợi nhuận** in ra = `(equity_cuối - 1) × 100%`.

→ Nếu bạn trade **đúng cùng cách** (mỗi lệnh dùng 25%/50%/100% vốn hiện tại), với vốn **$1000**:

- **Số dư cuối ≈ $1000 × (1 + tỷ_suất_lợi_nhuận/100)**.

Ví dụ: backtest +952% → số dư cuối ≈ $1000 × 10.52 ≈ **$10,520**.

---

## 2. Sizing theo volatility (risk % mỗi lệnh)

Thay vì “cược” 25–100% vốn mỗi lệnh, có thể **giới hạn rủi ro**: mỗi lệnh chỉ mất tối đa **X%** vốn nếu đúng stop.

### Công thức

- **Risk mỗi lệnh (USD):** `R = Vốn_hiện_tại × risk_pct`  
  Ví dụ: risk 1% với $1000 → R = $10.
- **Khoảng cách stop (theo giá):**  
  Long: `stop_pct = (entry - stop_below) / entry × 100`  
  Short: `stop_pct = (stop_above - entry) / entry × 100`  
  Strategy thường dùng ~2% (bear/sideways) hoặc ~3% (bull).
- **Notional (quy mô lệnh) để nếu chạm stop chỉ mất R:**

  **Notional (USD) = R / (stop_pct / 100) = R × 100 / stop_pct**

Ví dụ:

- Vốn $1000, risk 1% → R = $10.
- Stop 2% → Notional = $10 / 0.02 = **$500**.
- Stop 3% → Notional = $10 / 0.03 ≈ **$333**.

### Bảng gợi ý (vốn $1000, spot/swap)

| Risk/lệnh | R ($) | Stop 2% → Notional | Stop 3% → Notional |
|-----------|-------|---------------------|---------------------|
| 0.5%      | 5     | $250                | $167                |
| 1%        | 10    | $500                | $333                |
| 1.5%      | 15    | $750                | $500                |
| 2%        | 20    | $1000               | $667                |

- **Notional** = giá trị position (số coin × giá, hoặc số contract × giá hợp đồng).
- Sau mỗi lệnh, cập nhật **Vốn_hiện_tại** = số dư thực (hoặc equity curve) rồi tính R cho lệnh tiếp theo.

---

## 3. Cách đạt lợi nhuận “tương ứng” backtest với $1000

Hai hướng:

### A. Giữ đúng logic backtest (compound theo size_pct)

- Mỗi lệnh dùng **size_pct** của **vốn hiện tại** (25% / 50% / 100% theo regime).
- Số dư cuối ≈ **$1000 × (1 + return_backtest/100)**.
- Rủi ro cao (Bull = 100% vốn một lệnh).

### B. Sizing theo vol (risk 1–2% mỗi lệnh)

- Mỗi lệnh: **Notional = (Vốn × risk_pct) / (stop_pct)**.
- **Tỷ suất lợi nhuận** sẽ **không** giống backtest (vì backtest đang dùng size_pct lớn hơn nhiều).
- Ưu điểm: drawdown và rủi ro vốn thấp hơn; lợi nhuận thấp hơn nhưng ổn định hơn.

Khuyến nghị: dùng **risk 1–2%** (vd. 1% khi mới chạy, 2% khi đã quen). Khi chạy bot OKX có thể set `--size-usdt` theo Notional tính từ công thức trên (và cập nhật theo vốn/số dư thực tế).

---

## 4. Chạy backtest với vốn giả định $1000 (chiến lược cũ: theo regime)

Chiến lược mặc định: **sizing theo regime** (Bear 25%, Bull 100%, Sideways 50%).

```bash
python run_backtest.py --no-onchain --capital 1000
```

Sẽ in thêm dòng dạng: **Số dư cuối ≈ $X** cho từng cấu hình. Số đó là nếu bạn compound đúng như backtest với vốn $1000.
