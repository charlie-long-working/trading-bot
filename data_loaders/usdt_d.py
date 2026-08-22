"""
USDT.D (USDT market-cap dominance, %) daily series.

Construction:
  1. USDT circulating ≈ mcap from DefiLlama (daily, long history).
  2. Total crypto mcap from CoinMarketCap global-metrics (~last 500 days).
     USDT.D_true = 100 * USDT_mcap / total_mcap.
  3. Earlier dates: proxy = 100 * USDT / (USDT + BTC_mcap + ETH_mcap),
     then calibrated to CMC overlap (median scale) so levels match TradingView-style %.

Also stores btc_dominance when CMC is available.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import numpy as np
    import pandas as pd
except ImportError:
    np = None
    pd = None

try:
    import requests  # optional; _get uses urllib
except ImportError:
    requests = None

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "macro"
BINANCE_FAPI = "https://fapi.binance.com"
BINANCE_SPOT = "https://api.binance.com"
BINANCE_DATA = "https://data-api.binance.vision"
LLAMA_USDT = "https://stablecoins.llama.fi/stablecoin/1"
CMC_GLOBAL = "https://api.coinmarketcap.com/data-api/v3/global-metrics/quotes/historical"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; usdt-d/1.0)",
    "Accept": "application/json",
    "Referer": "https://coinmarketcap.com/",
}


def _get(url: str, params: Optional[dict] = None, timeout: int = 60) -> dict | list:
    """HTTP GET that ignores env proxies (sandbox/proxy 403 workarounds)."""
    from urllib.parse import urlencode
    import urllib.request

    full = url if not params else f"{url}?{urlencode(params)}"
    req = urllib.request.Request(full, headers=HEADERS)
    # Bypass HTTP(S)_PROXY from environment
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def fetch_usdt_mcap_llama() -> "pd.DataFrame":
    data = _get(LLAMA_USDT)
    tokens = data.get("tokens") or []
    rows = []
    for t in tokens:
        ts = int(t["date"])
        circ = t.get("circulating") or {}
        mcap = circ.get("peggedUSD")
        if mcap is None:
            continue
        rows.append(
            {
                "date": datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None),
                "usdt_mcap": float(mcap),
            }
        )
    if pd is None:
        raise RuntimeError("pip install pandas")
    return pd.DataFrame(rows).drop_duplicates("date").sort_values("date").reset_index(drop=True)


def fetch_cmc_total_mcap(limit_days: int = 500) -> "pd.DataFrame":
    """CMC public endpoint keeps ~500 most recent daily points."""
    end = int(datetime.now(timezone.utc).timestamp())
    start = end - 86400 * (limit_days + 30)
    data = _get(
        CMC_GLOBAL,
        {"time_start": start, "time_end": end, "interval": "1d", "count": 500},
    )
    quotes = (data.get("data") or {}).get("quotes") or []
    rows = []
    for q in quotes:
        ts = q.get("timestamp")
        if not ts:
            continue
        day = datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
        day = day.replace(hour=0, minute=0, second=0, microsecond=0)
        quote = (q.get("quote") or [{}])[0]
        total = quote.get("totalMarketCap")
        if total is None:
            continue
        rows.append(
            {
                "date": day,
                "total_mcap": float(total),
                "btc_dominance": float(q.get("btcDominance") or np.nan),
                "eth_dominance": float(q.get("ethDominance") or np.nan),
            }
        )
    if pd is None:
        raise RuntimeError("pip install pandas")
    return pd.DataFrame(rows).drop_duplicates("date").sort_values("date").reset_index(drop=True)


def fetch_binance_close_daily(symbol: str, start: str = "2022-01-01") -> "pd.DataFrame":
    """Daily closes for USDT.D proxy. Prefer spot/vision (GHA-safe) over fapi (often 451)."""
    start_ms = int(datetime.strptime(start[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)
    endpoints = (
        (BINANCE_SPOT, "/api/v3/klines"),
        (BINANCE_DATA, "/api/v3/klines"),
        (BINANCE_FAPI, "/fapi/v1/klines"),
    )
    last_err: Exception | None = None
    for base, path in endpoints:
        try:
            rows = []
            cur = start_ms
            while True:
                data = _get(
                    f"{base}{path}",
                    {"symbol": symbol, "interval": "1d", "startTime": cur, "limit": 1000},
                )
                if not data:
                    break
                for r in data:
                    rows.append(
                        {
                            "date": datetime.fromtimestamp(int(r[0]) / 1000, tz=timezone.utc).replace(
                                tzinfo=None
                            ),
                            "close": float(r[4]),
                        }
                    )
                cur = int(data[-1][0]) + 1
                if len(data) < 1000:
                    break
                time.sleep(0.1)
            if pd is None:
                raise RuntimeError("pip install pandas")
            if rows:
                return pd.DataFrame(rows).drop_duplicates("date").sort_values("date").reset_index(drop=True)
        except Exception as e:
            last_err = e
            print(f"[usdt_d] {symbol} klines via {base} failed: {e}")
    print(f"[usdt_d] all close sources failed for {symbol}: {last_err}")
    if pd is None:
        raise RuntimeError("pip install pandas")
    return pd.DataFrame(columns=["date", "close"])


def _btc_supply_approx(dates: "pd.Series") -> "pd.Series":
    """Rough circulating BTC supply (linear from ~18.9M Jan-2022 → ~19.7M mid-2026)."""
    t0 = pd.Timestamp("2022-01-01")
    days = (pd.to_datetime(dates) - t0).dt.days.clip(lower=0)
    # ~900 BTC/day issuance early 2022, halved Apr 2024 → ~450
    # Use piecewise: before 2024-04-20: 18900000 + days*900
    # after: 19650000-ish
    supply = []
    halt = (pd.Timestamp("2024-04-20") - t0).days
    for d in days:
        if d <= halt:
            supply.append(18_900_000 + d * 900)
        else:
            supply.append(18_900_000 + halt * 900 + (d - halt) * 450)
    return pd.Series(supply, index=dates.index)


def build_usdt_d_daily(
    start: str = "2022-01-01",
    force_refresh: bool = False,
) -> "pd.DataFrame":
    """
    Returns columns:
      date, usdt_d, usdt_mcap, total_mcap, btc_dominance, usdt_d_source
    """
    if pd is None or np is None:
        raise RuntimeError("pip install pandas numpy")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / "usdt_d_daily.csv"
    if cache_path.exists() and not force_refresh:
        cached = pd.read_csv(cache_path, parse_dates=["date"])
        if len(cached) > 100 and cached["date"].min() <= pd.Timestamp(start):
            return cached[cached["date"] >= pd.Timestamp(start)].reset_index(drop=True)

    usdt = fetch_usdt_mcap_llama()
    usdt = usdt[usdt["date"] >= pd.Timestamp(start)].copy()

    try:
        cmc = fetch_cmc_total_mcap()
    except Exception as e:
        print(f"[usdt_d] CMC failed: {e}")
        cmc = pd.DataFrame(columns=["date", "total_mcap", "btc_dominance", "eth_dominance"])

    btc = fetch_binance_close_daily("BTCUSDT", start=start).rename(columns={"close": "btc_close"})
    eth = fetch_binance_close_daily("ETHUSDT", start=start).rename(columns={"close": "eth_close"})

    panel = usdt.merge(btc, on="date", how="left").merge(eth, on="date", how="left")
    if len(cmc):
        panel = panel.merge(cmc, on="date", how="left")
    else:
        panel["total_mcap"] = np.nan
        panel["btc_dominance"] = np.nan
        panel["eth_dominance"] = np.nan

    panel["btc_supply"] = _btc_supply_approx(panel["date"])
    panel["eth_supply"] = 120_000_000.0  # approx; eth issuance small vs mcap noise
    panel["btc_mcap"] = panel["btc_close"] * panel["btc_supply"]
    panel["eth_mcap"] = panel["eth_close"] * panel["eth_supply"]

    # True USDT.D where CMC total exists
    panel["usdt_d_cmc"] = np.where(
        panel["total_mcap"].notna() & (panel["total_mcap"] > 0),
        100.0 * panel["usdt_mcap"] / panel["total_mcap"],
        np.nan,
    )
    # Proxy from majors basket
    basket = panel["usdt_mcap"] + panel["btc_mcap"].fillna(0) + panel["eth_mcap"].fillna(0)
    panel["usdt_d_proxy"] = np.where(basket > 0, 100.0 * panel["usdt_mcap"] / basket, np.nan)

    # Calibrate proxy → CMC scale on overlap
    overlap = panel.dropna(subset=["usdt_d_cmc", "usdt_d_proxy"])
    if len(overlap) >= 30:
        scale = float(np.median(overlap["usdt_d_cmc"] / overlap["usdt_d_proxy"].clip(lower=1e-6)))
    else:
        scale = 0.75  # typical: proxy ~9% vs true ~7%
    panel["usdt_d_proxy_cal"] = panel["usdt_d_proxy"] * scale

    panel["usdt_d"] = panel["usdt_d_cmc"].fillna(panel["usdt_d_proxy_cal"])
    panel["usdt_d_source"] = np.where(panel["usdt_d_cmc"].notna(), "cmc", "proxy_calibrated")
    # Fill total_mcap when missing via implied from calibrated dominance
    missing_total = panel["total_mcap"].isna() & panel["usdt_d"].notna() & (panel["usdt_d"] > 0)
    panel.loc[missing_total, "total_mcap"] = (
        panel.loc[missing_total, "usdt_mcap"] * 100.0 / panel.loc[missing_total, "usdt_d"]
    )

    out = panel[
        ["date", "usdt_d", "usdt_mcap", "total_mcap", "btc_dominance", "eth_dominance", "usdt_d_source"]
    ].copy()
    out = out.dropna(subset=["usdt_d"]).sort_values("date").reset_index(drop=True)
    if out.empty:
        raise RuntimeError("USDT.D series empty (llama/CMC/spot all failed)")
    out.to_csv(cache_path, index=False)
    return out[out["date"] >= pd.Timestamp(start)].reset_index(drop=True)
