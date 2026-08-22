"""
Crawl và gộp chính sách BĐS Việt Nam từ RSS tin tức + file CSV thủ công.

Nguồn RSS (ổn định hơn crawl trực tiếp SBV/MOC):
  - VnExpress Bất động sản
  - VnExpress Kinh doanh

Văn bản chính thức NHNN được duy trì trong data/events/real_estate_policies.csv.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import requests
except ImportError:
    requests = None

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "events"
POLICIES_CSV = DATA_DIR / "real_estate_policies.csv"

RSS_FEEDS = [
    ("VnExpress BDS", "https://vnexpress.net/rss/bat-dong-san.rss"),
    ("VnExpress KD", "https://vnexpress.net/rss/kinh-doanh.rss"),
    ("Dantri BDS", "https://dantri.com.vn/rss/bat-dong-san.rss"),
]

POLICY_KEYWORDS = [
    "chính sách", "lãi suất", "tín dụng", "nghị quyết", "quyết định",
    "công văn", "thông tư", "luật", "nhà ở", "nhnn", "ngân hàng nhà nước",
    "bất động sản", "địa ốc", "nhà ở xã hội", "tăng trưởng tín dụng",
    "thao túng", "quảng cáo", "kiểm soát",
]

POSITIVE_KEYWORDS = [
    "hỗ trợ", "ưu đãi", "giảm lãi", "mở rộng tín dụng", "tháo gỡ",
    "thúc đẩy", "linh hoạt", "không tính vào hạn mức", "nhà ở xã hội",
    "4,6%", "6,5%", "giảm lãi suất",
]

NEGATIVE_KEYWORDS = [
    "siết", "kiểm soát", "hạn mức", "thao túng", "cấm", "siết chặt",
    "rủi ro", "cảnh báo", "nợ xấu", "tăng trưởng tín dụng bđs",
]


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _classify_impact(title: str, summary: str) -> tuple[float, str]:
    blob = f"{title} {summary}".lower()
    pos = sum(1 for kw in POSITIVE_KEYWORDS if kw in blob)
    neg = sum(1 for kw in NEGATIVE_KEYWORDS if kw in blob)
    if pos > neg:
        score = min(0.5, 0.1 + 0.1 * (pos - neg))
        return score, "positive"
    if neg > pos:
        score = max(-0.5, -0.1 - 0.1 * (neg - pos))
        return score, "negative"
    return 0.0, "neutral"


BDS_KEYWORDS = [
    "bất động sản", "địa ốc", "nhà ở", "nhà đất", "chung cư", "dự án",
    "tín dụng bđs", "tín dụng bất động sản",
]


def _is_policy_related(title: str, summary: str, feed_name: str = "") -> bool:
    blob = f"{title} {summary}".lower()
    if not any(kw in blob for kw in POLICY_KEYWORDS):
        return False
    # RSS Kinh doanh rộng — chỉ giữ tin có từ khóa BĐS rõ ràng
    if "KD" in feed_name or "Kinh doanh" in feed_name:
        return any(kw in blob for kw in BDS_KEYWORDS)
    return True


def _parse_rss_date(raw: str) -> Optional[datetime]:
    if not raw:
        return None
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
    ):
        try:
            return datetime.strptime(raw.strip(), fmt).replace(tzinfo=None)
        except ValueError:
            continue
    return None


def fetch_rss_items(feed_name: str, url: str, timeout: int = 20) -> list[dict]:
    if requests is None:
        print("[policy] requests chưa cài. pip install requests")
        return []

    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "VRE-policy-crawler/1.0"})
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except Exception as e:
        print(f"[policy] RSS lỗi {feed_name}: {e}")
        return []

    items = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or link).strip()
        pub = _parse_rss_date(item.findtext("pubDate") or "")
        desc = _strip_html(item.findtext("description") or "")

        if not title or not pub:
            continue
        if not _is_policy_related(title, desc, feed_name=feed_name):
            continue

        score, direction = _classify_impact(title, desc)
        items.append({
            "date": pub.strftime("%Y-%m-%d"),
            "source": feed_name,
            "doc_id": guid[-40:] if guid else "",
            "title": title[:200],
            "category": "news",
            "impact_score": round(score, 2),
            "impact_direction": direction,
            "summary": desc[:400] if desc else title[:400],
            "url": link,
        })
    return items


def load_policies() -> Optional["pd.DataFrame"]:
    if pd is None:
        return None
    if not POLICIES_CSV.exists():
        return None
    df = pd.read_csv(POLICIES_CSV, parse_dates=["date"])
    return df.sort_values("date").reset_index(drop=True)


def save_policies(df: "pd.DataFrame") -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    out.to_csv(POLICIES_CSV, index=False)
    return POLICIES_CSV


def crawl_policies(months: int = 6) -> Optional["pd.DataFrame"]:
    """
    Crawl RSS 6 tháng gần nhất, gộp với CSV văn bản chính thức (dedup theo url).
    """
    if pd is None:
        return None

    cutoff = datetime.now() - timedelta(days=months * 30)
    crawled: list[dict] = []
    for name, url in RSS_FEEDS:
        for row in fetch_rss_items(name, url):
            if datetime.strptime(row["date"], "%Y-%m-%d") >= cutoff:
                crawled.append(row)

    existing = load_policies()
    if existing is None:
        merged = pd.DataFrame(crawled)
    elif crawled:
        merged = pd.concat([existing, pd.DataFrame(crawled)], ignore_index=True)
    else:
        merged = existing.copy()

    if len(merged) == 0:
        return merged

    merged["date"] = pd.to_datetime(merged["date"])
    merged = merged.drop_duplicates(subset=["url"], keep="first")
    merged = merged.sort_values("date").reset_index(drop=True)
    save_policies(merged)
    return merged


def filter_recent(policies: "pd.DataFrame", months: int = 6) -> "pd.DataFrame":
    cutoff = datetime.now() - timedelta(days=months * 30)
    p = policies.copy()
    p["date"] = pd.to_datetime(p["date"])
    return p[p["date"] >= cutoff].sort_values("date", ascending=False).reset_index(drop=True)
