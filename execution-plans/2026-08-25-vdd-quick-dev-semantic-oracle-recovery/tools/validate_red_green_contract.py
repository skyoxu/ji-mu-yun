"""Validate the executable RED/GREEN separation contract."""
from __future__ import annotations

import ast
import json
import subprocess
import sys
import re
from pathlib import Path


def validate(plan: Path) -> tuple[bool, list[str]]:
    contract = json.loads((plan / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    errors: list[str] = []
    subjects = {"S1": "compile_run_local_semantic_artifacts", "S2": "validate_descriptor", "S3": "validate_judge", "S4": "validate_many_to_many_cover", "S5": "validate_fixture_observation", "S6": "prepare_terminal_observation"}
    for item in contract.get("slices", []):
        sid = item.get("slice_id")
        red = item.get("tdd", {}).get("red", {})
        selector = red.get("test_selector")
        if not isinstance(selector, str):
            errors.append(f"{sid}:missing-red-selector")
            continue
        path = (plan.parents[1] / selector).resolve()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError):
            errors.append(f"{sid}:red-selector-unreadable")
            continue
        source = ast.unparse(tree)
        if "assert False" in source or "raise AssertionError" in source and "FAILURE_ID" not in source:
            errors.append(f"{sid}:constant-red-placeholder")
        if not any(isinstance(node, ast.Call) for node in ast.walk(tree)):
            errors.append(f"{sid}:red-has-no-behavior-call")
        if subjects.get(sid) and subjects[sid] not in source:
            errors.append(f"{sid}:red-subject-not-called:{subjects[sid]}")
        if "Path.cwd()" in source or "os.environ" in source:
            errors.append(f"{sid}:red-uses-environment-fixture")
        if "FileNotFoundError" in source or "ImportError" in source:
            errors.append(f"{sid}:red-environment-error-path")
        if sid == "S1" and "compile_run_local_semantic_artifacts" not in source:
            errors.append(f"{sid}:red-not-production-subject")
        green = item.get("tdd", {}).get("green", {})
        green_id = green.get("command_id")
        if not isinstance(green_id, str) or green_id == red.get("command_id"):
            errors.append(f"{sid}:green-reuses-red-command")
        regressions = item.get("tdd", {}).get("regression", {}).get("test_selectors")
        if not isinstance(regressions, list) or not regressions:
            errors.append(f"{sid}:missing-regression-selectors")
        else:
            for regression in regressions:
                regression_path = (plan.parents[1] / regression).resolve()
                if not regression_path.is_file():
                    errors.append(f"{sid}:regression-selector-missing:{regression}")
        if not isinstance(item.get("planned_new_files"), list) and not isinstance(item.get("allowed_changes", {}).get("production"), list):
            errors.append(f"{sid}:missing-implementation-entrypoint")
        if not item.get("allowed_changes", {}).get("production"):
            errors.append(f"{sid}:missing-success-artifact-owner")
    return not errors, errors

def probe_red_contracts(plan: Path) -> tuple[bool, list[str]]:
    contract = json.loads((plan / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    errors = []
    for item in contract.get("slices", []):
        red = item.get("tdd", {}).get("red", {})
        expected = set(red.get("expected_failure_ids", []))
        result = subprocess.run([sys.executable, "-m", "pytest", red["test_selector"], "-q"], cwd=plan.parents[1], capture_output=True, text=True)
        output = (result.stdout or "") + "\n" + (result.stderr or "")
        observed = set(re.findall(r"FAILURE_ID:([A-Z0-9-]+)", output))
        if result.returncode == 0 or observed != expected:
            errors.append(f"{item.get('slice_id')}:red-probe-mismatch:exit={result.returncode}:observed={sorted(observed)}:expected={sorted(expected)}")
    return not errors, errors

def verify_green_routing(plan: Path) -> tuple[bool, list[str]]:
    contract = json.loads((plan / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    errors = []
    for item in contract.get("slices", []):
        expected = item["tdd"]["red"]["test_selector"]
        for stage in ("green", "refactor"):
            result = subprocess.run([sys.executable, str(plan / "tools" / "stage_command.py"), "--slice", item["slice_id"], "--stage", stage, "--plan-dir", str(plan), "--resolve-selectors"], cwd=plan.parents[1], capture_output=True, text=True)
            try:
                value = json.loads(result.stdout or "{}")
            except json.JSONDecodeError:
                errors.append(f"{item['slice_id']}:{stage}:invalid-routing-output")
                continue
            if result.returncode != 0 or value.get("red_selector") != expected or not value.get("pytest_selectors") or value["pytest_selectors"][0] != expected:
                errors.append(f"{item['slice_id']}:{stage}:red-selector-not-first")
    return not errors, errors

def verify_repair_boundary(plan: Path) -> tuple[bool, list[str]]:
    base = "795b718e0dcd161e510ee1560ba65eb3b5b01177"
    result = subprocess.run(["git", "diff", "--name-only", f"{base}..HEAD"], cwd=plan.parents[1], capture_output=True, text=True, check=False)
    forbidden = {"semantic_oracle.py", "semantic_artifact_compiler.py", "descriptor_compiler.py", "independent_judge.py", "coverage_gate.py", "promotion_gate.py", "false_green_fixture_runner.py", "terminal_validator.py", "terminal_predicate.py", "validate_all.py", "artifact_owners.py", "build_run_inputs.py"}
    changed = [line for line in result.stdout.splitlines() if any(line.endswith(name) for name in forbidden)]
    return not changed, [f"repair-boundary-target-changed:{path}" for path in changed]


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--probe-red-contracts", action="store_true")
    parser.add_argument("--verify-green-routing", action="store_true")
    parser.add_argument("--verify-repair-boundary", action="store_true")
    args = parser.parse_args()
    plan = args.plan_dir.resolve()
    ok, errors = validate(plan)
    if args.probe_red_contracts:
        probe_ok, probe_errors = probe_red_contracts(plan)
        ok = ok and probe_ok
        errors.extend(probe_errors)
    if args.verify_green_routing:
        routing_ok, routing_errors = verify_green_routing(plan)
        ok = ok and routing_ok
        errors.extend(routing_errors)
    if args.verify_repair_boundary:
        boundary_ok, boundary_errors = verify_repair_boundary(plan)
        ok = ok and boundary_ok
        errors.extend(boundary_errors)
    print(json.dumps({"status": "pass" if ok else "blocked", "errors": errors}, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
