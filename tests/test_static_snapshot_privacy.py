"""
Privacy gate for the public static snapshot (GitHub Pages).

Scans the exported JSON and fails on: /Users/ paths, $HOME, local username / hostname,
token- or key-like strings, values from .env / secret env vars, tracebacks, and any field
outside the allowlist schema in botdown/static_snapshot.py.

  .venv/bin/python -m unittest tests.test_static_snapshot_privacy -v
  STATIC_SNAPSHOT_PATH=var/gh-pages-wt/data/latest.json .venv/bin/python -m unittest tests.test_static_snapshot_privacy

Works under pytest too. scripts/publish_static.sh runs it and aborts on failure.
"""

from __future__ import annotations

import getpass
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from botdown.static_snapshot import (  # noqa: E402
    SCHEMA,
    build_snapshot,
    privacy_violations,
    sanitize,
    short_error,
    validate_schema,
)

SNAPSHOT = Path(os.environ.get("STATIC_SNAPSHOT_PATH", ROOT / "web" / "data" / "latest.json"))
if not SNAPSHOT.is_absolute():
    SNAPSHOT = ROOT / SNAPSHOT


def _fake_playbook() -> dict:
    return {
        "caption": "c",
        "scenarios": [{"name": "K", "desc": "d", "why": "w"}],
        "exits": [{"tf": "1h", "tp_pct": 1.5, "sl_pct": 0.6, "rr": 2.5, "max_hold_bars": 48}],
        "exit_note": "n",
        "ops": ["o"],
        "disclaimer": "x",
    }


def _fake_result(**over) -> dict:
    r = {
        "symbol": "BTCUSDT",
        "interval": "1h",
        "side": "none",
        "ok": True,
        "error": None,
        "bar_time": "2026-01-01 00:00",
        "signal_at": "2026-01-01 00:00:00 UTC",
        "close": 100.0,
        "entry": 100.0,
        "stop": None,
        "target": None,
        "tp_pct": 0.015,
        "sl_pct": 0.006,
        "scenarios": [],
        "features": {"oi_z_30": 1.0},
        "telegram_preview": None,
    }
    r.update(over)
    return r


class TestExportedSnapshot(unittest.TestCase):
    """The real file that gets published."""

    @classmethod
    def setUpClass(cls):
        if not SNAPSHOT.exists():
            raise unittest.SkipTest(f"no snapshot at {SNAPSHOT.name}; run scripts/export_static_snapshot.py")
        cls.text = SNAPSHOT.read_text(encoding="utf-8")
        cls.obj = json.loads(cls.text)

    def test_no_privacy_violations(self):
        probs = privacy_violations(self.text, repo_root=ROOT)
        self.assertEqual(probs, [], "snapshot leaks / schema problems: " + "; ".join(probs))

    def test_no_users_path(self):
        self.assertNotIn("/Users/", self.text)
        self.assertNotIn(os.path.expanduser("~"), self.text)

    def test_no_local_username(self):
        user = getpass.getuser()
        if len(user) >= 3:
            self.assertNotIn(user.lower(), self.text.lower())

    def test_only_allowlisted_fields(self):
        self.assertEqual(validate_schema(self.obj, SCHEMA), [])

    def test_no_account_data(self):
        low = self.text.lower()
        for word in ("balance", "position", "okx_api", "chat_id", "bot_token", "hostname", "\"liq\""):
            self.assertNotIn(word, low, word)

    def test_has_data(self):
        self.assertTrue(self.obj["details"], "details empty")
        self.assertTrue(any(d["ok"] for d in self.obj["details"]), "every scan failed")


class TestSanitizer(unittest.TestCase):
    """Detector + sanitizer catch planted leaks (guards the gate itself)."""

    def test_detector_flags_leaks(self):
        home = os.path.expanduser("~")
        leaks = {
            "users path": "/Users/someone/x.py",
            "home": f"{home}/Documents/x",
            "telegram token": "123456789:" + "A" * 35,
            "github token": "ghp_" + "a1B2" * 9,
            "traceback": "Traceback (most recent call last):\n  File x",
            "kv secret": "api_key=abcdef123456",
        }
        for name, leak in leaks.items():
            text = json.dumps({"x": leak})
            self.assertTrue(privacy_violations(text, repo_root=ROOT), name)

    def test_detector_flags_extra_field(self):
        snap = build_snapshot([_fake_result()], _fake_playbook(), "2026-01-01T00:00:00Z", "1", 15)
        self.assertEqual(privacy_violations(json.dumps(snap), repo_root=ROOT), [])
        snap["details"][0]["balance_usdt"] = 1.0
        self.assertTrue(any("allowlist" in p for p in privacy_violations(json.dumps(snap), repo_root=ROOT)))

    def test_build_drops_unknown_fields(self):
        r = _fake_result(liq={"mark": 1}, balance=123.0, features={"oi_z_30": 1.0, "secret_x": 1})
        snap = build_snapshot([r], dict(_fake_playbook(), host="mac"), "2026-01-01T00:00:00Z", "1", 15)
        self.assertEqual(validate_schema(snap), [])
        text = json.dumps(snap)
        for bad in ("liq", "balance", "secret_x", "host"):
            self.assertNotIn(f'"{bad}"', text)

    def test_error_is_short_and_path_free(self):
        home = os.path.expanduser("~")
        err = f"cannot open {home}/Documents/Cursor/Trading-bot/data/x.csv\nTraceback (most recent call last):\n  File ..."
        out = short_error(err, "FileNotFoundError")
        self.assertTrue(out.startswith("FileNotFoundError: cannot open ~/Documents"))
        self.assertNotIn("Traceback", out)
        self.assertNotIn(home, out)
        self.assertLessEqual(len(out), 160)

        r = _fake_result(ok=False, side="error", error=err, error_type="FileNotFoundError", features={})
        snap = build_snapshot([r], _fake_playbook(), "2026-01-01T00:00:00Z", "1", 15)
        self.assertEqual(privacy_violations(json.dumps(snap), repo_root=ROOT), [])

    def test_sanitize_redacts_tokens(self):
        out = sanitize({"a": ["see /Users/bob/x", "t=123456789:" + "B" * 35]})
        self.assertEqual(out["a"][0], "see ~/x")
        self.assertNotIn("B" * 35, out["a"][1])


if __name__ == "__main__":
    unittest.main()
