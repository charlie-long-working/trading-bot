"""
Current long/short open interest estimated by liquidation-price buckets.

Primary (if COINGLASS_API_KEY): CoinGlass aggregated liquidation map.
Fallback: reconstruct from Binance + Bybit + OKX public OI, long/short ratio,
and 1h klines over the lookback window (Coinglass-style leverage mapping).

Long liquidations sit below mark (price drop cascades longs).
Short liquidations sit above mark (price rise squeezes shorts).
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests
except ImportError:
    requests = None

try:
    import pandas as pd
except ImportError:
    pd = None

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "liquidation"
REPORTS_DIR = ROOT / "botdown" / "reports"

COINGLASS_BASE = "https://open-api-v4.coinglass.com"
BINANCE_FAPI = "https://fapi.binance.com"
BYBIT = "https://api.bybit.com"
OKX = "https://www.okx.com"

# Typical BTC USDT-M leverage mix (weights sum to 1).
BTC_LEVERAGE_WEIGHTS: List[Tuple[float, float]] = [
    (5, 0.07),
    (10, 0.16),
    (15, 0.10),
    (20, 0.13),
    (25, 0.17),
    (50, 0.20),
    (75, 0.08),
    (100, 0.07),
    (125, 0.02),
]
BTC_MMR = 0.004
DEFAULT_LOOKBACK_HOURS = 72
DEFAULT_BIN_PCT = 0.005  # 0.5% of mark
NEAR_PCT = 0.03          # "nearby" window for the vote
RANGE_PCT = 0.15         # keep buckets within ±15% of mark
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; liquidation-map/1.0)"}


@dataclass
class LiqBucket:
    price_lo: float
    price_hi: float
    mid: float
    long_usd: float
    short_usd: float

    @property
    def total_usd(self) -> float:
        return self.long_usd + self.short_usd

    def as_dict(self, oi_usd: float) -> Dict[str, Any]:
        oi = oi_usd if oi_usd > 0 else 1.0
        return {
            "price_lo": round(self.price_lo, 2),
            "price_hi": round(self.price_hi, 2),
            "mid": round(self.mid, 2),
            "long_usd": round(self.long_usd, 2),
            "short_usd": round(self.short_usd, 2),
            "total_usd": round(self.total_usd, 2),
            "long_pct_oi": round(100.0 * self.long_usd / oi, 3),
            "short_pct_oi": round(100.0 * self.short_usd / oi, 3),
            "pct_from_mark": None,
        }


@dataclass
class LiqMapSnapshot:
    symbol: str
    mark: float
    ts_utc: str
    source: str
    lookback: str
    oi_usd: float
    long_frac: float
    short_frac: float
    exchanges: Dict[str, Dict[str, float]] = field(default_factory=dict)
    buckets: List[LiqBucket] = field(default_factory=list)
    nearby_long_usd: float = 0.0
    nearby_short_usd: float = 0.0
    nearest_long_cluster: Optional[Dict[str, Any]] = None
    nearest_short_cluster: Optional[Dict[str, Any]] = None
    max_pain: Optional[Dict[str, Any]] = None
    vote_side: str = "none"
    vote_confidence: float = 0.0
    vote_reason: str = ""
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    errors: List[str] = field(default_factory=list)

    def top_buckets(self, n: int = 12) -> List[Dict[str, Any]]:
        ranked = sorted(self.buckets, key=lambda b: b.total_usd, reverse=True)
        out = []
        for b in ranked[:n]:
            row = b.as_dict(self.oi_usd)
            row["pct_from_mark"] = round(100.0 * (b.mid / self.mark - 1.0), 3) if self.mark else None
            row["dominant"] = "long" if b.long_usd >= b.short_usd else "short"
            out.append(row)
        return out

    def buckets_table(self) -> List[Dict[str, Any]]:
        rows = []
        for b in sorted(self.buckets, key=lambda x: x.mid):
            if b.total_usd <= 0:
                continue
            row = b.as_dict(self.oi_usd)
            row["pct_from_mark"] = round(100.0 * (b.mid / self.mark - 1.0), 3) if self.mark else None
            row["dominant"] = "long" if b.long_usd >= b.short_usd else "short"
            rows.append(row)
        return rows

    def summary(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "mark": round(self.mark, 4),
            "ts_utc": self.ts_utc,
            "source": self.source,
            "lookback": self.lookback,
            "oi_usd": round(self.oi_usd, 2),
            "long_frac": round(self.long_frac, 4),
            "short_frac": round(self.short_frac, 4),
            "long_short_ratio": round(self.long_frac / self.short_frac, 4) if self.short_frac else None,
            "nearby_pct": NEAR_PCT,
            "nearby_long_usd": round(self.nearby_long_usd, 2),
            "nearby_short_usd": round(self.nearby_short_usd, 2),
            "nearby_long_pct_oi": round(100.0 * self.nearby_long_usd / self.oi_usd, 3) if self.oi_usd else 0,
            "nearby_short_pct_oi": round(100.0 * self.nearby_short_usd / self.oi_usd, 3) if self.oi_usd else 0,
            "nearest_long_cluster": self.nearest_long_cluster,
            "nearest_short_cluster": self.nearest_short_cluster,
            "max_pain": self.max_pain,
            "vote_side": self.vote_side,
            "vote_confidence": round(self.vote_confidence, 4),
            "vote_reason": self.vote_reason,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "exchanges": self.exchanges,
            "errors": self.errors,
            "top_clusters": self.top_buckets(12),
        }


def _get(url: str, params: Optional[dict] = None, headers: Optional[dict] = None, timeout: int = 20) -> Any:
    if requests is None:
        raise RuntimeError("pip install requests")
    h = dict(HEADERS)
    if headers:
        h.update(headers)
    r = requests.get(url, params=params, headers=h, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _coinglass_key() -> Optional[str]:
    return os.environ.get("COINGLASS_API_KEY") or os.environ.get("CG_API_KEY")


def _liq_long(entry: float, lev: float, mmr: float) -> float:
    return max(entry * (1.0 - 1.0 / lev + mmr), 0.0)


def _liq_short(entry: float, lev: float, mmr: float) -> float:
    return entry * (1.0 + 1.0 / lev - mmr)


def _bin_index(price: float, mark: float, bin_pct: float) -> int:
    step = mark * bin_pct
    if step <= 0:
        return 0
    return int(round(price / step))


def _empty_snapshot(symbol: str, lookback: str, errors: List[str]) -> LiqMapSnapshot:
    return LiqMapSnapshot(
        symbol=symbol,
        mark=0.0,
        ts_utc=datetime.now(timezone.utc).isoformat(),
        source="none",
        lookback=lookback,
        oi_usd=0.0,
        long_frac=0.5,
        short_frac=0.5,
        errors=errors,
        vote_reason="no_data",
    )


def _align_hourly(rows: List[Dict[str, Any]], key_ts: str = "ts") -> Dict[int, Dict[str, Any]]:
    out: Dict[int, Dict[str, Any]] = {}
    for r in rows:
        ts = int(r[key_ts])
        if ts > 10_000_000_000:
            ts = ts // 1000
        hour = ts - (ts % 3600)
        out[hour] = r
    return out


def _fetch_binance(symbol: str, hours: int) -> Dict[str, Any]:
    limit = min(max(hours, 2), 200)
    mark_j = _get(f"{BINANCE_FAPI}/fapi/v1/premiumIndex", {"symbol": symbol})
    oi_j = _get(f"{BINANCE_FAPI}/fapi/v1/openInterest", {"symbol": symbol})
    oi_h = _get(
        f"{BINANCE_FAPI}/futures/data/openInterestHist",
        {"symbol": symbol, "period": "1h", "limit": limit},
    )
    ls_h = _get(
        f"{BINANCE_FAPI}/futures/data/topLongShortPositionRatio",
        {"symbol": symbol, "period": "1h", "limit": limit},
    )
    kl = _get(
        f"{BINANCE_FAPI}/fapi/v1/klines",
        {"symbol": symbol, "interval": "1h", "limit": limit},
    )
    mark = float(mark_j["markPrice"])
    oi_btc = float(oi_j["openInterest"])
    oi_usd = oi_btc * mark
    last_ls = float(ls_h[-1]["longAccount"]) if ls_h else 0.5
    klines = []
    for row in kl:
        o, h, low, c = map(float, row[1:5])
        klines.append({
            "ts": int(row[0]) // 1000,
            "typical": (h + low + c) / 3.0,
            "quote_vol": float(row[7]),
        })
    oi_hist = [
        {"ts": int(x["timestamp"]) // 1000, "oi_usd": float(x["sumOpenInterestValue"])}
        for x in oi_h
    ]
    ls_hist = [
        {"ts": int(x["timestamp"]) // 1000, "long_frac": float(x["longAccount"])}
        for x in ls_h
    ]
    return {
        "exchange": "binance",
        "mark": mark,
        "oi_usd": oi_usd,
        "long_frac": last_ls,
        "klines": klines,
        "oi_hist": oi_hist,
        "ls_hist": ls_hist,
    }


def _fetch_bybit(symbol: str, hours: int) -> Dict[str, Any]:
    limit = min(max(hours, 2), 200)
    t = _get(f"{BYBIT}/v5/market/tickers", {"category": "linear", "symbol": symbol})
    row = t["result"]["list"][0]
    mark = float(row["markPrice"])
    oi_usd = float(row.get("openInterestValue") or 0)
    if oi_usd <= 0:
        oi_usd = float(row.get("openInterest") or 0) * mark
    oi_h = _get(
        f"{BYBIT}/v5/market/open-interest",
        {"category": "linear", "symbol": symbol, "intervalTime": "1h", "limit": limit},
    )
    ls_h = _get(
        f"{BYBIT}/v5/market/account-ratio",
        {"category": "linear", "symbol": symbol, "period": "1h", "limit": limit},
    )
    kl = _get(
        f"{BYBIT}/v5/market/kline",
        {"category": "linear", "symbol": symbol, "interval": "60", "limit": limit},
    )
    klines = []
    for item in kl["result"]["list"]:
        ts = int(item[0])
        if ts > 10_000_000_000:
            ts //= 1000
        o, h, low, c = map(float, item[1:5])
        vol = float(item[5]) if len(item) > 5 else 0.0
        klines.append({"ts": ts, "typical": (h + low + c) / 3.0, "quote_vol": vol * mark})
    klines.sort(key=lambda x: x["ts"])
    oi_hist = []
    for item in oi_h["result"]["list"]:
        ts = int(item["timestamp"])
        if ts > 10_000_000_000:
            ts //= 1000
        oi_hist.append({"ts": ts, "oi_usd": float(item["openInterest"]) * mark})
    ls_hist = []
    for item in ls_h["result"]["list"]:
        ts = int(item["timestamp"])
        if ts > 10_000_000_000:
            ts //= 1000
        ls_hist.append({"ts": ts, "long_frac": float(item["buyRatio"])})
    long_frac = ls_hist[-1]["long_frac"] if ls_hist else 0.5
    return {
        "exchange": "bybit",
        "mark": mark,
        "oi_usd": oi_usd,
        "long_frac": long_frac,
        "klines": klines,
        "oi_hist": oi_hist,
        "ls_hist": ls_hist,
    }


def _fetch_okx(inst_id: str, hours: int) -> Dict[str, Any]:
    limit = min(max(hours, 2), 100)
    mark_j = _get(f"{OKX}/api/v5/public/mark-price", {"instType": "SWAP", "instId": inst_id})
    oi_j = _get(f"{OKX}/api/v5/public/open-interest", {"instType": "SWAP", "instId": inst_id})
    ccy = inst_id.split("-")[0]
    ls_j = _get(
        f"{OKX}/api/v5/rubik/stat/contracts/long-short-account-ratio",
        {"ccy": ccy, "period": "1H"},
    )
    kl = _get(
        f"{OKX}/api/v5/market/candles",
        {"instId": inst_id, "bar": "1H", "limit": str(limit)},
    )
    mark = float(mark_j["data"][0]["markPx"])
    oi_usd = float(oi_j["data"][0].get("oiUsd") or 0)
    if oi_usd <= 0:
        oi_usd = float(oi_j["data"][0].get("oiCcy") or 0) * mark
    ls_hist = []
    for row in ls_j.get("data") or []:
        ts = int(row[0])
        if ts > 10_000_000_000:
            ts //= 1000
        ratio = float(row[1])  # long/short
        long_frac = ratio / (1.0 + ratio) if ratio >= 0 else 0.5
        ls_hist.append({"ts": ts, "long_frac": long_frac})
    ls_hist.sort(key=lambda x: x["ts"])
    klines = []
    for row in kl.get("data") or []:
        ts = int(row[0])
        if ts > 10_000_000_000:
            ts //= 1000
        o, h, low, c = map(float, row[1:5])
        vol_ccy = float(row[5]) if len(row) > 5 else 0.0
        klines.append({"ts": ts, "typical": (h + low + c) / 3.0, "quote_vol": vol_ccy * mark})
    klines.sort(key=lambda x: x["ts"])
    long_frac = ls_hist[-1]["long_frac"] if ls_hist else 0.5
    # OKX OI history is optional
    oi_hist = [{"ts": k["ts"], "oi_usd": oi_usd} for k in klines]
    try:
        oi_h = _get(
            f"{OKX}/api/v5/rubik/stat/contracts/open-interest-history",
            {"instId": inst_id, "period": "1H", "limit": str(limit)},
        )
        parsed = []
        for row in oi_h.get("data") or []:
            ts = int(row[0])
            if ts > 10_000_000_000:
                ts //= 1000
            val = float(row[1]) if len(row) > 1 else oi_usd
            parsed.append({"ts": ts, "oi_usd": val})
        if parsed:
            oi_hist = parsed
    except Exception:
        pass
    return {
        "exchange": "okx",
        "mark": mark,
        "oi_usd": oi_usd,
        "long_frac": long_frac,
        "klines": klines,
        "oi_hist": oi_hist,
        "ls_hist": ls_hist,
    }


def _reconstruct_exchange(
    pack: Dict[str, Any],
    mark: float,
    bin_pct: float,
    lev_weights: List[Tuple[float, float]],
    mmr: float,
) -> Dict[int, List[float]]:
    """Return {bin_index: [long_usd, short_usd]} for one exchange, scaled to that venue's OI."""
    k_map = _align_hourly(pack["klines"])
    oi_map = _align_hourly(pack["oi_hist"])
    ls_map = _align_hourly(pack["ls_hist"])
    hours = sorted(set(k_map) | set(oi_map) | set(ls_map))
    if not hours:
        hours = sorted(k_map)
    weights = []
    prev_oi = None
    cur_ls = float(pack.get("long_frac") or 0.5)
    for ts in hours:
        k = k_map.get(ts)
        oi = oi_map.get(ts)
        ls = ls_map.get(ts)
        if ls:
            cur_ls = float(ls["long_frac"])
        typical = float(k["typical"]) if k else mark
        qv = float(k["quote_vol"]) if k else 0.0
        oi_usd = float(oi["oi_usd"]) if oi else (prev_oi or 0.0)
        doi = max(0.0, oi_usd - prev_oi) if prev_oi is not None else 0.0
        prev_oi = oi_usd
        w = doi + 0.15 * qv
        if w <= 0:
            continue
        weights.append((typical, w, cur_ls))
    if not weights:
        # fallback: all OI at mark
        weights = [(mark, 1.0, float(pack.get("long_frac") or 0.5))]

    raw_long = sum(w * lf for _, w, lf in weights)
    raw_short = sum(w * (1.0 - lf) for _, w, lf in weights)
    target_oi = float(pack["oi_usd"])
    target_long = target_oi * float(pack.get("long_frac") or 0.5)
    target_short = target_oi - target_long
    sl = target_long / raw_long if raw_long > 0 else 0.0
    ss = target_short / raw_short if raw_short > 0 else 0.0

    acc: Dict[int, List[float]] = {}
    for entry, w, lf in weights:
        long_usd = w * lf * sl
        short_usd = w * (1.0 - lf) * ss
        for lev, lw in lev_weights:
            if long_usd > 0:
                idx = _bin_index(_liq_long(entry, lev, mmr), mark, bin_pct)
                acc.setdefault(idx, [0.0, 0.0])
                acc[idx][0] += long_usd * lw
            if short_usd > 0:
                idx = _bin_index(_liq_short(entry, lev, mmr), mark, bin_pct)
                acc.setdefault(idx, [0.0, 0.0])
                acc[idx][1] += short_usd * lw
    return acc


def _merge_bins(parts: List[Dict[int, List[float]]]) -> Dict[int, List[float]]:
    merged: Dict[int, List[float]] = {}
    for part in parts:
        for idx, pair in part.items():
            merged.setdefault(idx, [0.0, 0.0])
            merged[idx][0] += pair[0]
            merged[idx][1] += pair[1]
    return merged


def _bins_to_buckets(
    merged: Dict[int, List[float]],
    mark: float,
    bin_pct: float,
) -> List[LiqBucket]:
    step = mark * bin_pct
    lo_idx = _bin_index(mark * (1.0 - RANGE_PCT), mark, bin_pct)
    hi_idx = _bin_index(mark * (1.0 + RANGE_PCT), mark, bin_pct)
    buckets = []
    for idx in sorted(merged):
        if idx < lo_idx or idx > hi_idx:
            continue
        long_usd, short_usd = merged[idx]
        if long_usd + short_usd <= 0:
            continue
        mid = idx * step
        buckets.append(
            LiqBucket(
                price_lo=mid - step / 2.0,
                price_hi=mid + step / 2.0,
                mid=mid,
                long_usd=long_usd,
                short_usd=short_usd,
            )
        )
    return buckets


def _annotate(snap: LiqMapSnapshot) -> LiqMapSnapshot:
    mark = snap.mark
    if mark <= 0 or not snap.buckets:
        snap.vote_reason = snap.vote_reason or "no_buckets"
        return snap

    near_lo = mark * (1.0 - NEAR_PCT)
    near_hi = mark * (1.0 + NEAR_PCT)
    long_near = [b for b in snap.buckets if near_lo <= b.mid < mark]
    short_near = [b for b in snap.buckets if mark < b.mid <= near_hi]
    snap.nearby_long_usd = sum(b.long_usd for b in long_near)
    snap.nearby_short_usd = sum(b.short_usd for b in short_near)

    if long_near:
        best = max(long_near, key=lambda b: b.long_usd)
        snap.nearest_long_cluster = {
            "mid": round(best.mid, 2),
            "usd": round(best.long_usd, 2),
            "pct_from_mark": round(100.0 * (best.mid / mark - 1.0), 3),
        }
    if short_near:
        best = max(short_near, key=lambda b: b.short_usd)
        snap.nearest_short_cluster = {
            "mid": round(best.mid, 2),
            "usd": round(best.short_usd, 2),
            "pct_from_mark": round(100.0 * (best.mid / mark - 1.0), 3),
        }

    pain = max(snap.buckets, key=lambda b: b.total_usd)
    snap.max_pain = {
        "mid": round(pain.mid, 2),
        "usd": round(pain.total_usd, 2),
        "pct_from_mark": round(100.0 * (pain.mid / mark - 1.0), 3),
        "dominant": "long" if pain.long_usd >= pain.short_usd else "short",
    }

    a = snap.nearby_short_usd  # squeeze → long
    b = snap.nearby_long_usd   # cascade → short
    imb = max(a, b) / (min(a, b) + 1.0)
    # proximity of the dominant cluster
    prox = 0.0
    if a >= b and snap.nearest_short_cluster:
        prox = max(0.0, 1.0 - abs(snap.nearest_short_cluster["pct_from_mark"]) / (NEAR_PCT * 100))
    elif snap.nearest_long_cluster:
        prox = max(0.0, 1.0 - abs(snap.nearest_long_cluster["pct_from_mark"]) / (NEAR_PCT * 100))

    if a > b * 1.35 and a > 0:
        snap.vote_side = "long"
        snap.vote_reason = "short_squeeze_cluster"
        snap.take_profit = snap.nearest_short_cluster["mid"] if snap.nearest_short_cluster else None
        snap.stop_loss = snap.nearest_long_cluster["mid"] if snap.nearest_long_cluster else None
    elif b > a * 1.35 and b > 0:
        snap.vote_side = "short"
        snap.vote_reason = "long_cascade_cluster"
        snap.take_profit = snap.nearest_long_cluster["mid"] if snap.nearest_long_cluster else None
        snap.stop_loss = snap.nearest_short_cluster["mid"] if snap.nearest_short_cluster else None
    else:
        snap.vote_side = "none"
        snap.vote_reason = "balanced_liq_map"

    snap.vote_confidence = max(0.0, min(1.0, 0.42 + 0.16 * (imb - 1.0) + 0.28 * prox))
    if snap.vote_side == "none":
        snap.vote_confidence = min(snap.vote_confidence, 0.35)
    return snap


def _parse_coinglass_map(payload: Any, symbol: str, mark: float, lookback: str) -> Optional[LiqMapSnapshot]:
    if not isinstance(payload, dict) or str(payload.get("code")) not in ("0", "200"):
        return None
    data = payload.get("data") or {}
    raw = data.get("data") if isinstance(data, dict) else data
    if not isinstance(raw, dict) or not raw:
        # heatmap style: y_axis + liquidation_leverage_data
        y_axis = data.get("y_axis") if isinstance(data, dict) else None
        lev = data.get("liquidation_leverage_data") if isinstance(data, dict) else None
        if y_axis and lev:
            acc: Dict[int, List[float]] = {}
            for item in lev:
                if len(item) < 3:
                    continue
                y_i = int(item[1])
                usd = float(item[2])
                if y_i < 0 or y_i >= len(y_axis):
                    continue
                px = float(y_axis[y_i])
                idx = _bin_index(px, mark, DEFAULT_BIN_PCT)
                acc.setdefault(idx, [0.0, 0.0])
                if px < mark:
                    acc[idx][0] += usd
                else:
                    acc[idx][1] += usd
            buckets = _bins_to_buckets(acc, mark, DEFAULT_BIN_PCT)
            oi = sum(b.total_usd for b in buckets)
            long_usd = sum(b.long_usd for b in buckets)
            snap = LiqMapSnapshot(
                symbol=symbol,
                mark=mark,
                ts_utc=datetime.now(timezone.utc).isoformat(),
                source="coinglass_heatmap",
                lookback=lookback,
                oi_usd=oi,
                long_frac=(long_usd / oi) if oi else 0.5,
                short_frac=1.0 - ((long_usd / oi) if oi else 0.5),
                buckets=buckets,
            )
            return _annotate(snap)
        return None

    acc: Dict[int, List[float]] = {}
    for key, vals in raw.items():
        try:
            px = float(key)
        except (TypeError, ValueError):
            continue
        usd = 0.0
        long_usd = 0.0
        short_usd = 0.0
        if isinstance(vals, list) and vals:
            first = vals[0]
            if isinstance(first, list) and len(first) >= 2:
                usd = float(first[1] or 0)
                if len(first) >= 4 and first[2] is not None and first[3] is not None:
                    long_usd = float(first[2] or 0)
                    short_usd = float(first[3] or 0)
            elif isinstance(first, (int, float)):
                usd = float(first)
        if long_usd + short_usd <= 0:
            if px < mark:
                long_usd = usd
            else:
                short_usd = usd
        idx = _bin_index(px, mark, DEFAULT_BIN_PCT)
        acc.setdefault(idx, [0.0, 0.0])
        acc[idx][0] += long_usd
        acc[idx][1] += short_usd
    buckets = _bins_to_buckets(acc, mark, DEFAULT_BIN_PCT)
    oi = sum(b.total_usd for b in buckets)
    long_usd = sum(b.long_usd for b in buckets)
    snap = LiqMapSnapshot(
        symbol=symbol,
        mark=mark,
        ts_utc=datetime.now(timezone.utc).isoformat(),
        source="coinglass_map",
        lookback=lookback,
        oi_usd=oi,
        long_frac=(long_usd / oi) if oi else 0.5,
        short_frac=1.0 - ((long_usd / oi) if oi else 0.5),
        buckets=buckets,
    )
    return _annotate(snap)


def _try_coinglass(symbol_coin: str, mark: float, lookback: str) -> Tuple[Optional[LiqMapSnapshot], Optional[str]]:
    key = _coinglass_key()
    if not key:
        return None, None
    try:
        payload = _get(
            f"{COINGLASS_BASE}/api/futures/liquidation/aggregated-map",
            {"symbol": symbol_coin, "range": "1d" if lookback.endswith("h") else lookback},
            headers={"CG-API-KEY": key, "Accept": "application/json"},
        )
        snap = _parse_coinglass_map(payload, symbol_coin, mark, lookback)
        if snap:
            return snap, None
        return None, f"coinglass: {payload.get('msg') or 'empty'}"
    except Exception as e:
        return None, f"coinglass: {e}"


def _symbol_pack(symbol: str) -> Dict[str, str]:
    s = symbol.upper().replace("-", "").replace("/", "")
    if s.endswith("USDT"):
        coin = s[:-4]
    else:
        coin = s
        s = f"{s}USDT"
    okx = f"{coin}-USDT-SWAP"
    return {"binance": s, "bybit": s, "okx": okx, "coin": coin, "unified": s}


def fetch_liquidation_map(
    symbol: str = "BTCUSDT",
    lookback_hours: int = DEFAULT_LOOKBACK_HOURS,
    bin_pct: float = DEFAULT_BIN_PCT,
    use_coinglass: bool = True,
) -> LiqMapSnapshot:
    """
    Build current long/short liquidation-price buckets for a perpetual.
    """
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
        load_dotenv(ROOT.parent / "stock" / ".env")
    except ImportError:
        pass

    ids = _symbol_pack(symbol)
    lookback = f"{lookback_hours}h"
    errors: List[str] = []
    packs: List[Dict[str, Any]] = []

    jobs = {
        "binance": lambda: _fetch_binance(ids["binance"], lookback_hours),
        "bybit": lambda: _fetch_bybit(ids["bybit"], lookback_hours),
        "okx": lambda: _fetch_okx(ids["okx"], lookback_hours),
    }
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(fn): name for name, fn in jobs.items()}
        for fut in as_completed(futs):
            name = futs[fut]
            try:
                packs.append(fut.result())
            except Exception as e:
                errors.append(f"{name}: {e}")

    if not packs:
        return _empty_snapshot(ids["unified"], lookback, errors or ["all exchanges failed"])

    mark = sum(p["mark"] * p["oi_usd"] for p in packs) / max(sum(p["oi_usd"] for p in packs), 1.0)
    oi_usd = sum(p["oi_usd"] for p in packs)
    long_usd = sum(p["oi_usd"] * p["long_frac"] for p in packs)
    long_frac = long_usd / oi_usd if oi_usd else 0.5

    if use_coinglass:
        cg, cg_err = _try_coinglass(ids["coin"], mark, lookback)
        if cg_err:
            errors.append(cg_err)
        if cg:
            cg.exchanges = {p["exchange"]: {"mark": p["mark"], "oi_usd": p["oi_usd"], "long_frac": p["long_frac"]} for p in packs}
            cg.oi_usd = max(cg.oi_usd, oi_usd)
            cg.long_frac = long_frac
            cg.short_frac = 1.0 - long_frac
            cg.errors = errors
            return cg

    parts = [_reconstruct_exchange(p, mark, bin_pct, BTC_LEVERAGE_WEIGHTS, BTC_MMR) for p in packs]
    buckets = _bins_to_buckets(_merge_bins(parts), mark, bin_pct)
    snap = LiqMapSnapshot(
        symbol=ids["unified"],
        mark=mark,
        ts_utc=datetime.now(timezone.utc).isoformat(),
        source="reconstructed_oi_ls",
        lookback=lookback,
        oi_usd=oi_usd,
        long_frac=long_frac,
        short_frac=1.0 - long_frac,
        exchanges={p["exchange"]: {"mark": round(p["mark"], 4), "oi_usd": round(p["oi_usd"], 2), "long_frac": round(p["long_frac"], 4)} for p in packs},
        buckets=buckets,
        errors=errors,
    )
    return _annotate(snap)


def save_liquidation_reports(snap: LiqMapSnapshot, reports_dir: Optional[Path] = None) -> Dict[str, Path]:
    reports_dir = reports_dir or REPORTS_DIR
    reports_dir.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    stem = snap.symbol.lower()
    json_path = reports_dir / f"liquidation_map_{stem}.json"
    csv_path = reports_dir / f"liquidation_map_{stem}.csv"
    cache_path = CACHE_DIR / f"{stem}.json"

    payload = snap.summary()
    payload["buckets"] = snap.buckets_table()
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    json_path.write_text(text, encoding="utf-8")
    cache_path.write_text(text, encoding="utf-8")

    if pd is not None:
        rows = snap.buckets_table()
        pd.DataFrame(rows).to_csv(csv_path, index=False)
    else:
        csv_path = json_path

    return {"json": json_path, "csv": csv_path, "cache": cache_path}


def liquidation_vote_dict(snap: LiqMapSnapshot) -> Dict[str, Any]:
    return {
        "strategy": "liquidation_map",
        "side": snap.vote_side,
        "confidence": snap.vote_confidence,
        "reason": snap.vote_reason,
        "entry_price": snap.mark,
        "stop_loss": snap.stop_loss,
        "take_profit": snap.take_profit,
        "extra": {
            "source": snap.source,
            "nearby_long_usd": round(snap.nearby_long_usd, 2),
            "nearby_short_usd": round(snap.nearby_short_usd, 2),
            "nearest_long_cluster": snap.nearest_long_cluster,
            "nearest_short_cluster": snap.nearest_short_cluster,
            "max_pain": snap.max_pain,
            "long_frac": round(snap.long_frac, 4),
        },
    }
