# VRE — Vietnam Real Estate & Economic Dashboard

Interactive dashboard analyzing Vietnam real estate prices alongside global macro indicators.

**Giao diện:** Tiếng Việt — có mục *«Hướng dẫn đọc nhanh»* trong app để người không chuyên theo dõi chỉ số.

## Tự động cập nhật mỗi tuần (Streamlit Cloud)

1. **GitHub repo** → Settings → Secrets and variables → Actions → New repository secret  
   - Name: `FRED_API_KEY`  
   - Value: (key từ https://fred.stlouisfed.org/docs/api/api_key.html)

2. Workflow `.github/workflows/update-vre-data.yml` chạy **mỗi thứ Hai 07:00 VN** (hoặc chạy thủ công: Actions → Update VRE Data → Run workflow).

3. Sau khi push, Streamlit Cloud tự redeploy → biểu đồ dùng dữ liệu mới.

4. **Streamlit app** → Settings → Secrets: thêm `FRED_API_KEY` để nút «Làm mới dữ liệu» hoạt động khi có người bấm.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set FRED API key (free at https://fred.stlouisfed.org/docs/api/api_key.html)
export FRED_API_KEY="your_key_here"

# 3. Run dashboard
streamlit run vre/app.py
# Open http://localhost:8501
```

## Data Sources

| Indicator | Source | Series ID |
|-----------|--------|-----------|
| M2 Money Supply | FRED | `M2SL` |
| Fed Funds Rate | FRED | `FEDFUNDS` |
| CPI US | FRED | `CPIAUCSL` |
| CPI Vietnam | FRED | `FPCPITOTLZGVNM` |
| Oil WTI | FRED | `DCOILWTICO` |
| Dollar Index | FRED | `DTWEXBGS` |
| VN Property Prices | Local CSV | Market data |
| Property (US, UK, JP, DE, FR, KR) | FRED/BIS | `QUSR628BIS`, `QGBR628BIS`, etc. |
| Demographics (population, age) | FRED/World Bank | `POPTOT*`, `SPPOPDPNDOL*`, `SPPOP1564*` |
| VN Interest Rates | Manual CSV | SBV data |
| VN Real Estate Policies | CSV + RSS crawl | NHNN văn bản + VnExpress RSS |

## Crawl đầy đủ dữ liệu

```bash
cd Trading-bot
python3 vre/scripts/crawl_all_vre.py              # FRED + chính sách + tin/giá + vnstock
python3 vre/scripts/crawl_all_vre.py --merge-prices  # + gộp benchmark vào property_prices.csv
```

**Output:** `vre/data/crawled/`
- `news_articles.json` — 220 bài RSS (6 tháng)
- `price_extractions.csv` — 52 mức giá trích từ báo
- `quarterly_benchmarks.csv` — benchmark theo vùng/phân khúc
- `vn_market_snapshot.json` — VNIndex, tỷ giá, vàng
- `crawl_full_report.json` — tóm tắt

**Nguồn giá:** VnExpress + Dantri RSS (Batdongsan.com bị Cloudflare chặn crawl trực tiếp).
Số liệu Bộ Xây dựng Q2/2026: HN chung cư ~123 tr/m², HCM ~108 tr/m², đất nền HCM ~66 tr/m², cả nước ~40 tr/m².

**Chính sách:** `data/events/real_estate_policies.csv` (58 mục, gồm Dantri RSS).

**Lưu ý:** `property_prices.csv` giữ nguyên trừ khi chạy `--merge-prices` (phân khúc crawl khác mốc điều chỉnh thủ công).


Crawl chính sách 6 tháng gần nhất và điều chỉnh dự báo vĩ mô:

```bash
cd Trading-bot
python vre/scripts/crawl_policies_and_forecast.py
python vre/scripts/crawl_policies_and_forecast.py --months 6 --refresh-fred
```

- **Văn bản chính thức:** `vre/data/events/real_estate_policies.csv` (NHNN — thêm/sửa thủ công)
- **Tin tức RSS:** VnExpress BĐS + Kinh doanh (lọc từ khóa chính sách)
- **Báo cáo JSON:** `vre/data/reports/policy_forecast_YYYYMMDD.json`
- **Dashboard:** tab «Dự báo» → nút sidebar «Crawl chính sách 6 tháng»

Dự báo = mô hình vĩ mô (base) + điều chỉnh theo net impact chính sách gần đây.

## Manual CSV Data

Place files in `vre/data/vietnam/`:

**interest_rates.csv**
```csv
date,refinancing_rate,deposit_rate
2015-01-01,6.5,5.0
```

**property_prices.csv**
```csv
date,region,price_per_m2,yoy_change
2015-01-01,Ho Chi Minh,25000000,5.2
```

## Project Structure

```
vre/
  app.py                    # Streamlit dashboard (4 tabs)
  data_loaders/
    fred.py                 # FRED API client with CSV cache
    bis_property.py         # BIS property price index
    vietnam_econ.py         # Local CSV reader for VN data
  models/
    trend_predictor.py      # Correlation + regression model
  data/
    fred/                   # Cached FRED series
    bis/                    # Cached BIS data
    vietnam/                # Manual CSV data
```

## Dashboard Tabs

1. **Raw Data** — Time-series charts for each macro indicator + VN property prices
2. **Correlations** — Heatmap, lagged correlations, scatter plots
3. **Prediction** — Linear regression model with feature importance and forecasts
4. **VN History** — Detailed property price history, volatility, regional breakdown
5. **So sánh quốc tế** — Property price comparison (US, UK, Japan, Germany, France, Korea) + demographics (population, old-age dependency, working-age %)
