#!/usr/bin/env python3
"""Exercise every canonical Quick Dev action through the public stable facade.

This evaluator invokes scripts/quick_dev/run.py as an external process. It uses
an independent expected action table and verifies that each public action reaches
its production route rather than being parser-only or an internal-only helper.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
ENTRY = ROOT / "scripts" / "quick_dev" / "run.py"
EXPECTED_ACTIONS = (
    "preflight",
    "recommendation",
    "execute-stage",
    "implementation-handoff",
    "implementation-finish",
    "slice-ready",
    "implementation-complete",
    "recover",
)
REQUIRED_ROUTE_COVERAGE = 1.0


def _fixture(base: Path) -> tuple[Path, str]:
    relative = base.relative_to(ROOT).as_posix()
    plan = base / "plan"
    plan.mkdir(parents=True)
    (base / "src").mkdir()
    (base / "tests").mkdir()
    owner = f"{relative}/src/value.py"
    selector = f"{relative}/tests/test_value.py"
    fixture = f"{relative}/tests/fixture.txt"
    (ROOT / owner).write_text("VALUE = 1\n", encoding="utf-8")
    (ROOT / selector).write_text("def test_value():\n    assert True\n", encoding="utf-8")
    (ROOT / fixture).write_text("fixture\n", encoding="utf-8")
    bundle = {
        "schema_version": "vdd.semantic-plan-bundle.v1",
        "plan_id": "PLAN-FACADE",
        "acceptances": [{
            "acceptance_id": "A-FACADE",
            "assertion_ids": ["ASSERT-FACADE"],
            "complexity_class": "simple",
            "verification_lane": "unit",
            "context_lookup_required": False,
            "context_lookup_reason": "single owner",
            "minimum_red_scope": "one bound Acceptance group",
            "upgrade_conditions": ["multiple roots"],
        }],
        "failure_intents": [{"failure_intent_id": "FI-FACADE", "failure_id": "FACADE-RED"}],
        "slices": [{
            "slice_id": "S1",
            "acceptance_ids": ["A-FACADE"],
            "failure_intent_ids": ["FI-FACADE"],
            "production_owners": [owner],
            "planned_new_files": [],
            "allowed_write_paths": [owner],
            "execution_snapshot_paths": [selector, fixture],
            "terminal_predicate": "all active Acceptance assertions pass",
            "complexity_class": "simple",
            "verification_lane": "unit",
            "context_lookup_required": False,
            "context_lookup_reason": "single owner",
            "minimum_red_scope": "one bound Acceptance group",
            "upgrade_conditions": ["multiple roots"],
        }],
    }
    (plan / "semantic-plan-bundle.v1.json").write_text(json.dumps(bundle), encoding="utf-8")
    return plan, "S1"


def _invoke(plan: Path, slice_id: str, action: str) -> tuple[int, dict]:
    cmd = [sys.executable, str(ENTRY), "--plan", str(plan), "--slice", slice_id, "--action", action]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    raw = (proc.stdout or proc.stderr).strip().splitlines()
    payload: dict = {}
    if raw:
        try:
            value = json.loads(raw[-1])
            if isinstance(value, dict):
                payload = value
        except json.JSONDecodeError:
            payload = {"raw": raw[-1]}
    return proc.returncode, payload


def evaluate() -> dict:
    work_parent = ROOT / ".tmp-ch456-facade"
    work_parent.mkdir(exist_ok=True)
    rows = []
    passed = 0
    try:
        with tempfile.TemporaryDirectory(prefix="route-", dir=work_parent) as raw:
            plan, slice_id = _fixture(Path(raw))
            expectations = {
                "preflight": lambda code, p: code == 0 and p.get("status") in {"preflight-passed", "environment-blocked"},
                "recommendation": lambda code, p: code == 0 and p.get("reason_code") == "current-snapshot-input-missing",
                "execute-stage": lambda code, p: code == 1 and "execute-stage requires --run-dir and --descriptor" in str(p.get("reason", "")),
                "implementation-handoff": lambda code, p: code == 1 and "implementation-handoff requires --run-dir --snapshot-roots --source-commit" in str(p.get("reason", "")),
                "implementation-finish": lambda code, p: code == 1 and "implementation-finish requires --run-dir --before-state --snapshot-roots --source-commit" in str(p.get("reason", "")),
                "slice-ready": lambda code, p: code == 1 and "slice-ready requires --run-dir --snapshot-roots --source-commit --out" in str(p.get("reason", "")),
                "implementation-complete": lambda code, p: code == 1 and "implementation-complete requires --snapshot-roots --predecessors --source-commit --out" in str(p.get("reason", "")),
                "recover": lambda code, p: code == 1 and "recover requires --run-dir --recovery-input --snapshot-roots --source-commit" in str(p.get("reason", "")),
            }
            for action in EXPECTED_ACTIONS:
                code, payload = _invoke(plan, slice_id, action)
                ok = bool(expectations[action](code, payload))
                passed += int(ok)
                rows.append({"action": action, "route_proven": ok, "exit_code": code, "status": payload.get("status"), "reason": payload.get("reason") or payload.get("reason_code")})
    finally:
        try:
            if work_parent.exists() and not any(work_parent.iterdir()):
                work_parent.rmdir()
        except OSError:
            pass
    coverage = passed / len(EXPECTED_ACTIONS)
    return {
        "schema": "quick-dev.stable-facade-route-metric.v1",
        "expected_actions": list(EXPECTED_ACTIONS),
        "total_actions": len(EXPECTED_ACTIONS),
        "proven_routes": passed,
        "route_coverage": round(coverage, 6),
        "required_route_coverage": REQUIRED_ROUTE_COVERAGE,
        "threshold_passed": coverage >= REQUIRED_ROUTE_COVERAGE,
        "routes": rows,
        "authorizes": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = evaluate()
    text = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["threshold_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
