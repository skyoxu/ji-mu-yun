#!/usr/bin/env python3
"""Stable Chapter 4/5/6 Quick Dev entrypoint."""
from __future__ import annotations

from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / ".agents" / "skills" / "quick-dev-tdd-adapter" / "tools" / "stable_runner.py"
if not TARGET.is_file():
    raise SystemExit("stable Quick Dev runner is missing")
sys.path.insert(0, str(TARGET.parent))
runpy.run_path(str(TARGET), run_name="__main__")
