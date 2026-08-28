"""Validate the executable RED/GREEN separation contract."""
from __future__ import annotations

import ast
import json
import subprocess
import sys
import re
import hashlib
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

def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

def _ref_current(root: Path, value: object) -> bool:
    if not isinstance(value, dict) or set(value) != {"path", "sha256"}:
        return False
    path, expected = value.get("path"), value.get("sha256")
    if not isinstance(path, str) or not isinstance(expected, str):
        return False
    target = (root / path).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        return False
    return target.is_file() and _sha(target) == expected

def _candidate_is_ancestor(root: Path, commit: str) -> bool:
    result = subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=root)
    return result.returncode == 0

def verify_review(plan: Path) -> tuple[bool, list[str], dict]:
    root = plan.parents[1]
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    errors: list[str] = []
    inputs = sorted((plan / "governance").glob("external-semantic-review-input*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    selected = None
    for path in inputs:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if value.get("candidate", {}).get("head_commit") == head:
            selected = (path, value)
            break
    if selected is None:
        errors.append(f"candidate-review-input-missing-or-stale:HEAD={head}")
        return False, errors, {"candidate_commit": head, "hashes_current": False}
    input_path, value = selected
    candidate = value.get("candidate", {})
    if not _candidate_is_ancestor(root, candidate.get("head_commit", "")):
        errors.append("review-candidate-not-ancestor")
    for key in ("implementation_contract", "command_registry", "source_freeze", "requirements_mapping", "skill_input_receipt"):
        if not _ref_current(root, value.get(key)):
            errors.append(f"review-input-stale:{key}")
    bindings = value.get("required_review_bindings", {})
    run_candidates = sorted((plan / "governance").glob("vdd-review-run*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    run = None
    for path in run_candidates:
        try:
            rv = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if rv.get("status") == "accepted" and rv.get("decision") == "accepted" and all(rv.get(k) == bindings.get(k) for k in ("semantic_handoff_hash", "source_manifest_hash", "requirements_manifest_hash", "ambiguity_ids", "affected_requirement_ids")):
            run = (path, rv)
            break
    if run is None:
        errors.append("accepted-review-run-missing-or-binding-mismatch")
    binding_candidates = sorted((plan / "governance").glob("vdd-review-candidate-binding*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not any(_binding_matches(root, p, input_path, run[0] if run else None, candidate.get("head_commit")) for p in binding_candidates):
        errors.append("accepted-review-candidate-binding-missing-or-stale")
    return not errors, errors, {"candidate_commit": head, "hashes_current": not errors, "review_input": input_path.relative_to(root).as_posix(), "decision": run[1].get("decision") if run else None}

def _binding_matches(root: Path, path: Path, input_path: Path, run_path: Path | None, commit: str | None) -> bool:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (value.get("status") == "accepted" and value.get("decision") == "accepted" and value.get("candidate_commit") == commit and value.get("review_input") == {"path": input_path.relative_to(root).as_posix(), "sha256": _sha(input_path)} and (run_path is None or value.get("review_run") == {"path": run_path.relative_to(root).as_posix(), "sha256": _sha(run_path)}))

def verify_authorization(plan: Path) -> tuple[bool, list[str], dict]:
    root = plan.parents[1]
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    errors: list[str] = []
    path = plan / "implementation-authorization-receipt.v4.json"
    if not path.is_file():
        return False, ["implementation-authorization-v4-missing"], {"candidate_commit": head, "hashes_current": False, "authorizes_implementation": False}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, ["implementation-authorization-v4-invalid-json"], {"candidate_commit": head, "hashes_current": False, "authorizes_implementation": False}
    if value.get("schema_version") != "quick-dev-tdd-adapter.implementation-authorization.v4": errors.append("authorization-schema-not-v4")
    if value.get("candidate_commit") != head: errors.append("authorization-candidate-mismatch")
    if value.get("owner") != "maintainer": errors.append("authorization-owner-mismatch")
    if value.get("mode") != "high_velocity_tdd": errors.append("authorization-mode-mismatch")
    if value.get("authorizes") != ["implementation-authorized"]: errors.append("authorization-scope-mismatch")
    for key in ("review_candidate_binding", "implementation_contract", "command_registry", "requirements_mapping", "source_freeze", "authority_manifest"):
        if not _ref_current(root, value.get(key)):
            errors.append(f"authorization-stale:{key}")
    return not errors, errors, {"candidate_commit": head, "hashes_current": not errors, "owner": value.get("owner"), "authorizes_implementation": not errors}


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--probe-red-contracts", action="store_true")
    parser.add_argument("--verify-green-routing", action="store_true")
    parser.add_argument("--verify-repair-boundary", action="store_true")
    parser.add_argument("--verify-review", action="store_true")
    parser.add_argument("--verify-authorization", action="store_true")
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
    result = {"status": "pass" if ok else "blocked", "errors": errors}
    if args.verify_review:
        review_ok, review_errors, review_result = verify_review(plan)
        ok = ok and review_ok
        errors.extend(review_errors)
        result["external_review"] = review_result
    if args.verify_authorization:
        auth_ok, auth_errors, auth_result = verify_authorization(plan)
        ok = ok and auth_ok
        errors.extend(auth_errors)
        result["maintainer_authorization"] = auth_result
    result["status"] = "pass" if ok else "blocked"
    result["errors"] = errors
    print(json.dumps(result, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
