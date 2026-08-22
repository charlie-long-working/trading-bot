"""
Streamlit dashboard — live OI playbook (I + K) currently applied on GHA/Telegram.

  cd Trading-bot
  PYTHONPATH=. streamlit run botdown/dashboard_oi_playbook.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from botdown.oi_liq_strategy import TF_DEFAULTS
from botdown.oi_live_signal import (
    LIVE_SCENARIOS,
    SCENARIO_WHY,
    format_oi_telegram,
    scan_oi_live,
)

st.set_page_config(
    page_title="OI Playbook Live",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# Flat, readable — no purple gradient theme
st.markdown(
    """
    <style>
      .block-container { padding-top: 1.5rem; max-width: 1100px; }
      h1, h2, h3 { font-weight: 600; letter-spacing: -0.02em; }
      div[data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _playbook_panel() -> None:
    st.header("Strategy đang apply (live)")
    st.caption(
        "GitHub Actions · `oi-telegram-alerts.yml` · "
        "`python -m botdown.run_oi_telegram --interval auto` · symbols BTCUSDT, ETHUSDT"
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("Scenarios")
        for name, desc, _ in LIVE_SCENARIOS:
            st.markdown(f"**`{name}`**")
            st.write(desc)
            why = SCENARIO_WHY.get(name, "")
            if why:
                st.caption(why)
            st.divider()
    with c2:
        st.subheader("Exit (theo TF)")
        rows = []
        for tf, cfg in TF_DEFAULTS.items():
            if tf == "1d":
                continue  # live chỉ H1/H4
            rows.append(
                {
                    "TF": tf,
                    "TP %": f"{cfg['tp']*100:.1f}",
                    "SL %": f"{cfg['sl']*100:.1f}",
                    "R:R": f"{cfg['tp']/cfg['sl']:.2f}",
                    "Max hold (bars)": cfg["max_hold"],
                }
            )
        st.dataframe(rows, hide_index=True, use_container_width=True)
        st.caption("Entry ≈ close nến vừa đóng. SL/TP tính từ entry.")
    with c3:
        st.subheader("Ops")
        st.markdown(
            """
            - Cron: mỗi giờ UTC `:05`
            - `auto`: luôn **1h**; thêm **4h** khi `UTC hour % 4 == 0`
            - Chỉ Telegram khi side ≠ `none`
            - GHA dùng `--no-liq`
            - Ưu tiên scenario **K** nếu cả K và I cùng fire
            """
        )


def _scan_one(symbol: str, interval: str, lookback: int) -> dict:
    try:
        alert = scan_oi_live(
            symbol,
            interval=interval,
            lookback_bars=lookback,
            include_liq=False,
        )
        d = alert.as_dict()
        d["telegram_preview"] = format_oi_telegram(alert)
        d["ok"] = True
        d["error"] = None
        return d
    except Exception as e:
        return {
            "symbol": symbol,
            "interval": interval,
            "side": "error",
            "ok": False,
            "error": str(e),
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


def _signal_card(d: dict) -> None:
    title = f"{d.get('symbol')} · {d.get('interval')}"
    if not d.get("ok"):
        st.error(f"{title}: {d.get('error')}")
        return
    feat_err = (d.get("features") or {}).get("error")
    if feat_err:
        st.warning(f"{title}: {feat_err}")
        return

    side = d.get("side") or "none"
    if side == "long":
        st.success(f"**LONG** · {title}")
    elif side == "short":
        st.error(f"**SHORT** · {title}")
    else:
        st.info(f"**none** · {title} — không vào lệnh")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Bar", d.get("bar_time") or "—")
    m2.metric("Close / Entry", f"{float(d.get('close') or 0):,.2f}")
    stop = d.get("stop")
    target = d.get("target")
    m3.metric("SL", f"{float(stop):,.2f}" if stop is not None else "—")
    m4.metric("TP", f"{float(target):,.2f}" if target is not None else "—")

    tp, sl = float(d.get("tp_pct") or 0), float(d.get("sl_pct") or 0)
    if sl:
        st.caption(f"Plan: TP {tp*100:.1f}% / SL {sl*100:.1f}% · R:R {tp/sl:.2f}:1")

    scens = d.get("scenarios") or []
    if scens:
        st.markdown("**Triggers**")
        for s in scens:
            st.write(f"- `{s.get('scenario')}` ({s.get('side')}) — {s.get('desc')}")

    f = d.get("features") or {}
    if f and not f.get("error"):
        st.markdown("**Snapshot**")
        st.dataframe(
            [
                {
                    "OI Δ3d %": f.get("oi_chg_3_pct"),
                    "OI z30": f.get("oi_z_30"),
                    "Fund z": f.get("funding_z_30"),
                    "USDT.D": f.get("usdt_d"),
                    "USDT.D Δ3d": f.get("usdt_d_chg_3"),
                    "USDT.D z": f.get("usdt_d_z_30"),
                    "EMA": f.get("regime_ema"),
                    "risk-off": f.get("usdtd_risk_off"),
                    "risk-on": f.get("usdtd_risk_on"),
                }
            ],
            hide_index=True,
            use_container_width=True,
        )

    preview = d.get("telegram_preview")
    if preview:
        with st.expander("Telegram preview (HTML)"):
            st.code(preview, language="html")


def main() -> None:
    st.title("OI live playbook")
    st.caption(
        f"UTC now {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} · "
        "ALERT ONLY — not investment advice"
    )

    _playbook_panel()
    st.divider()

    st.header("Scan thị trường hiện tại")
    with st.sidebar:
        st.subheader("Scan")
        symbols = st.multiselect(
            "Symbols",
            ["BTCUSDT", "ETHUSDT"],
            default=["BTCUSDT", "ETHUSDT"],
        )
        intervals = st.multiselect("Intervals", ["1h", "4h"], default=["1h", "4h"])
        lookback = st.slider("Lookback bars", 200, 800, 400, 50)
        run = st.button("Scan now", type="primary", use_container_width=True)

    if not run:
        st.write("Chọn symbol/TF ở sidebar rồi bấm **Scan now** (gọi API public ≈ vài chục giây).")
        return

    if not symbols or not intervals:
        st.warning("Chọn ít nhất 1 symbol và 1 interval.")
        return

    results = []
    progress = st.progress(0.0)
    total = max(len(symbols) * len(intervals), 1)
    i = 0
    for sym in symbols:
        for iv in intervals:
            with st.spinner(f"Fetching {sym} {iv}…"):
                results.append(_scan_one(sym, iv, lookback))
            i += 1
            progress.progress(i / total)
    progress.empty()

    # Summary table
    summary = [
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
    st.subheader("Tóm tắt")
    st.dataframe(summary, hide_index=True, use_container_width=True)

    st.subheader("Chi tiết")
    cols = st.columns(2)
    for idx, r in enumerate(results):
        with cols[idx % 2]:
            _signal_card(r)


if __name__ == "__main__":
    main()
