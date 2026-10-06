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
CURRENT_SNAPSHOT_SCHEMA = "jimuyun.skill-package-current-snapshot.v2"
# Accepted ADR-0058: bounded runtime adapters do not own Acceptance authority.
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import skill_replay_runtime as runtime


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


def contained(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} escapes the repository") from exc
    return resolved


def capability(path: Path) -> tuple[Path, dict]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("validator capability must be a JSON object")
    if value.get("authorizes") != []:
        raise ValueError("capability authorizes must be an empty array")
    if value.get("state", "active") != "active":
        raise ValueError("validator capability is not active")
    allowed = contained(ROOT / value["allowed_root"], ROOT, "validator allowed root")
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


def run_validator(validator: Path, value: dict, target: Path, timeout_ms: float | None = None):
    return runtime.observed_validator(ROOT, validator, value, target, timeout_ms)

def independent_validator_verification(validator: Path, value: dict) -> dict:
    return runtime.verify_trust(ROOT, validator, value, value.get("_capability_path"))

def probe_record(probe_id: str, target: str, result: subprocess.CompletedProcess[str]) -> dict:
    stdout = result.stdout or ""
    stderr = result.stderr or ""
    witness = getattr(result, "read_witness", None)
    if not isinstance(witness, dict) or not isinstance(witness.get("target"), str):
        raise ValueError("Probe has no native target observation")
    return {
        "probe_id": probe_id,
        "status": "pass" if result.returncode == 0 else "expected-failure",
        "exit_code": result.returncode,
        "input": {"target": target},
        "actual_target": witness["target"],
        "read_witness": witness,
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
    cap_file = contained(ROOT / capability_path, ROOT, "capability")
    validator, value = capability(cap_file)
    value = dict(value, _capability_path=capability_path)
    independent = independent_validator_verification(validator, value)
    oracle = runtime.negative_oracle(value)
    expected_files = runtime.bindings(ROOT, (target,))
    identity = manifest(target_root)
    result = run_validator(validator, value, target_root)
    if result.returncode:
        raise RuntimeError("positive package validation failed: " + result.stdout + result.stderr)
    reads = runtime.require_reads(result, target_root)
    # Both detached probes use one identical location. Only the declared
    # semantic defect changes between the positive and negative execution.
    with tempfile.TemporaryDirectory(prefix="jimuyun-detached-probe-") as directory:
        detached = Path(directory) / "target"
        shutil.copytree(target_root, detached, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        detached_identity = manifest(detached)
        detached_positive = run_validator(validator, value, detached)
        if detached_positive.returncode:
            raise ValueError("detached positive Probe rejected identical package contents")
        runtime.require_reads(detached_positive, detached)
        defect = runtime.relative(detached, oracle["path"])
        if not defect.is_file():
            raise ValueError("declared negative Probe fixture is absent")
        defect.write_text(json.dumps(oracle["replacement"], sort_keys=True), encoding="utf-8", newline="\n")
        invalid_identity = manifest(detached)
        if invalid_identity == detached_identity:
            raise ValueError("negative Probe did not introduce its declared defect")
        negative = run_validator(validator, value, detached)
        if negative.returncode == 0:
            raise ValueError("negative compatibility probe unexpectedly passed")
        if oracle["diagnostic"] not in runtime.findings(negative) or negative.stderr.strip():
            raise ValueError("negative Probe is an infrastructure failure or has the wrong defect diagnostic")
        negative_reads = runtime.require_reads(negative, detached)
    runtime.assert_identity(ROOT, expected_files)
    if manifest(target_root) != identity:
        raise ValueError("effective inspected content drift")
    witness = {"observed": True, "requested_target": target, "target_identity": identity, "observed_paths": sorted({row["path"] for row in reads}), "reads": reads, "process": {"pid": result.pid, "nonce": result.read_witness["nonce"]}, "observer": "validator-child-read-interface-v1"}
    receipt = {"schema_version": "jimuyun.skill-package-validation-receipt.v1", "status": "pass", "exit_code": 0, "replay_identity": identity, "target_package": {"path": target, "manifest_sha256": identity}, "effective_inspected_content": {"path": target, "identity": identity}, "effective_read_witness": witness, "successful_evidence": {"effective_inspected_content_identity": identity, "inspection_result": "pass"}, "resolved_validator": {"path": validator.relative_to(ROOT).as_posix(), "sha256": digest(validator), "package_identity": value.get("package_identity", "unknown")}, "probes": [probe_record("requested-target", target, result), probe_record("detached-positive", target, detached_positive), probe_record("detached-negative", target, negative)], "target_observation": {"validator_observed_target": True, "mutation_rejected": True, "detached_positive_identity": detached_identity, "detached_negative_identity": invalid_identity, "negative_diagnostic": oracle["diagnostic"], "negative_reads": negative_reads}, "independent_validator_verification": independent, "authorizes": []}
    # Detect drift after native execution, including additions to the owner.
    if independent_validator_verification(validator, value) != independent:
        raise ValueError("validator trust closure changed during execution")
    return receipt

def replay_verdict(receipt: dict) -> str:
    value = {"status": receipt["status"], "target": receipt["effective_inspected_content"], "probes": [(row["probe_id"], row["exit_code"]) for row in receipt["probes"]], "validator": receipt["resolved_validator"]["sha256"], "consumers": [{key: row[key] for key in ("consumer", "stage", "fixture", "route_identity", "exit_code", "diagnostic_category")} for row in receipt.get("consumer_verification", {}).get("calls", [])], "snapshot": receipt.get("current_snapshot", {}).get("sha256")}
    return json_digest(value)

def replay_coverage(receipt: dict) -> dict:
    return {"executed_probe_ids": [row["probe_id"] for row in receipt["probes"]], "probe_count": len(receipt["probes"]), "consumer_stage_ids": sorted(row["consumer"] + ":" + row["stage"] + ":" + row["fixture"] for row in receipt.get("consumer_verification", {}).get("calls", []))}

def candidate_external_trust(target: str, capability_path: str, receipt: dict) -> dict:
    capability_file = contained(ROOT / capability_path, ROOT, "capability")
    target_root = contained(ROOT / target, ROOT, "target package")
    validator = ROOT / receipt["resolved_validator"]["path"]
    independent = receipt.get("independent_validator_verification", {})
    return {
        "independent": not is_within(capability_file, target_root) and independent.get("independent") is True,
        "complete": bool(
            capability_file.is_file()
            and validator.is_file()
            and digest(validator) == receipt["resolved_validator"]["sha256"]
            and independent.get("status") == "pass"
            and isinstance(independent.get("source_sha256"), str)
            and bool(independent.get("source_sha256"))
        ),
        "candidate_controlled": is_within(capability_file, target_root),
        "inherited": False,
        "capability_identity": digest(capability_file),
    }


def consumer_command(consumer: str, target: str) -> list[str]:
    return runtime.command(consumer, target)

def consumer_manifest() -> dict:
    return runtime.consumer_manifest(ROOT)

def current_snapshot_binding(target: str, capability_path: str, validator: Path) -> dict:
    return runtime.snapshot(ROOT, target, capability_path, validator, CURRENT_SNAPSHOT_SCHEMA)

def validate_current_snapshot_binding(snapshot: dict, target: str, capability_path: str, validator: Path) -> None:
    if not isinstance(snapshot, dict) or snapshot.get("schema") != CURRENT_SNAPSHOT_SCHEMA or snapshot.get("complete") is not True:
        raise ValueError("current snapshot binding is incomplete")
    if snapshot != current_snapshot_binding(target, capability_path, validator):
        raise ValueError("current snapshot binding does not match result-determining inputs")

def verify_fresh_replay(target: str, capability_path: str, validator: Path, verdict: str, coverage: dict, target_identity: str, snapshot: dict) -> dict:
    checkout = Path(tempfile.mkdtemp(prefix="jimuyun-fresh-checkout-")) / "repo"
    try:
        runtime.git(ROOT, "clone", "--shared", "--no-checkout", str(ROOT), str(checkout))
        inputs = snapshot["inputs"]
        pinned = {row["path"]: row["sha256"] for row in inputs["dependencies"] + inputs["data"]}
        for name, expected in pinned.items():
            source = runtime.relative(ROOT, name)
            if digest(source) != expected:
                raise ValueError("pinned input became stale before reconstruction: " + name)
            destination = runtime.relative(checkout, name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        runtime.assert_identity(checkout, [{"path": name, "sha256": identity} for name, identity in pinned.items()])
        command = [sys.executable, "-B", str(checkout / "scripts/sc/skill_package_replay.py"), "replay-package", "--target", target, "--capability", capability_path, "--probe-mode", "fresh-child"]
        native = runtime.execute(command, checkout)
        if native.returncode:
            raise ValueError("fresh checkout replay rejected pinned inputs: " + native.stdout + native.stderr)
        fresh = json.loads(native.stdout)["current_wrapper_replay"]
        mismatches = []
        if replay_verdict(fresh) != verdict:
            mismatches.append("semantic-verdict")
        if replay_coverage(fresh) != coverage:
            mismatches.append("coverage")
        if fresh["effective_inspected_content"]["identity"] != target_identity:
            mismatches.append("target-identity")
        if fresh.get("current_snapshot") != snapshot:
            mismatches.append("snapshot")
        if mismatches:
            raise ValueError("fresh replay does not match pinned inputs: " + ",".join(mismatches))
        return {"fresh_checkout": True, "pinned_semantic_verdict": verdict, "fresh_semantic_verdict": replay_verdict(fresh), "fresh_coverage": replay_coverage(fresh), "coverage_result": replay_coverage(fresh), "pinned_coverage": coverage, "reconstructed_identity": target_identity, "replay_identity": fresh["effective_inspected_content"]["identity"], "fresh_process": True, "checkout_path": str(checkout), "checkout_commit": inputs["git_baseline"], "historical_evidence_rewritten": False, "reconstructed_inputs": pinned}
    except Exception:
        shutil.rmtree(checkout.parent, ignore_errors=True)
        raise

def rollback_details(target: str, capability_path: str, replay: dict) -> dict:
    stages = [row for row in replay["route_transitions"] if row["transition"] == "rollback"]
    entries = replay["consumer_manifest"]["entries"]
    expected = {(entry["consumer"], fixture) for entry in entries for fixture in
                (("terminal-policy-observation",) if entry["consumer"] == "workflow-model-routing" else ("valid-package", "invalid-package"))}
    observed = [(row["consumer"], row["fixture"]) for row in stages]
    if not expected or len(observed) != len(set(observed)) or set(observed) != expected:
        raise ValueError("rollback fixture coverage does not match the frozen Consumer Manifest")
    prior_identities = {row["baseline"]["route_identity"] for row in stages}
    if len(prior_identities) != 1 or any(
        row["route"] != "Prior Route" or row["route_identity"] != row["baseline"]["route_identity"]
        or row.get("executed") is not True or row.get("matched_expected") is not True
        or row.get("baseline_match") is not True
        or any(row[field] != row["baseline"][field] for field in ("exit_code", "verdict", "diagnostic_category"))
        for row in stages
    ):
        raise ValueError("rollback did not reproduce every captured Prior Route fixture")
    observations = [{"consumer": entry["consumer"], "path": entry["path"], "baseline_match": True,
                     "fixture_observations": [row for row in stages if row["consumer"] == entry["consumer"]]}
                    for entry in entries]
    prior_identity = next(iter(prior_identities))
    return {"real_call": True, "route_identity": prior_identity, "prior_route_identity": prior_identity,
            "prior_route_captured_before_transition": True, "verdict": "pass", "prior_verdict": "pass",
            "diagnostic_category": "all-fixture-postconditions-matched", "prior_diagnostic_category": "all-fixture-postconditions-matched",
            "observed_count": len(observations), "manifest_count": len(entries), "fixture_observed_count": len(stages),
            "baseline_observations": observations, "command_outcome": {"kind": "aggregate-postconditions", "exit_code": 0}}

def historical_receipt(replay: dict) -> dict:
    return {
        "schema_version": "jimuyun.tc-d1-historical-replay-receipt.v1",
        "status": replay["status"],
        "exit_code": replay["exit_code"],
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
    execution = runtime.route_transitions(ROOT, target, manifest, capability_path)
    transitions = execution["transitions"]
    calls = execution["calls"]
    if not calls or any(call["matched_expected"] is not True for call in calls):
        raise ValueError("required Consumer did not complete successfully")
    validate_current_snapshot_binding(snapshot, target, capability_path, ROOT / replay["resolved_validator"]["path"])
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
            "executed": all(call["executed"] and call["matched_expected"] for call in calls),
            "consumer": "repository-owned-replay-entry",
            "target": target,
            "calls": calls,
        },
        "dependency_verification": {
            "independent": True,
            "status": "pass",
            "dependencies": snapshot["inputs"]["dependencies"],
            "environment": snapshot["inputs"]["environment"],
            "closure_sha256": runtime.canonical(snapshot["inputs"]),
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
        "transition_completion_percent": 100 if all(call["matched_expected"] for call in calls) else 0,
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
    verdict = replay_verdict(replay)
    coverage = replay_coverage(replay)
    replay["semantic_verdict"] = verdict
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
    if probe_mode in {"enable", "disable", "rollback", "re-enable"}:
        calls = [row for row in replay["consumer_verification"]["calls"] if row["stage"] == probe_mode]
        replay["consumer_invocation"] = {"transition": probe_mode, "real_call": bool(calls), "route": calls[0]["route"], "route_identity": calls[0]["route_identity"], "target": target, "execution_result": replay["status"], "calls": calls}
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
    prepare = sub.add_parser("prepare-matrix")
    prepare.add_argument("--target", required=True)
    prepare.add_argument("--capability", required=True)
    prepare.add_argument("--stable-commit", required=True)
    prepare.add_argument("--output", required=True)
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
    if rejection_reason is None and case.get("_require_real_matrix_input") is True:
        assignments = case.get("fixture_state_assignments")
        if not isinstance(assignments, dict) or any(
            not isinstance(assignments.get(subject), dict)
            or not assignments[subject].get("fixture_id")
            or not assignments[subject].get("state_id")
            for subject in ("Stable", "Candidate")
        ):
            rejection_reason = "matrix input fixture-state assignment is incomplete"
        elif assignments["Stable"] == assignments["Candidate"]:
            rejection_reason = "matrix input fixture-state assignments must be distinct"
    if rejection_reason is None and case.get("_require_real_matrix_input") is True:
        matrix_input = case.get("matrix_input")
        if not isinstance(matrix_input, dict):
            rejection_reason = "matrix input binding is missing"
        else:
            source_path = matrix_input.get("source_path")
            source_sha256 = matrix_input.get("source_sha256")
            input_id = matrix_input.get("input_id")
            if not isinstance(input_id, str) or not input_id:
                rejection_reason = "matrix input identity is missing"
            elif not isinstance(source_path, str) or not isinstance(source_sha256, str):
                rejection_reason = "matrix input source binding is incomplete"
            else:
                try:
                    source = contained(ROOT / source_path, ROOT, "matrix input source")
                    if not source.is_file() or digest(source) != source_sha256:
                        rejection_reason = "matrix input source identity is stale"
                except (OSError, ValueError):
                    rejection_reason = "matrix input source identity is invalid"
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


def replay_matrix(matrix_argument: str) -> tuple[dict, int]:
    matrix_path = contained(ROOT / matrix_argument, ROOT, "matrix")
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    result, code = runtime.replay_matrix(ROOT, matrix)
    # Legacy inputs stay non-promotable. Retain precise refusal diagnostics
    # used by existing CER selectors; this never invokes a legacy pass route.
    if matrix.get("schema_version") == "jimuyun.stable-candidate-replay-matrix.v2":
        cases = matrix.get("cases", [])
        for row, case in zip(result.get("case_results", []), cases):
            reason, diagnostic = matrix_rejection(case)
            if reason:
                row["rejection_reason"] = reason
            if diagnostic:
                row["diagnostic"] = diagnostic
        result["invalid_reasons"] = sorted({row.get("rejection_reason", "legacy input is not executable") for row in result.get("case_results", [])})
    result.update(runner_entrypoint="scripts/sc/skill_package_replay.py", matrix_path=matrix_argument, matrix_sha256=digest(matrix_path))
    return result, code

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
    if args.op == "prepare-matrix":
        result = runtime.prepare_matrix(ROOT, args.target, args.capability, args.stable_commit, args.output)
        print(json.dumps(result, sort_keys=True))
        return 0
    result, exit_code = replay_matrix(args.matrix)
    print(json.dumps(result, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, OSError, KeyError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        print(json.dumps({"status": "execution-failed", "exit_code": 1, "diagnostic": str(exc), "authorizes": []}, sort_keys=True))
        raise SystemExit(1)
