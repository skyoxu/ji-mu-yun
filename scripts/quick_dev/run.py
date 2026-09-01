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


def _peek_value(flag: str) -> str | None:
    if flag not in sys.argv:
        return None
    index = sys.argv.index(flag)
    if index + 1 >= len(sys.argv):
        return None
    return sys.argv[index + 1]


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


def _public_q1_planned_contract_guard() -> int | None:
    """Fail closed on an incomplete planned descriptor contract before Q1 runtime probe."""
    if "--recommendation-only" in sys.argv:
        return None
    action = _peek_value("--action") or "preflight"
    if action not in {"preflight", "run-preflight"}:
        return None
    plan_raw = _peek_value("--plan")
    slice_id = _peek_value("--slice")
    if plan_raw is None or slice_id is None:
        return None  # Let the stable argparse contract report missing required CLI values.
    plan = Path(plan_raw).resolve()
    try:
        plan.relative_to(ROOT.resolve())
    except ValueError:
        print(json.dumps({"status": "blocked", "recommended_action": "repair-vdd", "reason": "plan must be inside repository"}, sort_keys=True))
        return 1
    semantic = plan / "semantic-plan-bundle.v1.json"
    if not semantic.is_file() or semantic.is_symlink():
        return None  # Stable runner owns legacy/current plan routing diagnostics.
    timeout_raw = _peek_value("--worker-timeout-seconds")
    try:
        timeout_seconds = int(timeout_raw) if timeout_raw is not None else 600
        bundle = json.loads(semantic.read_text(encoding="utf-8"))
        if not isinstance(bundle, dict):
            raise ValueError("semantic plan must be JSON object")
        from q1_planned_preflight import validate_planned_preflight

        validate_planned_preflight(
            workspace=ROOT,
            bundle=bundle,
            slice_id=slice_id,
            timeout_seconds=timeout_seconds,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"status": "blocked", "recommended_action": "repair-vdd", "reason": str(exc)}, sort_keys=True))
        return 1
    return None


guard_exit = _public_repeat_guard()
if guard_exit is not None:
    raise SystemExit(guard_exit)
q1_exit = _public_q1_planned_contract_guard()
if q1_exit is not None:
    raise SystemExit(q1_exit)
runpy.run_path(str(TARGET), run_name="__main__")
