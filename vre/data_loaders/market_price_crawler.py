"""
Crawl giá BĐS từ tin tức (RSS + bài báo đầy đủ).

Batdongsan.com.vn bị Cloudflare → dùng:
  - VnExpress / Dantri RSS + nội dung bài
  - Số liệu Bộ Xây dựng / Batdongsan được trích dẫn trên báo
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

try:
    import pandas as pd
except ImportError:
    pd = None

from vre.data_loaders.rss_utils import fetch_rss, fetch_url_text, strip_html

CRAWL_DIR = Path(__file__).resolve().parent.parent / "data" / "crawled"
VN_DATA = Path(__file__).resolve().parent.parent / "data" / "vietnam"

NEWS_FEEDS = [
    ("VnExpress BDS", "https://vnexpress.net/rss/bat-dong-san.rss"),
    ("VnExpress KD", "https://vnexpress.net/rss/kinh-doanh.rss"),
    ("Dantri BDS", "https://dantri.com.vn/rss/bat-dong-san.rss"),
]

PRIORITY_URLS = [
    (
        "https://dantri.com.vn/bat-dong-san/bo-xay-dung-gia-chung-cu-da-giam-o-ha-noi-trung-binh-123-trieum2-20260821111147868.htm",
        "Bo Xay dung Q2-2026",
    ),
]

REGION_ALIASES = {
    "Ho Chi Minh": [
        r"tp\.?\s*hcm", r"tp\.?\s*hồ\s*chí\s*minh", r"hồ\s*chí\s*minh", r"tphcm",
    ],
    "Ha Noi": [r"hà\s*nội", r"ha\s*noi", r"hanoi"],
    "Da Nang": [r"đà\s*nẵng", r"da\s*nang"],
    "Binh Duong": [r"bình\s*dương", r"binh\s*duong"],
    "Dong Nai": [r"đồng\s*nai", r"dong\s*nai"],
    "National": [r"cả\s*nước", r"toàn\s*quốc", r"trên\s*cả\s*nước"],
}

PRICE_PATTERNS = [
    re.compile(
        r"(?P<region>TP\.?\s*HCM|TPHCM|TP\.?\s*Hồ\s*Chí\s*Minh|Hà\s*Nội|Đà\s*Nẵng|Bình\s*Dương|Đồng\s*Nai|cả\s*nước|toàn\s*quốc)"
        r"[^.\n]{0,120}?"
        r"(?P<price>\d{1,3}(?:[.,]\d{1,2})?)\s*triệu\s*(?:đồng\s*)?/?\s*m\s*2",
        re.I,
    ),
    re.compile(
        r"giá\s*(?:rao\s*bán\s*)?đất\s*nền\s*bình\s*quân\s*trên\s*cả\s*nước\s*giảm[^.\n]{0,40}?"
        r"còn\s*khoảng\s*(?P<price>\d{1,3}(?:[.,]\d{1,2})?)\s*triệu\s*(?:đồng\s*)?/?\s*m\s*2",
        re.I,
    ),
    re.compile(
        r"riêng\s*tại\s*TPHCM\s*giảm[^.\n]{0,40}?"
        r"xuống\s*khoảng\s*(?P<price>\d{1,3}(?:[.,]\d{1,2})?)\s*triệu\s*(?:đồng\s*)?/?\s*m\s*2",
        re.I,
    ),
]


def _normalize_region(raw: str) -> str:
    if not raw:
        return "Unknown"
    t = raw.lower()
    for canon, patterns in REGION_ALIASES.items():
        for p in patterns:
            if re.search(p, t, re.I):
                return canon
    return raw.strip()


def _parse_price_million(s: str) -> Optional[float]:
    if not s:
        return None
    s = s.replace(",", ".")
    try:
        return float(s) * 1_000_000
    except ValueError:
        return None


def extract_prices_from_text(
    text: str, source: str, url: str = "", pub_date: Optional[datetime] = None,
) -> list[dict]:
    if not text:
        return []
    clean = re.sub(r"\s+", " ", strip_html(text))
    rows = []
    seen = set()

    for pat in PRICE_PATTERNS:
        for m in pat.finditer(clean):
            region_raw = m.groupdict().get("region") or "National"
            price = _parse_price_million(m.groupdict().get("price"))
            if price is None or price < 1_000_000:
                continue
            region = _normalize_region(region_raw)
            key = (region, int(price), source[:40])
            if key in seen:
                continue
            seen.add(key)
            ctx = clean[max(0, m.start() - 80):m.end()].lower()
            segment = "land" if "đất nền" in ctx else ("apartment" if "chung cư" in ctx else "mixed")
            rows.append({
                "region": region,
                "price_per_m2": int(price),
                "segment": segment,
                "source": source,
                "url": url,
                "pub_date": pub_date.isoformat() if pub_date else "",
                "context": clean[max(0, m.start() - 30):m.end() + 30],
            })
    return rows


def crawl_news_articles(days: int = 180) -> list[dict]:
    cutoff = datetime.now() - timedelta(days=days)
    articles = []
    for name, url in NEWS_FEEDS:
        for row in fetch_rss(name, url):
            if row["pub_date"] >= cutoff:
                articles.append(row)
    return articles


def crawl_price_extractions(days: int = 180) -> list[dict]:
    extractions = []
    articles = crawl_news_articles(days=days)
    price_kw = re.compile(
        r"triệu|m2|m²|bình quân|bộ xây dựng|batdongsan|giảm\s*\d|đất nền|chung cư",
        re.I,
    )

    for art in articles:
        blob = f"{art['title']} {art['summary']}"
        if not price_kw.search(blob):
            continue
        text = blob
        if art.get("link"):
            page = fetch_url_text(art["link"])
            if page:
                text = f"{blob} {strip_html(page)}"
        extractions.extend(extract_prices_from_text(
            text, source=art["feed"], url=art.get("link", ""),
            pub_date=art.get("pub_date"),
        ))

    for url, label in PRIORITY_URLS:
        page = fetch_url_text(url)
        if page:
            extractions.extend(extract_prices_from_text(
                page, source=label, url=url, pub_date=datetime(2026, 8, 21),
            ))
    return extractions


def build_official_benchmarks(extractions: list[dict]) -> "pd.DataFrame":
    if pd is None or not extractions:
        return pd.DataFrame()
    df = pd.DataFrame(extractions)
    df["pub_date"] = pd.to_datetime(df["pub_date"], errors="coerce")
    df["quarter"] = df["pub_date"].dt.to_period("Q").astype(str)
    rank = {"Bo Xay dung Q2-2026": 0, "Dantri BDS": 1, "VnExpress BDS": 2, "VnExpress KD": 3}
    df["src_rank"] = df["source"].map(rank).fillna(9)
    return df.sort_values(["region", "quarter", "src_rank"]).drop_duplicates(
        subset=["region", "price_per_m2"], keep="first",
    ).reset_index(drop=True)


def _compute_yoy(prices: "pd.DataFrame", date: pd.Timestamp, region: str, price: float) -> Optional[float]:
    prev = prices[(prices["region"] == region) & (prices["date"] < date)].sort_values("date")
    if len(prev) == 0:
        return None
    p0 = float(prev.iloc[-1]["price_per_m2"])
    if p0 <= 0:
        return None
    months = max(1, (date.year - prev.iloc[-1]["date"].year) * 12 + date.month - prev.iloc[-1]["date"].month)
    if months >= 10:
        return round((price / p0 - 1) * 100, 1)
    return round(((price / p0) ** (12 / months) - 1) * 100, 1)


def merge_benchmarks_into_property_csv(
    benchmarks: "pd.DataFrame",
    target_date: str = "2026-07-01",
) -> tuple[int, int]:
    if pd is None or benchmarks is None or len(benchmarks) == 0:
        return 0, 0

    path = VN_DATA / "property_prices.csv"
    prices = pd.read_csv(path, parse_dates=["date"])
    target = pd.Timestamp(target_date)
    added, updated = 0, 0
    main_regions = ["Ho Chi Minh", "Ha Noi", "Da Nang", "Binh Duong", "Dong Nai"]

    sub = benchmarks[benchmarks["region"].isin(main_regions)].copy()
    nat = benchmarks[benchmarks["region"] == "National"]
    if len(nat) > 0:
        base = float(nat.iloc[0]["price_per_m2"])
        for reg, factor in [("Binh Duong", 0.38), ("Dong Nai", 0.35), ("Da Nang", 0.30)]:
            if reg not in sub["region"].values:
                sub = pd.concat([sub, pd.DataFrame([{
                    "region": reg, "price_per_m2": int(base * factor), "segment": "land_estimated",
                }])], ignore_index=True)

    for region in main_regions:
        reg_rows = sub[sub["region"] == region]
        if len(reg_rows) == 0:
            continue
        if region in ("Ho Chi Minh", "Ha Noi"):
            apt = reg_rows[reg_rows["segment"] == "apartment"]
            pick = apt.iloc[0] if len(apt) else reg_rows.iloc[0]
        else:
            land = reg_rows[reg_rows["segment"].isin(["land", "land_estimated", "mixed"])]
            pick = land.iloc[0] if len(land) else reg_rows.iloc[0]

        price = int(pick["price_per_m2"])
        yoy = _compute_yoy(prices, target, region, price) or 0.0
        mask = (prices["date"] == target) & (prices["region"] == region)
        if mask.any():
            prices.loc[mask, "price_per_m2"] = price
            prices.loc[mask, "yoy_change"] = yoy
            updated += 1
        else:
            prices = pd.concat([prices, pd.DataFrame([{
                "date": target, "region": region, "price_per_m2": price, "yoy_change": yoy,
            }])], ignore_index=True)
            added += 1

    prices = prices.sort_values(["date", "region"]).reset_index(drop=True)
    prices["date"] = pd.to_datetime(prices["date"]).dt.strftime("%Y-%m-%d")
    prices.to_csv(path, index=False)
    return added, updated


def save_crawl_outputs(extractions: list[dict], articles: list[dict]) -> dict:
    CRAWL_DIR.mkdir(parents=True, exist_ok=True)
    art_path = CRAWL_DIR / "news_articles.json"
    art_path.write_text(json.dumps(articles, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    if pd is not None and extractions:
        pd.DataFrame(extractions).to_csv(CRAWL_DIR / "price_extractions.csv", index=False)

    benchmarks = build_official_benchmarks(extractions)
    if len(benchmarks) > 0:
        benchmarks.to_csv(CRAWL_DIR / "quarterly_benchmarks.csv", index=False)

    return {
        "crawled_at": datetime.now().isoformat(),
        "n_articles": len(articles),
        "n_price_extractions": len(extractions),
        "n_benchmarks": len(benchmarks),
    }


def run_market_price_crawl(days: int = 180, merge_csv: bool = False) -> dict:
    articles = crawl_news_articles(days=days)
    extractions = crawl_price_extractions(days=days)
    manifest = save_crawl_outputs(extractions, articles)
    if merge_csv and pd is not None:
        b = build_official_benchmarks(extractions)
        a, u = merge_benchmarks_into_property_csv(b)
        manifest["merge"] = {"added": a, "updated": u}
    path = CRAWL_DIR / "crawl_manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest
