"""
Streamlit dashboard — live OI playbook (I + K) currently applied on GHA/Telegram.

  cd Trading-bot
  python3 run_strategy_dashboard.py
  # hoặc: PYTHONPATH=. streamlit run botdown/dashboard_oi_playbook.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

# Streamlit inserts this file's directory (botdown/) at sys.path[0], which shadows
# the top-level `strategy` package with botdown/strategy.py. Fix before imports.
_ROOT = Path(__file__).resolve().parents[1]
_BOTDOWN = Path(__file__).resolve().parent
_clean: list[str] = []
for _p in sys.path:
    try:
        if Path(_p).resolve() == _BOTDOWN.resolve():
            continue
    except OSError:
        pass
    _clean.append(_p)
sys.path[:] = _clean
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from botdown.oi_snapshot import playbook_data, scan_one, summary_rows

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
    pb = playbook_data()
    st.header("Strategy đang apply (live)")
    st.caption(pb["caption"])

    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("Scenarios")
        for sc in pb["scenarios"]:
            st.markdown(f"**`{sc['name']}`**")
            st.write(sc["desc"])
            if sc["why"]:
                st.caption(sc["why"])
            st.divider()
    with c2:
        st.subheader("Exit (theo TF)")
        rows = [
            {
                "TF": ex["tf"],
                "TP %": f"{ex['tp_pct']:.1f}",
                "SL %": f"{ex['sl_pct']:.1f}",
                "R:R": f"{ex['rr']:.2f}",
                "Max hold (bars)": ex["max_hold_bars"],
            }
            for ex in pb["exits"]
        ]
        st.dataframe(rows, hide_index=True, use_container_width=True)
        st.caption(pb["exit_note"])
    with c3:
        st.subheader("Ops")
        st.markdown("\n".join(f"- {line}" for line in pb["ops"]))


# Pure scan lives in botdown/oi_snapshot.py (shared with the static web exporter).
_scan_one = scan_one


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
    summary = summary_rows(results)
    st.subheader("Tóm tắt")
    st.dataframe(summary, hide_index=True, use_container_width=True)

    st.subheader("Chi tiết")
    cols = st.columns(2)
    for idx, r in enumerate(results):
        with cols[idx % 2]:
            _signal_card(r)


if __name__ == "__main__":
    main()
