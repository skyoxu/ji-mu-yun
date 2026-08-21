#!/usr/bin/env python3
"""Project one completed compact VDD target into Acceptance prerequisites."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any

from acceptance_core import InputError, canonical_hash, validate_run_input
from execution_control import ControlError, inspect_run, resolve_registered_command


HASH_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
RUN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InputError(f"projection input is unreadable: {path.name}") from exc
    if not isinstance(value, dict):
        raise InputError(f"projection input must be an object: {path.name}")
    return value


def _hash_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _file_ref(path: Path, target: Path) -> dict[str, str]:
    return {"path": path.relative_to(target).as_posix(), "sha256": _hash_bytes(path.read_bytes())}


def _relative(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or "\0" in value:
        raise InputError(f"{field} is invalid")
    normalized = value.replace("\\", "/")
    path = Path(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise InputError(f"{field} must be repository-relative")
    return normalized


def _git(root: Path, *args: str, allow_missing: bool = False, env: dict[str, str] | None = None, stdin: bytes | None = None) -> bytes | None:
    result = subprocess.run(["git", "-C", str(root), *args], input=stdin, capture_output=True, check=False, env=env)
    if result.returncode:
        if allow_missing:
            return None
        raise InputError("Git lookup failed during compact VDD projection")
    return result.stdout


def _git_blob(root: Path, revision: str, path: str) -> bytes | None:
    return _git(root, "show", f"{revision}:{path}", allow_missing=True)


def _validate_request(value: dict[str, Any]) -> None:
    required = {
        "schemaVersion", "targetPlan", "runId", "changeId", "baselineRevision",
        "changedPaths", "affectedConsumerRefs", "targetPlanPaths", "knowledgeContextPath",
        "codeReviewDomain", "codeReviewPolicyPath", "implementationReceiptPath",
        "implementationReceiptHash", "commands", "actions", "authorizes",
    }
    allowed = {frozenset(required), frozenset(required | {"baselineOverlaySources"}), frozenset(required | {"candidateRevision"}), frozenset(required | {"candidateRevision", "baselineOverlaySources"})}
    if set(value) not in allowed or value.get("schemaVersion") != "compact-vdd-acceptance-projection-request.v1" or value.get("authorizes") != []:
        raise InputError("compact VDD projection request fields are invalid")
    if not isinstance(value.get("runId"), str) or RUN_PATTERN.fullmatch(value["runId"]) is None:
        raise InputError("compact VDD projection runId is invalid")
    for field in ("targetPlan", "knowledgeContextPath", "codeReviewPolicyPath", "implementationReceiptPath"):
        _relative(value.get(field), field)
    if not isinstance(value.get("implementationReceiptHash"), str) or HASH_PATTERN.fullmatch(value["implementationReceiptHash"]) is None:
        raise InputError("compact VDD implementation receipt hash is invalid")
    for field in ("changedPaths", "affectedConsumerRefs", "targetPlanPaths"):
        values = value.get(field)
        if not isinstance(values, list) or not values or any(not isinstance(item, str) for item in values):
            raise InputError(f"compact VDD projection {field} is invalid")
        normalized = [_relative(item, field) for item in values]
        if normalized != sorted(set(normalized)):
            raise InputError(f"compact VDD projection {field} must be sorted and unique")
    if value.get("codeReviewDomain") not in {"phase_service", "toolchain"}:
        raise InputError("compact VDD projection code review domain is invalid")
    if not isinstance(value.get("commands"), list) or not value["commands"]:
        raise InputError("compact VDD projection commands are missing")
    if not isinstance(value.get("actions"), list) or not value["actions"]:
        raise InputError("compact VDD projection actions are missing")
    if "candidateRevision" in value:
        candidate = value["candidateRevision"]
        if not isinstance(candidate, str) or not re.fullmatch(r"[0-9a-f]{40}", candidate):
            raise InputError("compact VDD candidateRevision is invalid")
    overlays = value.get("baselineOverlaySources", {})
    if not isinstance(overlays, dict) or any(
        not isinstance(path, str) or not isinstance(source, str)
        for path, source in overlays.items()
    ):
        raise InputError("compact VDD baseline overlay sources are invalid")
    normalized_overlays = {
        _relative(path, "baseline overlay path"): _relative(source, "baseline overlay source")
        for path, source in overlays.items()
    }
    if list(normalized_overlays) != sorted(normalized_overlays) or not set(normalized_overlays).issubset(set(value["changedPaths"])):
        raise InputError("compact VDD baseline overlays must be sorted changed paths")


def _project_baseline_overlays(
    root: Path, baseline_revision: str, overlays: dict[str, str]
) -> str:
    resolved = _git(root, "rev-parse", "--verify", f"{baseline_revision}^{{commit}}")
    assert resolved is not None
    resolved_revision = resolved.decode("ascii").strip()
    if not overlays:
        return resolved_revision
    with tempfile.TemporaryDirectory(prefix="acceptance-baseline-index-") as directory:
        index_path = Path(directory) / "index"
        env = dict(os.environ)
        env["GIT_INDEX_FILE"] = str(index_path)
        _git(root, "read-tree", resolved_revision, env=env)
        for path, source in overlays.items():
            source_path = (root / source).resolve()
            try:
                source_path.relative_to(root)
            except ValueError as exc:
                raise InputError("baseline overlay source escapes repository root") from exc
            if not source_path.is_file():
                raise InputError(f"baseline overlay source is missing: {source}")
            blob = _git(root, "hash-object", "-w", "--", str(source_path), env=env)
            assert blob is not None
            object_id = blob.decode("ascii").strip()
            _git(root, "update-index", "--add", "--cacheinfo", f"100644,{object_id},{path}", env=env)
        tree = _git(root, "write-tree", env=env)
        assert tree is not None
        commit_env = dict(env)
        commit_env.update({
            "GIT_AUTHOR_NAME": "Refactor Acceptance",
            "GIT_AUTHOR_EMAIL": "acceptance@local.invalid",
            "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z",
            "GIT_COMMITTER_NAME": "Refactor Acceptance",
            "GIT_COMMITTER_EMAIL": "acceptance@local.invalid",
            "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z",
        })
        commit = _git(
            root, "commit-tree", tree.decode("ascii").strip(), "-p", resolved_revision,
            env=commit_env, stdin=b"Refactor Acceptance baseline overlay\n",
        )
        assert commit is not None
        return commit.decode("ascii").strip()


def _implementation_handoff(root: Path, target: Path, request: dict[str, Any]) -> tuple[Path, dict[str, Any], Path]:
    receipt_path = (root / request["implementationReceiptPath"]).resolve()
    try:
        receipt_path.relative_to(root)
    except ValueError as exc:
        raise InputError("implementation receipt escapes repository root") from exc
    if not receipt_path.is_file() or _hash_bytes(receipt_path.read_bytes()) != request["implementationReceiptHash"]:
        raise InputError("implementation receipt is missing or stale")
    receipt = _load(receipt_path)
    contract_path = target / "implementation-contract.v1.json"
    registry_path = target / "command-registry.v1.json"
    if not contract_path.is_file() or not registry_path.is_file():
        raise InputError("implementation handoff contract or registry is missing")
    contract = _load(contract_path)
    terminal = contract.get("terminal") if isinstance(contract, dict) else None
    if not isinstance(terminal, dict) or set(terminal) != {"command_id", "runner", "predicate"}:
        raise InputError("implementation handoff terminal contract is invalid")
    runner_value = terminal.get("runner")
    if not isinstance(runner_value, str):
        raise InputError("implementation handoff terminal runner is invalid")
    runner_path = (target / runner_value).resolve()
    try:
        runner_path.relative_to(target)
    except ValueError as exc:
        raise InputError("implementation handoff terminal runner escapes target") from exc
    if receipt.get("schema_version") == "quick-dev-implementation-complete.v2":
        if receipt.get("plan_id") != contract.get("plan_id") or receipt.get("predicate") != "implementation-complete" or receipt.get("status") != "pass":
            raise InputError("implementation receipt does not match the current Quick Dev terminal contract")
        for label, current in (("implementation_contract", contract_path), ("command_registry", registry_path)):
            descriptor = receipt.get(label)
            if not isinstance(descriptor, dict) or descriptor.get("sha256") != _hash_bytes(current.read_bytes()):
                raise InputError("implementation receipt does not match the current Quick Dev terminal contract")
        terminal_result = receipt.get("terminal_result")
        manifest_ref = receipt.get("candidate_source_manifest")
        if not isinstance(terminal_result, dict) or not isinstance(manifest_ref, dict):
            raise InputError("implementation receipt v2 binding is incomplete")
        terminal_path = (target / str(terminal_result.get("path", ""))).resolve()
        manifest_path = (target / str(manifest_ref.get("path", ""))).resolve()
        try:
            terminal_path.relative_to(target)
            manifest_path.relative_to(target)
        except ValueError as exc:
            raise InputError("implementation receipt v2 binding escapes target") from exc
        if not terminal_path.is_file() or _hash_bytes(terminal_path.read_bytes()) != terminal_result.get("sha256"):
            raise InputError("implementation receipt terminal result is stale")
        manifest = _load(manifest_path)
        entries = manifest.get("entries")
        if manifest.get("schema_version") != "jimuyun.candidate-source-manifest.v1" or not isinstance(entries, list):
            raise InputError("implementation candidate source manifest is invalid")
        canonical_entries: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {"path", "role", "slice_ids", "sha256"}:
                raise InputError("implementation candidate source manifest is invalid")
            source = (root / str(entry["path"])).resolve()
            try:
                source.relative_to(root)
            except ValueError as exc:
                raise InputError("implementation candidate source manifest escapes repository") from exc
            if not source.is_file() or _hash_bytes(source.read_bytes()) != entry["sha256"]:
                raise InputError("implementation candidate source manifest is stale")
            canonical_entries.append(entry)
        root_hash = _hash_bytes(json.dumps(sorted(canonical_entries, key=lambda item: (item["path"], item["role"], item["slice_ids"])), sort_keys=True, separators=(",", ":")).encode("utf-8"))
        if manifest.get("candidate_source_root") != root_hash or manifest_ref.get("candidate_source_root") != root_hash or manifest_ref.get("sha256") != _hash_bytes(manifest_path.read_bytes()):
            raise InputError("implementation candidate source manifest binding is stale")
        if receipt.get("authorizes") != ["acceptance-handoff"]:
            raise InputError("implementation receipt does not authorize acceptance-handoff")
    else:
        expected = {
            "schema_version": "quick-dev-implementation-complete.v1",
            "predicate": "implementation-complete",
            "status": "pass",
            "plan_id": contract.get("plan_id"),
            "contract_hash": _hash_bytes(contract_path.read_bytes()),
            "command_registry_hash": _hash_bytes(registry_path.read_bytes()),
            "terminal_command_id": terminal.get("command_id"),
        }
        if any(receipt.get(key) != value for key, value in expected.items()):
            raise InputError("implementation receipt does not match the current Quick Dev terminal contract")
        if receipt.get("authorizes") != ["implementation-complete"]:
            raise InputError("implementation receipt does not authorize implementation-complete")
    if not isinstance(receipt.get("validated_command_ids"), list) or not receipt["validated_command_ids"]:
        raise InputError("implementation receipt has no validated commands")
    if not runner_path.is_file():
        raise InputError("implementation handoff terminal runner is missing")
    return receipt_path, receipt, runner_path


def _candidate_payload(root: Path, request: dict[str, Any], path: str) -> bytes | None:
    revision = request.get("candidateRevision")
    if revision is not None:
        return _git_blob(root, revision, path)
    current = root / path
    return current.read_bytes() if current.is_file() else None


def _historical_evidence_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return (
        normalized.startswith("execution-plans/")
        and any(
            marker in normalized
            for marker in (
                "/.acceptance-snapshots/", "/in/", "/s/", "/acceptance-inputs/", "/acceptance-runs/",
                "/knowledge-context.history/", "/knowledge-context.freeze.history/",
            )
        )
    ) or normalized.startswith("_bmad-output/q/")


def project(repository_root: Path, request_path: Path) -> dict[str, Any]:
    root = repository_root.resolve()
    request = _load(request_path)
    _validate_request(request)
    if request.get("candidateRevision"):
        status = (_git(root, "status", "--porcelain") or b"").decode("utf-8")
        lines = [line for line in status.splitlines() if line]
        allowed_request = (
            len(lines) == 1
            and lines[0].startswith("?? ")
            and (root / lines[0][3:]).resolve() == request_path.resolve()
        )
        if status and not allowed_request:
            raise InputError("commit candidate requires a clean worktree apart from its projection request")
    target = (root / request["targetPlan"]).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise InputError("compact VDD target escapes repository root") from exc
    if not target.is_dir():
        raise InputError("compact VDD target is missing")
    receipt_path, receipt, validator = _implementation_handoff(root, target, request)
    knowledge = (target / request["knowledgeContextPath"]).resolve()
    policy_source = (root / request["codeReviewPolicyPath"]).resolve()
    if not knowledge.is_file() or not policy_source.is_file():
        raise InputError("compact VDD knowledge context or policy is missing")

    baseline_revision = request["baselineRevision"]
    resolved_revision = _project_baseline_overlays(
        root, baseline_revision, request.get("baselineOverlaySources", {})
    )

    baseline_files: list[dict[str, Any]] = []
    candidate_files: list[dict[str, Any]] = []
    present_payloads: dict[str, bytes] = {}
    for path in request["changedPaths"]:
        baseline_payload = _git_blob(root, resolved_revision, path)
        candidate_payload = _candidate_payload(root, request, path)
        if _historical_evidence_path(path):
            candidate_payload = None
        if baseline_payload is None and candidate_payload is None:
            raise InputError(f"changed path has neither baseline nor candidate bytes: {path}")
        if baseline_payload is not None:
            baseline_hash = _hash_bytes(baseline_payload)
            baseline_files.append({"path": path, "roles": ["implementation"], "sha256": baseline_hash, "inclusion_reason": "explicit compact VDD candidate baseline"})
        else:
            baseline_hash = None
        if candidate_payload is None:
            change_type = "deleted"
        elif baseline_payload is None:
            change_type = "untracked"
        elif candidate_payload != baseline_payload:
            change_type = "modified"
        else:
            raise InputError(f"declared changed path has unchanged bytes: {path}")
        candidate_hash = _hash_bytes(candidate_payload) if candidate_payload is not None else None
        candidate_files.append({
            "change_type": change_type,
            "roles": ["implementation"],
            "baseline_path": path if baseline_payload is not None else None,
            "baseline_sha256": baseline_hash,
            "candidate_path": path if candidate_payload is not None else None,
            "candidate_sha256": candidate_hash,
            "inclusion_reason": "explicit compact VDD candidate path",
        })
        if candidate_payload is not None and not _historical_evidence_path(path):
            present_payloads[path] = candidate_payload

    baseline_manifest = {"schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": baseline_files}
    candidate_manifest = {"schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete", "coverageGaps": [], "authorizes": [], "files": candidate_files}
    commands = request["commands"]
    registry = {"schema_version": "ria.command-registry.v1", "commands": commands}
    command_ids = [item.get("id") for item in commands if isinstance(item, dict)]
    if len(command_ids) != len(commands) or len(set(command_ids)) != len(commands):
        raise InputError("compact VDD command identities are invalid")
    for command_id in command_ids:
        try:
            resolve_registered_command(registry, command_id)
        except ControlError as exc:
            raise InputError(str(exc)) from exc
    try:
        inspect_run(request["actions"], set(), {command_id: index for index, command_id in enumerate(command_ids)})
    except ControlError as exc:
        raise InputError(str(exc)) from exc

    run_id = request["runId"]
    input_relative = Path("acceptance-inputs") / run_id
    final_input_dir = target / input_relative
    final_snapshot = target / ".acceptance-snapshots" / run_id
    final_request = target / f"acceptance-run-request.{run_id}.v1.json"
    if final_input_dir.exists() or final_snapshot.exists() or final_request.exists():
        raise InputError("compact VDD projection output already exists")

    with tempfile.TemporaryDirectory(prefix="acceptance-projection-") as directory:
        stage = Path(directory)
        stage_input = stage / "input"
        stage_snapshot = stage / "snapshot"
        stage_input.mkdir()
        stage_snapshot.mkdir()
        baseline_path = stage_input / "baseline-content-manifest.v1.json"
        candidate_path = stage_input / "candidate-content-manifest.v1.json"
        actions_path = stage_input / "action-dag.v1.json"
        registry_path = stage_input / "command-registry.v1.json"
        policy_path = stage_input / policy_source.name
        for path, value in (
            (baseline_path, baseline_manifest), (candidate_path, candidate_manifest),
            (actions_path, request["actions"]), (registry_path, registry),
        ):
            path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        policy_path.write_bytes(policy_source.read_bytes())
        for path, payload in present_payloads.items():
            destination = stage_snapshot / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)

        baseline_ref_path = input_relative / baseline_path.name
        candidate_ref_path = input_relative / candidate_path.name
        policy_ref_path = input_relative / policy_path.name
        run_request = {
            "run_id": run_id,
            "created_utc": "2026-08-01T00:00:00Z",
            "change_id": request["changeId"],
            # Run inputs are persisted evidence and must replay from another
            # checkout.  Keep the target as the repository-relative authority
            # identity rather than the local custody location.
            "target": request["targetPlan"],
            "target_plan_paths": request["targetPlanPaths"],
            "baseline_revision": resolved_revision,
            "candidate_revision": request.get("candidateRevision") or "dirty-worktree:" + canonical_hash(candidate_manifest).split(":", 1)[1],
            "candidate_mode": "commit" if request.get("candidateRevision") else "dirty_worktree",
            "execution_mode": "evidence_only",
            "baseline_content_manifest_path": baseline_ref_path.as_posix(),
            "baseline_content_manifest_hash": canonical_hash(baseline_manifest),
            "candidate_content_manifest_path": candidate_ref_path.as_posix(),
            "candidate_content_manifest_hash": canonical_hash(candidate_manifest),
            "code_review_domain": request["codeReviewDomain"],
            "code_review_policy_path": policy_ref_path.as_posix(),
            "code_review_policy_hash": _hash_bytes(policy_source.read_bytes()),
            "target_plan_hash": _hash_bytes((target / request["targetPlanPaths"][0]).read_bytes()),
            "validator_hash": _hash_bytes(validator.read_bytes()),
            "adapter_id": "run-refactor-implementation-acceptance",
            "adapter_version": "compact-vdd-projection.v1",
            "adapter_hash": _hash_bytes(Path(__file__).read_bytes()),
            "allowed_write_roots": [],
            "forbidden_write_roots": ["logs/phase-a-innernet/", "runtime/phase-a/"],
            "changed_paths": request["changedPaths"],
            "affected_consumer_refs": request["affectedConsumerRefs"],
        }
        if not request.get("candidateRevision"):
            run_request["candidate_frozen_snapshot_path"] = f".acceptance-snapshots/{run_id}"
        validate_run_input(run_request)
        stage_request = stage / final_request.name
        stage_request.write_text(json.dumps(run_request, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

        def staged_ref(path: Path, logical_path: Path) -> dict[str, str]:
            return {"path": logical_path.as_posix(), "sha256": _hash_bytes(path.read_bytes())}

        bundle = {
            "schemaVersion": "compact-vdd-acceptance-prerequisite-bundle.v1",
            "targetPlan": request["targetPlan"],
            "runId": run_id,
            "implementationReceipt": {
                # The prerequisite bundle is consumed from the target root.
                # Preserve a replayable target-relative reference rather than
                # leaking the request's repository-relative transport path.
                "path": receipt_path.relative_to(target).as_posix(),
                "sha256": request["implementationReceiptHash"],
            "terminalCommandId": receipt.get("terminal_command_id")
            or (receipt.get("terminal_result") or {}).get("command_id")
            or "terminal-full",
            },
            "terminalRunner": {
                "path": validator.relative_to(target).as_posix(),
                "sha256": _hash_bytes(validator.read_bytes()),
            },
            "baselineManifest": staged_ref(baseline_path, input_relative / baseline_path.name),
            "candidateManifest": staged_ref(candidate_path, input_relative / candidate_path.name),
            "candidateSnapshotPath": f".acceptance-snapshots/{run_id}",
            "runRequest": staged_ref(stage_request, final_request.relative_to(target)),
            "actionDag": staged_ref(actions_path, input_relative / actions_path.name),
            "commandRegistry": staged_ref(registry_path, input_relative / registry_path.name),
            "knowledgeContext": _file_ref(knowledge, target),
            "policy": staged_ref(policy_path, input_relative / policy_path.name),
            "authorizes": [],
        }
        bundle["bundleHash"] = canonical_hash(bundle)
        (stage_input / "compact-vdd-acceptance-prerequisite-bundle.v1.json").write_text(
            json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )

        final_input_dir.parent.mkdir(parents=True, exist_ok=True)
        final_snapshot.parent.mkdir(parents=True, exist_ok=True)
        os.replace(stage_input, final_input_dir)
        os.replace(stage_snapshot, final_snapshot)
        os.replace(stage_request, final_request)

    bundle_path = final_input_dir / "compact-vdd-acceptance-prerequisite-bundle.v1.json"
    return {"status": "ready", "bundle": bundle_path.relative_to(root).as_posix(), "bundleHash": bundle["bundleHash"], "runRequest": final_request.relative_to(root).as_posix(), "authorizes": []}


def project_or_quick_dev_recovery(repository_root: Path, request_path: Path) -> dict[str, Any]:
    """Return a typed owner handoff when only the Quick Dev receipt is stale.

    Projection remains strict and unchanged.  This adapter only classifies the
    narrow implementation-handoff failure family so an orchestrator can invoke
    the declared Quick Dev terminal route and retry projection with its successor
    receipt.  It never executes a command and never authorizes a lifecycle state.
    """
    try:
        return project(repository_root, request_path)
    except InputError as exc:
        message = str(exc)
        handoff_errors = {
            "implementation receipt is missing or stale",
            "implementation receipt does not match the current Quick Dev terminal contract",
            "implementation receipt does not authorize implementation-complete",
            "implementation receipt has no validated commands",
            "implementation handoff terminal runner is missing",
        }
        if message not in handoff_errors:
            raise
        request = _load(request_path)
        target = (repository_root / request["targetPlan"]).resolve()
        contract_path = target / "implementation-contract.v1.json"
        registry_path = target / "command-registry.v1.json"
        contract = _load(contract_path) if contract_path.is_file() else {}
        terminal = contract.get("terminal") if isinstance(contract, dict) else {}
        return {
            "schemaVersion": "quick-dev-terminal-recovery-required.v1",
            "status": "recovery_required",
            "reasonCode": "implementation_handoff_stale",
            "targetPlan": request["targetPlan"],
            "implementationReceiptPath": request["implementationReceiptPath"],
            "contractHash": _hash_bytes(contract_path.read_bytes()) if contract_path.is_file() else None,
            "commandRegistryHash": _hash_bytes(registry_path.read_bytes()) if registry_path.is_file() else None,
            "terminalCommandId": terminal.get("command_id") if isinstance(terminal, dict) else None,
            "terminalRunner": terminal.get("runner") if isinstance(terminal, dict) else None,
            "recoveryOwner": "quick-dev-tdd-adapter",
            "bootstrapInvoked": False,
            "authorizes": [],
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = project(args.repository_root, args.request)
    except (InputError, OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc), "authorizes": []}, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
