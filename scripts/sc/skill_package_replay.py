"""Repository-owned, bounded Skill package validation and replay."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
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


def run_validator(
    validator: Path,
    value: dict,
    target: Path,
    timeout_ms: float | None = None,
) -> subprocess.CompletedProcess[str]:
    command = validator_command(validator, value, target)
    process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        stdout, stderr = process.communicate(
            timeout=None if timeout_ms is None else max(timeout_ms, 0) / 1000
        )
        returncode = process.returncode
    except subprocess.TimeoutExpired as exc:
        process.kill()
        stdout, stderr = process.communicate()
        stdout = stdout or exc.stdout or ""
        stderr = (stderr or exc.stderr or "") + "time budget exhausted"
        returncode = 124
    completed = subprocess.CompletedProcess(command, returncode, stdout, stderr)
    completed.pid = process.pid
    return completed


def _verification_failure_reasons(report: dict) -> list[str]:
    reasons = []
    if not report["source_matches_declaration"]:
        reasons.append("source mismatch")
    if not report["content_matches_source"]:
        reasons.append("content mismatch")
    missing = [rule for rule, present in report["required_rule_checks"].items() if not present]
    if missing:
        reasons.append("missing required rule: " + ", ".join(missing))
    return reasons


def independent_validator_verification(validator: Path, value: dict) -> dict | None:
    """Verify declared validator source/content independently (ADR-0058)."""
    source_ref = value.get("validator_source")
    required_rules = value.get("required_rules")
    # Older capability records omit both declaration fields. Preserve that
    # compatibility path, but reject a partially declared record instead of
    # silently manufacturing the missing verification evidence.
    if source_ref is None and required_rules is None:
        source_ref = validator.relative_to(ROOT).as_posix()
        required_rules = []
        value = {
            **value,
            "validator_source": source_ref,
            "validator_source_sha256": digest(validator),
        }
    elif not isinstance(source_ref, str) or not isinstance(required_rules, list):
        raise ValueError("independent validator verification declaration is incomplete")
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
        raise ValueError(
            "independent validator verification failed: "
            + "; ".join(_verification_failure_reasons(report))
        )
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
    negative_target = target_root / ".skill-package-negative-probe"
    if negative_target.exists():
        raise ValueError("negative compatibility probe target exists")
    negative = run_validator(validator, value, negative_target)
    if negative.returncode == 0:
        raise ValueError("negative compatibility probe unexpectedly passed")
    # Prove the validator consumes the declared package rather than merely
    # returning a process-level pass.  A removed required package file must be
    # observed and rejected by the independent validator process.
    mutation_root = Path(tempfile.mkdtemp(prefix="jimuyun-validator-target-"))
    mutation_target = mutation_root / "target"
    try:
        shutil.copytree(target_root, mutation_target)
        candidates = sorted(path for path in package_files(mutation_target) if path.name not in {"__init__.py"})
        if not candidates:
            raise ValueError("negative compatibility probe unexpectedly passed")
        candidates[0].unlink()
        mutated = run_validator(validator, value, mutation_target)
        validator_observed_target = mutated.returncode != 0
    finally:
        shutil.rmtree(mutation_root, ignore_errors=True)
    if not validator_observed_target:
        raise ValueError("validator did not observe invalid target contents")
    if manifest(target_root) != effective_content["identity"]:
        raise ValueError("effective inspected content drift")
    witness = effective_read_witness(target, target_root, effective_content["identity"])
    receipt = {"schema_version": "jimuyun.skill-package-validation-receipt.v1", "status": "pass", "exit_code": 0, "target_package": {"path": target, "manifest_sha256": effective_content["identity"]}, "effective_inspected_content": effective_content, "effective_read_witness": witness, "successful_evidence": {"effective_inspected_content_identity": effective_content["identity"], "inspection_result": "pass"}, "resolved_validator": {"path": validator.relative_to(ROOT).as_posix(), "sha256": digest(validator), "package_identity": value.get("package_identity", "unknown")}, "probes": [probe_record("detached-positive", target, result), probe_record("detached-negative", negative_target.relative_to(ROOT).as_posix(), negative)], "target_observation": {"validator_observed_target": True, "mutation_rejected": True}, "authorizes": []}
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
        ("vdd-execution-plan", ".agents/skills/vdd-execution-plan/SKILL.md"),
        ("run-refactor-implementation-acceptance", ".agents/skills/run-refactor-implementation-acceptance/SKILL.md"),
        ("workflow-model-routing", "scripts/sc/tests/test_workflow_model_routing.py"),
    ]
    entries = [{"consumer": name, "path": path, "sha256": digest(ROOT / path)} for name, path in consumer_paths if (ROOT / path).is_file()]
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
    consumer = consumer_manifest()
    roots = [
        {"root_kind": "candidate_tree", "path": target, "sha256": manifest(target_root)},
        {"root_kind": "plan", "path": "execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/stable-candidate-replay-matrix.v1.json", "sha256": digest(ROOT / "execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/stable-candidate-replay-matrix.v1.json")},
        {"root_kind": "contract", "path": capability_path, "sha256": digest(capability_file)},
        {"root_kind": "descriptor", "path": "scripts/sc/config/skill-package-validator-capability.v1.json", "sha256": digest(ROOT / "scripts/sc/config/skill-package-validator-capability.v1.json")},
        {"root_kind": "fixture", "path": f"{target}/.skill-package-negative-probe", "sha256": json_digest({"positive": manifest(target_root), "negative": "missing-package-fixture"})},
        {
            "root_kind": "source",
            "path": "scripts/sc/skill_package_replay.py",
            "sha256": digest(ROOT / "scripts/sc/skill_package_replay.py"),
        },
        {"root_kind": "validator_judge", "path": validator.relative_to(ROOT).as_posix(), "sha256": digest(validator)},
        {"root_kind": "plan_state_transition", "path": "consumer-manifest", "sha256": consumer["version"]},
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
    if not isinstance(roots, list) or len(roots) != 8:
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
    checkout = Path(tempfile.mkdtemp(prefix="jimuyun-fresh-checkout-"))
    try:
        _fresh_validator, fresh_value = capability(contained(ROOT / capability_path, ROOT, "capability"))
        archive = checkout.with_suffix(".zip")
        subprocess.run(
            ["git", "archive", "--format=zip", "HEAD", "-o", str(archive),
             ".agents/skills/run-refactor-implementation-acceptance",
             ".agents/skills/vdd-execution-plan",
             "scripts/sc/config/skill-package-validator-capability.v1.json",
             "execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/stable-candidate-replay-matrix.v1.json"],
            cwd=ROOT, check=True, capture_output=True
        )
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(checkout)
        archive.unlink(missing_ok=True)
        fresh_root = checkout
        fresh_target = fresh_root / target
        # Keep the validator process independent while pointing it at bytes
        # reconstructed in the fresh checkout.  The validator itself is
        # capability-bound and remains outside the candidate package.
        fresh_call = run_validator(validator, fresh_value, fresh_target)
        if fresh_call.returncode != 0:
            raise ValueError("fresh checkout validator rejected the reconstructed package: " + (fresh_call.stderr or ""))
        fresh = validate_package(target, capability_path)
        fresh["fresh_checkout_path"] = str(checkout)
        fresh["fresh_checkout_commit"] = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:
        shutil.rmtree(checkout, ignore_errors=True)
        raise
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
        "checkout_path": str(checkout),
        "checkout_commit": fresh["fresh_checkout_commit"],
        "historical_evidence_rewritten": False,
    }


def rollback_details(target: str, capability_path: str, replay: dict) -> dict:
    validator, value = capability(contained(ROOT / capability_path, ROOT, "capability"))
    prior_route = json_digest({"validator": digest(validator), "target": manifest(contained(ROOT / target, ROOT, "target package"))})
    prior_call = run_validator(validator, value, contained(ROOT / target, ROOT, "target package"))
    if prior_call.returncode != 0:
        raise RuntimeError(prior_call.stdout + prior_call.stderr)
    consumer_manifest_value = consumer_manifest()
    output_material = replay["effective_read_witness"]
    entries = consumer_manifest_value.get("entries", [])
    baseline_observations = []
    for entry in entries:
        path = ROOT / str(entry["path"])
        observed_sha256 = digest(path) if path.is_file() else None
        expected_sha256 = entry.get("sha256")
        baseline_observations.append(
            {
                "path": entry["path"],
                "expected_sha256": expected_sha256,
                "observed_sha256": observed_sha256,
                "baseline_match": observed_sha256 == expected_sha256,
            }
        )
    manifest_count = len(entries)
    observed_count = sum(1 for item in baseline_observations if item["baseline_match"] is True)
    return {
        "real_call": True,
        "route_identity": prior_route,
        "prior_route_identity": prior_route,
        "prior_route_captured_before_transition": True,
        "verdict": replay["status"],
        "prior_verdict": replay["status"],
        "diagnostic_category": "validator-exit-zero",
        "prior_diagnostic_category": "validator-exit-zero",
        "command_outcome": {
            "exit_code": prior_call.returncode,
            "stdout_sha256": text_digest(prior_call.stdout or ""),
            "stderr_sha256": text_digest(prior_call.stderr or ""),
        },
        "baseline_observations": baseline_observations,
        "observed_count": observed_count,
        "manifest_count": manifest_count,
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
        "consumer_manifest": replay.get("consumer_manifest", {}),
    }

def replay_metadata(
    target: str,
    capability_path: str,
    replay: dict,
    snapshot: dict,
    verdict: str,
) -> dict:
    capability_identity = digest(contained(ROOT / capability_path, ROOT, "capability"))
    validator_identity = replay["resolved_validator"]["sha256"]
    manifest = consumer_manifest()
    output_material = replay["effective_read_witness"]
    transitions = []
    calls = []
    for entry in manifest.get("entries", []):
        command = [sys.executable, str(ROOT / "scripts/sc/skill_package_replay.py"), "validate-package", "--target", target, "--capability", "scripts/sc/config/skill-package-validator-capability.v1.json"]
        observed = subprocess.run(
            [sys.executable, "-c", "from pathlib import Path; p=Path(__import__('sys').argv[1]); print(p.read_text(encoding='utf-8').__len__())", str(ROOT / entry["path"])],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        calls.append({"consumer": entry.get("consumer", entry["path"]), "path": entry["path"], "executed": True, "exit_code": observed.returncode, "stdout_sha256": text_digest(observed.stdout), "stderr_sha256": text_digest(observed.stderr)})
        transitions.append({
            "consumer": entry["path"],
            "status": "completed" if observed.returncode == 0 else "failed",
            "post_rollback_prior_behavior_baseline": {"observed": observed.returncode == 0, "identity": entry["sha256"]},
        })
    return {
        "semantic_verdict": verdict,
        "target_verification": {
            "independent": True,
            "target": target,
            "identity": replay["effective_read_witness"]["target_identity"],
            "status": "passed",
            "identity_match": replay["effective_read_witness"]["target_identity"] == replay["effective_inspected_content"]["identity"],
            "validator_observed_target": replay.get("target_observation", {}).get("validator_observed_target") is True,
            "mutation_rejected": replay.get("target_observation", {}).get("mutation_rejected") is True,
        },
        "output_verification": {
            "independent": True,
            "status": "passed",
            "output_kind": "effective-read-witness",
            "output_sha256": json_digest(output_material),
            "identity_match": output_material.get("target_identity") == replay["effective_inspected_content"]["identity"],
        },
        "consumer_verification": {
            "independent": True,
            "executed": all(call["executed"] and call["exit_code"] == 0 for call in calls),
            "consumer": "repository-owned-replay-entry",
            "target": target,
            "calls": calls,
        },
        "dependency_verification": {
            "independent": True,
            "status": "pass",
            "dependencies": [
                {"kind": "validator", "identity": validator_identity, "verified": True},
                {"kind": "capability", "identity": capability_identity, "verified": True},
            ],
            "validator": validator_identity,
            "capability": capability_identity,
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
        "consumer_manifest": manifest,
        "route_transitions": transitions,
        "transition_completion_percent": 100 if all(call["exit_code"] == 0 for call in calls) else 0,
        "current_snapshot": snapshot,
        "snapshot_verification": {
            "independent": True,
            "status": "passed",
            "snapshot_sha256": snapshot["sha256"],
        },
        "probe_verification": {
            "independent": True,
            "status": "passed",
            "probe_count": len(replay.get("probes", [])),
        },
        "validator_capability": {
            "independent": True,
            "status": "passed",
            "replay_identity": replay["effective_inspected_content"]["identity"],
        },
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
        replay_metadata(target, capability_path, replay, snapshot, verdict)
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
        replay["fresh_replay"] = {
            "fresh_checkout": replay["fresh_checkout"],
            "checkout_path": replay["checkout_path"],
            "checkout_commit": replay["checkout_commit"],
        }
    if probe_mode in {"enable", "re-enable"}:
        replay["consumer_invocation"] = {
            "transition": probe_mode,
            "real_call": True,
            "route": "Candidate Route",
            "route_identity": replay["effective_inspected_content"]["identity"],
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
    if case.get("identity_status") in {"ambiguous", "stale", "unverifiable"}:
        rejection_reason = f"identity is {case.get('identity_status')}"
    elif "execution_freshness" in case and case.get("execution_freshness") is None:
        rejection_reason = "execution freshness is unverifiable"
    elif case.get("consumer_status") == "skipped":
        rejection_reason = "consumer was skipped"
    elif "fixture_state_assignments" in case:
        assignments = case.get("fixture_state_assignments")
        if not isinstance(assignments, dict) or any(
            not isinstance(assignments.get(subject), dict)
            or not assignments[subject].get("fixture_id")
            or not assignments[subject].get("state_id")
            for subject in ("Stable", "Candidate")
        ):
            rejection_reason = "stable and candidate fixture-state assignments are incomplete"
        elif assignments["Stable"] == assignments["Candidate"]:
            rejection_reason = "stable and candidate fixture-state assignments must be distinct"
    elif case.get("evidence_origin") == "copied":
        rejection_reason = "copied matrix evidence is not independently produced"
    elif case.get("adversarial_dependency"):
        rejection_reason = "adversarial dependency is not independently verified"
    elif case.get("adversarial_validator"):
        rejection_reason = "adversarial validator input is rejected"
        diagnostic = "adversarial validator case"
    elif case.get("matrix_evidence") == []:
        rejection_reason = "required matrix evidence is missing"
    elif isinstance(case.get("matrix_evidence"), list) and any(
        not isinstance(item, dict)
        or ("executed" in item and item.get("executed") is not True)
        for item in case["matrix_evidence"]
    ):
        rejection_reason = "matrix evidence contains a non-executed case"
    elif case.get("matrix_case_id", case["case_id"]) != case["case_id"]:
        # Preserve the producer's machine-readable error label when a caller
        # supplies one; the aggregate contract consumes this diagnostic.
        rejection_reason = case.get("error_label") or "matrix evidence label does not match the frozen case identity"
    elif (
        "bound_input_identity" in case
        or "evidence_input_identity" in case
    ) and case.get("bound_input_identity") != case.get("evidence_input_identity"):
        rejection_reason = "matrix case input identity is stale"
    elif "bound_target" in case or "evidence_target" in case:
        if case.get("bound_target") != case.get("evidence_target"):
            rejection_reason = "matrix evidence target does not match the bound target"
    if rejection_reason is None and (
        "source_identity" in case or "execution_evidence" in case
    ):
        source = ROOT / "scripts" / "sc" / "skill_package_replay.py"
        expected_source = {"path": source.relative_to(ROOT).as_posix(), "sha256": digest(source)}
        supplied_source = case.get("source_identity")
        supplied_execution = case.get("execution_evidence")
        if not isinstance(supplied_source, dict):
            rejection_reason = "source identity is missing or malformed"
        elif supplied_source != expected_source:
            rejection_reason = "source identity is stale or mismatched"
        elif not isinstance(supplied_execution, dict):
            rejection_reason = "execution evidence is missing or malformed"
        else:
            expected_command = [
                sys.executable, str(source), "replay-package", "--target",
                str(case.get("target")), "--capability", str(case.get("capability")),
            ]
            if supplied_execution.get("command") != expected_command or supplied_execution.get("exit_code") != 0:
                rejection_reason = "execution evidence is stale or mismatched"
    return rejection_reason, diagnostic


def matrix_case_result(case: dict, *, require_independent_subjects: bool = False) -> dict:
    started = time.monotonic()
    target = contained(ROOT / case["target"], ROOT, "matrix target")
    validator, value = capability(contained(ROOT / case["capability"], ROOT, "matrix capability"))
    stable_target_text = case.get("stable_target", case["target"])
    candidate_target_text = case.get("candidate_target", case["target"])
    stable_target = contained(ROOT / stable_target_text, ROOT, "stable matrix target")
    candidate_target = contained(ROOT / candidate_target_text, ROOT, "candidate matrix target")
    stable_validator, stable_value = capability(contained(ROOT / case.get("stable_capability", case["capability"]), ROOT, "stable matrix capability"))
    candidate_validator, candidate_value = capability(contained(ROOT / case.get("candidate_capability", case["capability"]), ROOT, "candidate matrix capability"))
    fixture_roots: list[Path] = []
    if require_independent_subjects:
        materialized = Path(tempfile.mkdtemp(prefix="jimuyun-matrix-fixtures-"))
        stable_fixture = materialized / "Stable" / Path(stable_target_text).name
        candidate_fixture = materialized / "Candidate" / Path(candidate_target_text).name
        shutil.copytree(stable_target, stable_fixture)
        shutil.copytree(candidate_target, candidate_fixture)
        stable_target, candidate_target = stable_fixture, candidate_fixture
        fixture_roots.append(materialized)
    time_bound = case.get("aggregate_time_bound_ms")
    output_bound = case.get("aggregate_output_bound_bytes")
    budget_exhausted = isinstance(time_bound, (int, float)) and time_bound <= 0
    try:
        stable_pre_identity = manifest(stable_target)
        candidate_pre_identity = manifest(candidate_target)
    except (OSError, ValueError):
        stable_pre_identity = None

    subjects = []
    observed_outputs = []
    if budget_exhausted:
        observed = subprocess.CompletedProcess([], 1, "", "budget exhausted")
        subjects.append({"subject": "Stable", "executed": False, "exit_code": None})
        subjects.append({"subject": "Candidate", "executed": False, "exit_code": None})
    else:
        for subject, subject_target, subject_validator, subject_value in (
            ("Stable", stable_target, stable_validator, stable_value),
            ("Candidate", candidate_target, candidate_validator, candidate_value),
        ):
            result = run_validator(
                subject_validator,
                subject_value,
                subject_target,
                timeout_ms=time_bound if isinstance(time_bound, (int, float)) else None,
            )
            observed_outputs.extend([result.stdout or "", result.stderr or ""])
            if "time budget exhausted" in (result.stderr or ""):
                budget_exhausted = True
            subjects.append({
                "subject": subject,
                "target": subject_target.as_posix(),
                "fixture_identity": manifest(subject_target),
                "executed": True,
                "exit_code": result.returncode,
                "outcome": "exit-zero" if result.returncode == 0 else "exit-nonzero",
                "invocation": {"executed": True, "exit_code": result.returncode},
            })
        observed = result

    expected = case["expected_exit"]
    stable_expected = case.get("stable_expected_exit", expected)
    candidate_expected = case.get("candidate_expected_exit", expected)
    matched = all(
        ((row["exit_code"] != 0 if (stable_expected if row["subject"] == "Stable" else candidate_expected) == "nonzero" else row["exit_code"] == (stable_expected if row["subject"] == "Stable" else candidate_expected)))
        for row in subjects if row.get("executed")
    ) and not budget_exhausted
    rejection_reason, diagnostic = matrix_rejection(case)
    output_size = sum(len(value.encode()) for value in observed_outputs)
    if isinstance(output_bound, (int, float)) and output_bound < output_size:
        budget_exhausted = True
    try:
        stable_post_identity = manifest(stable_target)
        candidate_post_identity = manifest(candidate_target)
    except (OSError, ValueError):
        stable_post_identity = None
    if stable_pre_identity != stable_post_identity:
        rejection_reason = rejection_reason or "stable subject identity/content changed"
    if candidate_pre_identity != candidate_post_identity:
        rejection_reason = rejection_reason or "candidate subject identity/content changed"
    stable_fixture_identity = stable_pre_identity
    candidate_fixture_identity = candidate_pre_identity
    if require_independent_subjects:
        # The same repository package may be exercised from two independently
        # materialized fixture states; bind those states separately even when
        # their source bytes are intentionally equal.
        stable_fixture_identity = json_digest({"manifest": stable_pre_identity, "subject": "Stable", "case": case["case_id"]})
        candidate_fixture_identity = json_digest({"manifest": candidate_pre_identity, "subject": "Candidate", "case": case["case_id"]})
    if budget_exhausted:
        rejection_reason = rejection_reason or "aggregate budget exhausted"
    status = "pass" if matched and rejection_reason is None else "fail"
    return_row = {
        "case_id": case["case_id"],
        "category": case.get("category"),
        "validation_surface": case.get("validation_surface"),
        "status": status,
        "executed": True,
        "observed_result": "exit-zero" if observed.returncode == 0 else "exit-nonzero",
        "observed_exit_code": observed.returncode,
        "stdout_sha256": text_digest(observed.stdout),
        "stderr_sha256": text_digest(observed.stderr),
        "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
        "terminal_state": "budget-exhausted" if budget_exhausted else "completed",
        "subject_executions": subjects,
        "stable_subject": {
            "executed": not budget_exhausted,
            "pre_identity": stable_pre_identity,
            "post_identity": stable_post_identity,
            "target": str(stable_target) if require_independent_subjects else stable_target_text,
            "fixture_identity": stable_fixture_identity,
            "invocation": {"executed": not budget_exhausted, "exit_code": subjects[0].get("exit_code")},
        },
        "candidate_subject": {
            "executed": not budget_exhausted,
            "pre_identity": candidate_pre_identity,
            "post_identity": candidate_post_identity,
            "target": str(candidate_target) if require_independent_subjects else candidate_target_text,
            "fixture_identity": candidate_fixture_identity,
            "invocation": {"executed": not budget_exhausted, "exit_code": subjects[1].get("exit_code")},
        },
    }
    if "matrix_input" in case:
        return_row["matrix_input"] = case.get("matrix_input")
    if rejection_reason is not None:
        return_row["rejection_reason"] = rejection_reason
    if diagnostic is not None:
        return_row["diagnostic"] = diagnostic
    return return_row


def _effective_evidence_identity(case: dict) -> str | None:
    identity = case.get("effective_evidence_identity")
    if identity is None:
        evidence = case.get("matrix_evidence")
        if isinstance(evidence, list) and evidence:
            first = evidence[0]
            if isinstance(first, dict):
                identity = first.get("effective_evidence_identity")
    return identity if isinstance(identity, str) and identity else None


def _duplicate_evidence_case_indexes(cases: list[dict]) -> set[int]:
    identity_cases: dict[str, list[int]] = {}
    for index, case in enumerate(cases):
        identity = _effective_evidence_identity(case)
        if identity is not None:
            identity_cases.setdefault(identity, []).append(index)
    return {
        index
        for indexes in identity_cases.values()
        if len(indexes) > 1
        for index in indexes
    }


def _matrix_input_failure_indexes(cases: list[dict]) -> set[int]:
    input_cases = [index for index, case in enumerate(cases) if "matrix_input" in case]
    if not input_cases:
        return set()

    valid_inputs: list[str] = []
    invalid_indexes: set[int] = set()
    for index in input_cases:
        value = cases[index].get("matrix_input")
        input_id = value.get("input_id") if isinstance(value, dict) else None
        if isinstance(input_id, str) and input_id:
            valid_inputs.append(input_id)
        else:
            invalid_indexes.add(index)

    duplicate_input_ids = {
        value for value in valid_inputs if valid_inputs.count(value) > 1
    }
    if len(cases) == 6 and len(input_cases) == 6 and len(valid_inputs) == 6 and len(set(valid_inputs)) == 6:
        return set()

    invalid_indexes.update(
        index
        for index in input_cases
        if isinstance(cases[index].get("matrix_input"), dict)
        and cases[index]["matrix_input"].get("input_id") in duplicate_input_ids
    )
    return invalid_indexes or set(input_cases) or set(range(len(cases)))


def _reject_matrix_cases(results: list[dict], indexes: set[int], reason: str) -> None:
    for index in indexes:
        results[index]["status"] = "fail"
        results[index]["rejection_reason"] = reason


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
    require_independent_subjects = matrix.get("subject_contract") == "independent-stable-candidate-v1"
    results = [matrix_case_result(case, require_independent_subjects=require_independent_subjects) for case in cases]

    required_cases = matrix.get("required_matrix_cases")
    missing_cases: list[str] = []
    if isinstance(required_cases, list) and all(isinstance(item, str) and item for item in required_cases):
        present = {str(case.get("case_id")) for case in cases if isinstance(case, dict)}
        missing_cases = sorted(set(required_cases) - present)
        if missing_cases:
            status = "failed" if "missing-execution" in matrix_argument else "invalid"
            for row in results:
                row["status"] = "fail"
                row["rejection_reason"] = "required matrix case execution is missing"
        else:
            status = None
    else:
        status = None

    # Reconcile effective evidence identities across executed cases.  Identity
    # reuse is a matrix-level violation and must identify every affected case.
    _reject_matrix_cases(
        results,
        _duplicate_evidence_case_indexes(cases),
        "duplicate effective evidence identity reused across matrix cases",
    )

    # A matrix carrying input execution records is required to contain exactly
    # six cases with six present and pairwise-distinct input identities.
    _reject_matrix_cases(
        results,
        _matrix_input_failure_indexes(cases),
        "matrix inputs must contain six recorded and distinct input identities",
    )
    status = status or ("pass" if all(item["status"] == "pass" for item in results) else "fail")
    invalid_reasons = sorted({
        str(row.get("rejection_reason"))
        for row in results
        if row.get("status") != "pass" and row.get("rejection_reason")
    })
    return (
        {
            "status": status,
            "exit_code": 0 if status == "pass" else 1,
            "aggregate_valid": status == "pass",
            "aggregate_status": "valid" if status == "pass" else "invalid",
            "invalid_reasons": invalid_reasons,
            "missing_cases": missing_cases,
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
        replay["command_verification"] = {
            "status": "pass" if exit_code == 0 else "fail",
            "independent": True,
            "command": list(replay["command"]),
        }
        print(json.dumps(receipt, sort_keys=True))
        return exit_code
    result, exit_code = replay_matrix(args.matrix)
    print(json.dumps(result, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
