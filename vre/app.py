"""
Vietnam Real Estate & Economic Dashboard

Run: streamlit run vre/app.py
Open: http://localhost:8501

Tự động cập nhật: GitHub Actions chạy mỗi tuần (Thứ Hai 07:00 VN), fetch FRED, push → Streamlit redeploy.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

# Streamlit Cloud: Secrets → FRED_API_KEY. Inject vào env để data loaders đọc được.
try:
    if hasattr(st, "secrets") and "FRED_API_KEY" in st.secrets and not os.environ.get("FRED_API_KEY"):
        os.environ["FRED_API_KEY"] = str(st.secrets["FRED_API_KEY"])
except Exception:
    pass
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

from vre.data_loaders.fred import get_all_series, get_merged_monthly, SERIES
from vre.data_loaders.vietnam_econ import (
    load_interest_rates, load_property_prices, load_property_national_avg,
    build_property_index,
)
from vre.data_loaders.comparison import (
    load_property_comparison, load_demographics,
    merge_property_with_vietnam,
    build_fertility_property_correlation,
    build_fertility_property_merged,
    compute_demographic_outlook,
)
from vre.models.trend_predictor import (
    run_full_analysis, prepare_analysis_dataframe, compute_correlations,
)
from vre.data_loaders.policy_crawler import crawl_policies, load_policies

st.set_page_config(
    page_title="BĐS & Kinh tế Việt Nam",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="auto",  # Thu gọn sidebar trên điện thoại, mở trên desktop
)

DARK_BG = "#0e1117"
CARD_BG = "#1a1c2c"
ACCENT = "#e94560"
ACCENT2 = "#4ade80"

# Mô tả chỉ số FRED — tiếng Việt (sidebar + biểu đồ)
VI_SERIES = {
    "M2SL": "Cung tiền M2 (Mỹ, tỷ USD/tháng) — tiền lưu hành, ảnh hưởng lạm phát & tài sản",
    "FEDFUNDS": "Lãi suất Fed (%, tháng) — lãi chính sách Mỹ, tác động USD & vốn toàn cầu",
    "CPIAUCSL": "CPI Mỹ (chỉ số giá tiêu dùng, tháng) — đo lạm phát Mỹ",
    "FPCPITOTLZGVNM": "Lạm phát Việt Nam (% so cùng kỳ năm trước, năm)",
    "DCOILWTICO": "Giá dầu WTI (USD/thùng, ngày) — chi phí năng lượng thế giới",
    "DTWEXBGS": "Chỉ số USD (bình quân thương mại, ngày) — USD mạnh/yếu so nhiều nước",
}

VI_GUIDE = """
**📊 Dữ liệu thô** — Xem các chỉ số kinh tế Mỹ/thế giới (M2, lãi Fed, lạm phát, dầu, USD), chỉ số giá nhà Việt Nam (chuẩn 2015=100), giá theo m² từng vùng, lãi suất NHNN.

**🔗 Tương quan** — Ma trận cho biết hai chỉ số nào “cùng chiều” hay “ngược chiều” (số gần +1 hoặc -1). Chỉ mang tính thống kê, không phải lời khuyên đầu tư.

**🔮 Dự báo** — Mô hình hồi quy đơn giản so sánh giá trị thực tế và dự đoán. R² càng cao càng “khớp” dữ liệu quá khứ; vẫn có thể sai tương lai.

**🏘️ Lịch sử VN** — Giá nhà theo khu vực, % tăng so năm trước, bình quân cả nước.

**🌍 So sánh quốc tế** — Giá BĐS các nước (chuẩn 2010=100), tỷ lệ sinh, dân số — để đặt Việt Nam trong bối cảnh thế giới.

*Nguồn: FRED, dữ liệu CSV Việt Nam. Không phải tư vấn tài chính.*
"""


def apply_custom_css():
    st.markdown("""
    <style>
    /* Desktop */
    .main .block-container { padding-top: 1rem; max-width: 1400px; padding-left: 1rem; padding-right: 1rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; flex-wrap: wrap; }
    .stTabs [data-baseweb="tab"] {
        background-color: #1a1c2c; border-radius: 8px 8px 0 0;
        padding: 10px 24px; font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #e94560 !important; color: white !important;
    }
    .metric-card {
        background: linear-gradient(135deg, #1a1c2c 0%, #16213e 100%);
        border: 1px solid #2a2d4a; border-radius: 12px;
        padding: 20px; text-align: center;
        min-width: 0;
    }
    .metric-card h3 { color: #8892b0; font-size: 0.85rem; margin-bottom: 4px; }
    .metric-card .value { color: #e6f1ff; font-size: 1.8rem; font-weight: 700; word-break: break-word; }
    .section-header {
        border-left: 4px solid #e94560; padding-left: 12px;
        margin: 24px 0 16px 0; font-size: 1.2rem; font-weight: 600;
    }
    /* Cột metric: tự stack trên mobile */
    [data-testid="column"] { min-width: 0 !important; }
    
    /* Mobile — max-width 768px */
    @media (max-width: 768px) {
        .main .block-container { padding-top: 0.5rem; padding-left: 0.75rem; padding-right: 0.75rem; }
        .stTabs [data-baseweb="tab-list"] { overflow-x: auto; flex-wrap: nowrap; -webkit-overflow-scrolling: touch; }
        .stTabs [data-baseweb="tab"] { padding: 8px 16px; font-size: 0.85rem; white-space: nowrap; }
        .metric-card { padding: 14px 12px; border-radius: 10px; margin-bottom: 8px; }
        .metric-card h3 { font-size: 0.75rem; }
        .metric-card .value { font-size: 1.4rem !important; }
        .section-header { font-size: 1rem; margin: 16px 0 12px 0; padding-left: 10px; }
        [data-testid="stHorizontalBlock"] > [data-testid="column"] { width: 100% !important; flex: 0 0 100% !important; }
        /* Sidebar: nút dễ bấm trên mobile */
        [data-testid="stSidebar"] .stButton > button { min-height: 44px; padding: 10px 16px; }
        /* Title nhỏ hơn */
        h1 { font-size: 1.5rem !important; }
        /* Plotly: giới hạn chiều cao trên mobile */
        .js-plotly-plot { max-height: 350px !important; }
    }
    
    /* Mobile nhỏ — max-width 480px */
    @media (max-width: 480px) {
        .main .block-container { padding-left: 0.5rem; padding-right: 0.5rem; }
        .metric-card .value { font-size: 1.25rem !important; }
        .stTabs [data-baseweb="tab"] { padding: 6px 12px; font-size: 0.8rem; }
        h1 { font-size: 1.3rem !important; }
    }
    </style>
    """, unsafe_allow_html=True)


def metric_card(label: str, value: str, delta: str = ""):
    delta_html = ""
    if delta:
        color = ACCENT2 if delta.startswith("+") or delta.startswith("▲") else ACCENT
        delta_html = f'<div style="color:{color}; font-size:0.9rem;">{delta}</div>'
    return f"""
    <div class="metric-card">
        <h3>{label}</h3>
        <div class="value">{value}</div>
        {delta_html}
    </div>
    """


def plotly_dark_layout(fig, title=""):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        title=dict(text=title, font=dict(size=16)),
        margin=dict(l=40, r=20, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
    )
    return fig


@st.cache_data(ttl=3600, show_spinner="Đang tải dữ liệu FRED...")
def cached_fred_series(force: bool = False):
    return get_all_series(force_refresh=force)


@st.cache_data(ttl=3600, show_spinner="Đang gộp dữ liệu theo tháng...")
def cached_fred_monthly(force: bool = False):
    return get_merged_monthly(force_refresh=force)


@st.cache_data(ttl=3600, show_spinner="Đang tính chỉ số giá BĐS...")
def cached_property_index():
    return build_property_index()


@st.cache_data(ttl=3600)
def cached_vn_rates():
    return load_interest_rates()


@st.cache_data(ttl=3600)
def cached_vn_prices():
    return load_property_prices()


@st.cache_data(ttl=3600)
def cached_vn_avg():
    return load_property_national_avg()


@st.cache_data(ttl=3600, show_spinner="Đang tải dữ liệu so sánh...")
def cached_property_comparison():
    return load_property_comparison()


@st.cache_data(ttl=1800, show_spinner="Đang crawl chính sách BĐS...")
def cached_policies(refresh: bool = False, months: int = 6):
    if refresh:
        return crawl_policies(months=months)
    existing = load_policies()
    if existing is not None and len(existing) > 0:
        return existing
    return crawl_policies(months=months)


@st.cache_data(ttl=3600)
def cached_demographics():
    return load_demographics()


def _get_last_updated() -> str | None:
    """Đọc thời điểm cập nhật dữ liệu (do GitHub Actions ghi)."""
    p = ROOT / "vre" / "data" / "last_updated.txt"
    if p.exists():
        try:
            return p.read_text().strip()
        except Exception:
            pass
    return None


def sidebar():
    st.sidebar.title("🏠 BĐS & kinh tế VN")
    last = _get_last_updated()
    if last:
        st.sidebar.caption(f"📅 Dữ liệu cập nhật: {last}")
    st.sidebar.markdown("---")
    force = st.sidebar.button("🔄 Làm mới toàn bộ dữ liệu", use_container_width=True)
    crawl_pol = st.sidebar.button("📜 Crawl chính sách 6 tháng", use_container_width=True)
    if st.sidebar.button("🕷️ Crawl đầy đủ dữ liệu", use_container_width=True):
        st.sidebar.info("Chạy: python vre/scripts/crawl_all_vre.py")
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Nguồn dữ liệu**")
    st.sidebar.markdown("""
    - [FRED](https://fred.stlouisfed.org/) — chỉ số kinh tế Mỹ/thế giới (cần API key để cập nhật mới)
    - NHNN (SBV) — lãi suất Việt Nam (file CSV)
    - CSV nội bộ — giá nhà theo m² (5 khu vực)
    """)
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Các mã chỉ số FRED**")
    for sid in SERIES:
        desc = VI_SERIES.get(sid, SERIES.get(sid, sid))
        st.sidebar.caption(f"`{sid}` — {desc}")
    return force, crawl_pol


def render_tab_raw_data(fred_data: dict, prop_index, vn_rates, vn_prices):
    st.markdown('<div class="section-header">Chỉ số kinh tế vĩ mô (Mỹ & thế giới)</div>',
                unsafe_allow_html=True)
    st.caption(
        "M2: lượng tiền; Fed: lãi Mỹ; CPI: lạm phát; Dầu WTI: năng lượng; "
        "Chỉ số USD: đô mạnh/yếu. Lạm phát VN: % so cùng kỳ năm trước."
    )

    fred_labels = {
        "M2SL": ("Cung tiền M2 (Mỹ)", "tỷ USD"),
        "FEDFUNDS": ("Lãi suất Fed", "%"),
        "CPIAUCSL": ("CPI Mỹ (giá tiêu dùng)", "chỉ số"),
        "FPCPITOTLZGVNM": ("Lạm phát Việt Nam", "% so cùng kỳ/năm"),
        "DCOILWTICO": ("Giá dầu WTI", "USD/thùng"),
        "DTWEXBGS": ("Chỉ số USD (bình quân thương mại)", "điểm"),
    }

    cols = st.columns(3)
    for i, (sid, df) in enumerate(fred_data.items()):
        if df is None or len(df) == 0:
            continue
        label, unit = fred_labels.get(sid, (sid, ""))
        with cols[i % 3]:
            latest = df["value"].iloc[-1]
            prev = df["value"].iloc[-2] if len(df) > 1 else latest
            delta = ((latest - prev) / prev * 100) if prev != 0 else 0
            delta_str = f"{'▲' if delta >= 0 else '▼'} {abs(delta):.2f}%"
            st.markdown(metric_card(label, f"{latest:,.2f} {unit}", delta_str),
                        unsafe_allow_html=True)

    selected = st.selectbox(
        "Chọn chỉ số để xem biểu đồ",
        list(fred_data.keys()),
        format_func=lambda x: fred_labels.get(x, (x,))[0],
    )
    if selected and selected in fred_data:
        df = fred_data[selected]
        label, unit = fred_labels.get(selected, (selected, ""))
        fig = px.line(df, x="date", y="value", title=f"{label} ({unit})")
        fig.update_traces(line_color=ACCENT)
        plotly_dark_layout(fig, f"{label} — theo thời gian")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="section-header">Giá nhà đất Việt Nam</div>',
                unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        if prop_index is not None and len(prop_index) > 0:
            st.subheader("Chỉ số giá BĐS bình quân (mốc 2015 = 100)")
            fig = px.line(prop_index, x="date", y="value",
                          title="Chỉ số giá nhà bình quân cả nước")
            fig.update_traces(line_color=ACCENT2, mode="lines+markers")
            plotly_dark_layout(fig)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Chưa có chỉ số — bổ sung dữ liệu trong `vre/data/vietnam/property_prices.csv`")

    with col2:
        if vn_prices is not None and len(vn_prices) > 0:
            st.subheader("Giá theo m² theo khu vực (VND)")
            regions = vn_prices["region"].unique() if "region" in vn_prices.columns else []
            if len(regions) > 0:
                fig = px.line(vn_prices, x="date", y="price_per_m2",
                              color="region",
                              title="Giá m² theo vùng")
                plotly_dark_layout(fig)
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Chưa có file CSV giá nhà địa phương.")

    if vn_rates is not None and len(vn_rates) > 0:
        st.markdown('<div class="section-header">Lãi suất Việt Nam (NHNN)</div>',
                    unsafe_allow_html=True)
        st.caption("Lãi tái cấp vốn / huy động — ảnh hưởng chi phí vay mua nhà.")
        rate_cols = [c for c in vn_rates.columns if "rate" in c.lower()]
        if rate_cols:
            fig = go.Figure()
            colors = [ACCENT, ACCENT2, "#fbbf24", "#818cf8"]
            name_vi = {
                "refinancing_rate": "Lãi tái cấp vốn",
                "deposit_rate": "Trần lãi huy động (tham chiếu)",
            }
            for j, col in enumerate(rate_cols):
                nm = name_vi.get(col, col.replace("_", " ").title())
                fig.add_trace(go.Scatter(
                    x=vn_rates["date"], y=vn_rates[col],
                    mode="lines+markers", name=nm,
                    line=dict(color=colors[j % len(colors)]),
                ))
            plotly_dark_layout(fig, "Lịch sử lãi suất Việt Nam")
            st.plotly_chart(fig, use_container_width=True)


def render_tab_correlation(merged):
    st.markdown('<div class="section-header">Phân tích tương quan</div>',
                unsafe_allow_html=True)
    st.caption(
        "Hệ số gần **+1**: hai chỉ số cùng tăng/giảm; gần **-1**: ngược chiều; gần **0**: ít liên hệ. "
        "Chỉ mang tính thống kê trên dữ liệu quá khứ."
    )

    if merged is None or len(merged) < 5:
        st.warning("Dữ liệu gộp chưa đủ để phân tích. Cần có dữ liệu FRED và giá BĐS Việt Nam.")
        return

    numeric = merged.select_dtypes(include=[np.number])
    if len(numeric.columns) < 2:
        st.warning("Không đủ cột số để tính tương quan.")
        return

    corr = numeric.corr()

    fig = px.imshow(
        corr,
        text_auto=".2f",
        color_continuous_scale="RdBu_r",
        zmin=-1, zmax=1,
        title="Ma trận tương quan — tất cả chỉ số",
        aspect="auto",
    )
    plotly_dark_layout(fig, "Ma trận tương quan")
    fig.update_layout(height=600)
    st.plotly_chart(fig, use_container_width=True)

    if "property_index" in numeric.columns:
        st.markdown('<div class="section-header">Tương quan trễ so với chỉ số giá BĐS</div>',
                    unsafe_allow_html=True)
        st.caption("So sánh chỉ số giá nhà với các yếu tố vĩ mô (có thể lệch thời gian).")
        corr_table = compute_correlations(merged)
        if corr_table is not None:
            st.dataframe(corr_table.set_index("feature"), use_container_width=True)

        st.markdown('<div class="section-header">Biểu đồ phân tán: chỉ số giá BĐS</div>',
                    unsafe_allow_html=True)
        feature_cols = [c for c in numeric.columns if c != "property_index"]
        sel_feat = st.selectbox("Chọn chỉ số để so với giá BĐS", feature_cols)
        if sel_feat:
            fig = px.scatter(
                merged.reset_index(), x=sel_feat, y="property_index",
                trendline="ols",
                title=f"Chỉ số giá BĐS theo {sel_feat}",
            )
            plotly_dark_layout(fig)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Chưa có cột chỉ số giá BĐS. Thêm dữ liệu giá nhà Việt Nam để xem tương quan.")

        feature_cols = list(numeric.columns)
        if len(feature_cols) >= 2:
            c1, c2 = st.columns(2)
            with c1:
                x_col = st.selectbox("Trục ngang (X)", feature_cols, index=0)
            with c2:
                y_col = st.selectbox("Trục dọc (Y)", feature_cols,
                                     index=min(1, len(feature_cols) - 1))
            if x_col and y_col:
                fig = px.scatter(
                    merged.reset_index(), x=x_col, y=y_col,
                    trendline="ols",
                    title=f"{y_col} theo {x_col}",
                )
                plotly_dark_layout(fig)
                st.plotly_chart(fig, use_container_width=True)


def render_tab_prediction(analysis_result):
    st.markdown('<div class="section-header">Mô hình dự báo xu hướng (tham khảo)</div>',
                unsafe_allow_html=True)
    st.caption(
        "**R²**: độ khớp với dữ liệu quá khứ (0–1, càng cao càng khớp). "
        "**MAE**: sai số trung bình. Mô hình tuyến tính đơn giản — không đảm bảo dự báo đúng tương lai."
    )

    if analysis_result is None:
        st.warning("Chưa có kết quả phân tích.")
        return

    model_res = analysis_result.get("model_result")
    if model_res is None:
        st.warning("Chưa xây dựng được mô hình. Cần chỉ số giá BĐS + ít nhất 2 biến vĩ mô và ≥10 điểm dữ liệu.")
        st.info(
            "Cần có:\n"
            "1. Giá BĐS Việt Nam (CSV)\n"
            "2. Dữ liệu FRED (M2, lãi Fed, CPI…)\n"
            "3. Lãi suất Việt Nam (CSV)"
        )
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(metric_card("R² (huấn luyện)", f"{model_res['r2_train']:.4f}"),
                    unsafe_allow_html=True)
    with c2:
        st.markdown(metric_card("MAE (sai số trung bình)", f"{model_res['mae_train']:.4f}"),
                    unsafe_allow_html=True)
    with c3:
        cv = model_res.get("cv_r2_mean")
        cv_str = f"{cv:.4f}" if cv is not None else "N/A"
        st.markdown(metric_card("R² trung bình (kiểm định chéo)", cv_str), unsafe_allow_html=True)

    st.markdown('<div class="section-header">Mức độ ảnh hưởng từng yếu tố</div>',
                unsafe_allow_html=True)
    importance = model_res["feature_importance"]
    fig = px.bar(
        importance, x="abs_importance", y="feature",
        orientation="h", title="Độ lớn hệ số (giá trị tuyệt đối)",
        color="coefficient",
        color_continuous_scale="RdBu_r",
    )
    plotly_dark_layout(fig)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="section-header">Thực tế so với dự đoán</div>',
                unsafe_allow_html=True)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        y=model_res["actual"], mode="lines", name="Thực tế",
        line=dict(color=ACCENT2),
    ))
    fig.add_trace(go.Scatter(
        y=model_res["predictions"], mode="lines", name="Mô hình dự đoán",
        line=dict(color=ACCENT, dash="dash"),
    ))
    plotly_dark_layout(fig, "Chỉ số giá BĐS: thực tế vs mô hình")
    st.plotly_chart(fig, use_container_width=True)

    # Backtest — kiểm định mô hình trên dữ liệu quá khứ
    backtest = analysis_result.get("backtest")
    if backtest is not None:
        st.markdown('<div class="section-header">Backtest — kiểm định trên dữ liệu quá khứ</div>',
                    unsafe_allow_html=True)
        st.caption(
            "Huấn luyện mô hình trên dữ liệu quá khứ, dự báo quý tiếp theo, so sánh với thực tế. "
            "Đánh giá độ tin cậy trước khi tin vào dự báo tương lai."
        )
        bt = backtest
        bc1, bc2, bc3 = st.columns(3)
        with bc1:
            st.metric("Số lần dự báo (out-of-sample)", bt["n_predictions"])
        with bc2:
            st.metric("MAE ngoài mẫu (sai số TB)", f"{bt['mae_oos']:.2f}")
        with bc3:
            st.metric("Độ chính xác hướng (Tăng/Giảm)", f"{bt['direction_accuracy']:.1f}%")
        bt_df = bt["backtest_df"].copy()
        bt_df = bt_df.rename(columns={
            "date": "Ngày",
            "actual": "Thực tế",
            "predicted": "Dự báo",
            "error": "Sai số",
            "actual_direction": "Hướng thực",
            "predicted_direction": "Hướng dự báo",
            "direction_correct": "Đúng hướng?",
        })
        with st.expander("Xem chi tiết từng kỳ backtest"):
            st.dataframe(bt_df, use_container_width=True, hide_index=True)

    hbt = analysis_result.get("horizon_backtest")
    if hbt is not None and hbt.get("national") is not None:
        st.markdown(
            '<div class="section-header">Backtest giá/m²: 11/2025 → 08/2026</div>',
            unsafe_allow_html=True,
        )
        st.warning(
            "Dữ liệu giá **07/2026** đã cập nhật theo khảo sát thị trường (giảm ~20–30% so với đỉnh cuối 2025). "
            "Backtest phản ánh mức sai lệch khi model momentum **chưa bắt kịp** đợt điều chỉnh mạnh."
        )
        st.caption(
            "Walk-forward: mỗi tháng chỉ dùng dữ liệu **trước** tháng đó để dự báo. "
            + (hbt.get("note") or "")
        )
        hm = hbt.get("metrics", {}).get("national", {})
        hc1, hc2, hc3, hc4 = st.columns(4)
        with hc1:
            st.metric("MAE", f"{hm.get('mae_vnd', 0):,.0f} đ/m²")
        with hc2:
            st.metric("MAPE", f"{hm.get('mape_pct', 0):.2f}%")
        with hc3:
            st.metric("RMSE", f"{hm.get('rmse_pct', 0):.2f}%")
        with hc4:
            da = hm.get("direction_accuracy_pct")
            st.metric("Đúng hướng", f"{da:.1f}%" if da is not None else "N/A")

        nat_bt = hbt["national"].copy()
        fig_bt = go.Figure()
        fig_bt.add_trace(go.Scatter(
            x=nat_bt["date"], y=nat_bt["price_actual"],
            mode="lines+markers", name="Thực tế",
            line=dict(color=ACCENT2),
        ))
        fig_bt.add_trace(go.Scatter(
            x=nat_bt["date"], y=nat_bt["price_predicted"],
            mode="lines+markers", name="Model (walk-forward)",
            line=dict(color=ACCENT, dash="dash"),
        ))
        plotly_dark_layout(fig_bt, "Giá m² bình quân — thực tế vs model")
        fig_bt.update_layout(yaxis_tickformat=",")
        st.plotly_chart(fig_bt, use_container_width=True)

        nat_show = nat_bt.copy()
        nat_show["date"] = nat_show["date"].astype(str).str[:7]
        nat_show = nat_show.rename(columns={
            "date": "Tháng",
            "price_actual": "Thực tế (VND/m²)",
            "price_predicted": "Model (VND/m²)",
            "error_pct": "Sai số (%)",
            "actual_kind": "Loại GT thực tế",
        })
        st.dataframe(nat_show, use_container_width=True, hide_index=True)

        with st.expander("Chi tiết theo từng vùng"):
            det = hbt["detail"]
            det = det[det["region"] != "National Avg"].copy()
            det["date"] = det["date"].astype(str).str[:7]
            det = det.rename(columns={
                "date": "Tháng", "region": "Vùng",
                "price_actual": "Thực tế", "price_predicted": "Model",
                "error_pct": "Sai số (%)", "actual_kind": "Loại GT",
            })
            st.dataframe(det, use_container_width=True, hide_index=True)

    forecast = analysis_result.get("forecast")
    forecast_adj = analysis_result.get("forecast_adjusted")
    policy_impact = analysis_result.get("policy_impact")

    if policy_impact is not None and policy_impact.get("n_policies", 0) > 0:
        st.markdown('<div class="section-header">Chính sách 6 tháng gần đây</div>',
                    unsafe_allow_html=True)
        st.caption(
            "Gồm văn bản NHNN (CSV) + tin RSS VnExpress. "
            "Điểm tác động: + hỗ trợ tín dụng, − siết/kiểm soát."
        )
        pc1, pc2, pc3, pc4 = st.columns(4)
        with pc1:
            st.metric("Số chính sách", policy_impact["n_policies"])
        with pc2:
            st.metric("Tác động ròng", f"{policy_impact['net_impact']:+.3f}")
        with pc3:
            st.metric("Điều chỉnh dự báo", f"{policy_impact['adjustment_pct']:+.2f}%")
        with pc4:
            st.metric("Hỗ trợ / Siết", f"+{policy_impact['positive_count']} / −{policy_impact['negative_count']}")

        recent = policy_impact.get("recent_policies")
        if recent is not None and len(recent) > 0:
            show = recent[["date", "source", "title", "impact_score", "impact_direction"]].copy()
            show["date"] = show["date"].astype(str).str[:10]
            show = show.rename(columns={
                "date": "Ngày", "source": "Nguồn", "title": "Tiêu đề",
                "impact_score": "Điểm", "impact_direction": "Hướng",
            })
            with st.expander("Xem danh sách chính sách"):
                st.dataframe(show, use_container_width=True, hide_index=True)

    if forecast is not None:
        st.markdown('<div class="section-header">Dự báo 1 quý tới (tham khảo)</div>',
                    unsafe_allow_html=True)
        st.caption(
            "**Tại sao chỉ 1 quý?** Mô hình dùng chỉ số vĩ mô (M2, Fed, CPI, dầu, USD...) làm đầu vào. "
            "Chúng ta không biết các chỉ số này ở tương lai → giả định «không đổi». "
            "Với giả định đó, dự báo Q2–Q4 sẽ giống Q1 nên chỉ hiển thị 1 quý."
        )
        merged = analysis_result.get("merged_data")
        current_idx = None
        if merged is not None and "property_index" in merged.columns:
            current_idx = float(merged["property_index"].iloc[-1])

        # Thêm cột: giá trị hiện tại, % thay đổi, hướng (tăng/giảm)
        df_display = forecast.copy()
        if forecast_adj is not None and "predicted_index" in forecast_adj.columns:
            df_display["predicted_index_policy"] = forecast_adj["predicted_index"]
        df_display = df_display.rename(columns={
            "quarter_ahead": "Quý tới",
            "predicted_index": "Chỉ số vĩ mô (base)",
            "predicted_index_policy": "Chỉ số + chính sách",
        })
        if current_idx is not None and current_idx != 0:
            df_display["Chỉ số hiện tại"] = round(current_idx, 1)
            base_col = "Chỉ số vĩ mô (base)" if "Chỉ số vĩ mô (base)" in df_display.columns else "Chỉ số dự báo"
            pred_col = "Chỉ số + chính sách" if "Chỉ số + chính sách" in df_display.columns else base_col
            pct = (df_display[pred_col] - current_idx) / current_idx * 100
            df_display["% thay đổi"] = pct.apply(lambda x: f"{x:+.1f}%")
            df_display["Hướng"] = pct.apply(
                lambda x: "Tăng" if x > 0.5 else ("Giảm" if x < -0.5 else "Ổn định")
            )
            cols = ["Quý tới", "Chỉ số hiện tại", base_col]
            if pred_col in df_display.columns and pred_col != base_col:
                cols.append(pred_col)
            cols += ["% thay đổi", "Hướng"]
            df_display = df_display[[c for c in cols if c in df_display.columns]]
        else:
            show_cols = ["Quý tới", "Chỉ số vĩ mô (base)"]
            if "Chỉ số + chính sách" in df_display.columns:
                show_cols.append("Chỉ số + chính sách")
            df_display = df_display[[c for c in show_cols if c in df_display.columns]]
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        st.caption(
            "Chỉ số giá BĐS (mốc 2015 = 100). «Dự báo» > «hiện tại» → xu hướng tăng; ngược lại → giảm. "
            "**Không phải tư vấn đầu tư.**"
        )

    horizon = analysis_result.get("horizon_forecast")
    if horizon is not None and horizon.get("national") is not None:
        nat = horizon["national"]
        summ = horizon.get("summary") or {}
        st.markdown(
            '<div class="section-header">Dự báo giá nhà 08/2026 → 12/2027</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "Giá/m² theo tháng: momentum YoY từng vùng (suy giảm dần) + vĩ mô + chính sách. "
            "Neo từ dữ liệu 01/2026, nội suy tới 08/2026. **Kịch bản tham khảo.**"
        )
        if summ:
            hc1, hc2, hc3, hc4 = st.columns(4)
            with hc1:
                st.metric("Giá BQ đầu kỳ (08/2026)", f"{summ.get('price_start_vnd', 0):,.0f} đ/m²")
            with hc2:
                st.metric("Giá BQ cuối kỳ (12/2027)", f"{summ.get('price_end_vnd', 0):,.0f} đ/m²")
            with hc3:
                st.metric("Tăng cả giai đoạn", f"{summ.get('change_pct', 0):+.1f}%")
            with hc4:
                st.metric("Cuối kỳ (+ chính sách)", f"{summ.get('price_end_policy_vnd', 0):,.0f} đ/m²")

        fig_h = go.Figure()
        fig_h.add_trace(go.Scatter(
            x=nat["date"], y=nat["price_per_m2"],
            mode="lines+markers", name="Dự báo base",
            line=dict(color=ACCENT2),
        ))
        fig_h.add_trace(go.Scatter(
            x=nat["date"], y=nat["price_per_m2_policy"],
            mode="lines", name="Dự báo + chính sách",
            line=dict(color=ACCENT, dash="dash"),
        ))
        plotly_dark_layout(fig_h, "Giá m² bình quân cả nước — dự báo 08/2026–12/2027")
        fig_h.update_layout(yaxis_tickformat=",")
        st.plotly_chart(fig_h, use_container_width=True)

        regional = horizon.get("regional")
        if regional is not None and len(regional) > 0:
            end_slice = regional[regional["date"] == regional["date"].max()].copy()
            end_slice = end_slice.sort_values("price_per_m2", ascending=False)
            end_show = end_slice[["region", "price_per_m2", "price_per_m2_policy", "yoy_implied"]].rename(columns={
                "region": "Khu vực",
                "price_per_m2": "Giá 12/2027 (base)",
                "price_per_m2_policy": "Giá 12/2027 (+ CS)",
                "yoy_implied": "YoY implied (%)",
            })
            st.subheader("Giá dự báo cuối kỳ theo vùng (12/2027)")
            st.dataframe(end_show, use_container_width=True, hide_index=True)

            sel_r = st.multiselect(
                "Biểu đồ theo vùng",
                sorted(regional["region"].unique()),
                default=sorted(regional["region"].unique())[:3],
                key="horizon_regions",
            )
            if sel_r:
                sub = regional[regional["region"].isin(sel_r)]
                fig_r = px.line(
                    sub, x="date", y="price_per_m2", color="region",
                    title="Giá/m² theo vùng — 08/2026 → 12/2027",
                )
                plotly_dark_layout(fig_r)
                fig_r.update_layout(yaxis_tickformat=",")
                st.plotly_chart(fig_r, use_container_width=True)

            with st.expander("Xem chi tiết từng tháng (tất cả vùng)"):
                detail = regional.copy()
                detail["date"] = detail["date"].astype(str).str[:7]
                detail = detail.rename(columns={
                    "date": "Tháng", "region": "Vùng",
                    "price_per_m2": "Giá base (VND/m²)",
                    "price_per_m2_policy": "Giá + CS (VND/m²)",
                    "yoy_implied": "YoY (%)",
                })
                st.dataframe(detail, use_container_width=True, hide_index=True)
    elif forecast is None:
        st.info("Chưa đủ dữ liệu để dự báo.")


def render_tab_vn_history(vn_prices, vn_avg, prop_index):
    st.markdown('<div class="section-header">Lịch sử giá nhà đất Việt Nam</div>',
                unsafe_allow_html=True)
    st.caption("Theo dõi giá theo vùng, % tăng so năm trước (YoY), và biến động theo thời gian.")

    has_local = vn_prices is not None and len(vn_prices) > 0
    has_avg = vn_avg is not None and len(vn_avg) > 0
    has_index = prop_index is not None and len(prop_index) > 0

    if not has_local:
        st.warning(
            "Chưa có dữ liệu giá nhà.\n\n"
            "Thêm file `vre/data/vietnam/property_prices.csv`\n\n"
            "Định dạng: `date,region,price_per_m2,yoy_change`"
        )
        return

    st.subheader("Giá theo khu vực")
    regions = sorted(vn_prices["region"].unique()) if "region" in vn_prices.columns else []
    selected_regions = st.multiselect(
        "Chọn khu vực hiển thị",
        regions, default=regions[:5] if len(regions) > 5 else regions,
    )
    if selected_regions:
        filtered = vn_prices[vn_prices["region"].isin(selected_regions)]
    else:
        filtered = vn_prices

    fig = px.line(
        filtered, x="date", y="price_per_m2", color="region",
        title="Giá m² theo thời gian (VND)",
    )
    plotly_dark_layout(fig)
    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)

    if "yoy_change" in vn_prices.columns:
        st.subheader("% thay đổi so cùng kỳ năm trước (YoY)")
        fig2 = px.bar(
            filtered, x="date", y="yoy_change", color="region",
            barmode="group", title="Tăng/giảm giá so năm trước (%)",
        )
        plotly_dark_layout(fig2)
        st.plotly_chart(fig2, use_container_width=True)

    if has_avg:
        st.subheader("Xu hướng bình quân cả nước")
        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            subplot_titles=("Giá m² bình quân", "% YoY"),
            vertical_spacing=0.1,
        )
        fig.add_trace(go.Scatter(
            x=vn_avg["date"], y=vn_avg["price_per_m2"],
            mode="lines+markers", name="Giá bình quân",
            line=dict(color=ACCENT2),
        ), row=1, col=1)

        if "yoy_change" in vn_avg.columns:
            colors = [ACCENT2 if v >= 0 else ACCENT
                      for v in vn_avg["yoy_change"].fillna(0)]
            fig.add_trace(go.Bar(
                x=vn_avg["date"], y=vn_avg["yoy_change"],
                name="YoY", marker_color=colors,
            ), row=2, col=1)

        plotly_dark_layout(fig, "Giá nhà bình quân — Việt Nam")
        fig.update_layout(height=600)
        st.plotly_chart(fig, use_container_width=True)

    if has_index:
        st.subheader("Chỉ số giá & độ biến động")
        st.caption("Biến động: đo mức dao động ngắn hạn quanh các kỳ gần nhất.")

        idx = prop_index.copy()
        idx["pct_change"] = idx["value"].pct_change() * 100
        idx["volatility"] = idx["pct_change"].rolling(4, min_periods=2).std()

        fig_vol = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            subplot_titles=("Chỉ số giá (2015 = 100)", "Biến động (4 kỳ)"),
        )
        fig_vol.add_trace(go.Scatter(
            x=idx["date"], y=idx["value"],
            name="Chỉ số", mode="lines+markers",
            line=dict(color="#818cf8"),
        ), row=1, col=1)
        fig_vol.add_trace(go.Scatter(
            x=idx["date"], y=idx["volatility"],
            name="Biến động", line=dict(color="#fbbf24"),
            fill="tozeroy",
        ), row=2, col=1)
        plotly_dark_layout(fig_vol, "Chỉ số giá BĐS & biến động")
        fig_vol.update_layout(height=500)
        st.plotly_chart(fig_vol, use_container_width=True)


def render_tab_comparison(prop_comp, demographics, prop_index_vn):
    st.markdown('<div class="section-header">So sánh giá BĐS với các nước phát triển + Trung Quốc</div>',
                unsafe_allow_html=True)
    st.caption(
        "Chỉ số giá nhà BIS (mốc 2010 = 100): so sánh cùng thang đo giữa các nước. "
        "Việt Nam được chuẩn hóa từ dữ liệu trong nước."
    )

    if prop_comp is None:
        st.warning(
            "Không có dữ liệu so sánh. Thử bấm «Làm mới dữ liệu» hoặc cấu hình FRED_API_KEY (Secrets trên Streamlit)."
        )
        return

    prop_with_vn = merge_property_with_vietnam(prop_comp, prop_index_vn)
    if prop_with_vn is None:
        prop_with_vn = prop_comp

    melt = prop_with_vn.melt(id_vars=["date"], var_name="country", value_name="index")
    melt = melt.dropna(subset=["index"])

    fig = px.line(
        melt, x="date", y="index", color="country",
        title="Chỉ số giá BĐS — Việt Nam và các nước (2010 = 100)",
    )
    plotly_dark_layout(fig)
    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)

    if len(prop_with_vn) > 0:
        latest = prop_with_vn.drop(columns=["date"]).iloc[-1]
        latest = latest.dropna().sort_values(ascending=False)
        st.subheader("Giá trị gần nhất (chỉ số 2010 = 100)")
        n = len(latest)
        cols = st.columns(min(n, 5))
        for i, (country, val) in enumerate(latest.items()):
            with cols[i % 5]:
                st.metric(country, f"{val:.1f}", None)

    st.markdown('<div class="section-header">Nhân khẩu học — Tỷ lệ sinh (số con trung bình/phụ nữ)</div>',
                unsafe_allow_html=True)

    demo_fertility = demographics.get("fertility") if demographics else None
    if demo_fertility is not None and len(demo_fertility) > 0:
        st.caption(
            "Tỷ lệ sinh thấp thường gắn với dân số già, nhu cầu nhà dài hạn có thể khác các nước trẻ."
        )
        melt_fert = demo_fertility.melt(id_vars=["date"], var_name="country", value_name="fertility")
        melt_fert = melt_fert.dropna()
        fig_fert = px.line(
            melt_fert, x="date", y="fertility", color="country",
            title="Tỷ lệ sinh theo thời gian — liên quan nhu cầu BĐS dài hạn",
        )
        plotly_dark_layout(fig_fert)
        st.plotly_chart(fig_fert, use_container_width=True)

    st.markdown('<div class="section-header">Tương quan: Tỷ lệ sinh vs Giá BĐS</div>',
                unsafe_allow_html=True)
    st.caption(
        "Tương quan dương: tỷ lệ sinh và giá BĐS cùng xu hướng; âm: ngược chiều. "
        "Chỉ mang tính thống kê."
    )

    corr_df = build_fertility_property_correlation(prop_with_vn, demo_fertility)
    merged_scatter = build_fertility_property_merged(prop_with_vn, demo_fertility)

    c1, c2 = st.columns(2)
    with c1:
        if corr_df is not None and len(corr_df) > 0:
            st.dataframe(corr_df.set_index("country"), use_container_width=True)
    with c2:
        if merged_scatter is not None and len(merged_scatter) > 0:
            sel_country = st.selectbox("Chọn quốc gia (scatter)", merged_scatter["country"].unique())
            sub = merged_scatter[merged_scatter["country"] == sel_country]
            if len(sub) > 0:
                fig_scatter = px.scatter(
                    sub, x="fertility", y="property",
                    trendline="ols",
                    title=f"Tỷ lệ sinh vs giá BĐS — {sel_country}",
                )
                plotly_dark_layout(fig_scatter)
                st.plotly_chart(fig_scatter, use_container_width=True)

    st.markdown('<div class="section-header">Dự đoán theo nhân khẩu học</div>',
                unsafe_allow_html=True)

    outlook = compute_demographic_outlook(demo_fertility)
    if outlook:
        st.info(outlook.get("narrative", ""))
        scores = outlook.get("scores")
        if scores is not None and len(scores) > 0:
            st.dataframe(scores, use_container_width=True, hide_index=True)
            st.caption(
                "Thuận lợi: fertility ≥1.8. Trung lập: 1.2–1.8. Áp lực dài hạn: <1.2. "
                "Không phải tư vấn đầu tư."
            )

    st.markdown('<div class="section-header">Nhân khẩu học khác — So sánh quốc tế</div>',
                unsafe_allow_html=True)

    if not demographics:
        st.info("Dữ liệu nhân khẩu: Ngân hàng Thế giới (World Bank), qua FRED.")
        return

    demo_pop = demographics.get("population")
    demo_dep = demographics.get("old_age_dependency")
    demo_work = demographics.get("working_age_pct")

    c1, c2 = st.columns(2)

    with c1:
        if demo_pop is not None and len(demo_pop) > 0:
            melt_pop = demo_pop.melt(id_vars=["date"], var_name="country", value_name="population")
            melt_pop = melt_pop.dropna()
            melt_pop["population_m"] = melt_pop["population"] / 1e6
            fig_pop = px.line(
                melt_pop, x="date", y="population_m", color="country",
                title="Dân số (triệu người)",
            )
            plotly_dark_layout(fig_pop)
            st.plotly_chart(fig_pop, use_container_width=True)

    with c2:
        if demo_dep is not None and len(demo_dep) > 0:
            melt_dep = demo_dep.melt(id_vars=["date"], var_name="country", value_name="ratio")
            melt_dep = melt_dep.dropna()
            fig_dep = px.line(
                melt_dep, x="date", y="ratio", color="country",
                title="Tỷ lệ phụ thuộc già (người 65+ / 100 lao động)",
            )
            plotly_dark_layout(fig_dep)
            st.plotly_chart(fig_dep, use_container_width=True)

    if demo_work is not None and len(demo_work) > 0:
        melt_work = demo_work.melt(id_vars=["date"], var_name="country", value_name="pct")
        melt_work = melt_work.dropna()
        fig_work = px.line(
            melt_work, x="date", y="pct", color="country",
            title="Tỷ lệ dân số trong độ tuổi lao động (15–64, % tổng dân số)",
        )
        plotly_dark_layout(fig_work)
        st.plotly_chart(fig_work, use_container_width=True)

    st.markdown("---")
    st.caption(
        "Nguồn: FRED — BIS (giá BĐS), World Bank (dân số, tỷ lệ sinh). "
        "Giá Việt Nam: chuẩn hóa từ dữ liệu nội bộ."
    )


def main():
    apply_custom_css()
    force_refresh, crawl_policies_btn = sidebar()

    policies = cached_policies(refresh=crawl_policies_btn, months=6)

    st.title("Bảng điều khiển: Bất động sản & kinh tế Việt Nam")
    st.caption(
        "Theo dõi chỉ số vĩ mô, giá nhà, tương quan và dự báo tham khảo — giao diện tiếng Việt."
    )

    with st.expander("📖 Hướng dẫn đọc nhanh (cho người theo dõi không chuyên)", expanded=False):
        st.markdown(VI_GUIDE)

    fred_data = cached_fred_series(force=force_refresh)
    fred_monthly = cached_fred_monthly(force=force_refresh)
    prop_index = cached_property_index()
    vn_rates = cached_vn_rates()
    vn_prices = cached_vn_prices()
    vn_avg = cached_vn_avg()

    merged = prepare_analysis_dataframe(fred_monthly, prop_index, vn_rates)
    analysis = run_full_analysis(fred_monthly, prop_index, vn_rates, policies=policies, policy_months=6)
    prop_comp = cached_property_comparison()
    demographics = cached_demographics()

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Dữ liệu thô",
        "🔗 Tương quan",
        "🔮 Dự báo",
        "🏘️ Lịch sử VN",
        "🌍 So sánh quốc tế",
    ])

    with tab1:
        render_tab_raw_data(fred_data, prop_index, vn_rates, vn_prices)

    with tab2:
        render_tab_correlation(merged)

    with tab3:
        render_tab_prediction(analysis)

    with tab4:
        render_tab_vn_history(vn_prices, vn_avg, prop_index)

    with tab5:
        render_tab_comparison(prop_comp, demographics, prop_index)


if __name__ == "__main__":
    main()
