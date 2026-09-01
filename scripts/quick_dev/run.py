#!/usr/bin/env python3
"""Stable Chapter 4/5/6 Quick Dev entrypoint."""
from __future__ import annotations

import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / ".agents" / "skills" / "quick-dev-tdd-adapter" / "tools"
TARGET = TOOLS / "stable_runner.py"
if not TARGET.is_file():
    raise SystemExit("stable Quick Dev runner is missing")
sys.path.insert(0, str(TOOLS))


def _consume_value(flag: str) -> str | None:
    if flag not in sys.argv:
        return None
    index = sys.argv.index(flag)
    if index + 1 >= len(sys.argv):
        raise SystemExit(f"{flag} requires a value")
    value = sys.argv[index + 1]
    del sys.argv[index:index + 2]
    return value


def _inside_root(raw: str, label: str) -> Path:
    path = Path(raw).resolve()
    try:
        path.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise SystemExit(f"{label} must be inside repository") from exc
    if not path.is_file() or path.is_symlink():
        raise SystemExit(f"{label} is missing or unsafe")
    return path


def _public_repeat_guard() -> int | None:
    """Block a third identical deterministic failure before process launch."""
    history_raw = _consume_value("--failure-history")
    if history_raw is None:
        return None
    action = None
    if "--action" in sys.argv:
        index = sys.argv.index("--action")
        action = sys.argv[index + 1] if index + 1 < len(sys.argv) else None
    if action != "execute-stage":
        raise SystemExit("--failure-history is valid only for --action execute-stage")
    if "--descriptor" not in sys.argv:
        raise SystemExit("--failure-history requires --descriptor")
    descriptor_index = sys.argv.index("--descriptor")
    if descriptor_index + 1 >= len(sys.argv):
        raise SystemExit("--descriptor requires a value")
    descriptor_path = _inside_root(sys.argv[descriptor_index + 1], "descriptor")
    history_path = _inside_root(history_raw, "failure-history")
    descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
    history = json.loads(history_path.read_text(encoding="utf-8"))
    if not isinstance(descriptor, dict) or not isinstance(history, list):
        raise SystemExit("repeat guard inputs must be descriptor object and history list")
    from repeat_guard import repeat_guard

    result = repeat_guard(descriptor=descriptor, history=history)
    if result["status"] == "blocked":
        print(json.dumps(result, sort_keys=True))
        return 0
    return None


guard_exit = _public_repeat_guard()
if guard_exit is not None:
    raise SystemExit(guard_exit)
runpy.run_path(str(TARGET), run_name="__main__")
