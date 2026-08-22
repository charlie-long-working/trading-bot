#!/usr/bin/env python3
"""
Crawl đầy đủ dữ liệu VRE:
  1. FRED (vĩ mô)
  2. Chính sách BĐS (RSS)
  3. Giá / tin thị trường (RSS + báo)
  4. VNIndex / vàng / tỷ giá (vnstock — nếu có)

Chạy: python vre/scripts/crawl_all_vre.py
      python vre/scripts/crawl_all_vre.py --merge-prices  # gộp benchmark vào property_prices.csv
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

CRAWL_DIR = ROOT / "vre" / "data" / "crawled"


def _step(name: str):
    print(f"\n{'='*50}\n[{name}]\n{'='*50}")


def crawl_fred() -> dict:
    _step("1/4 FRED — vĩ mô quốc tế")
    key = os.environ.get("FRED_API_KEY")
    if not key:
        print("  SKIP: không có FRED_API_KEY")
        return {"status": "skipped"}
    from vre.scripts import update_data
    rc = update_data.main()
    return {"status": "ok" if rc == 0 else "partial"}


def crawl_policies(months: int = 6) -> dict:
    _step("2/4 Chính sách BĐS — RSS")
    from vre.data_loaders.policy_crawler import crawl_policies
    df = crawl_policies(months=months)
    n = len(df) if df is not None else 0
    print(f"  OK: {n} mục chính sách")
    return {"status": "ok", "n_policies": n}


def crawl_market(days: int = 180, merge: bool = False) -> dict:
    _step("3/4 Giá & tin BĐS — RSS + báo")
    from vre.data_loaders.market_price_crawler import run_market_price_crawl
    m = run_market_price_crawl(days=days, merge_csv=merge)
    print(f"  Bài viết: {m.get('n_articles', 0)}")
    print(f"  Trích giá: {m.get('n_price_extractions', 0)}")
    print(f"  Benchmark: {m.get('n_benchmarks', 0)}")
    if merge and "merge" in m:
        print(f"  Gộp CSV: +{m['merge'].get('added', 0)} / ~{m['merge'].get('updated', 0)}")
    return m


def crawl_vnstock() -> dict:
    _step("4/4 VN market — vnstock")
    venv_py = ROOT.parent / "stock" / ".venv" / "bin" / "python3"
    py = str(venv_py) if venv_py.exists() else sys.executable
    script = '''
import json, sys
from datetime import datetime
from pathlib import Path
out = Path(sys.argv[1])
try:
    from vnstock import Quote
    from vnstock.explorer.misc import vcb_exchange_rate, sjc_gold_price
    q = Quote(symbol="VNINDEX", source="KBS")
    df = q.history(length="30", interval="1D")
    fx = vcb_exchange_rate(date=datetime.now().strftime("%Y-%m-%d"))
    gold = sjc_gold_price()
    payload = {
        "vnindex_rows": len(df) if df is not None else 0,
        "vnindex_last": float(df["close"].iloc[-1]) if df is not None and len(df) else None,
        "exchange_rate": fx.to_dict() if hasattr(fx, "to_dict") else str(fx)[:200],
        "gold": gold.to_dict() if hasattr(gold, "to_dict") else str(gold)[:200],
        "fetched_at": datetime.now().isoformat(),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print("  OK vnstock:", payload.get("vnindex_last"))
except Exception as e:
    print("  SKIP vnstock:", e)
'''
    out = CRAWL_DIR / "vn_market_snapshot.json"
    try:
        subprocess.run([py, "-c", script, str(out)], check=False, cwd=str(ROOT))
    except Exception as e:
        print(f"  SKIP: {e}")
        return {"status": "skipped"}
    return {"status": "ok", "file": str(out)}


def main():
    parser = argparse.ArgumentParser(description="Crawl đầy đủ dữ liệu VRE")
    parser.add_argument("--days", type=int, default=180, help="Số ngày crawl tin (mặc định 180)")
    parser.add_argument("--merge-prices", action="store_true",
                        help="Gộp benchmark crawl vào property_prices.csv")
    parser.add_argument("--skip-fred", action="store_true")
    args = parser.parse_args()

    CRAWL_DIR.mkdir(parents=True, exist_ok=True)
    report = {"started_at": datetime.now().isoformat(), "steps": {}}

    if not args.skip_fred:
        report["steps"]["fred"] = crawl_fred()
    report["steps"]["policies"] = crawl_policies()
    report["steps"]["market"] = crawl_market(days=args.days, merge=args.merge_prices)
    report["steps"]["vnstock"] = crawl_vnstock()

    report["finished_at"] = datetime.now().isoformat()
    report_path = CRAWL_DIR / "crawl_full_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'='*50}")
    print(f"XONG — báo cáo: {report_path}")
    print(f"Dữ liệu crawl: {CRAWL_DIR}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
