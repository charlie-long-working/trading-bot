"""
Static web snapshot (GitHub Pages): allowlist schema, sanitize, privacy check.

The repo is public and the snapshot is served to anyone, so everything written to
`web/data/latest.json` goes through:

  build_snapshot()  → only allowlisted fields are copied (unknown keys dropped)
  sanitize()        → home paths → "~", errors shortened to "ExcName: msg", secrets redacted
  validate_schema() → types / required keys / no extra keys
  privacy_violations() → final scan (also run by tests + scripts/publish_static.sh)

No Streamlit / network imports here: pure functions only.
"""

from __future__ import annotations

import getpass
import json
import os
import re
import socket
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

SCHEMA_VERSION = 1
MAX_ERROR_LEN = 160
MAX_TEXT_LEN = 4000

# ---------------------------------------------------------------------------
# Allowlist schema. Leaf specs: "str", "num", "int", "bool", "str?" (nullable)...
# dict → {key: spec}; list → [item_spec]. Keys prefixed with "?" are optional.
# ---------------------------------------------------------------------------

_SERIES = {
    "t": ["int"],
    "close": ["num?"],
    "oi_usd": ["num?"],
    "funding": ["num?"],
    "usdt_d": ["num?"],
}

_FEATURES = {
    "?oi_chg_3_pct": "num?",
    "?oi_z_30": "num?",
    "?funding_z_30": "num?",
    "?usdt_d": "num?",
    "?usdt_d_chg_3": "num?",
    "?usdt_d_z_30": "num?",
    "?usdtd_risk_off": "bool",
    "?usdtd_risk_on": "bool",
    "?regime_ema": "str",
    "?bars_per_day": "int",
    "?error": "str",
    "?n": "int",
}

_SCENARIO_HIT = {"scenario": "str", "side": "str", "desc": "str"}

_DETAIL = {
    "symbol": "str",
    "interval": "str",
    "side": "str",
    "ok": "bool",
    "error": "str?",
    "bar_time": "str",
    "signal_at": "str?",
    "close": "num",
    "entry": "num?",
    "stop": "num?",
    "target": "num?",
    "tp_pct": "num",
    "sl_pct": "num",
    "scenarios": [_SCENARIO_HIT],
    "features": _FEATURES,
    "telegram_preview": "str?",
    "?oi_source": "str",
    "?series": _SERIES,
}

_SUMMARY = {
    "symbol": "str",
    "interval": "str",
    "side": "str",
    "ok": "bool",
    "bar_time": "str",
    "entry": "num?",
    "stop": "num?",
    "target": "num?",
    "scenarios": ["str"],
}

_PLAYBOOK = {
    "caption": "str",
    "scenarios": [{"name": "str", "desc": "str", "why": "str"}],
    "exits": [
        {"tf": "str", "tp_pct": "num", "sl_pct": "num", "rr": "num", "max_hold_bars": "int"}
    ],
    "exit_note": "str",
    "ops": ["str"],
    "disclaimer": "str",
}

SCHEMA: Dict[str, Any] = {
    "schema_version": "int",
    "generated_at": "str",
    "version": "str",
    "refresh_minutes": "int",
    "playbook": _PLAYBOOK,
    "summary": [_SUMMARY],
    "details": [_DETAIL],
}


def _key(k: str) -> tuple[str, bool]:
    return (k[1:], True) if k.startswith("?") else (k, False)


def allowed_keys(spec: Dict[str, Any]) -> Dict[str, Any]:
    return {_key(k)[0]: v for k, v in spec.items()}


# ---------------------------------------------------------------------------
# Filtering + validation
# ---------------------------------------------------------------------------


def filter_allowlist(obj: Any, spec: Any) -> Any:
    """Copy only allowlisted keys (recursively). Unknown keys are dropped."""
    if isinstance(spec, dict):
        if not isinstance(obj, dict):
            return obj
        keys = allowed_keys(spec)
        return {k: filter_allowlist(obj[k], keys[k]) for k in keys if k in obj}
    if isinstance(spec, list):
        if not isinstance(obj, list):
            return obj
        return [filter_allowlist(x, spec[0]) for x in obj]
    return obj


def _leaf_ok(value: Any, leaf: str) -> bool:
    nullable = leaf.endswith("?")
    base = leaf.rstrip("?")
    if value is None:
        return nullable
    if base == "str":
        return isinstance(value, str)
    if base == "bool":
        return isinstance(value, bool)
    if base == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if base == "num":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    raise ValueError(f"unknown leaf spec {leaf!r}")


def validate_schema(obj: Any, spec: Any = None, path: str = "$") -> List[str]:
    """Return a list of problems (empty = valid). Extra keys are errors."""
    if spec is None:
        spec = SCHEMA
    errs: List[str] = []
    if isinstance(spec, dict):
        if not isinstance(obj, dict):
            return [f"{path}: expected object"]
        keys = allowed_keys(spec)
        for raw_k in spec:
            k, optional = _key(raw_k)
            if k not in obj and not optional:
                errs.append(f"{path}.{k}: missing")
        for k, v in obj.items():
            if k not in keys:
                errs.append(f"{path}.{k}: not in allowlist")
                continue
            errs.extend(validate_schema(v, keys[k], f"{path}.{k}"))
        return errs
    if isinstance(spec, list):
        if not isinstance(obj, list):
            return [f"{path}: expected array"]
        for i, item in enumerate(obj):
            errs.extend(validate_schema(item, spec[0], f"{path}[{i}]"))
        return errs
    if not _leaf_ok(obj, spec):
        errs.append(f"{path}: expected {spec}, got {type(obj).__name__}")
    return errs


# ---------------------------------------------------------------------------
# Sanitize
# ---------------------------------------------------------------------------

# Things that look like credentials. Kept conservative so prices / timestamps never match.
SECRET_PATTERNS = [
    ("telegram_bot_token", re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b")),
    ("github_token", re.compile(r"\b(?:gh[pousr]|github_pat)_[A-Za-z0-9_]{20,}\b")),
    ("openai_like_key", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")),
    ("aws_key_id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("bearer", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._-]{16,}")),
    ("uuid_like_key", re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)),
    ("long_hex", re.compile(r"\b[0-9a-fA-F]{32,}\b")),
    ("long_b64", re.compile(r"(?<![A-Za-z0-9+/_-])[A-Za-z0-9+/_-]{40,}={0,2}(?![A-Za-z0-9+/_-])")),
    ("kv_secret", re.compile(r"(?i)\b(api[_-]?key|secret|passphrase|password|token|chat[_-]?id)\s*[=:]\s*\S+")),
]

_ABS_USER_PATH = re.compile(r"(/Users|/home)/[^/\s'\"]+")
_PRIVATE_DIR = re.compile(r"(/private)?/var/folders/[^\s'\"]+")
_TRACEBACK = re.compile(r"Traceback \(most recent call last\):.*", re.S)


def _home_variants() -> List[str]:
    out = []
    for h in {os.path.expanduser("~"), os.environ.get("HOME", "")}:
        if h and h != "/":
            out.append(h.rstrip("/"))
            try:
                out.append(str(Path(h).resolve()))
            except OSError:
                pass
    return sorted(set(out), key=len, reverse=True)


def sanitize_text(s: str, max_len: int = MAX_TEXT_LEN) -> str:
    for h in _home_variants():
        s = s.replace(h, "~")
    s = _ABS_USER_PATH.sub("~", s)
    s = _PRIVATE_DIR.sub("<tmp>", s)
    s = _TRACEBACK.sub("", s)
    for name, pat in SECRET_PATTERNS:
        s = pat.sub(f"<redacted:{name}>", s)
    if len(s) > max_len:
        s = s[: max_len - 1] + "…"
    return s


def short_error(err: Optional[str], err_type: Optional[str] = None) -> Optional[str]:
    """'ExcName: first line of message' — never a traceback, never long."""
    if err is None:
        return None
    msg = str(err).strip()
    msg = _TRACEBACK.sub("", msg).strip()
    first = msg.splitlines()[0].strip() if msg else ""
    out = f"{err_type}: {first}" if err_type else first
    return sanitize_text(out or (err_type or "Error"), max_len=MAX_ERROR_LEN)


def sanitize(obj: Any) -> Any:
    """Recursively sanitize every string in a JSON-able structure."""
    if isinstance(obj, str):
        return sanitize_text(obj)
    if isinstance(obj, dict):
        return {str(k): sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize(v) for v in obj]
    if isinstance(obj, float) and obj != obj:  # NaN → null (invalid JSON otherwise)
        return None
    return obj


# ---------------------------------------------------------------------------
# Build snapshot from scan results
# ---------------------------------------------------------------------------


def _num(v: Any) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else f


def _detail(r: Dict[str, Any]) -> Dict[str, Any]:
    d = dict(r)
    d["error"] = short_error(r.get("error"), r.get("error_type")) if r.get("error") else None
    for k in ("close", "tp_pct", "sl_pct"):
        d[k] = _num(d.get(k)) or 0.0
    for k in ("entry", "stop", "target"):
        d[k] = _num(d.get(k))
    d["bar_time"] = str(d.get("bar_time") or "")
    feats = dict(d.get("features") or {})
    if "error" in feats:
        feats["error"] = short_error(str(feats["error"]))
    d["features"] = feats
    return filter_allowlist(d, _DETAIL)


def _summary(d: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "symbol": d["symbol"],
        "interval": d["interval"],
        "side": d["side"],
        "ok": d["ok"],
        "bar_time": d["bar_time"],
        "entry": d.get("entry") if d.get("entry") is not None else (d.get("close") or None),
        "stop": d.get("stop"),
        "target": d.get("target"),
        "scenarios": [s.get("scenario", "") for s in d.get("scenarios") or []],
    }


def build_snapshot(
    results: List[Dict[str, Any]],
    playbook: Dict[str, Any],
    generated_at: str,
    version: str,
    refresh_minutes: int,
) -> Dict[str, Any]:
    details = [_detail(r) for r in results]
    snap = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "version": version,
        "refresh_minutes": int(refresh_minutes),
        "playbook": filter_allowlist(playbook, _PLAYBOOK),
        "summary": [_summary(d) for d in details],
        "details": details,
    }
    return sanitize(filter_allowlist(snap, SCHEMA))


def scan_usable(results: List[Dict[str, Any]]) -> bool:
    """False when every scan failed (keep the previous latest.json in that case)."""
    for r in results:
        if r.get("ok") and not (r.get("features") or {}).get("error"):
            return True
    return False


# ---------------------------------------------------------------------------
# Privacy check (shared by tests/test_static_snapshot_privacy.py and publish)
# ---------------------------------------------------------------------------


def _local_identities() -> List[str]:
    ids = set()
    for fn in (getpass.getuser, lambda: os.environ.get("USER", ""), lambda: os.environ.get("LOGNAME", "")):
        try:
            v = fn()
        except Exception:
            v = ""
        if v and len(v) >= 3:
            ids.add(v)
    for fn in (socket.gethostname, lambda: os.uname().nodename):
        try:
            h = fn()
        except Exception:
            h = ""
        if h and len(h) >= 3 and h.lower() not in {"localhost"}:
            ids.add(h)
            ids.add(h.split(".")[0])
    return sorted(i for i in ids if len(i) >= 3)


def _dotenv_values(paths: Iterable[Path]) -> List[tuple[str, str]]:
    out = []
    for p in paths:
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            v = v.strip().strip("'\"")
            if len(v) >= 6 and v.lower() not in {"true", "false", "none", "null"}:
                out.append((k.strip().removeprefix("export ").strip(), v))
    return out


_SECRET_ENV = re.compile(r"(?i)(TOKEN|SECRET|KEY|PASS|CHAT_ID|WEBHOOK)")


def privacy_violations(text: str, repo_root: Optional[Path] = None) -> List[str]:
    """
    Problems found in serialized snapshot JSON. Messages never echo the secret itself.
    """
    probs: List[str] = []
    if "/Users/" in text or "/home/" in text:
        probs.append("absolute home path (/Users/ or /home/)")
    for h in _home_variants():
        if h in text:
            probs.append("$HOME path")
    low = text.lower()
    for ident in _local_identities():
        if re.search(r"(?<![a-z0-9])" + re.escape(ident.lower()) + r"(?![a-z0-9])", low):
            probs.append("local username/hostname")
            break
    for name, pat in SECRET_PATTERNS:
        if pat.search(text):
            probs.append(f"secret-like string ({name})")
    if "Traceback (most recent call last)" in text:
        probs.append("traceback")
    root = repo_root or Path(__file__).resolve().parents[1]
    for k, v in _dotenv_values([root / ".env"]):
        if v in text:
            probs.append(f".env value of {k}")
    for k, v in os.environ.items():
        if _SECRET_ENV.search(k) and v and len(v) >= 6 and v in text:
            probs.append(f"env value of {k}")

    try:
        obj = json.loads(text)
    except ValueError as e:
        probs.append(f"invalid JSON ({type(e).__name__})")
        return probs
    probs.extend(validate_schema(obj))
    return probs
