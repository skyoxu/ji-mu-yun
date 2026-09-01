"""Deterministic Q4 implementation and Q6 refactor gates."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from current_router import profile_contract, validate_expected_red, validate_write_delta
from runtime_evidence import current_snapshot, safe_relative, selector_identity_from_descriptor, sha256_value, validate_descriptor


def _git_delta_records(snapshot: Mapping[str, Any]) -> dict[str, str]:
    delta = snapshot.get("git_delta")
    if not isinstance(delta, Mapping):
        raise ValueError("current snapshot git delta missing")
    records: dict[str, str] = {}
    for kind in ("additions", "deletions"):
        values = delta.get(kind)
        if not isinstance(values, list):
            raise ValueError("current snapshot git delta malformed")
        for item in values:
            if not isinstance(item, Mapping) or not isinstance(item.get("path"), str):
                raise ValueError("current snapshot git delta path malformed")
            path = safe_relative(item["path"])
            records[f"{kind}:{path}"] = json.dumps(dict(item), sort_keys=True, separators=(",", ":"))
    renames = delta.get("renames")
    if not isinstance(renames, list):
        raise ValueError("current snapshot rename delta malformed")
    for item in renames:
        if not isinstance(item, Mapping) or not isinstance(item.get("from_path"), str) or not isinstance(item.get("to_path"), str):
            raise ValueError("current snapshot rename path malformed")
        before = safe_relative(item["from_path"])
        after = safe_relative(item["to_path"])
        encoded = json.dumps(dict(item), sort_keys=True, separators=(",", ":"))
        records[f"rename-from:{before}"] = encoded
        records[f"rename-to:{after}"] = encoded
    return records


def _q4_changed_paths(before_snapshot: Mapping[str, Any], after_snapshot: Mapping[str, Any]) -> list[str]:
    before = _git_delta_records(before_snapshot)
    after = _git_delta_records(after_snapshot)
    changed_keys = {key for key in set(before) | set(after) if before.get(key) != after.get(key)}
    paths: set[str] = set()
    for key in changed_keys:
        _kind, path = key.split(":", 1)
        paths.add(path)
    return sorted(paths)


def _matches_declared(path: str, declared: Sequence[str]) -> bool:
    for raw in declared:
        root = safe_relative(str(raw)).rstrip("/")
        if path == root or path.startswith(root + "/"):
            return True
    return False


def begin_q4(*, workspace: Path, snapshot_roots: Sequence[Mapping[str, str]], source_commit: str, red_stage_result: Mapping[str, Any], base_commit: str | None = None) -> dict[str, Any]:
    validate_expected_red(red_stage_result)
    snapshot = current_snapshot(workspace, snapshot_roots, source_commit=source_commit, base_commit=base_commit)
    return {
        "schema": "quick-dev.q4-before.v1",
        "predecessor_red_sha256": sha256_value(dict(red_stage_result)),
        "current_snapshot": snapshot,
        "authorizes": [],
    }


def finish_q4(*, workspace: Path, snapshot_roots: Sequence[Mapping[str, str]], source_commit: str, before: Mapping[str, Any], red_stage_result: Mapping[str, Any], changed_paths: Sequence[str], slice_item: Mapping[str, Any], base_commit: str | None = None) -> dict[str, Any]:
    validate_expected_red(red_stage_result)
    if before.get("schema") != "quick-dev.q4-before.v1" or before.get("predecessor_red_sha256") != sha256_value(dict(red_stage_result)):
        raise ValueError("Q4 before snapshot is not bound to RED predecessor")
    prior = before.get("current_snapshot")
    if not isinstance(prior, Mapping) or prior.get("schema") != "current-snapshot-resolver.v1":
        raise ValueError("Q4 before snapshot invalid")
    after = current_snapshot(workspace, snapshot_roots, source_commit=source_commit, base_commit=base_commit)
    actual_changed = _q4_changed_paths(prior, after)
    declared_changed = sorted({safe_relative(path) for path in changed_paths})
    if declared_changed and declared_changed != actual_changed:
        raise ValueError("Q4 caller changed-path claim does not match resolver-derived Git delta")
    validate_write_delta(actual_changed, slice_item.get("allowed_write_paths", []))
    snapshots = [str(path) for path in slice_item.get("execution_snapshot_paths", []) if isinstance(path, str)]
    if any(_matches_declared(path, snapshots) for path in actual_changed):
        raise ValueError("Q4 changed selector/fixture contract and invalidated RED")
    return {
        "schema": "quick-dev.q4-result.v1",
        "status": "implementation-successor",
        "predecessor_red_sha256": sha256_value(dict(red_stage_result)),
        "before_snapshot_sha256": prior.get("sha256"),
        "after_snapshot_sha256": after.get("sha256"),
        "changed_paths": actual_changed,
        "changed_paths_source": "current-snapshot-git-delta",
        "authorizes": [],
    }


def q6_refactor_gate(*, green_stage_result: Mapping[str, Any], green_descriptor: Mapping[str, Any], refactor_descriptor: Mapping[str, Any], changed_paths: Sequence[str], slice_item: Mapping[str, Any], profile: str, regression_results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if green_stage_result.get("stage") != "green" or green_stage_result.get("predicate_result") is not True or green_stage_result.get("verification_outcome") != "pass":
        raise ValueError("Q6 requires current observed GREEN")
    validate_descriptor(green_descriptor)
    validate_descriptor(refactor_descriptor)
    if selector_identity_from_descriptor(green_descriptor) != selector_identity_from_descriptor(refactor_descriptor):
        raise ValueError("Q6 selector drift")
    validate_write_delta(changed_paths, slice_item.get("allowed_write_paths", []))
    policy = profile_contract(profile)
    if policy.get("regression_required") is True:
        if not regression_results:
            raise ValueError("Q6 standard/self-hosted profile requires regression evidence")
        for result in regression_results:
            if not isinstance(result, Mapping) or result.get("status") != "pass" or result.get("predicate_result") is not True:
                raise ValueError("Q6 regression/schema validator failed")
    return {
        "schema": "quick-dev.q6-gate.v1",
        "status": "refactor-authorized",
        "green_predecessor_sha256": sha256_value(dict(green_stage_result)),
        "selector_identity": selector_identity_from_descriptor(green_descriptor),
        "changed_paths": list(changed_paths),
        "profile": profile,
        "regression_count": len(regression_results),
        "authorizes": [],
    }
