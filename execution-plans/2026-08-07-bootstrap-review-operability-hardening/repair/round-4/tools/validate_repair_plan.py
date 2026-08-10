from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any


ROUND_DIR = Path(__file__).resolve().parents[1]
SLICE_IDS = {"BROH-R4-S1"}
FINDING_IDS = {"BROH-R4-01", "BROH-R4-02", "BROH-R4-03"}
ACCEPTANCE_IDS = {f"BROH-R4-A{index:02d}" for index in range(1, 8)}
COMMAND_IDS = {
    "broh-r4-s1-target-test", "broh-r4-s2-regression", "broh-r4-s3-regression",
    "bootstrap-skill-tests", "round4-s1-validation", "round4-s2-validation",
    "round4-s3-validation", "round4-terminal-validation",
}


def _read(name: str) -> dict[str, Any]:
    value = json.loads((ROUND_DIR / name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"object required: {name}")
    return value


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def validate_plan(*, selected_slice: str | None = None) -> list[str]:
    errors: list[str] = []
    required = {
        "repair-findings.v1.json", "repair-plan.v1.json", "requirements.v1.json",
        "implementation-contract.v1.json", "command-registry.v1.json",
        "plan-state.v1.json", "resume-state.v1.json", "authority-manifest.v1.json",
        "knowledge-context-binding.v1.json", "tools/single_maintainer_tdd_bridge.py",
    }
    errors.extend(f"missing:{name}" for name in sorted(required) if not (ROUND_DIR / name).is_file())
    if errors:
        return errors
    try:
        findings = _read("repair-findings.v1.json")
        requirements = _read("requirements.v1.json")
        contract = _read("implementation-contract.v1.json")
        registry = _read("command-registry.v1.json")
        state = _read("plan-state.v1.json")
        resume = _read("resume-state.v1.json")
        knowledge = _read("knowledge-context-binding.v1.json")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        return [f"json-read:{exc}"]

    finding_ids = {item.get("id") for item in findings.get("findings", []) if isinstance(item, dict)}
    if finding_ids != FINDING_IDS or findings.get("round") != 4:
        errors.append("finding-set-invalid")
    acceptance_ids = {item.get("id") for item in requirements.get("acceptance", []) if isinstance(item, dict)}
    if set(requirements.get("findings", [])) != FINDING_IDS or acceptance_ids != ACCEPTANCE_IDS:
        errors.append("repair-requirements-invalid")

    slices = contract.get("slices", [])
    slice_ids = {item.get("slice_id") for item in slices if isinstance(item, dict)}
    if slice_ids != SLICE_IDS or len(slices) != 1:
        errors.append("repair-slice-set-invalid")
    if selected_slice is not None and selected_slice not in slice_ids:
        errors.append(f"unknown-slice:{selected_slice}")
    if {value for item in slices for value in item.get("finding_ids", [])} != FINDING_IDS:
        errors.append("repair-finding-coverage-invalid")
    if {value for item in slices for value in item.get("acceptance_ids", [])} != ACCEPTANCE_IDS:
        errors.append("repair-acceptance-coverage-invalid")
    if contract.get("acceptance_target") != "execution-plans/2026-08-07-bootstrap-review-operability-hardening":
        errors.append("acceptance-target-invalid")
    if contract.get("lineageFamilyId") != findings.get("lineageFamilyId"):
        errors.append("lineage-family-mismatch")
    if contract.get("authorizes") != []:
        errors.append("repair-contract-authority-leak")
    for path_key, hash_key in (("context_path", "context_sha256"), ("freeze_path", "freeze_sha256")):
        raw = knowledge.get(path_key)
        target = (ROUND_DIR / raw).resolve() if isinstance(raw, str) else None
        if target is None or not target.is_file() or knowledge.get(hash_key) != _sha(target):
            errors.append(f"repair-knowledge-binding-stale:{path_key}")
    if knowledge.get("authorizes") != []:
        errors.append("repair-knowledge-authority-leak")
    legacy = contract.get("legacy_regressions", [])
    if (
        {item.get("finding_id") for item in legacy if isinstance(item, dict)} != {"BROH-R4-02", "BROH-R4-03"}
        or any(not item.get("reason") or item.get("command_id") not in COMMAND_IDS for item in legacy if isinstance(item, dict))
    ):
        errors.append("repair-legacy-regressions-invalid")

    commands = {item.get("id"): item for item in registry.get("commands", []) if isinstance(item, dict)}
    if set(commands) != COMMAND_IDS or registry.get("authorizes") != []:
        errors.append("repair-command-registry-invalid")
    for item in slices:
        slice_id = item.get("slice_id")
        required_fields = {
            "finding_ids", "requirement_ids", "acceptance_ids", "source_refs", "depends_on",
            "allowed_changes", "planned_new_files", "execution_snapshot_paths", "forbidden_changes",
            "execution_read_set", "dependency_closure", "tdd_mode", "tdd",
            "post_refactor_command_id", "exit_predicate", "recovery",
        }
        if not required_fields.issubset(item):
            errors.append(f"repair-slice-fields-missing:{slice_id}")
            continue
        mode = item.get("tdd_mode")
        red = item.get("tdd", {}).get("red", {})
        green = item.get("tdd", {}).get("green", {})
        if mode == "red-green-refactor":
            if red.get("expected_exit") != "nonzero" or red.get("command_id") != green.get("command_id"):
                errors.append(f"repair-red-path-invalid:{slice_id}")
        elif mode == "legacy-regression":
            if red.get("expected_exit") != "zero" or not item.get("legacy_evidence"):
                errors.append(f"repair-legacy-path-invalid:{slice_id}")
            if any(item.get("allowed_changes", {}).get(group) for group in ("production", "tests", "documentation")):
                errors.append(f"repair-legacy-write-set-invalid:{slice_id}")
        else:
            errors.append(f"repair-tdd-mode-invalid:{slice_id}")
        used = [red.get("command_id"), green.get("command_id"), item.get("post_refactor_command_id")]
        used.extend(entry.get("command_id") for entry in item.get("tdd", {}).get("refactor", {}).get("invocations", []))
        if any(command_id not in commands for command_id in used):
            errors.append(f"repair-command-unregistered:{slice_id}")
        groups = item.get("allowed_changes", {})
        allowed = [path for group in groups.values() for path in group] if isinstance(groups, dict) else []
        if set(allowed) != set(item.get("execution_snapshot_paths", [])):
            errors.append(f"repair-snapshot-coverage-invalid:{slice_id}")
        if not set(item.get("planned_new_files", [])).issubset(allowed):
            errors.append(f"repair-planned-files-invalid:{slice_id}")

    state_ids = {item.get("id") for item in state.get("slices", []) if isinstance(item, dict)}
    lifecycle = state.get("state")
    lifecycle_valid = (
        lifecycle == "implementation-authorized"
        and state.get("state_owner") == "maintainer"
        and state.get("authorizes") == ["plan-ready", "implementation-authorized"]
    ) or (
        lifecycle == "implementation-complete"
        and state.get("state_owner") == "quick-dev-tdd-adapter"
        and state.get("authorizes") == ["implementation-complete"]
        and all(item.get("status") == "completed" for item in state.get("slices", []))
    )
    if not lifecycle_valid or state_ids != SLICE_IDS or state.get("blocking_conditions") != []:
        errors.append("repair-lifecycle-invalid")
    if set(resume.get("slice_status", {})) != SLICE_IDS or resume.get("authorizes") != []:
        errors.append("repair-resume-invalid")
    return sorted(set(errors))


def validate_terminal() -> list[str]:
    errors = validate_plan()
    if errors:
        return errors
    state = _read("plan-state.v1.json")
    if state.get("state") != "implementation-complete" or any(
        item.get("status") != "completed" for item in state.get("slices", [])
    ):
        errors.append("repair-implementation-not-complete")
    closure_name = _read("implementation-contract.v1.json").get("closure_output")
    closure_path = ROUND_DIR / str(closure_name)
    if not closure_path.is_file():
        errors.append("repair-closure-missing")
        return sorted(set(errors))
    try:
        closure = _read(str(closure_name))
        if closure.get("contract_sha256") != _sha(ROUND_DIR / "implementation-contract.v1.json") or closure.get("status") != "pass":
            errors.append("repair-closure-invalid")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        errors.append("repair-closure-invalid")
    closure_requirements = _read("implementation-contract.v1.json")["closure_requirements"]
    for key in ("root_cause_callsite_inventory", "composition_receipt", "changed_set_manifest", "review_scope"):
        name = closure_requirements.get(key)
        if not isinstance(name, str) or not (ROUND_DIR / name).is_file():
            errors.append(f"repair-closure-artifact-missing:{name}")
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slice", choices=sorted(SLICE_IDS))
    parser.add_argument("--terminal", action="store_true")
    args = parser.parse_args()
    errors = validate_terminal() if args.terminal else validate_plan(selected_slice=args.slice)
    payload: dict[str, Any] = {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "authorizes": [],
    }
    helper_path = ROUND_DIR / "tools" / "validate_all.py"
    spec = importlib.util.spec_from_file_location("broh_round4_validate_all", helper_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("repair candidate identity helper is unavailable")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    if args.terminal:
        snapshot = helper.validation_snapshot()
        payload.update({
            "predicate": "implementation-complete",
            "slice_id": "BROH-R4-S1",
            "contract_hash": _sha(ROUND_DIR / "implementation-contract.v1.json"),
            **snapshot,
            "validation_snapshot": snapshot,
        })
    elif args.slice:
        snapshot = helper.slice_validation_snapshot(args.slice)
        payload.update({
            "predicate": "slice-ready",
            "slice_id": args.slice,
            "contract_hash": _sha(ROUND_DIR / "implementation-contract.v1.json"),
            "predecessor_result_hashes": helper.predecessor_result_hashes(args.slice),
            **snapshot,
            "validation_snapshot": snapshot,
        })
    print(json.dumps(payload, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
