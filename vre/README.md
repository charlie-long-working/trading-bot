# VRE — Vietnam Real Estate & Economic Dashboard

Interactive dashboard analyzing Vietnam real estate prices alongside global macro indicators.

**Giao diện:** Tiếng Việt — có mục *«Hướng dẫn đọc nhanh»* trong app để người không chuyên theo dõi chỉ số.

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
