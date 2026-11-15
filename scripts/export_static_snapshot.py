#!/usr/bin/env python3
"""
Export the live OI playbook snapshot for the static web (GitHub Pages).

  .venv/bin/python scripts/export_static_snapshot.py            # scan + write
  .venv/bin/python scripts/export_static_snapshot.py --check    # privacy-check existing latest.json

Writes:
  web/data/latest.json                       (published; atomic tmp → rename)
  var/static-history/<YYYYMMDD-HHMM>.json    (LOCAL only, gitignored, pruned after 30 days)

Exit codes: 0 ok · 2 every scan failed (latest.json kept) · 3 schema/privacy check failed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from botdown.oi_snapshot import LIVE_INTERVALS, LIVE_SYMBOLS, playbook_data, scan_all  # noqa: E402
from botdown.static_snapshot import (  # noqa: E402
    build_snapshot,
    privacy_violations,
    scan_usable,
    validate_schema,
)

LATEST = ROOT / "web" / "data" / "latest.json"
HISTORY_DIR = ROOT / "var" / "static-history"
HISTORY_DAYS = 30


def _log(msg: str) -> None:
    print(f"[export_static] {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}Z {msg}", flush=True)


def _version() -> str:
    try:
        return (ROOT / "VERSION").read_text(encoding="utf-8").strip() or "0"
    except OSError:
        return "0"


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def prune_history(directory: Path, days: int = HISTORY_DAYS) -> int:
    if not directory.is_dir():
        return 0
    cutoff = time.time() - days * 86400
    n = 0
    for p in directory.glob("*.json"):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
                n += 1
        except OSError:
            pass
    return n


def check_file(path: Path) -> int:
    if not path.exists():
        _log(f"check: missing {path.relative_to(ROOT)}")
        return 3
    probs = privacy_violations(path.read_text(encoding="utf-8"), repo_root=ROOT)
    if probs:
        for p in probs:
            _log(f"PRIVACY/SCHEMA FAIL: {p}")
        return 3
    _log("check: ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbols", default=",".join(LIVE_SYMBOLS))
    ap.add_argument("--intervals", default=",".join(LIVE_INTERVALS))
    ap.add_argument("--lookback", type=int, default=None, help="bars (default: live DEFAULT_LOOKBACK per TF)")
    ap.add_argument("--refresh-minutes", type=int, default=int(os.environ.get("STATIC_REFRESH_MINUTES", "15")),
                    help="publish cadence; the web shows 'data cũ' after 2× this")
    ap.add_argument("--out", type=Path, default=LATEST)
    ap.add_argument("--no-history", action="store_true")
    ap.add_argument("--check", action="store_true", help="only privacy/schema-check --out")
    args = ap.parse_args(argv)

    if args.check:
        return check_file(args.out)

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    intervals = [s.strip() for s in args.intervals.split(",") if s.strip()]
    _log(f"scan {symbols} × {intervals}")
    results = scan_all(symbols, intervals, args.lookback, include_series=True)
    for r in results:
        _log(f"  {r.get('symbol')} {r.get('interval')}: side={r.get('side')} ok={r.get('ok')}")

    if not scan_usable(results):
        _log("every scan failed → keeping previous latest.json (not overwritten)")
        return 2

    now = datetime.now(timezone.utc).replace(microsecond=0)
    snap = build_snapshot(
        results,
        playbook_data(),
        generated_at=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        version=_version(),
        refresh_minutes=args.refresh_minutes,
    )
    errs = validate_schema(snap)
    if errs:
        for e in errs[:20]:
            _log(f"SCHEMA FAIL: {e}")
        return 3
    text = json.dumps(snap, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    probs = privacy_violations(text, repo_root=ROOT)
    if probs:
        for p in probs:
            _log(f"PRIVACY FAIL: {p}")
        return 3

    write_atomic(args.out, text)
    _log(f"wrote {args.out.relative_to(ROOT) if args.out.is_relative_to(ROOT) else args.out.name} ({len(text):,} bytes)")

    if not args.no_history:
        hist = HISTORY_DIR / f"{now:%Y%m%d-%H%M}.json"
        write_atomic(hist, text)
        pruned = prune_history(HISTORY_DIR)
        _log(f"history: {hist.relative_to(ROOT)} (pruned {pruned})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
