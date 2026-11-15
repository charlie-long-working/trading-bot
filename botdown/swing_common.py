"""
Shared helpers for the local 1D/1W swing runners (crypto, VN stocks, metals).

Used by:
  - Trading-bot  botdown/run_swing_signals.py          (BTC/ETH)
  - stock        vn_stock/scripts/run_swing_vn.py      (VN stocks)
  - precious-metals precious/scripts/run_swing_metals.py (gold/silver)

Contents: weekly trend read-out (EMA20/50, Ichimoku cloud, MACD, RSI), a common
Signal record + Telegram HTML formatting (all dynamic text escaped), and a small
JSON dedupe store keyed by closed-bar time so catch-up runs after sleep are idempotent.

Weekly trend is a *context/filter*, not a trade signal: no 1W strategy has enough
backtested trades (see skill docs). Not investment advice.
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

from botdown.engine_macd_rsi_bt import _ema, _rsi_wilder

VN_TZ = timezone(timedelta(hours=7))
TG_LIMIT = 3900


def h(x: object) -> str:
    """Escape for Telegram parse_mode=HTML."""
    return html.escape(str(x), quote=False)


def now_vn() -> datetime:
    return datetime.now(VN_TZ)


# --------------------------------------------------------------------------- indicators

def macd_hist(close: np.ndarray, fast: int = 12, slow: int = 26, sig: int = 9) -> np.ndarray:
    line = _ema(close, fast) - _ema(close, slow)
    return line - _ema(line, sig)


def _mid(high: np.ndarray, low: np.ndarray, n: int) -> np.ndarray:
    hi = pd.Series(high).rolling(n).max().to_numpy()
    lo = pd.Series(low).rolling(n).min().to_numpy()
    return (hi + lo) / 2.0


def ichimoku_cloud(high: np.ndarray, low: np.ndarray, close: np.ndarray, disp: int = 26):
    """Cloud (span A/B) that sits under the *current* bar, i.e. spans computed `disp` bars ago."""
    tenkan = _mid(high, low, 9)
    kijun = _mid(high, low, 26)
    span_a = (tenkan + kijun) / 2.0
    span_b = _mid(high, low, 52)
    n = len(close)
    top = np.full(n, np.nan)
    bot = np.full(n, np.nan)
    if n > disp:
        a = span_a[:-disp]
        b = span_b[:-disp]
        top[disp:] = np.fmax(a, b)
        bot[disp:] = np.fmin(a, b)
    return top, bot


def resample_ohlc(df: pd.DataFrame, rule: str, time_col: str = "date") -> pd.DataFrame:
    """Daily OHLC(V) → weekly. rule e.g. 'W-SUN' (crypto, Mon–Sun weeks) or 'W-FRI' (VN)."""
    d = df.copy()
    d[time_col] = pd.to_datetime(d[time_col])
    d = d.set_index(time_col).sort_index()
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    if "volume" in d.columns:
        agg["volume"] = "sum"
    w = d.resample(rule).agg(agg).dropna(subset=["close"])
    return w.reset_index().rename(columns={time_col: "week_end"})


def weekly_trend(high: Sequence[float], low: Sequence[float], close: Sequence[float]) -> Optional[Dict]:
    """
    Read-out of the last *closed* weekly bar (caller drops the forming week).
    Bias score = ±1 each for: close vs EMA20, EMA20 vs EMA50, position vs cloud, MACD hist sign.
    ≥ +2 → Tăng, ≤ −2 → Giảm, else Trung tính. Untested as a filter — context only.
    """
    hi, lo, cl = (np.asarray(x, dtype=float) for x in (high, low, close))
    n = len(cl)
    if n < 55:
        return None
    e20, e50 = _ema(cl, 20), _ema(cl, 50)
    hist = macd_hist(cl)
    rsi = _rsi_wilder(cl, 14)
    top, bot = ichimoku_cloud(hi, lo, cl)
    i = n - 1
    c = cl[i]
    score = 0
    score += 1 if c > e20[i] else -1
    score += 1 if e20[i] > e50[i] else -1
    cloud = None
    if not np.isnan(top[i]):
        if c > top[i]:
            cloud, score = "trên mây", score + 1
        elif c < bot[i]:
            cloud, score = "dưới mây", score - 1
        else:
            cloud = "trong mây"
    score += 1 if hist[i] > 0 else -1
    bias = "Tăng" if score >= 2 else ("Giảm" if score <= -2 else "Trung tính")
    chg4 = (c / cl[i - 4] - 1.0) * 100.0 if n > 4 and cl[i - 4] else None
    return {
        "close": float(c),
        "chg_4w_pct": None if chg4 is None else round(float(chg4), 1),
        "ema20_gt_ema50": bool(e20[i] > e50[i]),
        "above_ema20": bool(c > e20[i]),
        "cloud": cloud,
        "macd_hist": float(hist[i]),
        "macd_rising": bool(hist[i] > hist[i - 1]),
        "rsi": round(float(rsi[i]), 1),
        "score": int(score),
        "bias": bias,
    }


def trend_line(t: Optional[Dict]) -> str:
    if not t:
        return "chưa đủ dữ liệu tuần"
    parts = [
        f"{t['bias']} ({t['score']:+d})",
        "EMA20>EMA50" if t["ema20_gt_ema50"] else "EMA20<EMA50",
    ]
    if t.get("cloud"):
        parts.append(t["cloud"])
    parts.append(f"MACD {'+' if t['macd_hist'] > 0 else '−'}{'↑' if t['macd_rising'] else '↓'}")
    parts.append(f"RSI {t['rsi']:.0f}")
    return " · ".join(parts)


# --------------------------------------------------------------------------- signals

@dataclass
class Signal:
    asset: str                    # crypto | vn | metals
    symbol: str
    tf: str                       # 1D
    side: str                     # long | short
    strategy: str                 # e.g. G_regime_crowdfade, macd_rsi_atr
    rule: str                     # human-readable trigger
    bar_time: str                 # closed bar (date)
    entry: float
    stop: Optional[float]
    target: Optional[float]
    max_hold: Optional[str] = None
    evidence: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    decimals: int = 2
    unit: str = ""

    @property
    def key(self) -> str:
        return f"{self.symbol}|{self.tf}|{self.bar_time}|{self.strategy}|{self.side}"

    def px(self, x: Optional[float]) -> str:
        return "—" if x is None else f"{x:,.{self.decimals}f}"


def _pct(a: float, b: Optional[float]) -> str:
    if b is None or not a:
        return ""
    return f" ({(b / a - 1) * 100:+.1f}%)"


def format_signal(sig: Signal, weekly: Optional[Dict] = None) -> str:
    tag = "🟢 LONG" if sig.side == "long" else "🔴 SHORT"
    rr = ""
    if sig.stop is not None and sig.target is not None and sig.entry != sig.stop:
        rr = f" · R:R {abs(sig.target - sig.entry) / abs(sig.entry - sig.stop):.2f}"
    lines = [
        f"<b>{tag}</b> {h(sig.symbol)} · <b>{h(sig.tf)}</b> · <code>{h(sig.strategy)}</code>",
        f"Nến đóng: <code>{h(sig.bar_time)}</code> · gửi {now_vn():%d/%m %H:%M} VN",
        "",
        f"Entry <code>{sig.px(sig.entry)}</code>{h(' ' + sig.unit) if sig.unit else ''}",
        f"SL <code>{sig.px(sig.stop)}</code>{_pct(sig.entry, sig.stop)} · "
        f"TP <code>{sig.px(sig.target)}</code>{_pct(sig.entry, sig.target)}{rr}",
    ]
    if sig.max_hold:
        lines.append(f"Giữ tối đa: {h(sig.max_hold)}")
    lines += ["", f"Điều kiện: {h(sig.rule)}"]
    if weekly is not None:
        lines.append(f"Xu hướng tuần: {h(trend_line(weekly))}")
    for n in sig.notes:
        lines.append(f"• {h(n)}")
    if sig.evidence:
        lines.append(f"<i>Backtest: {h(sig.evidence)}</i>")
    lines.append("<i>ALERT ONLY — không phải lời khuyên đầu tư.</i>")
    return "\n".join(lines)


def format_weekly(title: str, rows: Iterable[tuple], footer: Optional[str] = None) -> str:
    """rows: (label, trend_dict, extra_text_or_None)."""
    rows = list(rows)
    up = sum(1 for _, t, _ in rows if t and t["bias"] == "Tăng")
    dn = sum(1 for _, t, _ in rows if t and t["bias"] == "Giảm")
    lines = [f"📅 <b>{h(title)}</b>", f"Tăng {up} · Giảm {dn} · Trung tính/thiếu dữ liệu {len(rows) - up - dn}", ""]
    for label, t, extra in rows:
        chg = f" · 4 tuần {t['chg_4w_pct']:+.1f}%" if t and t.get("chg_4w_pct") is not None else ""
        lines.append(f"<b>{h(label)}</b>: {h(trend_line(t))}{h(chg)}{(' · ' + h(extra)) if extra else ''}")
    lines += ["", "<i>Xu hướng tuần = bộ lọc bối cảnh cho lệnh 1D, chưa backtest như tín hiệu riêng.</i>"]
    if footer:
        lines.append(f"<i>{h(footer)}</i>")
    return "\n".join(lines)


def _split_block(b: str) -> List[str]:
    """Oversized block → pieces at line boundaries (a single line is never cut)."""
    if len(b) <= TG_LIMIT:
        return [b]
    pieces, buf = [], ""
    for line in b.split("\n"):
        if buf and len(buf) + len(line) + 1 > TG_LIMIT:
            pieces.append(buf)
            buf = line
        else:
            buf = f"{buf}\n{line}" if buf else line
    pieces.append(buf)
    return pieces


def split_messages(blocks: List[str], header: str = "") -> List[str]:
    msgs, cur = [], header
    for b in (p for blk in blocks for p in _split_block(blk)):
        if cur and len(cur) + len(b) + 2 > TG_LIMIT:
            msgs.append(cur)
            cur = b
        else:
            cur = f"{cur}\n\n{b}" if cur else b
    if cur:
        msgs.append(cur)
    return msgs


# --------------------------------------------------------------------------- dedupe

class SentStore:
    """Keys of messages already sent (closed-bar keyed) → idempotent catch-up runs."""

    def __init__(self, path: Path, max_keys: int = 2000):
        self.path = Path(path)
        self.max_keys = max_keys
        try:
            self.keys: List[str] = list(json.loads(self.path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            self.keys = []
        self._set = set(self.keys)

    def __contains__(self, key: str) -> bool:
        return key in self._set

    def add(self, key: str) -> None:
        if key not in self._set:
            self.keys.append(key)
            self._set.add(key)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.keys[-self.max_keys:], ensure_ascii=False, indent=0), encoding="utf-8")


def deliver(messages: List[str], send: Callable[[str], tuple], dry_run: bool) -> bool:
    """Send each message (or print when dry_run). Returns True if all succeeded."""
    ok_all = True
    for m in messages:
        if dry_run:
            print(m)
            print("-" * 40)
            continue
        ok, err = send(m)
        if not ok:
            ok_all = False
            print(f"SEND FAIL: {err}")
    return ok_all
