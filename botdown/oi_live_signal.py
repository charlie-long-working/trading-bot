"""
Live OI + USDT.D alerts for H1 / H4 (strategies I + K only).

Lightweight recent panel → enrich → active scenarios → OiAlert.
Not investment advice.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

try:
    import pandas as pd
except ImportError:
    pd = None

from botdown.oi_liq_strategy import (
    TF_DEFAULTS,
    enrich_features,
    signal_oi_usdtd_confluence,
    signal_usdtd_risk_off_short,
)
from data_loaders.oi_history import build_oi_panel_recent

# Live playbook: K primary, I secondary (no G on H1/H4)
LIVE_SCENARIOS = [
    ("K_oi_usdtd_confluence", "OI + USDT.D + EMA confluence", signal_oi_usdtd_confluence),
    ("I_usdtd_risk_off_short", "USDT.D↑ risk-off + fund+ → SHORT", signal_usdtd_risk_off_short),
]

DEFAULT_LOOKBACK = {"1h": 800, "4h": 500, "1d": 400}


@dataclass
class OiAlert:
    symbol: str
    interval: str
    side: str  # long | short | none
    bar_time: str
    close: float
    scenarios: List[Dict[str, str]] = field(default_factory=list)
    tp_pct: float = 0.0
    sl_pct: float = 0.0
    entry: Optional[float] = None
    stop: Optional[float] = None
    target: Optional[float] = None
    features: Dict[str, Any] = field(default_factory=dict)
    liq: Optional[Dict[str, Any]] = None

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _fmt_bar(ts, interval: str) -> str:
    t = pd.Timestamp(ts)
    if interval == "1d":
        return str(t.date())
    return t.strftime("%Y-%m-%d %H:%M")


def _levels(close: float, side: str, tp_pct: float, sl_pct: float) -> tuple[float, float, float]:
    entry = close
    if side == "long":
        return entry, entry * (1 - sl_pct), entry * (1 + tp_pct)
    if side == "short":
        return entry, entry * (1 + sl_pct), entry * (1 - tp_pct)
    return entry, entry, entry


def scan_oi_live(
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    lookback_bars: Optional[int] = None,
    include_liq: bool = True,
    panel: Optional["pd.DataFrame"] = None,
) -> OiAlert:
    """
    Build recent panel (or use provided), evaluate I + K on last closed-style bar.
    Uses last row of enriched panel (caller should run after candle close).
    """
    if pd is None:
        raise RuntimeError("pip install pandas")
    if interval not in TF_DEFAULTS:
        raise ValueError(f"interval must be one of {list(TF_DEFAULTS)}")

    cfg = TF_DEFAULTS[interval]
    bpd = int(cfg["bars_per_day"])
    tp, sl = float(cfg["tp"]), float(cfg["sl"])
    n_bars = lookback_bars or DEFAULT_LOOKBACK.get(interval, 800)

    if panel is None:
        panel = build_oi_panel_recent(symbol, interval=interval, lookback_bars=n_bars)

    df = enrich_features(panel, bars_per_day=bpd)
    need = ["oi_z_30", "fund_z_30", "ema50"]
    if "usdt_d_z_30" in df.columns:
        need.append("usdt_d_z_30")
    df = df.dropna(subset=[c for c in need if c in df.columns]).reset_index(drop=True)
    if len(df) < 50:
        return OiAlert(
            symbol=symbol,
            interval=interval,
            side="none",
            bar_time="",
            close=0.0,
            features={"error": "insufficient_bars", "n": len(df)},
        )

    row = df.iloc[-1]
    active: List[Dict[str, str]] = []
    for name, desc, fn in LIVE_SCENARIOS:
        sig = fn(df)
        v = int(sig.iloc[-1])
        if v == 0:
            continue
        side = "long" if v > 0 else "short"
        active.append({"scenario": name, "side": side, "desc": desc})

    # Prefer K if present; else I
    side = "none"
    if active:
        k = [a for a in active if a["scenario"].startswith("K_")]
        pick = k[0] if k else active[0]
        side = pick["side"]

    close = float(row["close"])
    entry, stop, target = _levels(close, side, tp, sl) if side != "none" else (close, None, None)

    regime = "bull" if bool(row["bull"]) else ("bear" if bool(row["bear"]) else "neutral")
    feats = {
        "oi_chg_3_pct": round(100 * float(row["oi_chg_3"]), 2) if pd.notna(row.get("oi_chg_3")) else None,
        "oi_z_30": round(float(row["oi_z_30"]), 2) if pd.notna(row.get("oi_z_30")) else None,
        "funding_z_30": round(float(row["fund_z_30"]), 2) if pd.notna(row.get("fund_z_30")) else None,
        "usdt_d": round(float(row["usdt_d"]), 3) if pd.notna(row.get("usdt_d")) else None,
        "usdt_d_chg_3": round(float(row["usdt_d_chg_3"]), 3) if pd.notna(row.get("usdt_d_chg_3")) else None,
        "usdt_d_z_30": round(float(row["usdt_d_z_30"]), 2) if pd.notna(row.get("usdt_d_z_30")) else None,
        "usdtd_risk_off": bool(row["usdtd_risk_off"]) if "usdtd_risk_off" in df.columns else False,
        "usdtd_risk_on": bool(row["usdtd_risk_on"]) if "usdtd_risk_on" in df.columns else False,
        "regime_ema": regime,
        "bars_per_day": bpd,
    }

    liq_summary = None
    if include_liq and side != "none":
        try:
            from data_loaders.liquidation_map import fetch_liquidation_map
            snap = fetch_liquidation_map(symbol)
            liq_summary = {
                k: snap.summary().get(k)
                for k in (
                    "mark", "vote_side", "vote_reason",
                    "nearest_long_cluster", "nearest_short_cluster", "source", "error",
                )
            }
            # Prefer liq clusters for stop/target when available
            nl = (liq_summary.get("nearest_long_cluster") or {}).get("mid")
            ns = (liq_summary.get("nearest_short_cluster") or {}).get("mid")
            if side == "short" and ns is not None:
                stop = float(ns)
            if side == "short" and nl is not None:
                target = float(nl)
            if side == "long" and nl is not None:
                stop = float(nl)
            if side == "long" and ns is not None:
                target = float(ns)
        except Exception as e:
            liq_summary = {"error": str(e)}

    return OiAlert(
        symbol=symbol,
        interval=interval,
        side=side,
        bar_time=_fmt_bar(row["date"], interval),
        close=round(close, 2),
        scenarios=active,
        tp_pct=tp,
        sl_pct=sl,
        entry=round(entry, 2) if entry is not None else None,
        stop=round(stop, 2) if stop is not None else None,
        target=round(target, 2) if target is not None else None,
        features=feats,
        liq=liq_summary,
    )


def format_oi_telegram(alert: OiAlert) -> Optional[str]:
    """HTML message for Telegram; None if no side."""
    if alert.side == "none":
        return None
    side_u = alert.side.upper()
    tag = "🟢 LONG" if alert.side == "long" else "🔴 SHORT"
    scen_html = ", ".join(f"<code>{a['scenario']}</code>" for a in alert.scenarios) or "—"
    f = alert.features
    rr_line = ""
    if alert.sl_pct:
        rr_line = (
            f"Plan exit: TP {alert.tp_pct*100:.1f}% / SL {alert.sl_pct*100:.1f}% "
            f"(R:R {alert.tp_pct/alert.sl_pct:.2f}:1)"
        )
    lines = [
        f"<b>{tag}</b> {alert.symbol} · <b>{alert.interval}</b>",
        f"Bar: <code>{alert.bar_time}</code>",
        "",
        f"Close: <code>{alert.close:,.2f}</code>",
        f"Entry~ <code>{alert.entry}</code> | SL <code>{alert.stop}</code> | TP <code>{alert.target}</code>",
    ]
    if rr_line:
        lines.append(rr_line)
    lines.extend([
        "",
        f"Scenarios: {scen_html}",
        f"OI Δ3d: {f.get('oi_chg_3_pct')}% | z30: {f.get('oi_z_30')} | fund z: {f.get('funding_z_30')}",
        f"USDT.D: {f.get('usdt_d')}% (Δ3d {f.get('usdt_d_chg_3')}, z {f.get('usdt_d_z_30')})",
        f"EMA: <b>{f.get('regime_ema')}</b> | risk-off={f.get('usdtd_risk_off')} risk-on={f.get('usdtd_risk_on')}",
    ])
    liq = alert.liq or {}
    if liq and not liq.get("error"):
        nl = (liq.get("nearest_long_cluster") or {}).get("mid", "—")
        ns = (liq.get("nearest_short_cluster") or {}).get("mid", "—")
        lines.extend([
            "",
            "<b>Liq map</b>",
            f"Long cluster (below): <code>{nl}</code> | Short (above): <code>{ns}</code>",
            f"Vote: {liq.get('vote_side', 'none')} — {liq.get('vote_reason', '')}",
        ])
    lines.extend(["", "<i>ALERT ONLY — not investment advice. Playbook I+K H1/H4.</i>"])
    return "\n".join(lines)
