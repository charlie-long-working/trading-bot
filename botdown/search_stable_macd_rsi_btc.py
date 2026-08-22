#!/usr/bin/env python3
"""
Tải BTCUSDT 1D từ Binance (công khai), backtest MACD+RSI với lưới tham số,
gợi ý cấu hình cân bằng return / drawdown trên khoảng ngày chỉ định.

Cảnh báo: tối ưu trên một cửa sổ = in-sample; cần kiểm chứng out-of-sample.

Chạy (từ thư mục Trading-bot):
  python -m botdown.search_stable_macd_rsi_btc --start 2025-10-01
"""

from __future__ import annotations

import argparse
import itertools
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

from botdown.engine_macd_rsi_bt import MacdRsiParams, run_macd_rsi_backtest  # noqa: E402


def fetch_binance_daily_btc(start_ms: int, end_ms: int) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
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
    high = np.array([float(k[2]) for k in rows])
    low = np.array([float(k[3]) for k in rows])
    close = np.array([float(k[4]) for k in rows])
    return open_time, high, low, close


def _ts_label(ms: int) -> str:
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=str, default="2025-10-01", help="YYYY-MM-DD (UTC)")
    ap.add_argument("--end", type=str, default=None, help="YYYY-MM-DD inclusive; mặc định = nến cuối API")
    ap.add_argument("--fee", type=float, default=0.001, help="Phí round-trip (decimal)")
    args = ap.parse_args()

    start_ms = int(datetime.strptime(args.start[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    if args.end:
        end_ms = int(
            datetime.strptime(args.end[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000
        )
        end_ms += 86400 * 1000 - 1

    raw = fetch_binance_daily_btc(start_ms, end_ms)
    if raw is None:
        print("Không tải được nến Binance.", file=sys.stderr)
        sys.exit(1)
    open_time, high, low, close = raw
    start_d = args.start[:10]
    end_d = args.end[:10] if args.end else _ts_label(int(open_time[-1]))

    bh = (float(close[-1]) / float(close[0]) - 1.0) * 100
    print(f"BTC 1D spot (Binance UTC): {_ts_label(int(open_time[0]))} → {end_d}  ({len(close)} nến)")
    print(f"Buy & hold gần đúng: {bh:+.2f}%\n")

    tps = [0.05, 0.06, 0.07, 0.08, 0.10, 0.12, 0.15]
    sls = [0.02, 0.025, 0.03, 0.035, 0.04, 0.05, 0.06]
    rsi_pairs = [(70, 30), (75, 25), (65, 35), (72, 28)]
    macd_sets = [(12, 26, 9), (8, 21, 5)]
    allow_shorts = [True, False]

    results: List[Dict[str, Any]] = []
    for macd, (tp, sl), (ob, os), ash in itertools.product(
        macd_sets,
        itertools.product(tps, sls),
        rsi_pairs,
        allow_shorts,
    ):
        rr = tp / sl if sl > 0 else 0
        if rr < 1.2 or rr > 4.5:
            continue
        fast, slow, sig = macd
        p = MacdRsiParams(
            fast_period=fast,
            slow_period=slow,
            signal_period=sig,
            rsi_overbought=float(ob),
            rsi_oversold=float(os),
            exit_mode="pct",
            take_profit_pct=tp,
            stop_loss_pct=sl,
            fee_roundtrip=args.fee,
        )
        r = run_macd_rsi_backtest(
            open_time, high, low, close,
            start_date=start_d,
            end_date=end_d,
            params=p,
            allow_short=ash,
        )
        if r is None or r.num_trades == 0:
            continue
        dd = r.max_drawdown_pct
        ret = r.total_return_pct
        sh = r.sharpe_ratio
        pf = r.profit_factor
        stability = ret - 0.45 * dd + 2.0 * min(sh, 5.0) + 3.0 * min(np.log1p(max(pf, 0.01)), 2.0)
        results.append(
            {
                "macd": [fast, slow, sig],
                "tp_pct": tp,
                "sl_pct": sl,
                "rsi_ob": ob,
                "rsi_os": os,
                "allow_short": ash,
                "return_pct": round(ret, 2),
                "max_dd_pct": round(dd, 2),
                "num_trades": r.num_trades,
                "win_rate": round(r.win_rate, 1),
                "profit_factor": round(pf, 3),
                "sharpe_approx": round(sh, 3),
                "stability_score": round(float(stability), 2),
            }
        )

    if not results:
        print("Lưới không cho kết quả (thiếu nến?).")
        sys.exit(1)

    results.sort(key=lambda x: -x["stability_score"])
    pos = [x for x in results if x["return_pct"] > 0]
    pos.sort(key=lambda x: (-x["return_pct"], x["max_dd_pct"]))

    balanced = [x for x in results if x["return_pct"] > 0 and x["max_dd_pct"] <= 10.0]
    balanced.sort(key=lambda x: (-x["return_pct"], x["max_dd_pct"]))

    print("--- Gợi ý cân bằng (dương lợi nhuận, Max DD ≤ 10%) ---")
    if balanced:
        b = balanced[0]
        print(
            f"  MACD({b['macd'][0]},{b['macd'][1]},{b['macd'][2]})  "
            f"TP {b['tp_pct']*100:.1f}%  SL {b['sl_pct']*100:.1f}%  "
            f"RSI long <{b['rsi_ob']} / short >{b['rsi_os']}  short={b['allow_short']}"
        )
        print(
            f"  → Return {b['return_pct']:+.2f}%  DD {b['max_dd_pct']:.1f}%  "
            f"{b['num_trades']} lệnh  WR {b['win_rate']:.0f}%  PF {b['profit_factor']:.2f}"
        )
    else:
        print("  (Không có trong lưới — nới DD hoặc mở rộng tham số.)")

    print("\n--- Top return (dương) ---")
    for x in pos[:5]:
        print(
            f"  {x['return_pct']:+.2f}%  DD {x['max_dd_pct']:.1f}%  n={x['num_trades']}  "
            f"MACD{x['macd']} TP/SL {x['tp_pct']*100:.1f}/{x['sl_pct']*100:.1f}% "
            f"RSI {x['rsi_ob']}/{x['rsi_os']} short={x['allow_short']}"
        )

    out = ROOT / "botdown" / "reports" / f"macd_rsi_grid_{start_d}_{end_d}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "source": "binance_spot_BTCUSDT_1d",
                "start": start_d,
                "end": end_d,
                "buy_hold_pct_approx": round(bh, 2),
                "fee_roundtrip": args.fee,
                "best_balanced_dd10": balanced[0] if balanced else None,
                "top_by_stability": results[:30],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nĐã ghi {out}")


if __name__ == "__main__":
    main()
