"""
Load Vietnam stock & macro data via vnstock.

Tái sử dụng vnstock (github.com/thinh-vu/vnstock) để lấy:
- Chỉ số thị trường (VNIndex, HNXIndex)
- Giá cổ phiếu lịch sử
- Tỷ giá VCB, giá vàng SJC
- Báo cáo tài chính (optionally)

Dùng cùng với vietnam_econ, comparison trong module vre.
"""

from pathlib import Path
from typing import Optional, List, Tuple
from datetime import datetime, timedelta

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    from vnstock import Quote, Listing
    from vnstock.explorer.misc import vcb_exchange_rate, sjc_gold_price
    _VNSTOCK_AVAILABLE = True
except ImportError:
    _VNSTOCK_AVAILABLE = False

# Default cache dir
CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "vnstock"
DEFAULT_SOURCE = "KBS"

# Mã chỉ số phổ biến
VN_INDICES = ["VNINDEX", "HNXINDEX", "VN30"]


def _ensure_vnstock():
    if not _VNSTOCK_AVAILABLE:
        raise ImportError(
            "vnstock chưa được cài đặt. Chạy: pip install vnstock"
        )


def load_vnindex(
    start: str,
    end: Optional[str] = None,
    source: str = DEFAULT_SOURCE,
    cache: bool = True,
) -> Optional["pd.DataFrame"]:
    """
    Lấy giá lịch sử VNIndex.

    Args:
        start: Ngày bắt đầu YYYY-MM-DD
        end: Ngày kết thúc YYYY-MM-DD (mặc định: hôm nay)
        source: Nguồn dữ liệu (KBS, VCI)
        cache: Đọc/ghi cache CSV để giảm API calls

    Returns:
        DataFrame [time, open, high, low, close, volume] hoặc None
    """
    if pd is None:
        return None
    _ensure_vnstock()

    if end is None:
        end = datetime.now().strftime("%Y-%m-%d")

    cache_path = CACHE_DIR / "vnindex.csv" if cache else None
    if cache_path and cache_path.exists():
        try:
            df = pd.read_csv(cache_path, parse_dates=["time"])
            df["time"] = pd.to_datetime(df["time"]).dt.normalize()
            mask = (df["time"] >= pd.Timestamp(start)) & (df["time"] <= pd.Timestamp(end))
            if mask.any():
                return df.loc[mask].sort_values("time").reset_index(drop=True)
        except Exception:
            pass

    try:
        q = Quote(symbol="VNINDEX", source=source)
        df = q.history(start=start, end=end, interval="1D")
    except Exception as e:
        print(f"[VN] vnstock Quote VNINDEX error: {e}")
        return None

    if df is None or len(df) == 0:
        return None

    # Chuẩn hóa cột nếu vnstock trả về tên khác
    col_map = {
        "t": "time",
        "o": "open",
        "h": "high",
        "l": "low",
        "c": "close",
        "v": "volume",
    }
    for old, new in col_map.items():
        if old in df.columns and new not in df.columns:
            df = df.rename(columns={old: new})

    if cache_path:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        if cache_path.exists():
            try:
                existing = pd.read_csv(cache_path, parse_dates=["time"])
                combined = pd.concat([existing, df]).drop_duplicates(subset=["time"])
                combined = combined.sort_values("time").reset_index(drop=True)
                combined.to_csv(cache_path, index=False)
            except Exception:
                df.to_csv(cache_path, index=False)
        else:
            df.to_csv(cache_path, index=False)

    return df


def load_index_history(
    symbol: str = "VNINDEX",
    start: Optional[str] = None,
    end: Optional[str] = None,
    length: Optional[int] = None,
    source: str = DEFAULT_SOURCE,
) -> Optional["pd.DataFrame"]:
    """
    Lấy giá lịch sử chỉ số (VNINDEX, HNXINDEX, VN30...).

    Args:
        symbol: Mã chỉ số
        start, end: Khoảng ngày YYYY-MM-DD
        length: Số ngày gần nhất (dùng khi không có start/end)
        source: KBS hoặc VCI
    """
    if pd is None:
        return None
    _ensure_vnstock()

    try:
        q = Quote(symbol=symbol.upper(), source=source)
        if start and end:
            df = q.history(start=start, end=end, interval="1D")
        elif length:
            df = q.history(length=str(length), interval="1D")
        else:
            end_d = datetime.now()
            start_d = end_d - timedelta(days=365)
            df = q.history(
                start=start_d.strftime("%Y-%m-%d"),
                end=end_d.strftime("%Y-%m-%d"),
                interval="1D",
            )
    except Exception as e:
        print(f"[VN] vnstock Quote {symbol} error: {e}")
        return None

    return df if df is not None and len(df) > 0 else None


def load_stock_history(
    symbol: str,
    start: str,
    end: Optional[str] = None,
    source: str = DEFAULT_SOURCE,
) -> Optional["pd.DataFrame"]:
    """Lấy giá lịch sử cổ phiếu (VD: VCB, FPT, VNM)."""
    if pd is None:
        return None
    _ensure_vnstock()

    if end is None:
        end = datetime.now().strftime("%Y-%m-%d")

    try:
        q = Quote(symbol=symbol.upper(), source=source)
        df = q.history(start=start, end=end, interval="1D")
    except Exception as e:
        print(f"[VN] vnstock Quote {symbol} error: {e}")
        return None

    return df if df is not None and len(df) > 0 else None


def load_exchange_rate(date: str) -> Optional["pd.DataFrame"]:
    """Tỷ giá ngoại tệ VCB theo ngày. Date: YYYY-MM-DD."""
    if pd is None:
        return None
    _ensure_vnstock()

    try:
        return vcb_exchange_rate(date=date)
    except Exception as e:
        print(f"[VN] vcb_exchange_rate error: {e}")
        return None


def load_gold_price(date: Optional[str] = None) -> Optional["pd.DataFrame"]:
    """Giá vàng SJC. Date: YYYY-MM-DD hoặc None = hôm nay."""
    if pd is None:
        return None
    _ensure_vnstock()

    try:
        return sjc_gold_price(date=date)
    except Exception as e:
        print(f"[VN] sjc_gold_price error: {e}")
        return None


def get_all_symbols(source: str = DEFAULT_SOURCE) -> Optional[List[str]]:
    """Danh sách mã cổ phiếu niêm yết."""
    _ensure_vnstock()

    try:
        listing = Listing(source=source)
        symbols = listing.all_symbols()
        if isinstance(symbols, pd.DataFrame) and "ticker" in symbols.columns:
            return symbols["ticker"].tolist()
        if isinstance(symbols, (list, tuple)):
            return list(symbols)
        return None
    except Exception as e:
        print(f"[VN] Listing.all_symbols error: {e}")
        return None


def get_all_vnstock_data(
    start: str = "2020-01-01",
    end: Optional[str] = None,
) -> dict:
    """
    Load tổng hợp dữ liệu VN từ vnstock.

    Returns:
        dict: {
            "vnindex": DataFrame,
            "exchange_rate": DataFrame (latest),
            "gold_price": DataFrame (latest),
        }
    """
    result = {}
    vnindex = load_vnindex(start=start, end=end)
    if vnindex is not None:
        result["vnindex"] = vnindex

    if end:
        latest_date = end
    else:
        latest_date = datetime.now().strftime("%Y-%m-%d")

    fx = load_exchange_rate(date=latest_date)
    if fx is not None:
        result["exchange_rate"] = fx

    gold = load_gold_price(date=latest_date)
    if gold is not None:
        result["gold_price"] = gold

    return result
