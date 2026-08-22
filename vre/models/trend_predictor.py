"""
Trend prediction model for Vietnam real estate prices.

Uses correlation analysis and linear regression to assess
how macro indicators (M2, Fed rate, VN rate, CPI, oil, DXY)
relate to property price movements and forecast short-term trends.
"""

from typing import Optional, Tuple
import warnings

try:
    import pandas as pd
    import numpy as np
except ImportError:
    pd = None
    np = None

try:
    from sklearn.linear_model import LinearRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.metrics import r2_score, mean_absolute_error
except ImportError:
    LinearRegression = None

FEATURE_COLS = [
    "M2SL", "FEDFUNDS", "CPIAUCSL", "FPCPITOTLZGVNM",
    "DCOILWTICO", "DTWEXBGS", "vn_refinancing_rate",
]
TARGET_COL = "property_index"


def compute_correlations(df: "pd.DataFrame",
                         target: str = TARGET_COL) -> Optional["pd.DataFrame"]:
    """
    Compute Pearson correlation of each feature vs property index.
    Also computes lagged correlations (1–4 quarters shift).
    Returns DataFrame with columns [feature, lag_0, lag_1, lag_2, lag_3, lag_4].
    """
    if pd is None:
        return None
    features = [c for c in FEATURE_COLS if c in df.columns]
    if target not in df.columns or not features:
        return None

    rows = []
    for feat in features:
        row = {"feature": feat}
        for lag in range(5):
            shifted = df[target].shift(-lag) if lag > 0 else df[target]
            valid = pd.concat([df[feat], shifted], axis=1).dropna()
            if len(valid) > 3:
                corr = valid.iloc[:, 0].corr(valid.iloc[:, 1])
                row[f"lag_{lag}"] = round(corr, 4)
            else:
                row[f"lag_{lag}"] = None
        rows.append(row)
    return pd.DataFrame(rows)


def build_regression_model(
    df: "pd.DataFrame",
    target: str = TARGET_COL,
) -> Optional[dict]:
    """
    Train a linear regression: features -> property index YoY change.
    Returns dict with model, scaler, metrics, feature_importance, predictions.
    """
    if LinearRegression is None or pd is None or np is None:
        return None

    features = [c for c in FEATURE_COLS if c in df.columns]
    if target not in df.columns or len(features) < 2:
        return None

    data = df[features + [target]].dropna()
    if len(data) < 10:
        return None

    X = data[features].values
    y = data[target].values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    tscv = TimeSeriesSplit(n_splits=min(3, len(data) // 5))
    scores = []
    for train_idx, test_idx in tscv.split(X_scaled):
        model = LinearRegression()
        model.fit(X_scaled[train_idx], y[train_idx])
        pred = model.predict(X_scaled[test_idx])
        scores.append(r2_score(y[test_idx], pred))

    final_model = LinearRegression()
    final_model.fit(X_scaled, y)
    y_pred = final_model.predict(X_scaled)

    importance = pd.DataFrame({
        "feature": features,
        "coefficient": final_model.coef_,
        "abs_importance": np.abs(final_model.coef_),
    }).sort_values("abs_importance", ascending=False)

    return {
        "model": final_model,
        "scaler": scaler,
        "features": features,
        "r2_train": round(r2_score(y, y_pred), 4),
        "mae_train": round(mean_absolute_error(y, y_pred), 4),
        "cv_r2_scores": [round(s, 4) for s in scores],
        "cv_r2_mean": round(np.mean(scores), 4) if scores else None,
        "feature_importance": importance,
        "predictions": y_pred,
        "actual": y,
        "dates": data.index if isinstance(data.index, pd.DatetimeIndex) else None,
    }


def forecast_next_quarters(
    model_result: dict,
    latest_features: "pd.DataFrame",
    n_quarters: int = 1,
) -> Optional["pd.DataFrame"]:
    """
    Forecast property index for next quarter(s) using the trained model.
    Giả định: chỉ số vĩ mô (M2, Fed, CPI...) không đổi — không có dữ liệu tương lai.
    → Dự báo 1 quý tới là hợp lý; Q2–Q4 sẽ giống Q1 nếu giả định đó đúng.
    latest_features: single-row DataFrame with the most recent feature values.
    """
    if model_result is None or pd is None or np is None:
        return None

    model = model_result["model"]
    scaler = model_result["scaler"]
    features = model_result["features"]

    available = [f for f in features if f in latest_features.columns]
    if len(available) < len(features):
        return None

    X = latest_features[features].values
    if X.ndim == 1:
        X = X.reshape(1, -1)

    X_scaled = scaler.transform(X)
    pred_val = float(model.predict(X_scaled)[0])
    predictions = []
    for q in range(1, n_quarters + 1):
        predictions.append({
            "quarter_ahead": q,
            "predicted_index": round(pred_val, 2),
        })

    return pd.DataFrame(predictions)


def run_backtest(
    merged: "pd.DataFrame",
    min_train: int = 12,
    n_forecast: int = 1,
) -> Optional[dict]:
    """
    Backtest: rolling forecast — train on past, predict next quarter, so sánh với thực tế.
    Returns dict with: backtest_df, mae_oos, direction_accuracy, n_predictions.
    """
    if pd is None or np is None or LinearRegression is None:
        return None

    features = [c for c in FEATURE_COLS if c in merged.columns]
    if TARGET_COL not in merged.columns or len(features) < 2:
        return None

    data = merged[features + [TARGET_COL]].dropna()
    if len(data) < min_train + n_forecast:
        return None

    rows = []
    for i in range(min_train, len(data) - n_forecast + 1):
        train = data.iloc[:i]
        X_train = train[features].values
        y_train = train[TARGET_COL].values
        scaler = StandardScaler()
        X_sc = scaler.fit_transform(X_train)
        model = LinearRegression()
        model.fit(X_sc, y_train)

        X_test = data.iloc[i : i + n_forecast][features].values
        X_test_sc = scaler.transform(X_test)
        pred = model.predict(X_test_sc)[-1]
        actual = data[TARGET_COL].iloc[i + n_forecast - 1]

        idx = data.index[i + n_forecast - 1]
        prev_actual = data[TARGET_COL].iloc[i - 1]
        actual_direction = "Tăng" if actual > prev_actual else ("Giảm" if actual < prev_actual else "Ổn định")
        pred_direction = "Tăng" if pred > prev_actual else ("Giảm" if pred < prev_actual else "Ổn định")

        rows.append({
            "date": idx,
            "actual": round(actual, 2),
            "predicted": round(pred, 2),
            "error": round(actual - pred, 2),
            "actual_direction": actual_direction,
            "predicted_direction": pred_direction,
            "direction_correct": actual_direction == pred_direction,
        })

    if not rows:
        return None

    bt_df = pd.DataFrame(rows)
    mae_oos = float(np.abs(bt_df["error"]).mean())
    dir_acc = float(bt_df["direction_correct"].mean()) * 100

    return {
        "backtest_df": bt_df,
        "mae_oos": round(mae_oos, 4),
        "direction_accuracy": round(dir_acc, 1),
        "n_predictions": len(rows),
    }


def prepare_analysis_dataframe(
    fred_monthly: Optional["pd.DataFrame"],
    property_df: Optional["pd.DataFrame"],
    vn_rates: Optional["pd.DataFrame"],
) -> Optional["pd.DataFrame"]:
    """
    Merge all data sources into a single analysis-ready DataFrame.
    Aligns everything to monthly frequency.
    """
    if pd is None:
        return None

    dfs = []

    if fred_monthly is not None and len(fred_monthly) > 0:
        fm = fred_monthly.copy()
        fm["date"] = pd.to_datetime(fm["date"])
        fm = fm.set_index("date")
        dfs.append(fm)

    if property_df is not None and len(property_df) > 0:
        prop = property_df.copy()
        prop["date"] = pd.to_datetime(prop["date"])
        if "value" in prop.columns:
            prop = prop.rename(columns={"value": TARGET_COL})
        elif "price_per_m2" in prop.columns:
            prop = prop.rename(columns={"price_per_m2": TARGET_COL})
        prop = prop.set_index("date")
        if TARGET_COL in prop.columns:
            prop = prop[[TARGET_COL]]
            prop = prop.resample("MS").last().ffill()
            dfs.append(prop)

    if vn_rates is not None and len(vn_rates) > 0:
        vr = vn_rates.copy()
        vr["date"] = pd.to_datetime(vr["date"])
        vr = vr.set_index("date")
        rename_map = {}
        if "refinancing_rate" in vr.columns:
            rename_map["refinancing_rate"] = "vn_refinancing_rate"
        if "deposit_rate" in vr.columns:
            rename_map["deposit_rate"] = "vn_deposit_rate"
        if rename_map:
            vr = vr.rename(columns=rename_map)
        rate_cols = [c for c in vr.columns if "rate" in c.lower()]
        if rate_cols:
            vr = vr[rate_cols].resample("MS").last().ffill()
            dfs.append(vr)

    if not dfs:
        return None

    merged = dfs[0]
    for df in dfs[1:]:
        merged = merged.join(df, how="outer")

    merged = merged.ffill().bfill()
    return merged


def run_full_analysis(
    fred_monthly: Optional["pd.DataFrame"],
    property_df: Optional["pd.DataFrame"],
    vn_rates: Optional["pd.DataFrame"],
    policies: Optional["pd.DataFrame"] = None,
    policy_months: int = 6,
) -> dict:
    """
    Run the complete analysis pipeline:
    1. Merge data
    2. Compute correlations
    3. Build regression model
    4. Generate forecasts
    5. Optional: adjust forecast by recent policy impact
    Returns dict with all results.
    """
    warnings.filterwarnings("ignore")

    merged = prepare_analysis_dataframe(fred_monthly, property_df, vn_rates)
    result = {"merged_data": merged, "correlations": None,
              "model_result": None, "forecast": None, "forecast_adjusted": None,
              "policy_impact": None}

    if merged is None:
        return result

    correlations = compute_correlations(merged)
    result["correlations"] = correlations

    model_result = build_regression_model(merged)
    result["model_result"] = model_result

    if model_result is not None and len(merged) > 0:
        latest = merged.iloc[[-1]]
        forecast = forecast_next_quarters(model_result, latest, n_quarters=1)
        result["forecast"] = forecast

        if policies is not None and len(policies) > 0 and forecast is not None:
            try:
                from vre.models.policy_scenarios import (
                    compute_policy_net_impact, apply_policy_adjustment,
                )
                current_idx = None
                if "property_index" in merged.columns:
                    current_idx = float(merged["property_index"].iloc[-1])
                impact = compute_policy_net_impact(policies, months=policy_months)
                result["policy_impact"] = impact
                result["forecast_adjusted"] = apply_policy_adjustment(
                    forecast, impact, current_index=current_idx,
                )
            except Exception:
                pass

    backtest = run_backtest(merged, min_train=12, n_forecast=1)
    result["backtest"] = backtest

    try:
        from vre.data_loaders.vietnam_econ import load_property_prices
        from vre.models.backtest_horizon import run_walk_forward_backtest
        prices_bt = load_property_prices()
        if prices_bt is not None and fred_monthly is not None:
            result["horizon_backtest"] = run_walk_forward_backtest(
                prices_bt, fred_monthly, vn_rates,
                start="2025-11-01", end="2026-08-01",
            )
    except Exception:
        result["horizon_backtest"] = None

    if property_df is not None:
        try:
            from vre.data_loaders.vietnam_econ import load_property_prices
            from vre.models.forecast_horizon import build_horizon_forecast
            prices = load_property_prices()
            result["horizon_forecast"] = build_horizon_forecast(
                prices,
                merged=merged,
                model_result=model_result,
                policy_impact=result.get("policy_impact"),
                start="2026-08-01",
                end="2027-12-01",
            )
        except Exception:
            result["horizon_forecast"] = None

    return result
