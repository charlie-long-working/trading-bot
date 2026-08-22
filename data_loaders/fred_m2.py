"""
Lấy M2 YoY từ FRED (Federal Reserve Economic Data).

- Series: M2SL (M2 Money Supply, tỷ USD, tháng).
- YoY = (M2 hiện tại - M2 12 tháng trước) / M2 12 tháng trước * 100.
- Dùng cho regime classifier (m2_yoy < 0 ủng hộ bear).
- Cần FRED_API_KEY (miễn phí tại https://fred.stlouisfed.org/docs/api/api_key.html).
"""

import os
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from fredapi import Fred
except ImportError:
    Fred = None

# Cache M2 under data/fred; optionally read sibling stock/vre FRED CSV
REPO_ROOT = Path(__file__).resolve().parent.parent
_STOCK_FRED = REPO_ROOT.parent / "stock" / "vre" / "data" / "fred"
CACHE_DIR = REPO_ROOT / "data" / "fred"
if not (CACHE_DIR / "M2SL.csv").exists() and (_STOCK_FRED / "M2SL.csv").exists():
    CACHE_DIR = _STOCK_FRED
else:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

M2_SERIES_ID = "M2SL"


def _get_api_key() -> Optional[str]:
    return os.environ.get("FRED_API_KEY")


def get_m2_yoy(api_key: Optional[str] = None) -> Optional[float]:
    """
    Lấy M2 YoY (%, tăng trưởng so cùng kỳ năm trước).

    - Fetch M2SL từ FRED (hoặc đọc cache).
    - Tính YoY từ 2 điểm: tháng mới nhất và 12 tháng trước.
    - Trả về None nếu thiếu API key hoặc không đủ dữ liệu.
    """
    if Fred is None:
        return None
    key = api_key or _get_api_key()
    if not key:
        return None
    try:
        fred = Fred(api_key=key)
        s = fred.get_series(M2_SERIES_ID)
        if s is None or len(s) < 13:
            return None
        s = s.dropna()
        if len(s) < 13:
            return None
        latest = float(s.iloc[-1])
        year_ago = float(s.iloc[-13])  # 12 tháng trước (index -13 vì -1 là tháng hiện tại)
        if year_ago <= 0:
            return None
        yoy = (latest - year_ago) / year_ago * 100.0
        return round(yoy, 2)
    except Exception:
        return None
