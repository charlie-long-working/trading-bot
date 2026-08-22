#!/usr/bin/env python3
"""Launch OI live playbook Streamlit dashboard."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = ROOT / "botdown" / "dashboard_oi_playbook.py"


def main() -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return subprocess.call(
        [sys.executable, "-m", "streamlit", "run", str(APP), "--server.headless", "true"],
        cwd=str(ROOT),
        env=env,
    )


if __name__ == "__main__":
    raise SystemExit(main())
