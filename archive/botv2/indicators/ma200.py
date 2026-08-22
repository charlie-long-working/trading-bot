"""
Indicator: MA200 (Simple Moving Average 200) và % chênh lệch giá so với MA200.

- MA200: trung bình 200 nến gần nhất của close.
- Chênh lệch %: (giá - MA200) / MA200 * 100
  - Dương = giá trên MA200, âm = giá dưới MA200.
"""

import numpy as np


def ma200(close: np.ndarray, period: int = 200) -> np.ndarray:
    """
    MA200 – Simple Moving Average với chu kỳ mặc định 200.

    Args:
        close: mảng giá đóng cửa (index 0 = cũ nhất, -1 = mới nhất).
        period: chu kỳ MA (mặc định 200).

    Returns:
        Mảng cùng length với close; np.nan cho các index chưa đủ period nến.
    """
    close = np.asarray(close, dtype=np.float64)
    n = len(close)
    out = np.full(n, np.nan, dtype=np.float64)
    if n < period:
        return out
    # Convolve với kernel [1/period]*period = SMA
    kernel = np.ones(period) / period
    out[period - 1:] = np.convolve(close, kernel, mode="valid")
    return out


def price_vs_ma200_pct(
    close: np.ndarray,
    ma200_arr: np.ndarray | None = None,
    period: int = 200,
) -> np.ndarray:
    """
    Chênh lệch giá với MA200 theo %: (giá - MA200) / MA200 * 100.

    Args:
        close: mảng giá đóng cửa.
        ma200_arr: nếu None thì tính MA200 từ close với period; nếu có thì dùng trực tiếp.
        period: chu kỳ MA khi ma200_arr is None.

    Returns:
        Mảng % chênh lệch, cùng length với close; np.nan khi MA200 không có (chưa đủ nến hoặc MA200 = 0).
    """
    close = np.asarray(close, dtype=np.float64)
    if ma200_arr is None:
        ma200_arr = ma200(close, period=period)
    else:
        ma200_arr = np.asarray(ma200_arr, dtype=np.float64)
    out = np.full_like(close, np.nan, dtype=np.float64)
    valid = np.isfinite(ma200_arr) & (ma200_arr != 0)
    out[valid] = (close[valid] - ma200_arr[valid]) / ma200_arr[valid] * 100.0
    return out


def ma200_and_pct_deviation(
    close: np.ndarray,
    period: int = 200,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Tính cả MA200 và % chênh lệch trong một lần gọi.

    Returns:
        (ma200_arr, pct_deviation_arr)
    """
    ma200_arr = ma200(close, period=period)
    pct_arr = price_vs_ma200_pct(close, ma200_arr=ma200_arr, period=period)
    return ma200_arr, pct_arr
