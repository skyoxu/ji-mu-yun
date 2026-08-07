from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


PLAN_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = PLAN_DIR.parents[1]
PLAN_ID = "quick-dev-phase-regression-repair-mode"
PLAN_DIRECTORY = "2026-08-06-quick-dev-phase-regression-repair-mode"
REPORT = "95-implementation-evolution-and-completion-report.md"
SLICE_IDS = ["RMAP-S0", "RMAP-S1", "RMAP-S2"]
REQUIRED_MODULES = {
    "repository-governance",
    "quick-dev-repair-protocol",
    "phase-service-maintenance",
    "historical-log-evidence",
    "acceptance-boundary",
}
REQUIRED_CASES = {
    "valid-phase-repair",
    "missing-callsite",
    "missing-historical-log-search",
    "error-without-new-evidence-file",
    "new-test-with-existing-test",
    "speculative-hypothesis",
    "protected-phase-path-without-approval",
    "historical-log-treated-as-authority",
    "wrong-red-selector-or-id",
}
REQUIRED_FILES = [
    "00-index.md",
    "requirements.v1.json",
    "implementation-contract.v1.json",
    "command-registry.v1.json",
    "authority-manifest.v1.json",
    "baseline-and-scope.v1.json",
    "plan-state.v1.json",
    "resume-state.v1.json",
    "model-route-decision.v1.json",
    "knowledge-context.v1.json",
    "knowledge-context.freeze.v1.json",
    "fixtures/regression-repair-contract-cases.v1.json",
    REPORT,
    "tools/validate_plan.py",
    "tools/validate_implementation.py",
    "tools/tests/test_validate_plan.py",
    "tools/tests/test_validate_implementation.py",
]


def load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"invalid-json:{path.as_posix()}:{exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"json-root-not-object:{path.as_posix()}")
        return {}
    return value


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def duplicates(values: list[str]) -> set[str]:
    return {value for value in values if values.count(value) > 1}


def check_dependency_graph(slices: list[dict[str, Any]], errors: list[str]) -> None:
    graph = {item.get("slice_id"): item.get("depends_on", []) for item in slices}
    if list(graph) != SLICE_IDS:
        errors.append("slice-order-or-set-invalid")
        return
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            errors.append(f"slice-cycle:{node}")
            return
        if node in visited:
            return
        visiting.add(node)
        for dependency in graph.get(node, []):
            if dependency not in graph:
                errors.append(f"unknown-slice-dependency:{node}:{dependency}")
            else:
                visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)


def validate_contract_schema(contract: dict[str, Any], errors: list[str]) -> None:
    runtime_path = REPO_ROOT / ".agents/skills/bmad-quick-dev/scripts/_schema_runtime.py"
    schema_path = REPO_ROOT / ".agents/skills/quick-dev-tdd-adapter/schemas/plan-owned-implementation-contract.v1.schema.json"
    spec = importlib.util.spec_from_file_location("qddr_schema_runtime", runtime_path)
    if spec is None or spec.loader is None:
        errors.append("schema-runtime-unavailable")
        return
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema_errors = module.schema_errors(schema, contract)
    if schema_errors:
        errors.extend(f"implementation-contract-schema:{item}" for item in schema_errors[:10])


def validate_knowledge(plan_dir: Path, context: dict[str, Any], freeze: dict[str, Any], errors: list[str]) -> None:
    if context.get("preflight", {}).get("status") != "ready":
        errors.append("knowledge-context-not-ready")
    if set(context.get("required_modules", [])) != REQUIRED_MODULES:
        errors.append("knowledge-required-modules-invalid")
    accepted: set[str] = set()
    for decision in context.get("decisions", []):
        if decision.get("decision") == "accepted":
            accepted.update(decision.get("satisfies", []))
    if not REQUIRED_MODULES.issubset(accepted):
        errors.append("knowledge-required-module-unaccepted")
    if freeze.get("authorizes") != []:
        errors.append("knowledge-freeze-authorizing")
    context_path = plan_dir / "knowledge-context.v1.json"
    if freeze.get("context_sha256") != sha256(context_path):
        errors.append("knowledge-freeze-byte-hash-mismatch")
    command = [
        sys.executable,
        "-B",
        str(REPO_ROOT / ".agents/skills/vdd-execution-plan/scripts/vdd_knowledge_preflight.py"),
        "--input",
        str(context_path),
        "--repository-root",
        str(REPO_ROOT),
    ]
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        shell=False,
        check=False,
    )
    if completed.returncode != 0:
        errors.append("knowledge-preflight-command-failed")


def validate_plan(
    plan_dir: Path = PLAN_DIR,
    repo_root: Path = REPO_ROOT,
    *,
    implementation_state: bool = False,
    check_index: bool = True,
    check_source_hashes: bool = True,
) -> list[str]:
    errors: list[str] = []
    for relative in REQUIRED_FILES:
        if not (plan_dir / relative).is_file():
            errors.append(f"missing-plan-file:{relative}")
    if errors:
        return errors

    requirements = load_json(plan_dir / "requirements.v1.json", errors)
    contract = load_json(plan_dir / "implementation-contract.v1.json", errors)
    commands = load_json(plan_dir / "command-registry.v1.json", errors)
    authority = load_json(plan_dir / "authority-manifest.v1.json", errors)
    baseline = load_json(plan_dir / "baseline-and-scope.v1.json", errors)
    state = load_json(plan_dir / "plan-state.v1.json", errors)
    resume = load_json(plan_dir / "resume-state.v1.json", errors)
    route = load_json(plan_dir / "model-route-decision.v1.json", errors)
    context = load_json(plan_dir / "knowledge-context.v1.json", errors)
    freeze = load_json(plan_dir / "knowledge-context.freeze.v1.json", errors)
    fixtures = load_json(plan_dir / "fixtures/regression-repair-contract-cases.v1.json", errors)

    for label, value in (
        ("requirements", requirements),
        ("contract", contract),
        ("authority", authority),
        ("baseline", baseline),
        ("state", state),
        ("resume", resume),
    ):
        if value.get("plan_id") != PLAN_ID:
            errors.append(f"plan-id-mismatch:{label}")
    if requirements.get("profile") != "self-hosted" or contract.get("profile") != "self-hosted":
        errors.append("profile-not-self-hosted")

    validate_contract_schema(contract, errors)
    mode = contract.get("maintenance_mode_contract", {})
    if mode.get("typed_values") != ["implementation", "regression_repair"]:
        errors.append("maintenance-mode-values-invalid")
    if mode.get("legacy_missing_value") != "implementation":
        errors.append("legacy-mode-default-invalid")
    if mode.get("strict_lane") != "strict_tdd_plan" or mode.get("free_form_lane_forbidden") is not True:
        errors.append("repair-lane-boundary-invalid")
    investigation = contract.get("repair_investigation_contract", {})
    expected_classes = {"assertion", "compile", "harness", "timeout", "infrastructure", "unexpected_pass"}
    if set(investigation.get("failure_classes", [])) != expected_classes:
        errors.append("failure-class-set-invalid")
    if investigation.get("existing_test_priority") is not True:
        errors.append("existing-test-priority-disabled")
    if investigation.get("speculative_repair_disposition") != "blocked":
        errors.append("speculative-repair-not-blocked")
    if investigation.get("repeated_failure_threshold") != 2:
        errors.append("repeat-threshold-invalid")

    requirement_rows = requirements.get("requirements", [])
    acceptance_rows = requirements.get("acceptance", [])
    requirement_ids = [item.get("id") for item in requirement_rows]
    acceptance_ids = [item.get("id") for item in acceptance_rows]
    if len(requirement_ids) != 15 or duplicates(requirement_ids):
        errors.append("requirement-set-invalid")
    if len(acceptance_ids) != 22 or duplicates(acceptance_ids):
        errors.append("acceptance-set-invalid")
    slices = contract.get("slices", [])
    check_dependency_graph(slices, errors)
    slice_map = {item.get("slice_id"): item for item in slices}
    covered: set[str] = set()
    for item in requirement_rows:
        for acceptance_id in item.get("acceptance_ids", []):
            if acceptance_id not in acceptance_ids:
                errors.append(f"unknown-requirement-acceptance:{item.get('id')}:{acceptance_id}")
        for slice_id in item.get("slice_ids", []):
            if slice_id not in slice_map:
                errors.append(f"unknown-requirement-slice:{item.get('id')}:{slice_id}")
    for item in slices:
        slice_id = item.get("slice_id")
        covered.update(item.get("acceptance_ids", []))
        for requirement_id in item.get("requirement_ids", []):
            if requirement_id not in requirement_ids:
                errors.append(f"unknown-slice-requirement:{slice_id}:{requirement_id}")
        for acceptance_id in item.get("acceptance_ids", []):
            if acceptance_id not in acceptance_ids:
                errors.append(f"unknown-slice-acceptance:{slice_id}:{acceptance_id}")
        if not item.get("execution_snapshot_paths"):
            errors.append(f"missing-execution-snapshot-path:{slice_id}")
        if "execution-plans/2026-08-06-toolchain-plan-delivery-loop-skill/**" not in item.get("forbidden_changes", []):
            errors.append(f"delivery-plan-not-forbidden:{slice_id}")
        test_paths = item.get("allowed_changes", {}).get("tests", [])
        for relative in test_paths:
            if "*" not in relative and not (repo_root / relative).is_file():
                errors.append(f"declared-existing-test-missing:{slice_id}:{relative}")
    if covered != set(acceptance_ids):
        errors.append("acceptance-not-fully-covered")

    command_rows = commands.get("commands", [])
    command_ids = [item.get("id") for item in command_rows]
    if duplicates(command_ids):
        errors.append("duplicate-command-id")
    for item in command_rows:
        if item.get("shell") is not False:
            errors.append(f"command-shell-not-false:{item.get('id')}")
    for required in {"plan-validator", "plan-validator-tests", "parent-router-tests", "adapter-existing-tests", "adapter-contract-check", "terminal-implementation-validation"}:
        if required not in command_ids:
            errors.append(f"missing-command:{required}")
    for item in slices:
        tdd = item.get("tdd", {})
        used = [
            tdd.get("red", {}).get("command_id"),
            tdd.get("green", {}).get("command_id"),
            item.get("post_refactor_command_id"),
            *[entry.get("command_id") for entry in tdd.get("refactor", {}).get("invocations", [])],
        ]
        for command_id in used:
            if command_id not in command_ids:
                errors.append(f"slice-command-not-registered:{item.get('slice_id')}:{command_id}")

    expected_terminal = (
        "py -3 -B execution-plans/2026-08-06-quick-dev-phase-regression-repair-mode/"
        "tools/validate_implementation.py"
    )
    if requirements.get("terminal_validation") != expected_terminal:
        errors.append("terminal-validation-mismatch")

    allowed_states = {"plan-ready"}
    if implementation_state:
        allowed_states |= {"implementation-authorized", "implementation-complete", "acceptance-passed"}
    if state.get("state") not in allowed_states:
        errors.append(f"plan-state-invalid:{state.get('state')}")
    if state.get("state") == "plan-ready":
        if state.get("state_owner") != "vdd-execution-plan" or state.get("authorizes") != ["plan-ready"]:
            errors.append("plan-ready-owner-or-authority-invalid")
    if resume.get("current_slice") not in SLICE_IDS or set(resume.get("slice_status", {})) != set(SLICE_IDS):
        errors.append("resume-state-invalid")
    elif implementation_state and state.get("state") == "implementation-complete":
        pending = [slice_id for slice_id in SLICE_IDS if resume["slice_status"].get(slice_id) != "completed"]
        if pending:
            errors.append("implementation-complete-with-incomplete-slices:" + ",".join(pending))

    if route.get("classification") != "self-hosted" or route.get("status") != "observe_only":
        errors.append("model-route-invalid")
    if route.get("actualExecution") is not None or route.get("authorizes") != []:
        errors.append("model-route-authorizing-or-executed")

    validate_knowledge(plan_dir, context, freeze, errors)

    case_ids = [item.get("case_id") for item in fixtures.get("cases", [])]
    if set(case_ids) != REQUIRED_CASES or duplicates(case_ids):
        errors.append("regression-repair-fixture-set-invalid")
    valid_cases = [item for item in fixtures.get("cases", []) if item.get("expected") == "pass"]
    if len(valid_cases) != 1 or valid_cases[0].get("case_id") != "valid-phase-repair":
        errors.append("fixture-positive-case-invalid")
    if valid_cases:
        facts = valid_cases[0].get("facts", {})
        search = facts.get("historical_log_search", {})
        if not search.get("query") or not search.get("fingerprint") or not isinstance(search.get("matched_paths"), list):
            errors.append("fixture-historical-search-evidence-incomplete")
        reads = facts.get("error_evidence_reads", {})
        if not reads or any(not isinstance(item, dict) or item.get("read_order") != 1 or not item.get("sha256") for values in reads.values() for item in values):
            errors.append("fixture-error-read-evidence-incomplete")
        probe = facts.get("forbidden_write_probe", {})
        if probe.get("status") != "pass" or probe.get("writes") != []:
            errors.append("fixture-forbidden-write-probe-invalid")
    if fixtures.get("authorizes") != []:
        errors.append("fixtures-authorizing")

    if baseline.get("git", {}).get("head") != "49c5cff216646cf82179d906db60426d5f1ef314":
        errors.append("baseline-head-invalid")
    if baseline.get("git", {}).get("tree") != "bb82574606412a36a235a9c8ab49a1cc1b2a246e":
        errors.append("baseline-tree-invalid")
    for item in baseline.get("historical_error_evidence", []):
        path = repo_root / item.get("path", "")
        if not path.is_file():
            errors.append(f"historical-evidence-missing:{item.get('path')}")
        elif sha256(path) != item.get("sha256"):
            errors.append(f"historical-evidence-drift:{item.get('path')}")

    closure = authority.get("bounded_related_closure", {})
    if not closure.get("producer_files") or not closure.get("direct_consumers") or not closure.get("existing_tests"):
        errors.append("bounded-related-closure-incomplete")
    producers = set(closure.get("producer_files", []))
    consumers = set(closure.get("direct_consumers", []))
    if producers & consumers:
        errors.append("bounded-related-closure-overlap")
    declared = {item.get("path") for item in authority.get("current_sources", [])}
    for path in producers | consumers:
        if path not in declared and not path.endswith("/**"):
            errors.append(f"bounded-related-file-unbound:{path}")
    if check_source_hashes:
        for source in authority.get("current_sources", []):
            if implementation_state and source.get("mutable_during_implementation") is True:
                continue
            source_path = repo_root / source.get("path", "")
            if not source_path.is_file():
                errors.append(f"authority-source-missing:{source.get('path')}")
            elif sha256(source_path) != source.get("sha256"):
                errors.append(f"authority-source-drift:{source.get('path')}")

    if check_index:
        index = load_json(repo_root / "execution-plans/95-implementation-report-index.v1.json", errors)
        matches = [
            item for item in index.get("entries", [])
            if item.get("plan_directory") == PLAN_DIRECTORY and item.get("report_filename") == REPORT
        ]
        if len(matches) != 1:
            errors.append("report-index-entry-invalid")
        elif matches[0].get("sha256") and sha256(repo_root / "execution-plans/95-implementation-report-index.v1.json") != matches[0]["sha256"]:
            errors.append("report-index-hash-invalid")

    for path in plan_dir.rglob("*"):
        if not path.is_file() or path.suffix not in {".md", ".json", ".py"}:
            continue
        text = path.read_text(encoding="utf-8")
        profile_patterns = ("C:/" + "Users/", "C:" + "\\Users\\")
        if any(pattern in text for pattern in profile_patterns):
            errors.append(f"machine-specific-path:{path.relative_to(plan_dir).as_posix()}")

    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--implementation-state", action="store_true")
    args = parser.parse_args()
    errors = validate_plan(implementation_state=args.implementation_state)
    result = {
        "schema_version": "jimuyun.quick-dev-phase-regression-repair-plan-validation.v1",
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "validated_state": "implementation-state" if args.implementation_state else "plan-ready",
        "authorizes": ["plan-ready"] if not errors and not args.implementation_state else [],
    }
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
