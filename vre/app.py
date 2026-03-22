"""
Vietnam Real Estate & Economic Dashboard

Run: streamlit run vre/app.py
Open: http://localhost:8501
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
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

st.set_page_config(
    page_title="VN Real Estate & Economy",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

DARK_BG = "#0e1117"
CARD_BG = "#1a1c2c"
ACCENT = "#e94560"
ACCENT2 = "#4ade80"


def apply_custom_css():
    st.markdown("""
    <style>
    .main .block-container { padding-top: 1rem; max-width: 1400px; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
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
    }
    .metric-card h3 { color: #8892b0; font-size: 0.85rem; margin-bottom: 4px; }
    .metric-card .value { color: #e6f1ff; font-size: 1.8rem; font-weight: 700; }
    .section-header {
        border-left: 4px solid #e94560; padding-left: 12px;
        margin: 24px 0 16px 0; font-size: 1.2rem; font-weight: 600;
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


@st.cache_data(ttl=3600, show_spinner="Loading FRED data...")
def cached_fred_series(force: bool = False):
    return get_all_series(force_refresh=force)


@st.cache_data(ttl=3600, show_spinner="Loading FRED monthly merge...")
def cached_fred_monthly(force: bool = False):
    return get_merged_monthly(force_refresh=force)


@st.cache_data(ttl=3600, show_spinner="Building property index...")
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


@st.cache_data(ttl=3600, show_spinner="Loading comparison data...")
def cached_property_comparison():
    return load_property_comparison()


@st.cache_data(ttl=3600)
def cached_demographics():
    return load_demographics()


def sidebar():
    st.sidebar.title("🏠 VN Real Estate")
    st.sidebar.markdown("---")
    force = st.sidebar.button("🔄 Refresh All Data", use_container_width=True)
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Data Sources**")
    st.sidebar.markdown("""
    - [FRED](https://fred.stlouisfed.org/) — US macro indicators
    - SBV — VN interest rates (CSV)
    - Local CSV — VN property prices (5 regions)
    """)
    st.sidebar.markdown("---")
    st.sidebar.markdown("**FRED Series**")
    for sid, desc in SERIES.items():
        st.sidebar.caption(f"`{sid}` — {desc}")
    return force


def render_tab_raw_data(fred_data: dict, prop_index, vn_rates, vn_prices):
    st.markdown('<div class="section-header">Macro Economic Indicators</div>',
                unsafe_allow_html=True)

    fred_labels = {
        "M2SL": ("M2 Money Supply", "Billions USD"),
        "FEDFUNDS": ("Fed Funds Rate", "%"),
        "CPIAUCSL": ("CPI US (All Urban)", "Index"),
        "FPCPITOTLZGVNM": ("CPI Vietnam (Inflation)", "% YoY"),
        "DCOILWTICO": ("Oil WTI", "USD/barrel"),
        "DTWEXBGS": ("US Dollar Index", "Index"),
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
        "Select indicator to chart",
        list(fred_data.keys()),
        format_func=lambda x: fred_labels.get(x, (x,))[0],
    )
    if selected and selected in fred_data:
        df = fred_data[selected]
        label, unit = fred_labels.get(selected, (selected, ""))
        fig = px.line(df, x="date", y="value", title=f"{label} ({unit})")
        fig.update_traces(line_color=ACCENT)
        plotly_dark_layout(fig, f"{label} — Historical")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="section-header">Vietnam Property Prices</div>',
                unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        if prop_index is not None and len(prop_index) > 0:
            st.subheader("VN Property Price Index (base 2015 = 100)")
            fig = px.line(prop_index, x="date", y="value",
                          title="National Avg Property Price Index")
            fig.update_traces(line_color=ACCENT2, mode="lines+markers")
            plotly_dark_layout(fig)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Property index unavailable — add data to `vre/data/vietnam/property_prices.csv`")

    with col2:
        if vn_prices is not None and len(vn_prices) > 0:
            st.subheader("Price per m² by Region")
            regions = vn_prices["region"].unique() if "region" in vn_prices.columns else []
            if len(regions) > 0:
                fig = px.line(vn_prices, x="date", y="price_per_m2",
                              color="region",
                              title="Price per m² by Region")
                plotly_dark_layout(fig)
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Local property prices: no CSV data found")

    if vn_rates is not None and len(vn_rates) > 0:
        st.markdown('<div class="section-header">Vietnam Interest Rates (SBV)</div>',
                    unsafe_allow_html=True)
        rate_cols = [c for c in vn_rates.columns if "rate" in c.lower()]
        if rate_cols:
            fig = go.Figure()
            colors = [ACCENT, ACCENT2, "#fbbf24", "#818cf8"]
            for j, col in enumerate(rate_cols):
                fig.add_trace(go.Scatter(
                    x=vn_rates["date"], y=vn_rates[col],
                    mode="lines+markers", name=col.replace("_", " ").title(),
                    line=dict(color=colors[j % len(colors)]),
                ))
            plotly_dark_layout(fig, "Vietnam Interest Rates History")
            st.plotly_chart(fig, use_container_width=True)


def render_tab_correlation(merged):
    st.markdown('<div class="section-header">Correlation Analysis</div>',
                unsafe_allow_html=True)

    if merged is None or len(merged) < 5:
        st.warning("Not enough merged data for correlation analysis. "
                    "Ensure FRED data and property price data are available.")
        return

    numeric = merged.select_dtypes(include=[np.number])
    if len(numeric.columns) < 2:
        st.warning("Not enough numeric columns for correlation.")
        return

    corr = numeric.corr()

    fig = px.imshow(
        corr,
        text_auto=".2f",
        color_continuous_scale="RdBu_r",
        zmin=-1, zmax=1,
        title="Correlation Matrix — All Indicators",
        aspect="auto",
    )
    plotly_dark_layout(fig, "Correlation Matrix")
    fig.update_layout(height=600)
    st.plotly_chart(fig, use_container_width=True)

    if "property_index" in numeric.columns:
        st.markdown('<div class="section-header">Lagged Correlations vs Property Index</div>',
                    unsafe_allow_html=True)
        corr_table = compute_correlations(merged)
        if corr_table is not None:
            st.dataframe(corr_table.set_index("feature"), use_container_width=True)

        st.markdown('<div class="section-header">Scatter Plots vs Property Index</div>',
                    unsafe_allow_html=True)
        feature_cols = [c for c in numeric.columns if c != "property_index"]
        sel_feat = st.selectbox("Select feature for scatter", feature_cols)
        if sel_feat:
            fig = px.scatter(
                merged.reset_index(), x=sel_feat, y="property_index",
                trendline="ols",
                title=f"Property Index vs {sel_feat}",
            )
            plotly_dark_layout(fig)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Property index column not found. Add VN property data to see correlations.")

        feature_cols = list(numeric.columns)
        if len(feature_cols) >= 2:
            c1, c2 = st.columns(2)
            with c1:
                x_col = st.selectbox("X axis", feature_cols, index=0)
            with c2:
                y_col = st.selectbox("Y axis", feature_cols,
                                     index=min(1, len(feature_cols) - 1))
            if x_col and y_col:
                fig = px.scatter(
                    merged.reset_index(), x=x_col, y=y_col,
                    trendline="ols",
                    title=f"{y_col} vs {x_col}",
                )
                plotly_dark_layout(fig)
                st.plotly_chart(fig, use_container_width=True)


def render_tab_prediction(analysis_result):
    st.markdown('<div class="section-header">Trend Prediction Model</div>',
                unsafe_allow_html=True)

    if analysis_result is None:
        st.warning("No analysis result available.")
        return

    model_res = analysis_result.get("model_result")
    if model_res is None:
        st.warning("Could not build regression model. "
                    "Need property index + at least 2 macro features with >=10 data points.")
        st.info("Ensure the following data is available:\n"
                "1. VN property prices (CSV or BIS)\n"
                "2. FRED macro data (M2, Fed rate, CPI, etc.)\n"
                "3. VN interest rates (CSV)")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(metric_card("R² (Train)", f"{model_res['r2_train']:.4f}"),
                    unsafe_allow_html=True)
    with c2:
        st.markdown(metric_card("MAE (Train)", f"{model_res['mae_train']:.4f}"),
                    unsafe_allow_html=True)
    with c3:
        cv = model_res.get("cv_r2_mean")
        cv_str = f"{cv:.4f}" if cv is not None else "N/A"
        st.markdown(metric_card("CV R² (Mean)", cv_str), unsafe_allow_html=True)

    st.markdown('<div class="section-header">Feature Importance</div>',
                unsafe_allow_html=True)
    importance = model_res["feature_importance"]
    fig = px.bar(
        importance, x="abs_importance", y="feature",
        orientation="h", title="Feature Importance (Absolute Coefficient)",
        color="coefficient",
        color_continuous_scale="RdBu_r",
    )
    plotly_dark_layout(fig)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="section-header">Actual vs Predicted</div>',
                unsafe_allow_html=True)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        y=model_res["actual"], mode="lines", name="Actual",
        line=dict(color=ACCENT2),
    ))
    fig.add_trace(go.Scatter(
        y=model_res["predictions"], mode="lines", name="Predicted",
        line=dict(color=ACCENT, dash="dash"),
    ))
    plotly_dark_layout(fig, "Actual vs Predicted Property Index")
    st.plotly_chart(fig, use_container_width=True)

    forecast = analysis_result.get("forecast")
    if forecast is not None:
        st.markdown('<div class="section-header">Forecast (Next Quarters)</div>',
                    unsafe_allow_html=True)
        st.dataframe(forecast, use_container_width=True)
        st.caption("Based on current macro conditions. "
                   "This is a simple linear model — not financial advice.")
    else:
        st.info("Forecast not available (insufficient data for prediction)")


def render_tab_vn_history(vn_prices, vn_avg, prop_index):
    st.markdown('<div class="section-header">Vietnam Real Estate Price History</div>',
                unsafe_allow_html=True)

    has_local = vn_prices is not None and len(vn_prices) > 0
    has_avg = vn_avg is not None and len(vn_avg) > 0
    has_index = prop_index is not None and len(prop_index) > 0

    if not has_local:
        st.warning("No property price data available.\n\n"
                    "Add CSV at `vre/data/vietnam/property_prices.csv`\n\n"
                    "Format: `date,region,price_per_m2,yoy_change`")
        return

    st.subheader("Price by Region")
    regions = sorted(vn_prices["region"].unique()) if "region" in vn_prices.columns else []
    selected_regions = st.multiselect(
        "Filter regions",
        regions, default=regions[:5] if len(regions) > 5 else regions,
    )
    if selected_regions:
        filtered = vn_prices[vn_prices["region"].isin(selected_regions)]
    else:
        filtered = vn_prices

    fig = px.line(
        filtered, x="date", y="price_per_m2", color="region",
        title="Price per m² by Region Over Time",
    )
    plotly_dark_layout(fig)
    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)

    if "yoy_change" in vn_prices.columns:
        st.subheader("YoY Price Change (%)")
        fig2 = px.bar(
            filtered, x="date", y="yoy_change", color="region",
            barmode="group", title="Year-over-Year Price Change",
        )
        plotly_dark_layout(fig2)
        st.plotly_chart(fig2, use_container_width=True)

    if has_avg:
        st.subheader("National Average Trend")
        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            subplot_titles=("Avg Price per m²", "YoY Change %"),
            vertical_spacing=0.1,
        )
        fig.add_trace(go.Scatter(
            x=vn_avg["date"], y=vn_avg["price_per_m2"],
            mode="lines+markers", name="Avg Price",
            line=dict(color=ACCENT2),
        ), row=1, col=1)

        if "yoy_change" in vn_avg.columns:
            colors = [ACCENT2 if v >= 0 else ACCENT
                      for v in vn_avg["yoy_change"].fillna(0)]
            fig.add_trace(go.Bar(
                x=vn_avg["date"], y=vn_avg["yoy_change"],
                name="YoY Change", marker_color=colors,
            ), row=2, col=1)

        plotly_dark_layout(fig, "National Average Property Price — Vietnam")
        fig.update_layout(height=600)
        st.plotly_chart(fig, use_container_width=True)

    if has_index:
        st.subheader("Property Price Index + Volatility")

        idx = prop_index.copy()
        idx["pct_change"] = idx["value"].pct_change() * 100
        idx["volatility"] = idx["pct_change"].rolling(4, min_periods=2).std()

        fig_vol = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            subplot_titles=("Price Index (2015 = 100)", "Rolling Volatility (4-period)"),
        )
        fig_vol.add_trace(go.Scatter(
            x=idx["date"], y=idx["value"],
            name="Index", mode="lines+markers",
            line=dict(color="#818cf8"),
        ), row=1, col=1)
        fig_vol.add_trace(go.Scatter(
            x=idx["date"], y=idx["volatility"],
            name="Volatility", line=dict(color="#fbbf24"),
            fill="tozeroy",
        ), row=2, col=1)
        plotly_dark_layout(fig_vol, "Property Price Index + Volatility")
        fig_vol.update_layout(height=500)
        st.plotly_chart(fig_vol, use_container_width=True)


def render_tab_comparison(prop_comp, demographics, prop_index_vn):
    st.markdown('<div class="section-header">So sánh giá BĐS với các nước phát triển + Trung Quốc</div>',
                unsafe_allow_html=True)
    st.caption("BIS Real Residential Property Price Index (2010=100). Vietnam chuẩn hóa từ dữ liệu local.")

    if prop_comp is None:
        st.warning("Không có dữ liệu so sánh. Kiểm tra FRED_API_KEY.")
        return

    prop_with_vn = merge_property_with_vietnam(prop_comp, prop_index_vn)
    if prop_with_vn is None:
        prop_with_vn = prop_comp

    melt = prop_with_vn.melt(id_vars=["date"], var_name="country", value_name="index")
    melt = melt.dropna(subset=["index"])

    fig = px.line(
        melt, x="date", y="index", color="country",
        title="Property Price Index — Vietnam vs Developed Countries + China (2010=100)",
    )
    plotly_dark_layout(fig)
    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)

    if len(prop_with_vn) > 0:
        latest = prop_with_vn.drop(columns=["date"]).iloc[-1]
        latest = latest.dropna().sort_values(ascending=False)
        st.subheader("Giá trị gần nhất (index 2010=100)")
        n = len(latest)
        cols = st.columns(min(n, 5))
        for i, (country, val) in enumerate(latest.items()):
            with cols[i % 5]:
                st.metric(country, f"{val:.1f}", None)

    st.markdown('<div class="section-header">Nhân khẩu học — Tỷ lệ sinh (fertility)</div>',
                unsafe_allow_html=True)

    demo_fertility = demographics.get("fertility") if demographics else None
    if demo_fertility is not None and len(demo_fertility) > 0:
        melt_fert = demo_fertility.melt(id_vars=["date"], var_name="country", value_name="fertility")
        melt_fert = melt_fert.dropna()
        fig_fert = px.line(
            melt_fert, x="date", y="fertility", color="country",
            title="Tỷ lệ sinh (số con/phụ nữ) — Tương quan với nhu cầu BĐS dài hạn",
        )
        plotly_dark_layout(fig_fert)
        st.plotly_chart(fig_fert, use_container_width=True)

    st.markdown('<div class="section-header">Tương quan: Tỷ lệ sinh vs Giá BĐS</div>',
                unsafe_allow_html=True)
    st.caption("Correlation dương: fertility cao đi kèm giá BĐS cao (cùng xu hướng). Âm: ngược lại.")

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
                    title=f"Fertility vs Property — {sel_country}",
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
        st.info("Dữ liệu nhân khẩu từ World Bank qua FRED.")
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
        "Nguồn: FRED — BIS (property), World Bank WDI (demographics, fertility). "
        "Vietnam property: chuẩn hóa từ dữ liệu local."
    )


def main():
    apply_custom_css()
    force_refresh = sidebar()

    st.title("Vietnam Real Estate & Economic Dashboard")
    st.caption("Macro indicators, property prices, correlation analysis, and trend prediction")

    fred_data = cached_fred_series(force=force_refresh)
    fred_monthly = cached_fred_monthly(force=force_refresh)
    prop_index = cached_property_index()
    vn_rates = cached_vn_rates()
    vn_prices = cached_vn_prices()
    vn_avg = cached_vn_avg()

    merged = prepare_analysis_dataframe(fred_monthly, prop_index, vn_rates)
    analysis = run_full_analysis(fred_monthly, prop_index, vn_rates)
    prop_comp = cached_property_comparison()
    demographics = cached_demographics()

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Raw Data",
        "🔗 Correlations",
        "🔮 Prediction",
        "🏘️ VN History",
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
