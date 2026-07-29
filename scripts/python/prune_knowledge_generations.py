"""Report or explicitly prune unprotected immutable knowledge generations."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import publish_knowledge_catalog as publication


GENERATION_ID = re.compile(r"^[0-9a-f]{64}$")
DEFAULT_POLICY = Path("knowledge/policies/generation-retention.v1.json")


def _load_json_bytes(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label}_schema_invalid") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label}_schema_invalid")
    return value


def _validate_policy(policy: dict[str, Any]) -> int:
    keep = policy.get("keep_recent_successful")
    if (
        policy.get("schema_version") != "jimuyun.knowledge-generation-retention-policy.v1"
        or not isinstance(policy.get("policy_revision"), str)
        or not isinstance(keep, int)
        or isinstance(keep, bool)
        or keep < 1
        or policy.get("protect_current") is not True
        or policy.get("protect_last_known_good") is not True
        or policy.get("pruning_mode") != "explicit-only"
        or policy.get("failure_evidence_root") != "logs/knowledge-context"
    ):
        raise ValueError("generation_retention_policy_invalid")
    return keep


def _canonical_policy(repository_root: Path) -> tuple[dict[str, Any], bytes, str]:
    main_commit = publication._main_commit(repository_root)
    main_bytes = publication._main_blob(repository_root, main_commit, DEFAULT_POLICY)
    formal_path = repository_root / DEFAULT_POLICY
    if not formal_path.is_file() or formal_path.read_bytes() != main_bytes:
        raise ValueError("dirty_or_stale_generation_retention_policy")
    policy = _load_json_bytes(main_bytes, "generation_retention_policy")
    _validate_policy(policy)
    return policy, main_bytes, main_commit


def _load_valid_pointer(index_root: Path, filename: str) -> tuple[dict[str, Any], bytes]:
    return publication._load_pointer(index_root / filename, filename)


def _validated_generation(repository_root: Path, generation_id: str) -> tuple[dict[str, Any], int]:
    root = repository_root / "knowledge" / "indexes" / "generations" / generation_id
    manifest_bytes = (root / "manifest.json").read_bytes()
    manifest = _load_json_bytes(manifest_bytes, "generation_manifest")
    pointer = {
        "schema_version": publication.POINTER_SCHEMA_VERSION,
        "generation_id": generation_id,
        "generation_sha256": publication._sha(manifest_bytes),
        "main_commit": manifest.get("main_commit"),
        "source_snapshot_id": manifest.get("source_snapshot_id"),
    }
    _, payloads = publication._generation_payloads(repository_root, pointer)
    publication._validate_generation_payloads(manifest, payloads)
    size = sum(item.stat().st_size for item in root.rglob("*") if item.is_file())
    return manifest, size


def _main_commit_order(repository_root: Path) -> dict[str, int]:
    completed = subprocess.run(
        ["git", "-C", str(repository_root), "rev-list", "--reverse", "--topo-order", "refs/heads/main"],
        capture_output=True,
        text=True,
        encoding="ascii",
        check=False,
    )
    if completed.returncode:
        raise ValueError("main_history_unavailable")
    return {commit: index for index, commit in enumerate(completed.stdout.splitlines()) if commit}


def _generation_first_commit(repository_root: Path, generation_id: str, commit_order: dict[str, int]) -> int:
    relative = f"knowledge/indexes/generations/{generation_id}/manifest.json"
    completed = subprocess.run(
        ["git", "-C", str(repository_root), "log", "--diff-filter=A", "--format=%H", "refs/heads/main", "--", relative],
        capture_output=True,
        text=True,
        encoding="ascii",
        check=False,
    )
    commits = [value for value in completed.stdout.splitlines() if value]
    if completed.returncode or not commits:
        raise ValueError("generation_not_committed_to_main")
    first = min(commits, key=lambda value: commit_order.get(value, len(commit_order)))
    if first not in commit_order:
        raise ValueError("generation_commit_not_on_main")
    return commit_order[first]


def inventory(repository_root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    index_root = repository_root / "knowledge" / "indexes"
    generation_root = index_root / "generations"
    keep = _validate_policy(policy)
    current_pointer, _ = _load_valid_pointer(index_root, "current.json")
    lkg_pointer, _ = _load_valid_pointer(index_root, "last-known-good.json")
    for label, pointer in (("current", current_pointer), ("last_known_good", lkg_pointer)):
        try:
            manifest, payloads = publication._generation_payloads(repository_root, pointer)
            publication._validate_generation_payloads(manifest, payloads)
        except (OSError, UnicodeError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            raise ValueError(f"{label}_pointer_generation_invalid") from error
    current = current_pointer["generation_id"]
    lkg = lkg_pointer["generation_id"]
    commit_order = _main_commit_order(repository_root)
    valid: list[tuple[int, str, int]] = []
    invalid: list[str] = []
    for path in sorted(generation_root.iterdir(), key=lambda item: item.name):
        if not path.is_dir() or not GENERATION_ID.fullmatch(path.name):
            invalid.append(path.name)
            continue
        try:
            _, size = _validated_generation(repository_root, path.name)
            order = _generation_first_commit(repository_root, path.name, commit_order)
            valid.append((order, path.name, size))
        except (OSError, UnicodeError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            invalid.append(path.name)
    valid_ids = {generation_id for _, generation_id, _ in valid}
    if current not in valid_ids or lkg not in valid_ids:
        raise ValueError("protected_generation_missing_or_invalid")
    recent = {generation_id for _, generation_id, _ in sorted(valid, reverse=True)[:keep]}
    protected = {current, lkg, *recent}
    candidates = [generation_id for _, generation_id, _ in valid if generation_id not in protected]
    sizes = {generation_id: size for _, generation_id, size in valid}
    return {
        "schema_version": "jimuyun.knowledge-generation-prune-report.v1",
        "status": "checked",
        "policy_revision": policy["policy_revision"],
        "keep_recent_successful": keep,
        "current_generation_id": current,
        "last_known_good_generation_id": lkg,
        "recent_generation_ids": sorted(recent),
        "protected_generation_ids": sorted(protected),
        "candidate_generation_ids": sorted(candidates),
        "invalid_generation_ids": sorted(invalid),
        "generation_count": len(valid),
        "candidate_bytes": sum(sizes[generation_id] for generation_id in candidates),
    }


def _append_evidence(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = publication._render(value)
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def run(repository_root: Path, *, prune: bool) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    try:
        policy, policy_bytes, main_commit = _canonical_policy(repository_root)
        index_root = repository_root / "knowledge" / "indexes"
        with publication._single_writer(index_root):
            report = inventory(repository_root, policy)
            pointer_bytes = {
                filename: (index_root / filename).read_bytes()
                for filename in ("current.json", "last-known-good.json")
            }
            if not prune:
                return report
            if publication._main_commit(repository_root) != main_commit:
                raise ValueError("main_advanced_during_generation_pruning")
            now = datetime.now(timezone.utc)
            operation_id = f"{now.strftime('%H%M%S%f')}-{uuid.uuid4().hex}"
            evidence_root = repository_root / "logs" / "knowledge-context" / now.date().isoformat() / "generation-pruning" / operation_id
            intent = {
                **report,
                "schema_version": "jimuyun.knowledge-generation-prune-intent.v1",
                "status": "authorized",
                "operation_id": operation_id,
                "main_commit": main_commit,
                "policy_sha256": publication._sha(policy_bytes),
                "recorded_at": now.isoformat(),
                "authorizes": [],
            }
            _append_evidence(evidence_root / "intent.json", intent)
            generation_root = (index_root / "generations").resolve()
            removed: list[str] = []
            cleanup_failed: list[str] = []
            quarantined: list[str] = []
            committed = False
            candidates = list(report["candidate_generation_ids"])
            try:
                for generation_id in candidates:
                    if publication._main_commit(repository_root) != main_commit:
                        raise ValueError("main_advanced_during_generation_pruning")
                    target = (generation_root / generation_id).resolve()
                    target.relative_to(generation_root)
                    if target.parent != generation_root or not GENERATION_ID.fullmatch(target.name):
                        raise ValueError("generation_prune_target_invalid")
                    for filename, expected in pointer_bytes.items():
                        if (index_root / filename).read_bytes() != expected:
                            raise ValueError("generation_pointer_changed_during_pruning")
                    _validated_generation(repository_root, generation_id)
                    _append_evidence(evidence_root / "authorizations" / f"{generation_id}.json", {
                        "schema_version": "jimuyun.knowledge-generation-prune-authorization.v1",
                        "status": "authorized",
                        "operation_id": operation_id,
                        "generation_id": generation_id,
                        "intent_sha256": publication._sha((evidence_root / "intent.json").read_bytes()),
                        "recorded_at": datetime.now(timezone.utc).isoformat(),
                        "authorizes": [f"delete:{generation_id}"],
                    })
                    quarantine = evidence_root / "quarantine" / generation_id
                    quarantine.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(target, quarantine)
                    quarantined.append(generation_id)
                if publication._main_commit(repository_root) != main_commit:
                    raise ValueError("main_advanced_during_generation_pruning")
                for filename, expected in pointer_bytes.items():
                    if (index_root / filename).read_bytes() != expected:
                        raise ValueError("generation_pointer_changed_during_pruning")
                _append_evidence(evidence_root / "commit.json", {
                    "schema_version": "jimuyun.knowledge-generation-prune-commit.v1",
                    "status": "committed",
                    "operation_id": operation_id,
                    "main_commit": main_commit,
                    "generation_ids": quarantined,
                    "pointer_sha256": {
                        filename: publication._sha(payload)
                        for filename, payload in pointer_bytes.items()
                    },
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                    "authorizes": [],
                })
                committed = True
                removed.extend(quarantined)
                for generation_id in list(quarantined):
                    quarantine = evidence_root / "quarantine" / generation_id
                    cleanup_failed.append(generation_id)
                    deletion_evidence = evidence_root / "deletions" / f"{generation_id}.json"
                    _append_evidence(deletion_evidence, {
                        "schema_version": "jimuyun.knowledge-generation-prune-deletion.v1",
                        "status": "removed-from-generation-authority",
                        "operation_id": operation_id,
                        "generation_id": generation_id,
                        "recorded_at": datetime.now(timezone.utc).isoformat(),
                        "authorizes": [],
                    })
                    shutil.rmtree(quarantine)
                    cleanup_failed.remove(generation_id)
                    quarantined.remove(generation_id)
            except Exception as error:
                rollback_errors: list[str] = []
                if not committed:
                    for generation_id in reversed(quarantined):
                        quarantine = evidence_root / "quarantine" / generation_id
                        target = generation_root / generation_id
                        try:
                            if quarantine.exists():
                                os.replace(quarantine, target)
                            if not target.is_dir():
                                rollback_errors.append(generation_id)
                        except OSError:
                            rollback_errors.append(generation_id)
                    if rollback_errors:
                        error = RuntimeError(f"{error}; generation_prune_rollback_failed:{','.join(rollback_errors)}")
                    else:
                        quarantined.clear()
                remaining = [generation_id for generation_id in candidates if generation_id not in removed]
                failure = {
                    "schema_version": "jimuyun.knowledge-generation-prune-failure.v1",
                    "status": "failed",
                    "operation_id": operation_id,
                    "error": str(error),
                    "removed_generation_ids": removed,
                    "remaining_generation_ids": remaining,
                    "cleanup_failed_generation_ids": cleanup_failed,
                    "quarantined_generation_ids": list(quarantined),
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                    "authorizes": [],
                }
                failure_path = evidence_root / "failure.json"
                try:
                    _append_evidence(failure_path, failure)
                    evidence_value: str | None = failure_path.relative_to(repository_root).as_posix()
                except OSError:
                    evidence_value = None
                return {**failure, "evidence": evidence_value}
            result = {
                **report,
                "status": "pruned",
                "operation_id": operation_id,
                "removed_generation_ids": removed,
                "cleanup_failed_generation_ids": cleanup_failed,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            }
            try:
                _append_evidence(evidence_root / "result.json", result)
            except OSError as error:
                failure = {
                    "schema_version": "jimuyun.knowledge-generation-prune-failure.v1",
                    "status": "failed",
                    "operation_id": operation_id,
                    "error": str(error),
                    "removed_generation_ids": removed,
                    "remaining_generation_ids": [],
                    "cleanup_failed_generation_ids": cleanup_failed,
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                    "authorizes": [],
                }
                try:
                    _append_evidence(evidence_root / "failure.json", failure)
                    evidence_value = (evidence_root / "failure.json").relative_to(repository_root).as_posix()
                except OSError:
                    evidence_value = None
                return {**failure, "evidence": evidence_value}
            return {**result, "evidence": (evidence_root / "result.json").relative_to(repository_root).as_posix()}
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        return {"status": "blocked", "error": str(error)}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Report protected and prune-candidate generations (default).")
    mode.add_argument("--prune", action="store_true", help="Delete only generations allowed by the retention policy.")
    args = parser.parse_args()
    result = run(args.repository_root, prune=args.prune)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] in {"checked", "pruned"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
