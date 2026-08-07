from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


PLAN_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = PLAN_DIR.parents[1]
PLAN_ID = "toolchain-plan-delivery-loop-skill"
PLAN_DIRECTORY = "2026-08-06-toolchain-plan-delivery-loop-skill"
REPORT = "95-implementation-evolution-and-completion-report.md"
SLICE_IDS = ["RMAP-S0", "RMAP-S1", "RMAP-S2", "RMAP-S3"]
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
        errors.append(f"invalid-json:{path.relative_to(REPO_ROOT).as_posix()}:{exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"json-root-not-object:{path.relative_to(REPO_ROOT).as_posix()}")
        return {}
    return value


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def duplicates(values: list[str]) -> set[str]:
    return {value for value in values if values.count(value) > 1}


def check_dependency_graph(slices: list[dict[str, Any]], errors: list[str]) -> None:
    slice_ids = [item.get("slice_id") for item in slices]
    if duplicates(slice_ids):
        errors.append("duplicate-slice-id")
        return
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


def validate_plan(
    plan_dir: Path = PLAN_DIR,
    repo_root: Path = REPO_ROOT,
    *,
    allow_draft: bool = False,
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

    for name, value in [
        ("requirements", requirements),
        ("contract", contract),
        ("authority", authority),
        ("baseline", baseline),
        ("state", state),
        ("resume", resume),
    ]:
        if value.get("plan_id") != PLAN_ID:
            errors.append(f"plan-id-mismatch:{name}")

    if requirements.get("profile") != "self-hosted":
        errors.append("requirements-profile-not-self-hosted")
    if contract.get("profile") != "self-hosted":
        errors.append("contract-profile-not-self-hosted")

    requirement_rows = requirements.get("requirements", [])
    acceptance_rows = requirements.get("acceptance", [])
    req_ids = [item.get("id") for item in requirement_rows]
    acceptance_ids = [item.get("id") for item in acceptance_rows]
    if duplicates(req_ids):
        errors.append("duplicate-requirement-id")
    if duplicates(acceptance_ids):
        errors.append("duplicate-acceptance-id")
    if len(req_ids) != 18 or len(acceptance_ids) != 27:
        errors.append("requirement-or-acceptance-count-invalid")

    slices = contract.get("slices", [])
    check_dependency_graph(slices, errors)
    slice_map = {item.get("slice_id"): item for item in slices}
    covered_acceptance: set[str] = set()
    for item in requirement_rows:
        for acceptance_id in item.get("acceptance_ids", []):
            if acceptance_id not in acceptance_ids:
                errors.append(f"unknown-requirement-acceptance:{item.get('id')}:{acceptance_id}")
        for slice_id in item.get("slice_ids", []):
            if slice_id not in slice_map:
                errors.append(f"unknown-requirement-slice:{item.get('id')}:{slice_id}")
    for item in slices:
        for requirement_id in item.get("requirement_ids", []):
            if requirement_id not in req_ids:
                errors.append(f"unknown-slice-requirement:{item.get('slice_id')}:{requirement_id}")
        for acceptance_id in item.get("acceptance_ids", []):
            covered_acceptance.add(acceptance_id)
            if acceptance_id not in acceptance_ids:
                errors.append(f"unknown-slice-acceptance:{item.get('slice_id')}:{acceptance_id}")
        snapshot_paths = item.get("execution_snapshot_paths", [])
        if not snapshot_paths:
            errors.append(f"missing-execution-snapshot-path:{item.get('slice_id')}")
        forbidden = item.get("forbidden_changes", [])
        for child in [
            ".agents/skills/run-phase-bootstrap-review/**",
            ".agents/skills/quick-dev-tdd-adapter/**",
            ".agents/skills/run-refactor-implementation-acceptance/**",
        ]:
            if child not in forbidden:
                errors.append(f"child-skill-not-forbidden:{item.get('slice_id')}:{child}")
    if covered_acceptance != set(acceptance_ids):
        errors.append("acceptance-not-fully-covered")

    terminal = requirements.get("terminal_validation")
    expected_terminal = (
        "py -3 -B execution-plans/2026-08-06-toolchain-plan-delivery-loop-skill/"
        "tools/validate_implementation.py"
    )
    if terminal != expected_terminal:
        errors.append("terminal-validation-mismatch")

    command_rows = commands.get("commands", [])
    command_ids = [item.get("id") for item in command_rows]
    if duplicates(command_ids):
        errors.append("duplicate-command-id")
    for item in command_rows:
        if item.get("shell") is not False:
            errors.append(f"command-shell-not-false:{item.get('id')}")
    for required_command in [
        "plan-validator",
        "coordinator-tests",
        "coordinator-self-check",
        "coordinator-package-validation",
        "terminal-implementation-validation",
    ]:
        if required_command not in command_ids:
            errors.append(f"missing-command:{required_command}")
    for item in slices:
        tdd = item.get("tdd", {})
        used = [
            tdd.get("red", {}).get("command_id"),
            tdd.get("green", {}).get("command_id"),
            item.get("post_refactor_command_id"),
        ] + [entry.get("command_id") for entry in tdd.get("refactor", {}).get("invocations", [])]
        for command_id in used:
            if command_id not in command_ids:
                errors.append(f"slice-command-not-registered:{item.get('slice_id')}:{command_id}")

    coordination = contract.get("coordination_contract", {})
    if coordination.get("finding_confidence_source") != "bootstrap-review-finding.confidence":
        errors.append("confidence-source-invalid")
    if coordination.get("parallel_confidence_scoring_forbidden") is not True:
        errors.append("parallel-confidence-not-forbidden")
    hook = coordination.get("post_run_hook", {})
    if hook.get("enabled") is not True:
        errors.append("post-run-hook-disabled")
    if hook.get("scope") != "coordinator-only":
        errors.append("post-run-hook-scope-invalid")
    if hook.get("installation") != "explicit-project-local-entrypoint":
        errors.append("post-run-hook-installation-invalid")
    if set(hook.get("suppress_on", [])) != {"user-stop", "manual-pause"}:
        errors.append("post-run-hook-suppression-invalid")
    if hook.get("child_skills_attach_hook") is not False:
        errors.append("child-skill-hook-attachment-invalid")
    loop = coordination.get("loop", {})
    if loop.get("stages") != ["recover", "plan", "execute", "verify", "iterate"]:
        errors.append("loop-stage-order-invalid")
    if loop.get("state_authority") != "filesystem-only":
        errors.append("loop-state-authority-invalid")
    if loop.get("early_convergence_forbidden") is not True:
        errors.append("early-convergence-not-forbidden")
    session = coordination.get("fresh_session_recovery", {})
    if session.get("assumes_global_new_command") is not False:
        errors.append("fresh-session-global-new-assumption")
    if session.get("launcher_authority") != "project-local-explicit-launcher":
        errors.append("fresh-session-launcher-authority-invalid")
    effects = coordination.get("effect_policy", {})
    if effects.get("idempotency") != "required" or effects.get("rollback") != "journaled-or-owner-declared":
        errors.append("effect-policy-invalid")
    background = coordination.get("background_process", {})
    if background.get("enabled") is not False:
        errors.append("background-process-enabled")
    expected_forbidden = {
        "timer-poller",
        "scheduled-task",
        "service",
        "detached-codex-launch",
        "process-name-skill-detection",
    }
    if set(background.get("forbidden", [])) != expected_forbidden:
        errors.append("background-forbidden-set-invalid")
    publishers = coordination.get("lifecycle_publishers", {})
    if publishers != {
        "plan-ready": "vdd-execution-plan",
        "implementation-authorized": "maintainer",
        "implementation-complete": "quick-dev-tdd-adapter",
        "acceptance-passed": "run-refactor-implementation-acceptance",
    }:
        errors.append("lifecycle-publishers-invalid")

    allowed_states = {"draft", "plan-ready"} if allow_draft else {"plan-ready"}
    if implementation_state:
        allowed_states |= {"implementation-authorized", "implementation-complete", "acceptance-passed"}
    if state.get("state") not in allowed_states:
        errors.append(f"plan-state-invalid:{state.get('state')}")
    if state.get("state") == "plan-ready" and state.get("state_owner") != "vdd-execution-plan":
        errors.append("plan-ready-owner-invalid")
    if resume.get("current_slice") not in SLICE_IDS:
        errors.append("resume-current-slice-invalid")
    if set(resume.get("slice_status", {})) != set(SLICE_IDS):
        errors.append("resume-slice-set-invalid")
    repair = resume.get("repair", {})
    if repair.get("status") == "closed" and isinstance(repair.get("current_round"), int) and repair["current_round"] >= 2:
        closure = repair.get("closure")
        expected_closure = f"repair/round-{repair['current_round']}/bootstrap-repair-closure.v1.json"
        if closure != expected_closure:
            errors.append("resume-bootstrap-repair-closure-path-invalid")
        else:
            closure_value = load_json(plan_dir / closure, errors)
            if closure_value.get("schemaVersion") != "bootstrap-repair-closure.v1":
                errors.append("resume-bootstrap-repair-closure-schema-invalid")

    if route.get("classification") != "self-hosted" or route.get("status") != "observe_only":
        errors.append("model-route-invalid")
    if route.get("actualExecution") is not None or route.get("authorizes") != []:
        errors.append("model-route-authorizing-or-executed")

    if context.get("preflight", {}).get("status") != "ready":
        errors.append("knowledge-context-not-ready")
    required_modules = set(context.get("required_modules", []))
    if required_modules != {"repository-rules", "existing-workflow", "toolchain-consumer-authority"}:
        errors.append("knowledge-required-modules-invalid")
    accepted_modules: set[str] = set()
    for decision in context.get("decisions", []):
        if decision.get("decision") == "accepted":
            accepted_modules.update(decision.get("satisfies", []))
    if not required_modules.issubset(accepted_modules):
        errors.append("knowledge-required-module-unaccepted")
    if freeze.get("authorizes") != []:
        errors.append("knowledge-freeze-authorizing")

    if baseline.get("git", {}).get("head") != "8c47a52fc8f241f76da9ccb5d936b0fafe807f0f":
        errors.append("baseline-head-invalid")
    if check_source_hashes:
        for source in authority.get("current_sources", []):
            source_path = repo_root / source.get("path", "")
            if not source_path.is_file():
                errors.append(f"authority-source-missing:{source.get('path')}")
            elif sha256(source_path) != source.get("sha256"):
                errors.append(f"authority-source-drift:{source.get('path')}")

    if check_index:
        index = load_json(repo_root / "execution-plans/95-implementation-report-index.v1.json", errors)
        matches = [
            item
            for item in index.get("entries", [])
            if item.get("plan_directory") == PLAN_DIRECTORY
            and item.get("report_filename") == REPORT
        ]
        if len(matches) != 1:
            errors.append("report-index-entry-invalid")

    for path in plan_dir.rglob("*"):
        if not path.is_file() or path.suffix not in {".md", ".json", ".py"}:
            continue
        text = path.read_text(encoding="utf-8")
        windows_profile_patterns = ("C:/" + "Users/", "C:" + "\\Users\\")
        if any(pattern in text for pattern in windows_profile_patterns):
            errors.append(f"machine-specific-path:{path.relative_to(plan_dir).as_posix()}")

    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-draft", action="store_true")
    parser.add_argument("--implementation-state", action="store_true")
    args = parser.parse_args()
    errors = validate_plan(
        allow_draft=args.allow_draft,
        implementation_state=args.implementation_state,
    )
    result = {
        "schema_version": "jimuyun.toolchain-plan-delivery-loop-plan-validation.v1",
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "authorizes": ["plan-ready"] if not errors and not args.implementation_state else [],
    }
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
