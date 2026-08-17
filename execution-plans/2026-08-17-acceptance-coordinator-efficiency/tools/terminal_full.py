"""Emit machine-readable targeted and terminal predicates for this plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


PLAN = Path(__file__).resolve().parents[1]
ROOT = PLAN.parents[1]


def _hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _run(suites: tuple[tuple[str, str], ...]) -> tuple[bool, list[str]]:
    completed: list[str] = []
    for directory, pattern in suites:
        command = (
            [sys.executable, "-B", "-m", "pytest", pattern, "-q"]
            if directory == "pytest"
            else [sys.executable, "-B", "-m", "unittest", "discover", "-s", directory, "-p", pattern]
        )
        result = subprocess.run(
            command,
            cwd=ROOT, capture_output=True, check=False,
        )
        if result.returncode:
            return False, completed
        completed.append(f"pytest:{pattern}" if directory == "pytest" else f"unittest:{directory}:{pattern}")
    return True, completed


def _result(predicate: str, command_id: str, suites: tuple[tuple[str, str], ...]) -> dict[str, object]:
    passed, validated = _run(suites)
    document: dict[str, object] = {
        "schema_version": "acceptance-coordinator-efficiency.terminal-result.v1",
        "status": "pass" if passed else "fail",
        "predicate": predicate,
        "plan_id": "acceptance-coordinator-efficiency",
        "contract_hash": _hash(PLAN / "implementation-contract.v1.json"),
        "terminal_command_id": command_id,
        "validated_command_ids": validated,
        "authorizes": ["implementation-complete"] if predicate == "implementation-complete" and passed else [],
    }
    return document


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slice", choices=("S0", "S1", "S2"))
    parser.add_argument("--quick-dev-regression", action="store_true")
    parser.add_argument("--repository-root", type=Path)
    parser.add_argument("--plan-dir", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    suites_by_slice = {
        "S0": ((".agents/skills/quick-dev-tdd-adapter/tools/tests", "test_candidate_identity.py"),),
        "S1": ((".agents/skills/run-refactor-implementation-acceptance/tests", "test_review_requirement.py"),),
        "S2": (("pytest", ".agents/skills/run-refactor-implementation-acceptance/tests/test_deterministic_finalization.py"),),
    }
    quick_dev_regression = (
        (".agents/skills/quick-dev-tdd-adapter/tools/tests", "test_candidate_identity.py"),
        (".agents/skills/quick-dev-tdd-adapter/tools/tests", "test_plan_directory_loop.py"),
        (".agents/skills/quick-dev-tdd-adapter/tools/tests", "test_adapter.py"),
    )
    if args.slice:
        result = _result("slice-ready", f"s{args.slice[1]}-terminal", suites_by_slice[args.slice])
    elif args.quick_dev_regression:
        result = _result("slice-ready", "quick-dev-suite", quick_dev_regression)
    else:
        if args.repository_root is None or args.plan_dir is None or args.out is None:
            parser.error("terminal mode requires --repository-root, --plan-dir, and --out")
        result = _result(
            "implementation-complete", "terminal-full",
            (*quick_dev_regression, ("pytest", ".agents/skills/run-refactor-implementation-acceptance/tests")),
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, separators=(",", ":")))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
