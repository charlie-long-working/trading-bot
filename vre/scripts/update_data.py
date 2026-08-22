#!/usr/bin/env python3
"""
Cập nhật dữ liệu FRED (macro, BIS property, demographics).
Chạy thủ công hoặc qua GitHub Actions mỗi tuần.

Cần: FRED_API_KEY trong env hoặc .env
Chạy: python vre/scripts/update_data.py  (từ thư mục gốc project)
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# Đảm bảo project root trong path
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from vre.data_loaders.fred import SERIES, get_series, CACHE_DIR
from vre.data_loaders.comparison import (
    PROPERTY_SERIES, DEMO_POPULATION, DEMO_OLD_AGE_DEPENDENCY,
    DEMO_WORKING_AGE_PCT, DEMO_FERTILITY,
    _get_fred, _fetch_and_cache,
)


def collect_all_series_ids():
    """Thu thập tất cả series ID cần fetch từ FRED."""
    ids = set(SERIES.keys())
    for s in [PROPERTY_SERIES, DEMO_POPULATION, DEMO_OLD_AGE_DEPENDENCY,
              DEMO_WORKING_AGE_PCT, DEMO_FERTILITY]:
        ids.update(s.values())
    return sorted(ids)


def main():
    key = os.environ.get("FRED_API_KEY")
    if not key:
        print("ERROR: FRED_API_KEY chưa đặt. Export hoặc thêm vào .env / GitHub Secrets.")
        sys.exit(1)

    os.environ["FRED_API_KEY"] = key  # Đảm bảo các module đọc được

    all_ids = collect_all_series_ids()
    print(f"[update_data] Bắt đầu fetch {len(all_ids)} series từ FRED...")

    fred = _get_fred()
    ok, fail = 0, 0
    for sid in all_ids:
        if sid in SERIES:
            df = get_series(sid, force_refresh=True, api_key=key)
        else:
            df = _fetch_and_cache(sid, fred, force_refresh=True) if fred else None

        if df is not None and len(df) > 0:
            ok += 1
            print(f"  OK  {sid}")
        else:
            fail += 1
            print(f"  FAIL {sid}")

    # Ghi timestamp cập nhật
    meta_dir = CACHE_DIR.parent
    meta_dir.mkdir(parents=True, exist_ok=True)
    meta_file = meta_dir / "last_updated.txt"
    meta_file.write_text(datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC") + "\n")

    print(f"\n[update_data] Xong: {ok} OK, {fail} fail. Cập nhật: {meta_file.read_text().strip()}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
