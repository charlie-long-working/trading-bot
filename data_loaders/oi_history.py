"""
Historical BTC open interest + funding + klines panel (2022 → now).

Sources (public, no paid key):
  - Bybit linear OI (1d / 4h / 1h) — full history from 2022
  - Binance USDT-M funding rate (8h) → as-of onto each bar
  - Binance USDT-M klines (1d / 4h / 1h)
  - USDT.D daily (DefiLlama + CMC), forward-filled onto intraday bars

Binance openInterestHist only keeps ~30 days publicly; joined when available.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
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

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "oi"
REPORTS_DIR = ROOT / "botdown" / "reports"

BYBIT = "https://api.bybit.com"
BINANCE_FAPI = "https://fapi.binance.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; oi-history/1.1)"}

INTERVAL_MS = {"1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}
INTERVAL_HOURS = {"1h": 1, "4h": 4, "1d": 24}
BARS_PER_DAY = {"1h": 24, "4h": 6, "1d": 1}
REPORT_SUFFIX = {"1h": "1h", "4h": "4h", "1d": "daily"}
BYBIT_OI_INTERVAL = {"1h": "1h", "4h": "4h", "1d": "1d"}
BN_OI_PERIOD = {"1h": "1h", "4h": "4h", "1d": "1d"}


def _get(url: str, params: Optional[dict] = None, timeout: int = 30, retries: int = 3) -> dict | list:
    import json
    from urllib.parse import urlencode
    import urllib.request
    import urllib.error

    full = url if not params else f"{url}?{urlencode(params)}"
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(full, headers=HEADERS)
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last_err = e
            time.sleep(0.4 * (attempt + 1))
    raise RuntimeError(f"GET failed {full[:120]}: {last_err}")


def _ms_to_naive(ts: int) -> datetime:
    t = int(ts)
    if t > 10_000_000_000:
        t //= 1000
    return datetime.fromtimestamp(t, tz=timezone.utc).replace(tzinfo=None)


def _start_ms(start: str) -> int:
    return int(datetime.strptime(start[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)


def fetch_bybit_oi(
    symbol: str = "BTCUSDT",
    interval: str = "1d",
    start: str = "2022-01-01",
    end: Optional[str] = None,
) -> "pd.DataFrame":
    """Open interest in base-coin contracts from Bybit (chunked, 2022→now)."""
    if pd is None:
        raise RuntimeError("pip install pandas")
    if interval not in INTERVAL_MS:
        raise ValueError(f"interval must be one of {list(INTERVAL_MS)}")
    start_ms = _start_ms(start)
    end_ms = (
        int(datetime.strptime(end[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)
        if end
        else int(datetime.now(timezone.utc).timestamp() * 1000)
    )
    step = 200 * INTERVAL_MS[interval]
    bybit_iv = BYBIT_OI_INTERVAL[interval]
    rows = []
    cur = start_ms
    n_req = 0
    while cur < end_ms:
        chunk_end = min(cur + step - 1, end_ms)
        data = _get(
            f"{BYBIT}/v5/market/open-interest",
            {
                "category": "linear",
                "symbol": symbol,
                "intervalTime": bybit_iv,
                "limit": 200,
                "startTime": cur,
                "endTime": chunk_end,
            },
        )
        lst = (data.get("result") or {}).get("list") or []
        rows.extend(lst)
        n_req += 1
        if n_req % 25 == 0:
            print(f"  [oi {interval}] requests={n_req} points={len(rows)} t={_ms_to_naive(cur)}")
        cur = chunk_end + 1
        time.sleep(0.08)

    if not rows:
        return pd.DataFrame(columns=["date", "oi_btc"])

    seen = set()
    out = []
    for r in rows:
        ts = int(r["timestamp"])
        if ts in seen:
            continue
        seen.add(ts)
        out.append({"date": _ms_to_naive(ts), "oi_btc": float(r["openInterest"])})
    df = pd.DataFrame(out).drop_duplicates("date").sort_values("date").reset_index(drop=True)
    print(f"  [oi {interval}] {len(df)} bars  {df['date'].min()} → {df['date'].max()}  ({n_req} req)")
    return df


def fetch_bybit_oi_daily(
    symbol: str = "BTCUSDT",
    start: str = "2022-01-01",
    end: Optional[str] = None,
) -> "pd.DataFrame":
    return fetch_bybit_oi(symbol, interval="1d", start=start, end=end)


def fetch_binance_funding(symbol: str = "BTCUSDT", start: str = "2022-01-01") -> "pd.DataFrame":
    """Raw 8h funding timestamps (not aggregated)."""
    if pd is None:
        raise RuntimeError("pip install pandas")
    start_ms = _start_ms(start)
    rows = []
    cur = start_ms
    while True:
        data = _get(
            f"{BINANCE_FAPI}/fapi/v1/fundingRate",
            {"symbol": symbol, "startTime": cur, "limit": 1000},
        )
        if not data:
            break
        rows.extend(data)
        cur = int(data[-1]["fundingTime"]) + 1
        if len(data) < 1000:
            break
        time.sleep(0.1)

    if not rows:
        return pd.DataFrame(columns=["date", "funding"])

    return pd.DataFrame(
        {
            "date": [_ms_to_naive(int(r["fundingTime"])) for r in rows],
            "funding": [float(r["fundingRate"]) for r in rows],
        }
    ).drop_duplicates("date").sort_values("date").reset_index(drop=True)


def fetch_binance_funding_daily(symbol: str = "BTCUSDT", start: str = "2022-01-01") -> "pd.DataFrame":
    raw = fetch_binance_funding(symbol, start=start)
    if raw.empty:
        return pd.DataFrame(columns=["date", "funding_mean", "funding_sum"])
    tmp = raw.copy()
    tmp["day"] = tmp["date"].dt.normalize()
    daily = tmp.groupby("day", as_index=False).agg(
        funding_mean=("funding", "mean"),
        funding_sum=("funding", "sum"),
    )
    daily = daily.rename(columns={"day": "date"})
    return daily


def fetch_binance_klines(
    symbol: str = "BTCUSDT",
    interval: str = "1d",
    start: str = "2022-01-01",
) -> "pd.DataFrame":
    if pd is None:
        raise RuntimeError("pip install pandas")
    if interval not in INTERVAL_MS:
        raise ValueError(f"interval must be one of {list(INTERVAL_MS)}")
    start_ms = _start_ms(start)
    rows = []
    cur = start_ms
    while True:
        data = _get(
            f"{BINANCE_FAPI}/fapi/v1/klines",
            {"symbol": symbol, "interval": interval, "startTime": cur, "limit": 1500},
        )
        if not data:
            break
        rows.extend(data)
        cur = int(data[-1][0]) + 1
        if len(data) < 1500:
            break
        time.sleep(0.1)

    out = []
    for r in rows:
        out.append(
            {
                "date": _ms_to_naive(int(r[0])),
                "open": float(r[1]),
                "high": float(r[2]),
                "low": float(r[3]),
                "close": float(r[4]),
                "volume": float(r[5]),
                "quote_volume": float(r[7]),
            }
        )
    df = pd.DataFrame(out).drop_duplicates("date").sort_values("date").reset_index(drop=True)
    print(f"  [klines {interval}] {len(df)} bars  {df['date'].min()} → {df['date'].max()}")
    return df


def fetch_binance_klines_daily(symbol: str = "BTCUSDT", start: str = "2022-01-01") -> "pd.DataFrame":
    return fetch_binance_klines(symbol, interval="1d", start=start)


def fetch_binance_oi_recent(symbol: str = "BTCUSDT", period: str = "1d") -> "pd.DataFrame":
    """~30 days only (Binance public retention)."""
    if pd is None:
        raise RuntimeError("pip install pandas")
    try:
        data = _get(
            f"{BINANCE_FAPI}/futures/data/openInterestHist",
            {"symbol": symbol, "period": period, "limit": 500},
        )
    except Exception:
        return pd.DataFrame(columns=["date", "bn_oi_usd", "bn_oi_btc"])
    if not data:
        return pd.DataFrame(columns=["date", "bn_oi_usd", "bn_oi_btc"])
    rows = []
    for r in data:
        rows.append(
            {
                "date": _ms_to_naive(int(r["timestamp"])),
                "bn_oi_usd": float(r["sumOpenInterestValue"]),
                "bn_oi_btc": float(r["sumOpenInterest"]),
            }
        )
    return pd.DataFrame(rows).drop_duplicates("date").sort_values("date").reset_index(drop=True)


def _align_funding(panel: "pd.DataFrame", fund_raw: "pd.DataFrame", interval: str) -> "pd.DataFrame":
    if fund_raw.empty:
        panel["funding_mean"] = 0.0
        panel["funding_sum"] = 0.0
        return panel
    if interval == "1d":
        tmp = fund_raw.copy()
        tmp["day"] = tmp["date"].dt.normalize()
        daily = tmp.groupby("day", as_index=False).agg(
            funding_mean=("funding", "mean"),
            funding_sum=("funding", "sum"),
        )
        daily = daily.rename(columns={"day": "date"})
        return panel.merge(daily, on="date", how="left")

    fr = fund_raw.sort_values("date")[["date", "funding"]].rename(columns={"funding": "funding_mean"})
    panel = pd.merge_asof(panel.sort_values("date"), fr, on="date", direction="backward")
    # last 24h of funding payments ≈ 3 * 8h; use 3 unique 8h prints via rolling on ffill
    hours = INTERVAL_HOURS[interval]
    n3 = max(int(round(24 / hours)), 1)
    panel["funding_sum"] = panel["funding_mean"].rolling(n3, min_periods=1).sum()
    return panel


def build_oi_panel(
    symbol: str = "BTCUSDT",
    start: str = "2022-01-01",
    force_refresh: bool = False,
    interval: str = "1d",
) -> "pd.DataFrame":
    """
    Merge Bybit OI + Binance price/funding + USDT.D.

    Columns: date, open, high, low, close, oi_btc, oi_usd, funding_mean, usdt_d, ...
    """
    if pd is None:
        raise RuntimeError("pip install pandas")
    if interval not in INTERVAL_MS:
        raise ValueError(f"interval must be one of {list(INTERVAL_MS)}")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    suffix = REPORT_SUFFIX[interval]
    cache_path = CACHE_DIR / f"{symbol.lower()}_oi_panel_{suffix}.csv"
    if cache_path.exists() and not force_refresh:
        cached = pd.read_csv(cache_path, parse_dates=["date"])
        if (
            len(cached) > 100
            and cached["date"].min() <= pd.Timestamp(start)
            and "usdt_d" in cached.columns
            and cached["usdt_d"].notna().sum() > 100
        ):
            return cached

    print(f"[oi_history] building {symbol} {interval} from {start}...")
    oi = fetch_bybit_oi(symbol, interval=interval, start=start)
    px = fetch_binance_klines(symbol, interval=interval, start=start)
    fund = fetch_binance_funding(symbol, start=start)
    bn_oi = fetch_binance_oi_recent(symbol, period=BN_OI_PERIOD[interval])

    panel = px.sort_values("date").reset_index(drop=True)
    oi = oi.sort_values("date")
    tol = pd.Timedelta(hours=INTERVAL_HOURS[interval] * 2)
    panel = pd.merge_asof(panel, oi, on="date", direction="backward", tolerance=tol)
    panel = _align_funding(panel, fund, interval)
    if len(bn_oi):
        bn_oi = bn_oi.sort_values("date")
        panel = pd.merge_asof(
            panel.sort_values("date"),
            bn_oi,
            on="date",
            direction="backward",
            tolerance=pd.Timedelta(hours=INTERVAL_HOURS[interval] * 3),
        )
    panel["oi_usd"] = panel["oi_btc"] * panel["close"]

    try:
        from data_loaders.usdt_d import build_usdt_d_daily
        usdtd = build_usdt_d_daily(start=start, force_refresh=force_refresh)
        usdtd = usdtd.sort_values("date")
        cols = [c for c in ["date", "usdt_d", "usdt_mcap", "total_mcap", "btc_dominance", "usdt_d_source"] if c in usdtd.columns]
        panel = pd.merge_asof(panel.sort_values("date"), usdtd[cols], on="date", direction="backward")
    except Exception as e:
        print(f"[oi_history] USDT.D merge skipped: {e}")

    panel = panel.dropna(subset=["oi_btc", "close"]).sort_values("date").reset_index(drop=True)
    panel.to_csv(cache_path, index=False)
    print(f"[oi_history] cache {cache_path} rows={len(panel)}")
    return panel


def save_panel_reports(
    panel: "pd.DataFrame",
    symbol: str = "BTCUSDT",
    interval: str = "1d",
) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = REPORT_SUFFIX.get(interval, interval)
    path = REPORTS_DIR / f"oi_panel_{symbol.lower()}_{suffix}.csv"
    panel.to_csv(path, index=False)
    kpath = REPORTS_DIR / f"klines_{symbol.lower()}_{suffix}.csv"
    kcols = [c for c in ["date", "open", "high", "low", "close", "volume", "quote_volume"] if c in panel.columns]
    panel[kcols].to_csv(kpath, index=False)
    return path


def build_oi_panel_recent(
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    lookback_bars: int = 800,
) -> "pd.DataFrame":
    """
    Lightweight panel for live alerts: last `lookback_bars` only (no full 2022 crawl).

    Enough history for EMA200 + calendar 30d z-scores on 1h/4h.
    """
    if pd is None:
        raise RuntimeError("pip install pandas")
    if interval not in INTERVAL_MS:
        raise ValueError(f"interval must be one of {list(INTERVAL_MS)}")

    hours = INTERVAL_HOURS[interval]
    # +10% buffer for gaps / incomplete merge
    lookback_h = int(lookback_bars * hours * 1.15) + 48
    now = datetime.now(timezone.utc)
    start_dt = now - pd.Timedelta(hours=lookback_h)
    start = start_dt.strftime("%Y-%m-%d")

    print(f"[oi_history] recent {symbol} {interval} lookback≈{lookback_bars} from {start}...")
    oi = fetch_bybit_oi(symbol, interval=interval, start=start)
    px = fetch_binance_klines(symbol, interval=interval, start=start)
    fund = fetch_binance_funding(symbol, start=start)

    panel = px.sort_values("date").reset_index(drop=True)
    oi = oi.sort_values("date")
    tol = pd.Timedelta(hours=hours * 2)
    panel = pd.merge_asof(panel, oi, on="date", direction="backward", tolerance=tol)
    panel = _align_funding(panel, fund, interval)
    panel["oi_usd"] = panel["oi_btc"] * panel["close"]

    try:
        from data_loaders.usdt_d import build_usdt_d_daily
        # Warm USDT.D from ~90d before lookback for z/rolling
        usdtd_start = (start_dt - pd.Timedelta(days=120)).strftime("%Y-%m-%d")
        usdtd = build_usdt_d_daily(start=usdtd_start, force_refresh=False)
        usdtd = usdtd.sort_values("date")
        cols = [
            c
            for c in ["date", "usdt_d", "usdt_mcap", "total_mcap", "btc_dominance", "usdt_d_source"]
            if c in usdtd.columns
        ]
        panel = pd.merge_asof(panel.sort_values("date"), usdtd[cols], on="date", direction="backward")
    except Exception as e:
        print(f"[oi_history] USDT.D merge skipped: {e}")

    panel = panel.dropna(subset=["oi_btc", "close"]).sort_values("date").reset_index(drop=True)
    if len(panel) > lookback_bars:
        panel = panel.iloc[-lookback_bars:].reset_index(drop=True)
    print(f"[oi_history] recent rows={len(panel)}  {panel['date'].min()} → {panel['date'].max()}")
    return panel
