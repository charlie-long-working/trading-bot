import numpy as np


def sma(x: np.ndarray, period: int) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    n = len(x)
    out = np.full(n, np.nan)
    for i in range(period - 1, n):
        out[i] = np.mean(x[i - period + 1 : i + 1])
    return out


def rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    c = np.asarray(close, dtype=float)
    n = len(c)
    out = np.full(n, np.nan)
    delta = np.diff(c, prepend=c[0])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    for i in range(period, n):
        ag = np.mean(gain[i - period + 1 : i + 1])
        al = np.mean(loss[i - period + 1 : i + 1])
        if al < 1e-12:
            out[i] = 100.0
        else:
            rs = ag / al
            out[i] = 100.0 - (100.0 / (1.0 + rs))
    return out
