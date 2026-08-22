# Data loaders for klines and optional macro/on-chain.
# Keep this package init lazy — Streamlit puts botdown/ on sys.path first;
# eager imports of strategy/ here would resolve to botdown.strategy by mistake.

from __future__ import annotations

from typing import Any

__all__ = [
    "load_merged_klines",
    "load_klines_as_arrays",
    "MarketContext",
    "make_decision",
    "load_sopr_mvrv_for_klines",
    "get_onchain_for_bar",
    "fetch_sopr",
    "fetch_mvrv",
    "SYMBOL_TO_ASSET",
    "fetch_binance_klines",
    "fetch_binance_ticker_price",
    "load_klines_with_realtime_fallback",
    "fetch_liquidation_map",
    "save_liquidation_reports",
]


def __getattr__(name: str) -> Any:
    if name in ("load_merged_klines", "load_klines_as_arrays"):
        from .load_klines import load_merged_klines, load_klines_as_arrays

        return {"load_merged_klines": load_merged_klines, "load_klines_as_arrays": load_klines_as_arrays}[name]
    if name in ("MarketContext", "make_decision"):
        from .decision import MarketContext, make_decision

        return {"MarketContext": MarketContext, "make_decision": make_decision}[name]
    if name in (
        "load_sopr_mvrv_for_klines",
        "get_onchain_for_bar",
        "fetch_sopr",
        "fetch_mvrv",
        "SYMBOL_TO_ASSET",
    ):
        from . import glassnode as g

        return getattr(g, name)
    if name in (
        "fetch_binance_klines",
        "fetch_binance_ticker_price",
        "load_klines_with_realtime_fallback",
    ):
        from . import realtime as r

        return getattr(r, name)
    if name in ("fetch_liquidation_map", "save_liquidation_reports"):
        from .liquidation_map import fetch_liquidation_map, save_liquidation_reports

        return {
            "fetch_liquidation_map": fetch_liquidation_map,
            "save_liquidation_reports": save_liquidation_reports,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
