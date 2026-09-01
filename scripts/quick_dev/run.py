#!/usr/bin/env python3
"""Stable Chapter 4/5/6 Quick Dev entrypoint."""
from __future__ import annotations

from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / ".agents" / "skills" / "quick-dev-tdd-adapter" / "tools" / "current_router.py"
if not TARGET.is_file():
    raise SystemExit("current Quick Dev router is missing")
sys.path.insert(0, str(TARGET.parent))
runpy.run_path(str(TARGET), run_name="__main__")
