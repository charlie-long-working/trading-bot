#!/usr/bin/env python3
"""
So sánh backtest MACD+RSI vs SMC (OB + FVG + supply/demand) trên 3 cửa sổ.
Cả hai đều bật lọc xu hướng: **Bull** = EMA20>EMA50 và close>EMA50; **Bear** = EMA20<EMA50 và close<EMA50.
Long chỉ trong bull, short chỉ trong bear.

1) 2017-12-11 → 2018-08-06  (CSV spot)
2) 2021-11-08 → 2022-12-19  (CSV spot)
3) 2025-10-01 → nến mới nhất (Binance API; warmup từ 2025-08-01)

Cùng thoát: TP 10% / SL 4%, phí 0.1%, long+short, process giống engine MACD.

Chạy từ Trading-bot:
  python -m botdown.compare_macd_smc_three_windows
"""

from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from botdown.data import load_btc_daily  # noqa: E402
from botdown.engine_macd_rsi_bt import MacdRsiParams, run_macd_rsi_backtest  # noqa: E402
from botdown.engine_smc_bt import SmcParams, run_smc_backtest  # noqa: E402


WINDOWS_CSV = [
    ("Bear 2017–2018", "2017-12-11", "2018-08-06"),
    ("Bear 2021–2022", "2021-11-08", "2022-12-19"),
]


def fetch_binance_daily(start_ms: int, end_ms: int) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    rows: List = []
    cur = start_ms
    while cur < end_ms:
        url = (
            "https://api.binance.com/api/v3/klines?"
            f"symbol=BTCUSDT&interval=1d&startTime={cur}&endTime={end_ms}&limit=1000"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=45) as resp:
            chunk = json.loads(resp.read().decode())
        if not chunk:
            break
        rows.extend(chunk)
        cur = int(chunk[-1][0]) + 1
        if len(chunk) < 1000:
            break
    if not rows:
        return None
    open_time = np.array([int(k[0]) for k in rows], dtype=np.int64)
    open_ = np.array([float(k[1]) for k in rows])
    high = np.array([float(k[2]) for k in rows])
    low = np.array([float(k[3]) for k in rows])
    close = np.array([float(k[4]) for k in rows])
    volume = np.array([float(k[5]) for k in rows])
    return open_time, open_, high, low, close, volume


def _ts_label(ms: int) -> str:
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def _serialize_result(name: str, r) -> Dict[str, Any]:
    return {
        "strategy": name,
        "return_pct": round(r.total_return_pct, 2),
        "buy_hold_pct": round(r.buy_hold_pct, 2),
        "vs_hold_pct": round(r.total_return_pct - r.buy_hold_pct, 2),
        "max_drawdown_pct": round(r.max_drawdown_pct, 2),
        "num_trades": r.num_trades,
        "win_rate": round(r.win_rate, 1),
        "profit_factor": round(r.profit_factor, 3),
        "sharpe_approx": round(r.sharpe_ratio, 3),
    }


def main() -> None:
    macd_p = MacdRsiParams(
        exit_mode="pct",
        take_profit_pct=0.10,
        stop_loss_pct=0.04,
        fee_roundtrip=0.001,
        use_ema_trend_filter=True,
        ema_trend_fast=20,
        ema_trend_slow=50,
    )
    smc_p = SmcParams(
        take_profit_pct=0.10,
        stop_loss_pct=0.04,
        fee_roundtrip=0.001,
        use_ema_trend_filter=True,
        ema_trend_fast=20,
        ema_trend_slow=50,
    )

    data_csv = load_btc_daily(ROOT, "spot")
    if data_csv is None:
        print("Không đọc được BTC CSV.", file=sys.stderr)
        sys.exit(1)
    ot_c, o_c, h_c, l_c, c_c, v_c = data_csv

    warmup_ms = int(datetime(2025, 8, 1, tzinfo=timezone.utc).timestamp() * 1000)
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    api = fetch_binance_daily(warmup_ms, end_ms)
    if api is None:
        print("Không tải được Binance (cửa sổ 2025+).", file=sys.stderr)
        sys.exit(1)
    ot_a, o_a, h_a, l_a, c_a, v_a = api
    last_d = _ts_label(int(ot_a[-1]))

    rows_out: List[Dict[str, Any]] = []

    print(
        "=== MACD+RSI vs SMC | TP 10% SL 4% phí 0.1% | EMA20/50 bull-bear + close vs EMA50 ===\n"
        "SMC: vừa chạm OB/FVG/zone **và** cùng hướng EMA trend.\n"
    )

    for label, s, e in WINDOWS_CSV:
        rm = run_macd_rsi_backtest(ot_c, h_c, l_c, c_c, s, e, params=macd_p, allow_short=True)
        rs = run_smc_backtest(ot_c, o_c, h_c, l_c, c_c, s, e, params=smc_p, allow_short=True)
        if rm is None or rs is None:
            print(f"{label}: thiếu dữ liệu")
            continue
        block = {
            "window": label,
            "start": s,
            "end": e,
            "data": "spot CSV",
            "macd_rsi": _serialize_result("macd_rsi", rm),
            "smc_zones": _serialize_result("smc_ob_fvg_zones", rs),
        }
        rows_out.append(block)
        print(f"{label} ({s} → {e})")
        print(
            f"  MACD+RSI: {rm.total_return_pct:+.2f}%  hold {rm.buy_hold_pct:+.2f}%  "
            f"DD {rm.max_drawdown_pct:.1f}%  n={rm.num_trades}  WR {rm.win_rate:.0f}%  PF {rm.profit_factor:.2f}"
        )
        print(
            f"  SMC:      {rs.total_return_pct:+.2f}%  hold {rs.buy_hold_pct:+.2f}%  "
            f"DD {rs.max_drawdown_pct:.1f}%  n={rs.num_trades}  WR {rs.win_rate:.0f}%  PF {rs.profit_factor:.2f}"
        )
        print()

    s3, e3 = "2025-10-01", last_d
    label3 = f"Oct 2025 → nay (API đến {last_d})"
    rm3 = run_macd_rsi_backtest(ot_a, h_a, l_a, c_a, s3, e3, params=macd_p, allow_short=True)
    rs3 = run_smc_backtest(ot_a, o_a, h_a, l_a, c_a, s3, e3, params=smc_p, allow_short=True)
    if rm3 and rs3:
        block3 = {
            "window": label3,
            "start": s3,
            "end": e3,
            "data": "binance_api",
            "warmup_from": "2025-08-01",
            "macd_rsi": _serialize_result("macd_rsi", rm3),
            "smc_zones": _serialize_result("smc_ob_fvg_zones", rs3),
        }
        rows_out.append(block3)
        print(f"{label3}")
        print(
            f"  MACD+RSI: {rm3.total_return_pct:+.2f}%  hold {rm3.buy_hold_pct:+.2f}%  "
            f"DD {rm3.max_drawdown_pct:.1f}%  n={rm3.num_trades}  WR {rm3.win_rate:.0f}%  PF {rm3.profit_factor:.2f}"
        )
        print(
            f"  SMC:      {rs3.total_return_pct:+.2f}%  hold {rs3.buy_hold_pct:+.2f}%  "
            f"DD {rs3.max_drawdown_pct:.1f}%  n={rs3.num_trades}  WR {rs3.win_rate:.0f}%  PF {rs3.profit_factor:.2f}"
        )

    out_path = ROOT / "botdown" / "reports" / "compare_macd_smc_three_windows.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "macd_rsi_params": {
                    "exit": "pct",
                    "tp": macd_p.take_profit_pct,
                    "sl": macd_p.stop_loss_pct,
                    "fee": macd_p.fee_roundtrip,
                    "ema_trend": "EMA20>EMA50 & close>EMA50 → bull long; EMA20<EMA50 & close<EMA50 → bear short",
                },
                "smc_params": {
                    "entry": "edge_touch_ob_or_fvg_or_zone",
                    "tp": smc_p.take_profit_pct,
                    "sl": smc_p.stop_loss_pct,
                    "fee": smc_p.fee_roundtrip,
                    "ob_lookback": smc_p.ob_lookback,
                    "fvg_lookback": smc_p.fvg_lookback,
                    "zone_lookback": smc_p.zone_lookback,
                    "ema_trend": "same as MACD",
                },
                "windows": rows_out,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nĐã ghi {out_path}")


if __name__ == "__main__":
    main()
