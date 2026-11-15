"""
Pure data layer for the live OI playbook (I + K) — no Streamlit import.

Used by:
  - botdown/dashboard_oi_playbook.py (Streamlit, local)
  - scripts/export_static_snapshot.py (static web on GitHub Pages)

Not investment advice.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from botdown.oi_liq_strategy import TF_DEFAULTS
from botdown.oi_live_signal import (
    DEFAULT_LOOKBACK,
    _drop_forming_bar,
    LIVE_SCENARIOS,
    SCENARIO_WHY,
    format_oi_telegram,
    scan_oi_live,
)

LIVE_SYMBOLS = ["BTCUSDT", "ETHUSDT"]
LIVE_INTERVALS = ["1h", "4h"]

PLAYBOOK_CAPTION = (
    "GitHub Actions · `oi-telegram-alerts.yml` · "
    "`python -m botdown.run_oi_telegram --interval auto` · symbols BTCUSDT, ETHUSDT"
)
EXIT_NOTE = "Entry ≈ close nến vừa đóng. SL/TP tính từ entry."
OPS_NOTES = [
    "Cron: mỗi giờ UTC `:05`",
    "`auto`: luôn **1h**; thêm **4h** khi `UTC hour % 4 == 0`",
    "Chỉ Telegram khi side ≠ `none`",
    "GHA dùng `--no-liq`",
    "Ưu tiên scenario **K** nếu cả K và I cùng fire",
]
DISCLAIMER = "ALERT ONLY — not investment advice"

# Columns exported for the static chart (last N bars of the scan panel)
SERIES_BARS = {"1h": 240, "4h": 180}


def playbook_data() -> Dict[str, Any]:
    """Scenarios / exit table / ops notes shown in the playbook panel."""
    scenarios = [
        {"name": name, "desc": desc, "why": SCENARIO_WHY.get(name, "")}
        for name, desc, _ in LIVE_SCENARIOS
    ]
    exits = []
    for tf, cfg in TF_DEFAULTS.items():
        if tf == "1d":
            continue  # live chỉ H1/H4
        exits.append(
            {
                "tf": tf,
                "tp_pct": round(cfg["tp"] * 100, 3),
                "sl_pct": round(cfg["sl"] * 100, 3),
                "rr": round(cfg["tp"] / cfg["sl"], 2),
                "max_hold_bars": int(cfg["max_hold"]),
            }
        )
    return {
        "caption": PLAYBOOK_CAPTION,
        "scenarios": scenarios,
        "exits": exits,
        "exit_note": EXIT_NOTE,
        "ops": list(OPS_NOTES),
        "disclaimer": DISCLAIMER,
    }


def _error_result(symbol: str, interval: str, exc: Exception) -> Dict[str, Any]:
    return {
        "symbol": symbol,
        "interval": interval,
        "side": "error",
        "ok": False,
        "error": str(exc),
        "error_type": type(exc).__name__,
        "features": {},
        "scenarios": [],
        "telegram_preview": None,
        "bar_time": "",
        "close": 0,
        "entry": None,
        "stop": None,
        "target": None,
        "tp_pct": 0,
        "sl_pct": 0,
    }


def _series_from_panel(panel, interval: str) -> Dict[str, List[Any]]:
    """Compact recent series for charts: epoch seconds + close / OI USD / funding / USDT.D."""
    import pandas as pd

    n = SERIES_BARS.get(interval, 200)
    # Same closed-bar view as the signal (drop the still-forming kline)
    df = _drop_forming_bar(panel.sort_values("date").reset_index(drop=True), interval).tail(n)

    def col(name: str, nd: int) -> List[Optional[float]]:
        if name not in df.columns:
            return [None] * len(df)
        out: List[Optional[float]] = []
        for v in df[name].tolist():
            try:
                fv = float(v)
            except (TypeError, ValueError):
                out.append(None)
                continue
            out.append(None if pd.isna(fv) else round(fv, nd))
        return out

    ts = pd.to_datetime(df["date"], utc=True)
    return {
        "t": [int(t.timestamp()) for t in ts],
        "close": col("close", 2),
        "oi_usd": col("oi_usd", 0),
        "funding": col("funding", 6),
        "usdt_d": col("usdt_d", 3),
    }


def scan_one(
    symbol: str,
    interval: str,
    lookback: int,
    include_series: bool = False,
) -> Dict[str, Any]:
    """
    Scan one symbol × TF. Never raises: on failure returns an `ok=False` row with
    `error=str(e)` (callers that publish must sanitize it).
    """
    try:
        panel = None
        if include_series:
            from data_loaders.oi_history import build_oi_panel_recent

            panel = build_oi_panel_recent(symbol, interval=interval, lookback_bars=lookback)
        alert = scan_oi_live(
            symbol,
            interval=interval,
            lookback_bars=lookback,
            include_liq=False,
            panel=panel,
        )
        d = alert.as_dict()
        d["telegram_preview"] = format_oi_telegram(alert)
        d["ok"] = True
        d["error"] = None
        if panel is not None:
            d["series"] = _series_from_panel(panel, interval)
            if "oi_source" in panel.columns and len(panel):
                d["oi_source"] = str(panel["oi_source"].iloc[-1])
        return d
    except Exception as e:
        return _error_result(symbol, interval, e)


def summary_rows(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Rows of the 'Tóm tắt' table."""
    return [
        {
            "Symbol": r.get("symbol"),
            "TF": r.get("interval"),
            "Side": r.get("side"),
            "Bar": r.get("bar_time"),
            "Entry": r.get("entry") or r.get("close"),
            "SL": r.get("stop"),
            "TP": r.get("target"),
            "Scenarios": ", ".join(s.get("scenario", "") for s in (r.get("scenarios") or [])),
        }
        for r in results
    ]


def scan_all(
    symbols: Optional[List[str]] = None,
    intervals: Optional[List[str]] = None,
    lookback: Optional[int] = None,
    include_series: bool = False,
) -> List[Dict[str, Any]]:
    """Scan every symbol × interval (default: live playbook set)."""
    out = []
    for sym in symbols or LIVE_SYMBOLS:
        for iv in intervals or LIVE_INTERVALS:
            lb = lookback or DEFAULT_LOOKBACK.get(iv, 400)
            out.append(scan_one(sym, iv, lb, include_series=include_series))
    return out
