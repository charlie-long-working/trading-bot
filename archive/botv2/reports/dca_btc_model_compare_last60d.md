# DCA BTC Models Compare (last ~2 months)

**Window**: 2026-01-13 → 2026-03-14
**BTC change**: 93,389.63 → 70,672.53 (-24.3%)
**MA200(1D) dev**: -24.36% → choose direction **short**

---

## 1) Best by ROI (PnL)

| Direction | Leverage | Price deviation | Take profit | Max SO | Vol scale | Step scale | ROI | TP cycles | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| short | 8x | 0.75% | 2.00% | 10 | 1.00x | 1.10x | +136.5% | 32 | 6.7% |

## 2) Best by TP cycles (cycles ăn được nhiều nhất)

| Direction | Leverage | Price deviation | Take profit | Max SO | TP cycles | Cycles | ROI | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| short | 8x | 0.53% | 1.00% | 15 | 93 | 94 | +103.9% | 7.4% |

---

## 3) Top 10 by ROI (no liquidation)

| # | Lev | dev | TP | MaxSO | ROI | TP cycles | Liq | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 8x | 0.75% | 2.00% | 10 | +136.5% | 32 | 0 | 6.7% |
| 2 | 8x | 1.00% | 2.00% | 8 | +135.5% | 31 | 0 | 6.8% |
| 3 | 8x | 0.45% | 2.00% | 15 | +130.0% | 33 | 0 | 7.6% |
| 4 | 8x | 1.00% | 1.50% | 8 | +121.7% | 47 | 0 | 7.2% |
| 5 | 8x | 1.00% | 1.70% | 8 | +117.8% | 39 | 0 | 7.3% |
| 6 | 8x | 0.75% | 1.50% | 10 | +117.4% | 45 | 0 | 7.2% |
| 7 | 8x | 0.53% | 2.00% | 15 | +116.5% | 33 | 0 | 7.0% |
| 8 | 8x | 0.75% | 1.00% | 10 | +116.2% | 86 | 0 | 7.2% |
| 9 | 8x | 1.00% | 2.00% | 10 | +116.2% | 32 | 0 | 6.1% |
| 10 | 8x | 0.45% | 1.50% | 15 | +114.4% | 47 | 0 | 8.1% |

---

## 4) Recommended OKX setup (parameter-only)

- Direction: **short**
- Leverage: **8x**
- Price deviation: **0.75%**
- Take profit: **2.00%**
- Max safety orders: **10**
- Vol scale: **1.00x**
- Step scale: **1.10x**

**Important**: bạn đang cần cả điều kiện Start/Stop và số tiền cho Initial/Safety order để đảm bảo đủ margin fill SO; thông số amount không có trong report này.

*Generated: 2026-03-18 18:58 UTC*