"""Download kline ZIPs with rate limiting and exponential backoff on 429."""

import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import CrawlConfig
from .url_builder import kline_url

import requests
from tqdm import tqdm


def _download_one(
    url: str,
    dest_path: Path,
    session: requests.Session,
    rate_limit_sleep: float = 0.2,
    max_backoff: float = 60.0,
) -> Tuple[str, bool, Optional[str]]:
    """
    Download one ZIP. Returns (url, success, error_message).
    Uses exponential backoff on 429.
    """
    sleep_time = rate_limit_sleep
    last_error: Optional[str] = None
    for attempt in range(10):
        try:
            r = session.get(url, timeout=30, stream=True)
            if r.status_code == 429:
                time.sleep(sleep_time)
                sleep_time = min(sleep_time * 2, max_backoff)
                continue
            r.raise_for_status()
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            with open(dest_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
            return (url, True, None)
        except requests.RequestException as e:
            last_error = str(e)
            if hasattr(e, "response") and e.response is not None and e.response.status_code == 429:
                time.sleep(sleep_time)
                sleep_time = min(sleep_time * 2, max_backoff)
            else:
                return (url, False, last_error)
    return (url, False, last_error or "max retries exceeded")


def _dest_path(
    out_dir: str,
    market_type: str,
    symbol: str,
    interval: str,
    filename: str,
) -> Path:
    """Structured path: data/{market_type}/klines/{symbol}/{interval}/{filename}."""
    return Path(out_dir) / market_type / "klines" / symbol / interval / filename


def _generate_download_tasks(config: CrawlConfig) -> List[Tuple[str, Path]]:
    """Generate (url, dest_path) for all requested files. Uses monthly for past, daily for recent if needed."""
    tasks: List[Tuple[str, Path]] = []
    # Normalize interval for path (1M for futures monthly)
    path_interval = lambda mt, iv: "1M" if (iv == "1mo" and mt == "um") else iv

    for market_type in config.market_types:
        for symbol in config.symbols:
            for interval in config.intervals:
                pi = path_interval(market_type, interval)
                if config.frequency == "monthly":
                    # One task per month
                    d = config.start_date
                    while d <= config.end_date:
                        month_str = d.strftime("%Y-%m")
                        url = kline_url(symbol, interval, month_str, market_type, "monthly")
                        filename = f"{symbol}-{pi}-{month_str}.zip"
                        dest = _dest_path(config.out_dir, market_type, symbol, interval, filename)
                        tasks.append((url, dest))
                        # Next month
                        if d.month == 12:
                            d = d.replace(year=d.year + 1, month=1)
                        else:
                            d = d.replace(month=d.month + 1)
                else:
                    # Daily: one task per day
                    d = config.start_date
                    while d <= config.end_date:
                        url = kline_url(symbol, interval, d, market_type, "daily")
                        filename = f"{symbol}-{pi}-{d.strftime('%Y-%m-%d')}.zip"
                        dest = _dest_path(config.out_dir, market_type, symbol, interval, filename)
                        tasks.append((url, dest))
                        d += timedelta(days=1)
    return tasks


def _filter_existing(tasks: List[Tuple[str, Path]], skip_existing: bool) -> List[Tuple[str, Path]]:
    if not skip_existing:
        return tasks
    return [(u, p) for u, p in tasks if not p.exists()]


def download_all(config: CrawlConfig) -> None:
    """Download all kline ZIPs per config. Rate-limited, optional parallel workers."""
    tasks = _generate_download_tasks(config)
    tasks = _filter_existing(tasks, config.skip_existing)
    if not tasks:
        return
    session = requests.Session()
    session.headers.setdefault("User-Agent", "BinanceKlinesCrawler/1.0")

    def do_one(item: Tuple[str, Path]) -> Tuple[str, bool, Optional[str]]:
        url, dest = item
        return _download_one(url, dest, session)

    workers = max(1, min(config.workers, 4))
    failed: List[Tuple[str, str]] = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(do_one, t): t for t in tasks}
        for fut in tqdm(as_completed(futures), total=len(futures), desc="Downloading"):
            url, ok, err = fut.result()
            if not ok and err:
                failed.append((url, err))
    if failed:
        for url, err in failed[:10]:
            tqdm.write(f"FAILED: {url} -> {err}")
        if len(failed) > 10:
            tqdm.write(f"... and {len(failed) - 10} more failures.")


def unzip_and_merge_to_csv(config: CrawlConfig) -> None:
    """
    Unzip all downloaded ZIPs under out_dir and merge into one CSV per (market_type, symbol, interval).
    """
    out = Path(config.out_dir)
    if not out.exists():
        return
    # Collect all zip paths
    zips: List[Path] = []
    for market_type in config.market_types:
        base = out / market_type / "klines"
        if not base.exists():
            continue
        for symbol in config.symbols:
            for interval in config.intervals:
                folder = base / symbol / interval
                if folder.exists():
                    zips.extend(folder.glob("*.zip"))
    if not zips:
        return

    # Kline CSV columns (no header in Binance files)
    header = (
        "open_time,open,high,low,close,volume,close_time,quote_asset_volume,"
        "num_trades,taker_buy_base_asset_volume,taker_buy_quote_asset_volume,ignore\n"
    )

    # Group by (market_type, symbol, interval) -> list of zips (sort by name = by date)
    from collections import defaultdict
    groups: Dict[Tuple[str, str, str], List[Path]] = defaultdict(list)
    for z in zips:
        # .../spot/klines/BTCUSDT/1h/BTCUSDT-1h-2025-03.zip
        try:
            parts = z.relative_to(out).parts
            # parts: ('spot', 'klines', symbol, interval, filename)
            if len(parts) >= 5:
                mt, _, sym, iv, _ = parts[0], parts[1], parts[2], parts[3], parts[4]
                groups[(mt, sym, iv)].append(z)
        except ValueError:
            continue

    for (market_type, symbol, interval), paths in groups.items():
        paths.sort(key=lambda p: p.name)
        rows: List[str] = []
        for zp in paths:
            try:
                with zipfile.ZipFile(zp, "r") as zf:
                    for name in zf.namelist():
                        if name.endswith(".csv"):
                            with zf.open(name) as f:
                                content = f.read().decode("utf-8")
                                lines = content.strip().split("\n")
                                rows.extend(lines)
                            break
            except Exception:
                continue
        if not rows:
            continue
        # Dedupe by open_time (first column); skip header-like lines (non-numeric key)
        seen = set()
        unique_rows: List[str] = []
        for line in rows:
            if not line.strip():
                continue
            key = line.split(",")[0].strip()
            if not key.isdigit():
                continue
            if key in seen:
                continue
            seen.add(key)
            unique_rows.append(line)
        unique_rows.sort(key=lambda l: int(l.split(",")[0]))
        merge_path = out / market_type / "klines" / symbol / f"{symbol}-{interval}.csv"
        merge_path.parent.mkdir(parents=True, exist_ok=True)
        with open(merge_path, "w") as f:
            f.write(header)
            f.write("\n".join(unique_rows))
            f.write("\n")
