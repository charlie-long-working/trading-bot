#!/usr/bin/env python3
"""
Scan OI + USDT.D live (I + K) on H1/H4 → Telegram when side != none.

  cd Trading-bot
  PYTHONPATH=. python3 -m botdown.run_oi_telegram --dry-run --interval 1h
  PYTHONPATH=. python3 -m botdown.run_oi_telegram --interval auto
  PYTHONPATH=. python3 -m botdown.run_oi_telegram --symbols BTCUSDT --interval 4h --force
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Set

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from botdown.oi_live_signal import format_oi_telegram, scan_oi_live
from notify.telegram import send_message

CACHE_PATH = ROOT / "botdown" / "reports" / "oi_telegram_sent.json"


def _load_cache() -> Set[str]:
    if not CACHE_PATH.exists():
        return set()
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        return set(data.get("keys", []))
    except (json.JSONDecodeError, TypeError, OSError):
        return set()


def _save_cache(keys: Set[str], max_keys: int = 400) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    trimmed = sorted(keys)[-max_keys:]
    CACHE_PATH.write_text(
        json.dumps(
            {"updated_at": datetime.now(timezone.utc).isoformat(), "keys": trimmed},
            indent=2,
        ),
        encoding="utf-8",
    )


def _alert_key(symbol: str, interval: str, side: str, bar_time: str, scenarios: list) -> str:
    names = "+".join(sorted(a.get("scenario", "") for a in scenarios))
    return f"{symbol}|{interval}|{side}|{bar_time}|{names}"


def resolve_intervals(mode: str) -> List[str]:
    """auto: always 1h; add 4h when UTC hour divisible by 4."""
    if mode == "auto":
        hour = datetime.now(timezone.utc).hour
        out = ["1h"]
        if hour % 4 == 0:
            out.append("4h")
        return out
    return [mode]


def main() -> int:
    ap = argparse.ArgumentParser(description="OI I+K H1/H4 → Telegram alerts")
    ap.add_argument("--symbols", default="BTCUSDT,ETHUSDT")
    ap.add_argument(
        "--interval",
        default="auto",
        help="1h | 4h | auto (1h always; 4h when UTC hour %% 4 == 0)",
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="ignore dedupe cache")
    ap.add_argument("--no-liq", action="store_true", help="skip liquidation map fetch")
    ap.add_argument("--no-dedupe", action="store_true")
    args = ap.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    intervals = resolve_intervals(args.interval.strip().lower())
    for iv in intervals:
        if iv not in ("1h", "4h"):
            print(f"Unsupported interval {iv}; use 1h, 4h, or auto", file=sys.stderr)
            return 2

    dedupe = not args.no_dedupe and not args.force
    cache = _load_cache() if dedupe else set()
    new_keys: Set[str] = set()
    sent = 0
    scanned = 0
    errors = 0

    print(f"Intervals={intervals} symbols={symbols} dry_run={args.dry_run}")
    for symbol in symbols:
        for interval in intervals:
            scanned += 1
            try:
                alert = scan_oi_live(
                    symbol,
                    interval=interval,
                    include_liq=not args.no_liq,
                )
            except Exception as e:
                errors += 1
                print(f"ERR {symbol} {interval}: {e}", file=sys.stderr)
                continue

            if alert.features.get("error"):
                errors += 1
                print(f"ERR {symbol} {interval}: {alert.features.get('error')}")
                continue

            if alert.side == "none":
                print(f"  {symbol} {interval}: none @ {alert.bar_time or '?'}")
                continue

            key = _alert_key(symbol, interval, alert.side, alert.bar_time, alert.scenarios)
            if dedupe and key in cache:
                print(f"  {symbol} {interval}: {alert.side} @ {alert.bar_time} (deduped)")
                continue

            msg = format_oi_telegram(alert)
            if not msg:
                continue

            if args.dry_run:
                print("---")
                print(msg)
                sent += 1
                new_keys.add(key)
                continue

            ok, err = send_message(msg)
            if ok:
                sent += 1
                new_keys.add(key)
                print(f"SENT {alert.side} {symbol} {interval} @ {alert.bar_time}")
            else:
                errors += 1
                print(f"SEND FAIL {symbol} {interval}: {err}", file=sys.stderr)

    if dedupe and new_keys and not args.dry_run:
        cache |= new_keys
        _save_cache(cache)
    elif args.dry_run and new_keys:
        print(f"(dry-run) would cache {len(new_keys)} keys")

    print(f"Done scanned={scanned} alerts={sent} errors={errors}")
    # Fail job if every scan errored (e.g. Bybit 403 without fallback)
    if scanned > 0 and errors >= scanned and sent == 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
