"""
DCA optimization: find best hour (daily), best (day, hour) (weekly), best BTC/ETH ratio.
"""

from typing import Tuple

from .simulate import dca_daily, dca_weekly


def optimize_daily_hour(
    amount_per_day: float = 10.0,
    start_date: str = "2017-01-01",
    end_date: str = "2026-03-15",
    btc_ratio: float = 0.7,
) -> Tuple[int, float, list]:
    """
    Find hour_utc (0-23) that maximizes final portfolio for daily DCA.
    Returns (best_hour, best_final_value, list of (hour, value) for top 5).
    """
    best_hour = 0
    best_value = 0.0
    all_results = []
    for h in range(24):
        try:
            fv, inv, _ = dca_daily(amount_per_day, start_date, end_date, btc_ratio, h)
            all_results.append((h, fv))
            if fv > best_value:
                best_value = fv
                best_hour = h
        except Exception:
            all_results.append((h, 0.0))
    all_results.sort(key=lambda x: x[1], reverse=True)
    return best_hour, best_value, all_results[:5]


def optimize_weekly_day_hour(
    amount_per_week: float = 100.0,
    start_date: str = "2017-01-01",
    end_date: str = "2026-03-15",
    btc_ratio: float = 0.7,
) -> Tuple[int, int, float, list]:
    """
    Find (day_of_week, hour_utc) that maximizes final portfolio for weekly DCA.
    day_of_week: 0=Mon, 6=Sun.
    Returns (best_day, best_hour, best_value, top 10 list).
    """
    best_day = 0
    best_hour = 0
    best_value = 0.0
    all_results = []
    for d in range(7):
        for h in range(24):
            try:
                fv, inv, _ = dca_weekly(amount_per_week, start_date, end_date, btc_ratio, d, h)
                all_results.append((d, h, fv))
                if fv > best_value:
                    best_value = fv
                    best_day = d
                    best_hour = h
            except Exception:
                all_results.append((d, h, 0.0))
    all_results.sort(key=lambda x: x[2], reverse=True)
    return best_day, best_hour, best_value, all_results[:10]


def optimize_btc_ratio(
    amount_per_day: float = 10.0,
    start_date: str = "2017-01-01",
    end_date: str = "2026-03-15",
    hour_utc: int = 0,
    step: float = 0.1,
) -> Tuple[float, float, list]:
    """
    Find btc_ratio (0-1) that maximizes final portfolio for daily DCA at given hour.
    Returns (best_btc_ratio, best_value, list of (ratio, value) for top 5).
    """
    best_ratio = 0.5
    best_value = 0.0
    all_results = []
    r = 0.0
    while r <= 1.0:
        try:
            fv, inv, _ = dca_daily(amount_per_day, start_date, end_date, r, hour_utc)
            all_results.append((r, fv))
            if fv > best_value:
                best_value = fv
                best_ratio = r
        except Exception:
            all_results.append((r, 0.0))
        r = round(r + step, 2)
    all_results.sort(key=lambda x: x[1], reverse=True)
    return best_ratio, best_value, all_results[:5]
