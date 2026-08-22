"""RSS fetch + parse helpers (stdlib, no feedparser)."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional

try:
    import requests
except ImportError:
    requests = None

USER_AGENT = "VRE-crawler/1.0 (+local research; contact: local)"


def strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_rss_date(raw: str) -> Optional[datetime]:
    if not raw:
        return None
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z"):
        try:
            return datetime.strptime(raw.strip(), fmt).replace(tzinfo=None)
        except ValueError:
            continue
    return None


def fetch_rss(feed_name: str, url: str, timeout: int = 25) -> list[dict]:
    if requests is None:
        return []
    try:
        resp = requests.get(
            url, timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml"},
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except Exception as e:
        print(f"[rss] {feed_name}: {e}")
        return []

    rows = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or link).strip()
        pub = parse_rss_date(item.findtext("pubDate") or "")
        desc = strip_html(item.findtext("description") or "")
        if title and pub:
            rows.append({
                "feed": feed_name,
                "title": title,
                "link": link,
                "guid": guid,
                "pub_date": pub,
                "summary": desc,
            })
    return rows


def fetch_url_text(url: str, timeout: int = 25) -> str:
    if requests is None or not url:
        return ""
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"[fetch] {url[:60]}...: {e}")
        return ""
