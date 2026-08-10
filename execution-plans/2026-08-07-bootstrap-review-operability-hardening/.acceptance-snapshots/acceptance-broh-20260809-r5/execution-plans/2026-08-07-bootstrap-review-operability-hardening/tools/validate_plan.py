from __future__ import annotations

import importlib.util
import json
from pathlib import Path


PLAN_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLAN_DIR.parents[1]
REQUIRED = {f"BROH-{index:03d}" for index in range(1, 25)}
ACCEPTANCE = {f"BROH-A{index:02d}" for index in range(1, 47)}
SLICE_IDS = {f"BROH-S{index}" for index in range(8)}
COMMANDS = {
    "plan-validator", "plan-validator-tests", "skill-tests", "skill-whole-directory-validator",
    "acceptance-review-requirement-tests", "acceptance-bootstrap-integration-tests", "bootstrap-wave-tests",
    "broh-s0-slice-validation", "broh-s1-slice-validation", "broh-s2-slice-validation", "broh-s3-slice-validation",
    "broh-s4-slice-validation", "broh-s5-slice-validation", "broh-s6-slice-validation",
    "composition-fixtures-tests", "terminal-implementation-validation", "terminal-validation",
    "broh-s0-target-test", "broh-s1-target-test", "broh-s2-target-test", "broh-s3-target-test",
    "broh-s4-target-test", "broh-s5-target-test", "broh-s6-target-test", "broh-s7-target-test",
}
REQUIRED_CASES = {
    "missing-context-diagnostic", "planned-new-file", "dependency-omission", "closure-binding-preview",
    "dead-attempt-recovery", "windows-safe-transport-heartbeat", "readonly-repository-access",
    "exact-evidence-crlf-range", "repeated-stale-evidence-stop-loss", "pre-review-skipped-maintainer-authorized",
    "pre-review-skipped-no-maintainer-auth", "low-risk-deterministic-only", "explicit-maintainer-review-upgrade",
    "workflow-control-plane-required", "unknown-risk-fail-closed", "p2-no-new-full-round",
    "repaired-p0-p1-focused-only", "later-discovery-needs-user-confirmation", "discovery-wave-three-isolated-roles",
    "discovery-wave-partial-transport-failure", "discovery-wave-single-semantic-round", "wave-high-cost-no-auto-ack",
    "legacy-requirement-decision-readable", "skill-route-not-exact-reuse-widened", "bootstrap-clean-no-lifecycle-authority",
    "current-target-post-implementation-review", "deterministic-facts-frozen-for-semantic-review",
    "risk-lens-preserves-full-coverage", "clean-discovery-zero-findings-valid", "semantic-stop-after-clean",
    "semantic-stop-after-p2-closure", "focused-failure-does-not-escalate", "typed-trigger-required-for-later-discovery",
}


def _read(name: str) -> dict:
    return json.loads((PLAN_DIR / name).read_text(encoding="utf-8"))


def _command_path(item: dict) -> str | None:
    for value in item.get("argv", []):
        if isinstance(value, dict) and value.get("type") == "plan_path":
            raw = value.get("value")
            if isinstance(raw, str) and raw.endswith((".py", ".json")):
                return raw
    return None


def _command_test_path(item: dict) -> str | None:
    plan_relative = PLAN_DIR.relative_to(PLAN_DIR.parents[1]).as_posix()
    for value in item.get("argv", []):
        if isinstance(value, str) and value.endswith(".py"):
            return value.replace("\\", "/")
        if isinstance(value, dict) and value.get("type") == "plan_path":
            raw = value.get("value")
            if isinstance(raw, str) and raw.endswith(".py"):
                return f"{plan_relative}/{raw}".replace("\\", "/")
    return None


def _is_acyclic(slices: list[dict]) -> bool:
    deps = {item.get("slice_id"): set(item.get("depends_on", [])) for item in slices}
    if any(not isinstance(key, str) or not values.issubset(deps) for key, values in deps.items()):
        return False
    visited: set[str] = set()
    active: set[str] = set()

    def visit(node: str) -> bool:
        if node in active:
            return False
        if node in visited:
            return True
        active.add(node)
        if any(not visit(dep) for dep in deps[node]):
            return False
        active.remove(node)
        visited.add(node)
        return True

    return all(visit(node) for node in deps)


def validate_plan() -> list[str]:
    errors: list[str] = []
    required_files = [
        "00-index.md", "95-implementation-evolution-and-completion-report.md", "requirements.v1.json",
        "plan-state.v1.json", "resume-state.v1.json", "command-registry.v1.json", "authority-manifest.v1.json",
        "baseline-and-scope.v1.json", "implementation-contract.v1.json", "fixtures/operability-cases.v1.json",
        "tools/stage_projection_builder.py", "tools/validate_slice.py", "tools/validate_implementation.py",
        "tools/single_maintainer_tdd_bridge.py",
    ]
    errors.extend(f"missing:{name}" for name in required_files if not (PLAN_DIR / name).is_file())
    try:
        requirements = _read("requirements.v1.json")
        contract = _read("implementation-contract.v1.json")
        state = _read("plan-state.v1.json")
        resume = _read("resume-state.v1.json")
        commands = _read("command-registry.v1.json")
        fixtures = _read("fixtures/operability-cases.v1.json")
        authority = _read("authority-manifest.v1.json")
        baseline = _read("baseline-and-scope.v1.json")
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"json-read:{exc}"]

    req_items = requirements.get("requirements", [])
    req_ids = {item.get("id") for item in req_items}
    if req_ids != REQUIRED:
        errors.append("requirements-incomplete")
    acceptance_ids = [item.get("id") for item in requirements.get("acceptance", [])]
    if set(acceptance_ids) != ACCEPTANCE or len(acceptance_ids) != len(set(acceptance_ids)):
        errors.append("acceptance-incomplete-or-duplicate")
    referenced_acceptance = {value for item in req_items for value in item.get("acceptance_ids", [])}
    if referenced_acceptance != ACCEPTANCE:
        errors.append("acceptance-mapping-incomplete")

    slices = contract.get("slices", [])
    slice_ids = {item.get("slice_id") for item in slices}
    if slice_ids != SLICE_IDS or len(slices) != len(slice_ids):
        errors.append("slice-set-invalid")
    if not _is_acyclic(slices):
        errors.append("slice-dependency-cycle-or-missing")
    required_slice_fields = {
        "slice_id", "title", "requirement_ids", "acceptance_ids", "source_refs", "depends_on", "allowed_changes", "planned_new_files",
        "execution_snapshot_paths", "forbidden_changes", "execution_read_set", "dependency_closure", "tdd",
        "post_refactor_command_id", "exit_predicate", "recovery",
    }
    for item in slices:
        slice_id = item.get("slice_id")
        if not required_slice_fields.issubset(item):
            errors.append(f"slice-fields-missing:{slice_id}")
        if item.get("exit_predicate") == "implementation-complete" and "validate_implementation.py" not in json.dumps(item):
            errors.append("implementation-terminal-not-declared")
        groups = item.get("allowed_changes")
        if not isinstance(groups, dict) or set(groups) != {"production", "tests", "documentation"}:
            errors.append(f"slice-write-set-invalid:{slice_id}")
            continue
        if any(not isinstance(values, list) for values in groups.values()):
            errors.append(f"slice-write-set-invalid:{slice_id}")
            continue
        allowed_paths = [path for values in groups.values() if isinstance(values, list) for path in values]
        planned_new = item.get("planned_new_files")
        if (
            not isinstance(planned_new, list)
            or any(not isinstance(path, str) or not path or any(token in path for token in "*?[]") for path in planned_new)
            or len(planned_new) != len(set(planned_new))
            or not set(planned_new).issubset(set(allowed_paths))
        ):
            errors.append(f"planned-new-files-invalid:{slice_id}")
        else:
            for path in allowed_paths:
                if not (REPOSITORY_ROOT / path).is_file() and path not in planned_new:
                    errors.append(f"snapshot-path-missing:{slice_id}:{path}")
        snapshots = item.get("execution_snapshot_paths")
        if (
            any(not isinstance(path, str) or not path or any(token in path for token in "*?[]") for path in allowed_paths)
            or not isinstance(snapshots, list)
            or any(not isinstance(path, str) or not path or any(token in path for token in "*?[]") for path in snapshots)
            or len(allowed_paths) != len(set(allowed_paths))
            or len(snapshots) != len(set(snapshots))
            or set(allowed_paths) != set(snapshots)
        ):
            errors.append(f"slice-snapshot-coverage-invalid:{slice_id}")
        red_id = item.get("tdd", {}).get("red", {}).get("command_id")
        green_id = item.get("tdd", {}).get("green", {}).get("command_id")
        expected_target = f"broh-s{str(slice_id).removeprefix('BROH-S')}-target-test"
        if red_id != expected_target or green_id != red_id:
            errors.append(f"slice-target-test-invalid:{slice_id}")
    if contract.get("terminal_validation") != "py -3 -B execution-plans/2026-08-07-bootstrap-review-operability-hardening/tools/validate_implementation.py":
        errors.append("terminal-validation-invalid")
    if requirements.get("terminal_validation") != contract.get("terminal_validation"):
        errors.append("requirements-terminal-validation-mismatch")
    if contract.get("authorizes") != []:
        errors.append("contract-authorizes")
    if contract.get("adapter_bridge") != {
        "runner": "tools/single_maintainer_tdd_bridge.py",
        "mode": "current-session-four-phase",
        "parallel_owners": False,
        "external_requirement_injection": False,
    }:
        errors.append("adapter-bridge-invalid")

    command_ids = {item.get("id") for item in commands.get("commands", [])}
    if command_ids != COMMANDS:
        errors.append("command-set-invalid")
    if commands.get("authorizes") != []:
        errors.append("command-registry-authorizes")
    command_items = {item.get("id"): item for item in commands.get("commands", [])}
    if any(
        "controlled-red" in str(command_id)
        or "controlled_red_probe.py" in json.dumps(command, sort_keys=True)
        for command_id, command in command_items.items()
    ):
        errors.append("synthetic-red-command-forbidden")
    for item in slices:
        slice_id = item.get("slice_id")
        red = item.get("tdd", {}).get("red", {})
        command = command_items.get(red.get("command_id"))
        argv = command.get("argv", []) if isinstance(command, dict) else []
        try:
            selector = argv[argv.index("-k") + 1]
        except (ValueError, IndexError):
            selector = None
        declared_tests = item.get("allowed_changes", {}).get("tests", [])
        if (
            command is None
            or command.get("shell") is not False
            or selector != red.get("test_selector")
            or _command_test_path(command) not in declared_tests
        ):
            errors.append(f"slice-target-command-invalid:{slice_id}")
    contract_allowed = {
        path
        for item in slices
        for group in item.get("allowed_changes", {}).values()
        for path in group
        if isinstance(path, str)
    }
    for command_id, command in command_items.items():
        planned = command.get("planned_output")
        path = _command_path(command)
        if path and not (PLAN_DIR / path).is_file():
            if not isinstance(planned, str) or planned not in contract_allowed:
                errors.append(f"command-path-missing:{command_id}")
        if isinstance(planned, str) and planned not in contract_allowed:
            errors.append(f"planned-output-outside-write-set:{command_id}")
    fixture_ids = {item.get("case_id") for item in fixtures.get("cases", [])}
    if fixture_ids != REQUIRED_CASES or fixtures.get("authorizes") != []:
        errors.append("fixtures-invalid")
    if requirements.get("authorizes") != []:
        errors.append("requirements-authorizes")

    state_slice_ids = {item.get("id") for item in state.get("slices", [])}
    resume_slice_ids = set(resume.get("slice_status", {}))
    if state_slice_ids != SLICE_IDS or resume_slice_ids != SLICE_IDS:
        errors.append("lifecycle-slice-set-invalid")
    lifecycle_state = state.get("state")
    if lifecycle_state == "plan-ready":
        if state.get("authorizes") != ["plan-ready"] or state.get("blocking_conditions") != []:
            errors.append("state-invalid")
    elif lifecycle_state == "implementation-authorized":
        if (
            state.get("state_owner") != "maintainer"
            or state.get("authorizes") != ["plan-ready", "implementation-authorized"]
            or state.get("blocking_conditions") != []
        ):
            errors.append("state-invalid")
    elif lifecycle_state == "implementation-complete":
        if (
            state.get("state_owner") != "quick-dev-tdd-adapter"
            or state.get("authorizes") != ["implementation-complete"]
            or state.get("blocking_conditions") != []
            or any(item.get("status") != "completed" for item in state.get("slices", []))
        ):
            errors.append("state-invalid")
    elif lifecycle_state == "draft":
        if state.get("authorizes") != [] or not state.get("blocking_conditions"):
            errors.append("draft-blocker-state-invalid")
    else:
        errors.append("state-invalid")
    if resume.get("authorizes") != []:
        errors.append("resume-authorizes")

    source_paths = {item.get("path") for item in authority.get("current_sources", [])}
    required_sources = {
        ".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py",
        ".agents/skills/run-refactor-implementation-acceptance/scripts/bootstrap_integration.py",
        ".agents/skills/quick-dev-tdd-adapter/SKILL.md",
        ".agents/skills/run-refactor-implementation-acceptance/SKILL.md",
        "docs/architecture/ADR_INDEX_PHASE.md",
    }
    if not required_sources.issubset(source_paths):
        errors.append("authority-sources-incomplete")
    forbidden = set(baseline.get("forbidden_changes", []))
    if not {"knowledge/**", "logs/reviews/**", "execution-plans/2026-08-06-toolchain-plan-delivery-loop-skill/**"}.issubset(forbidden):
        errors.append("forbidden-boundaries-weakened")
    repair_validator_path = PLAN_DIR / "repair" / "round-4" / "tools" / "validate_repair_plan.py"
    if not repair_validator_path.is_file():
        errors.append("repair-round-validator-missing:4")
    else:
        spec = importlib.util.spec_from_file_location("broh_round4_validate_plan", repair_validator_path)
        if spec is None or spec.loader is None:
            errors.append("repair-round-validator-unavailable:4")
        else:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            errors.extend(f"repair-round-4:{error}" for error in module.validate_plan())
    return sorted(set(errors))


if __name__ == "__main__":
    errors = validate_plan()
    print(json.dumps({"status": "pass" if not errors else "fail", "errors": errors, "authorizes": []}, sort_keys=True))
    raise SystemExit(0 if not errors else 1)
