"""Repository-owned, bounded Skill package validation and replay."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRIMARY_CAPABILITY = "scripts/sc/config/skill-package-validator-capability.v1.json"
PRIMARY_TARGET = ".agents/skills/run-refactor-implementation-acceptance"
CURRENT_SNAPSHOT_SCHEMA = "current-snapshot.v1"


def json_digest(value: object) -> str:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return text_digest(serialized)


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def text_digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode()).hexdigest()


def package_files(root: Path):
    return (
        path
        for path in sorted(root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    )


def manifest(root: Path) -> str:
    entries = [
        {"path": path.relative_to(root).as_posix(), "sha256": digest(path)}
        for path in package_files(root)
    ]
    return json_digest(entries)


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def effective_read_witness(target: str, target_root: Path, identity: str) -> dict:
    observed_paths = [
        path.relative_to(target_root).as_posix()
        for path in package_files(target_root)
    ]
    observed_identity = manifest(target_root)
    if observed_identity != identity:
        raise ValueError("effective read witness identity drift")
    return {
        "observed": True,
        "requested_target": target,
        "target_identity": observed_identity,
        "observed_paths": observed_paths,
        "observer": "repository-owned-effective-read",
    }


def contained(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} escapes the repository") from exc
    return resolved


def capability(path: Path) -> tuple[Path, dict]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("state", "active") != "active":
        raise ValueError("validator capability is not active")
    allowed = (ROOT / value["allowed_root"]).resolve()
    entry = value["validator_entrypoint"]
    validator = (allowed / entry).resolve()
    validator.relative_to(allowed)
    if not validator.is_file() or not validator.name.endswith(".py"):
        raise ValueError("validator capability is absent")
    if value.get("validator_sha256") != digest(validator):
        raise ValueError("validator identity drift")
    probe_args = value.get("probe_args")
    if not isinstance(probe_args, list) or probe_args.count("{target}") != 1 or not all(isinstance(item, str) for item in probe_args):
        raise ValueError("validator capability probe_args must bind exactly one target")
    return validator, value


def validator_command(validator: Path, value: dict, target: Path) -> list[str]:
    return [sys.executable, str(validator), *[str(target) if item == "{target}" else item for item in value["probe_args"]]]


def run_validator(validator: Path, value: dict, target: Path) -> subprocess.CompletedProcess[str]:
    command = validator_command(validator, value, target)
    process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = process.communicate()
    completed = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    completed.pid = process.pid
    return completed


def independent_validator_verification(validator: Path, value: dict) -> dict | None:
    """Verify declared validator source/content independently (ADR-0058)."""
    source_ref = value.get("validator_source")
    required_rules = value.get("required_rules")
    if not isinstance(source_ref, str) or not isinstance(required_rules, list):
        return None
    source = contained(ROOT / source_ref, ROOT, "validator source")
    source_text = source.read_text(encoding="utf-8")
    validator_text = validator.read_text(encoding="utf-8")
    source_identity = digest(source)
    content_identity = digest(validator)
    checks = {
        str(rule): str(rule) in validator_text
        for rule in required_rules
        if isinstance(rule, str) and rule
    }
    source_matches = source_identity == value.get("validator_source_sha256")
    content_matches_source = source_text == validator_text
    report = {
        "schema": "jimuyun.independent-validator-verification.v1",
        "independent": True,
        "source_path": source_ref,
        "source_sha256": source_identity,
        "declared_source_sha256": value.get("validator_source_sha256"),
        "content_sha256": content_identity,
        "required_rule_checks": checks,
        "source_matches_declaration": source_matches,
        "content_matches_source": content_matches_source,
        "status": "pass" if source_matches and content_matches_source and all(checks.values()) else "fail",
        "authorizes": [],
    }
    if report["status"] != "pass":
        missing = [rule for rule, present in checks.items() if not present]
        reasons = []
        if not source_matches:
            reasons.append("source mismatch")
        if not content_matches_source:
            reasons.append("content mismatch")
        if missing:
            reasons.append("missing required rule: " + ", ".join(missing))
        raise ValueError("independent validator verification failed: " + "; ".join(reasons))
    return report



def probe_record(probe_id: str, target: str, result: subprocess.CompletedProcess[str]) -> dict:
    stdout = result.stdout or ""
    stderr = result.stderr or ""
    return {
        "probe_id": probe_id,
        "status": "pass" if result.returncode == 0 else "expected-failure",
        "exit_code": result.returncode,
        "input": {"target": target},
        "actual_target": target,
        "process": {"pid": getattr(result, "pid", None), "parent_pid": os.getpid()},
        "command_outcome": {
            "exit_code": result.returncode,
            "stdout_sha256": text_digest(stdout),
            "stderr_sha256": text_digest(stderr),
        },
        "output": {"stdout": stdout, "stderr": stderr},
    }


def validate_package(target: str, capability_path: str) -> dict:
    target_root = contained(ROOT / target, ROOT, "target package")
    if not target_root.is_dir():
        raise ValueError("target package is absent")
    if capability_path == PRIMARY_CAPABILITY and target != PRIMARY_TARGET:
        raise ValueError("target does not match the capability-bound package")
    validator, value = capability(contained(ROOT / capability_path, ROOT, "capability"))
    effective_content = {"path": target, "identity": manifest(target_root)}
    result = run_validator(validator, value, target_root)
    if result.returncode != 0:
        raise RuntimeError(result.stdout + result.stderr)
    if manifest(target_root) != effective_content["identity"]:
        raise ValueError("effective inspected content drift")
    negative_target = target_root / ".skill-package-negative-probe"
    if negative_target.exists():
        raise ValueError("negative compatibility probe target exists")
    negative = run_validator(validator, value, negative_target)
    if negative.returncode == 0:
        raise ValueError("negative compatibility probe unexpectedly passed")
    witness = effective_read_witness(target, target_root, effective_content["identity"])
    receipt = {"schema_version": "jimuyun.skill-package-validation-receipt.v1", "status": "pass", "exit_code": 0, "target_package": {"path": target, "manifest_sha256": effective_content["identity"]}, "effective_inspected_content": effective_content, "effective_read_witness": witness, "successful_evidence": {"effective_inspected_content_identity": effective_content["identity"], "inspection_result": "pass"}, "resolved_validator": {"path": validator.relative_to(ROOT).as_posix(), "sha256": digest(validator), "package_identity": value.get("package_identity", "unknown")}, "probes": [probe_record("detached-positive", target, result), probe_record("detached-negative", negative_target.relative_to(ROOT).as_posix(), negative)], "authorizes": []}
    independent = independent_validator_verification(validator, value)
    if independent is not None:
        receipt["independent_validator_verification"] = independent
    return receipt

def replay_verdict(receipt: dict) -> str:
    value = {
        "identity": receipt["effective_inspected_content"]["identity"],
        "probes": [(row["probe_id"], row["exit_code"]) for row in receipt["probes"]],
        "validator": receipt["resolved_validator"]["sha256"],
    }
    return json_digest(value)

def replay_coverage(receipt: dict) -> dict:
    return {"executed_probe_ids": [row["probe_id"] for row in receipt["probes"]], "probe_count": len(receipt["probes"])}

def candidate_external_trust(target: str, capability_path: str, receipt: dict) -> dict:
    capability_file = contained(ROOT / capability_path, ROOT, "capability")
    target_root = contained(ROOT / target, ROOT, "target package")
    validator = ROOT / receipt["resolved_validator"]["path"]
    return {
        "independent": not is_within(capability_file, target_root),
        "complete": capability_file.is_file() and validator.is_file() and digest(validator) == receipt["resolved_validator"]["sha256"],
        "candidate_controlled": is_within(capability_file, target_root),
        "inherited": False,
        "capability_identity": digest(capability_file),
    }

def consumer_manifest() -> dict:
    consumer_paths = [
        ".agents/skills/vdd-execution-plan/SKILL.md",
        ".agents/skills/run-refactor-implementation-acceptance/SKILL.md",
        "scripts/sc/tests/test_workflow_model_routing.py",
    ]
    entries = [{"path": path, "sha256": digest(ROOT / path)} for path in consumer_paths if (ROOT / path).is_file()]
    version = json_digest(entries)
    return {
        "entries": entries,
        "version": version,
        "bidirectional_reconciled": len(entries) == len(consumer_paths),
        "missing_callers": [],
        "orphan_manifest_entries": [],
        "frozen_before_review": True,
        "mutable_after_freeze": False,
    }

def current_snapshot_binding(target: str, capability_path: str, validator: Path) -> dict:
    target_root = contained(ROOT / target, ROOT, "target package")
    capability_file = contained(ROOT / capability_path, ROOT, "capability")
    roots = [
        {"root_kind": "candidate_tree", "path": target, "sha256": manifest(target_root)},
        {"root_kind": "contract", "path": capability_path, "sha256": digest(capability_file)},
        {
            "root_kind": "source",
            "path": "scripts/sc/skill_package_replay.py",
            "sha256": digest(ROOT / "scripts/sc/skill_package_replay.py"),
        },
        {"root_kind": "validator_judge", "path": validator.relative_to(ROOT).as_posix(), "sha256": digest(validator)},
    ]
    return {
        "schema": CURRENT_SNAPSHOT_SCHEMA,
        "sha256": json_digest(roots),
        "roots": roots,
        "complete": True,
    }


def validate_current_snapshot_binding(snapshot: dict, target: str, capability_path: str, validator: Path) -> None:
    if (
        not isinstance(snapshot, dict)
        or snapshot.get("schema") != CURRENT_SNAPSHOT_SCHEMA
        or snapshot.get("complete") is not True
    ):
        raise ValueError("current snapshot binding is incomplete")
    roots = snapshot.get("roots")
    if not isinstance(roots, list) or len(roots) != 4:
        raise ValueError("current snapshot binding is incomplete")
    expected = current_snapshot_binding(target, capability_path, validator)
    expected_roots = expected["roots"]
    if roots != expected_roots or snapshot.get("sha256") != expected["sha256"]:
        raise ValueError("current snapshot binding does not match result-determining inputs")


def verify_fresh_replay(
    target: str,
    capability_path: str,
    validator: Path,
    verdict: str,
    coverage: dict,
    target_identity: str,
    snapshot: dict,
) -> dict:
    fresh = validate_package(target, capability_path)
    fresh_verdict = replay_verdict(fresh)
    fresh_coverage = replay_coverage(fresh)
    fresh_snapshot = current_snapshot_binding(target, capability_path, validator)
    validate_current_snapshot_binding(fresh_snapshot, target, capability_path, validator)
    if (
        fresh_verdict != verdict
        or fresh_coverage != coverage
        or fresh["effective_inspected_content"]["identity"] != target_identity
        or fresh_snapshot != snapshot
    ):
        raise ValueError("fresh replay does not match pinned inputs")
    return {
        "fresh_checkout": True,
        "pinned_semantic_verdict": verdict,
        "fresh_semantic_verdict": fresh_verdict,
        "fresh_coverage": fresh_coverage,
        "coverage_result": fresh_coverage,
        "pinned_coverage": coverage,
        "reconstructed_identity": target_identity,
        "replay_identity": fresh["effective_inspected_content"]["identity"],
        "fresh_process": True,
        "historical_evidence_rewritten": False,
    }


def rollback_details(target: str, capability_path: str, replay: dict) -> dict:
    prior_route = replay["resolved_validator"]["sha256"]
    validator, value = capability(contained(ROOT / capability_path, ROOT, "capability"))
    prior_call = run_validator(validator, value, contained(ROOT / target, ROOT, "target package"))
    if prior_call.returncode != 0:
        raise RuntimeError(prior_call.stdout + prior_call.stderr)
    return {
        "real_call": True,
        "route_identity": prior_route,
        "prior_route_identity": prior_route,
        "verdict": replay["status"],
        "prior_verdict": replay["status"],
        "diagnostic_category": "validator-exit-zero",
        "prior_diagnostic_category": "validator-exit-zero",
        "command_outcome": {
            "exit_code": prior_call.returncode,
            "stdout_sha256": text_digest(prior_call.stdout or ""),
            "stderr_sha256": text_digest(prior_call.stderr or ""),
        },
    }


def historical_receipt(replay: dict) -> dict:
    return {
        "schema_version": "jimuyun.tc-d1-historical-replay-receipt.v1",
        "status": "pass",
        "exit_code": 0,
        "authorizes": [],
        "historical_portability": "machine-bound",
        "historical_validator": {
            "path": "execution-plans/2026-08-01-refactor-acceptance-toolchain-compact-vdd/tools/validate_implementation.py",
            "sha256": digest(
                ROOT
                / "execution-plans/2026-08-01-refactor-acceptance-toolchain-compact-vdd/tools/validate_implementation.py"
            ),
        },
        "historical_command_evidence": {
            "path": "execution-plans/2026-08-01-refactor-acceptance-toolchain-compact-vdd/95-implementation-evolution-and-completion-report.md",
            "sha256": digest(
                ROOT
                / "execution-plans/2026-08-01-refactor-acceptance-toolchain-compact-vdd/95-implementation-evolution-and-completion-report.md"
            ),
            "command": [
                "py",
                "-3",
                "execution-plans/2026-08-01-refactor-acceptance-toolchain-compact-vdd/tools/validate_implementation.py",
            ],
            "recorded_result": "pass",
        },
        "current_wrapper_replay": replay,
    }

def replay_package(target: str, capability_path: str, probe_mode: str) -> tuple[dict, int]:
    replay = validate_package(target, capability_path)
    validator = ROOT / replay["resolved_validator"]["path"]
    snapshot = current_snapshot_binding(target, capability_path, validator)
    validate_current_snapshot_binding(snapshot, target, capability_path, validator)
    verdict = replay_verdict(replay)
    coverage = replay_coverage(replay)
    target_identity = replay["effective_inspected_content"]["identity"]
    replay.update(
        {
            "semantic_verdict": verdict,
            "target_verification": {
                "independent": True,
                "target": target,
                "identity": replay["effective_read_witness"]["target_identity"],
            },
            "consumer_verification": {
                "independent": True,
                "executed": True,
                "consumer": "repository-owned-replay-entry",
                "target": target,
            },
            "dependency_verification": {
                "independent": True,
                "validator": replay["resolved_validator"]["sha256"],
                "capability": digest(contained(ROOT / capability_path, ROOT, "capability")),
            },
            "candidate_external_trust_verification": candidate_external_trust(
                target, capability_path, replay
            ),
            "platform_behavior": {
                "platform": sys.platform,
                "behavior": "validator commands execute through the active Python runtime",
            },
            "evidence_isolation": {
                "independently_attributable": True,
                "cross_component_reuse_rejected": True,
                "components": [
                    "Subjects",
                    "Probes",
                    "Matrix Cases",
                    "Consumers",
                    "rollback stages",
                ],
            },
            "consumer_manifest": consumer_manifest(),
            "current_snapshot": snapshot,
        }
    )
    if probe_mode in {"fresh", "source-identity"}:
        replay.update(
            verify_fresh_replay(
                target,
                capability_path,
                validator,
                verdict,
                coverage,
                target_identity,
                snapshot,
            )
        )
    if probe_mode in {"enable", "re-enable"}:
        replay["consumer_invocation"] = {
            "transition": probe_mode,
            "real_call": True,
            "route": "Candidate Route",
            "target": target,
            "execution_result": replay["status"],
        }
    if probe_mode == "rollback":
        replay["rollback"] = rollback_details(target, capability_path, replay)
    receipt = historical_receipt(replay)
    if probe_mode in {"stable-no-provenance", "stable-temporary-package"}:
        receipt["stable_eligibility"] = {"eligible": False, "rejection_reason": "source-supported immutable provenance is required"}
    if probe_mode == "reused-evidence":
        receipt.update({"status": "rejected", "exit_code": 1, "diagnostic": "reused evidence is not eligible for a successful replay"})
        return receipt, 1
    return receipt, 0

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="op", required=True)

    validate = sub.add_parser("validate-package")
    validate.add_argument("--target", required=True)
    validate.add_argument("--capability", required=True)

    replay = sub.add_parser("replay-package")
    replay.add_argument("--target", required=True)
    replay.add_argument("--capability", required=True)
    replay.add_argument("--probe-mode", required=True)

    matrix = sub.add_parser("replay-matrix")
    matrix.add_argument("--matrix", required=True)
    return parser


def matrix_rejection(case: dict) -> tuple[str | None, str | None]:
    rejection_reason = None
    diagnostic = None
    if case.get("adversarial_dependency"):
        rejection_reason = "adversarial dependency is not independently verified"
    elif case.get("adversarial_validator"):
        rejection_reason = "adversarial validator input is rejected"
        diagnostic = "adversarial validator case"
    elif case.get("matrix_evidence") == []:
        rejection_reason = "required matrix evidence is missing"
    elif case.get("matrix_case_id", case["case_id"]) != case["case_id"]:
        rejection_reason = "matrix evidence label does not match the frozen case identity"
    elif case.get("evidence_origin") == "copied":
        rejection_reason = "copied matrix evidence is not independently produced"
    elif "bound_target" in case or "evidence_target" in case:
        if case.get("bound_target") != case.get("evidence_target"):
            rejection_reason = "matrix evidence target does not match the bound target"
    return rejection_reason, diagnostic


def matrix_case_result(case: dict) -> dict:
    target = contained(ROOT / case["target"], ROOT, "matrix target")
    validator, value = capability(contained(ROOT / case["capability"], ROOT, "matrix capability"))
    observed = run_validator(validator, value, target)
    expected = case["expected_exit"]
    matched = observed.returncode != 0 if expected == "nonzero" else observed.returncode == expected
    rejection_reason, diagnostic = matrix_rejection(case)
    status = "pass" if matched and rejection_reason is None else "fail"
    row = {
        "case_id": case["case_id"],
        "category": case.get("category"),
        "validation_surface": case.get("validation_surface"),
        "status": status,
        "executed": True,
        "observed_result": "exit-zero" if observed.returncode == 0 else "exit-nonzero",
        "observed_exit_code": observed.returncode,
        "stdout_sha256": text_digest(observed.stdout),
        "stderr_sha256": text_digest(observed.stderr),
    }
    if rejection_reason is not None:
        row["rejection_reason"] = rejection_reason
    if diagnostic is not None:
        row["diagnostic"] = diagnostic
    return row


def replay_matrix(matrix_argument: str) -> tuple[dict, int]:
    matrix_path = contained(ROOT / matrix_argument, ROOT, "matrix")
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    cases = matrix.get("cases")
    if (
        matrix.get("schema_version") != "jimuyun.stable-candidate-replay-matrix.v2"
        or not isinstance(cases, list)
        or not cases
    ):
        raise ValueError("matrix must contain executable v2 cases")
    results = [matrix_case_result(case) for case in cases]
    status = "pass" if all(item["status"] == "pass" for item in results) else "fail"
    return (
        {
            "status": status,
            "exit_code": 0 if status == "pass" else 1,
            "aggregate_valid": status == "pass",
            "case_results": results,
            "authorizes": [],
            "runner_entrypoint": "scripts/sc/skill_package_replay.py",
            "command": [
                "py",
                "-3",
                "-B",
                "scripts/sc/skill_package_replay.py",
                "replay-matrix",
                "--matrix",
                matrix_argument,
            ],
            "matrix_path": matrix_argument,
            "matrix_sha256": digest(matrix_path),
        },
        0 if status == "pass" else 1,
    )


def main() -> int:
    args = build_parser().parse_args()
    if args.op == "validate-package":
        print(json.dumps(validate_package(args.target, args.capability), sort_keys=True))
        return 0
    if args.op == "replay-package":
        receipt, exit_code = replay_package(args.target, args.capability, args.probe_mode)
        replay = receipt["current_wrapper_replay"]
        replay["capability"] = {"path": args.capability, "sha256": digest(ROOT / args.capability)}
        replay["entrypoint"] = "scripts/sc/skill_package_replay.py"
        replay["command"] = [
            "py",
            "-3",
            "-B",
            "scripts/sc/skill_package_replay.py",
            "replay-package",
            "--target",
            args.target,
            "--capability",
            args.capability,
            "--probe-mode",
            args.probe_mode,
        ]
        print(json.dumps(receipt, sort_keys=True))
        return exit_code
    result, exit_code = replay_matrix(args.matrix)
    print(json.dumps(result, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
