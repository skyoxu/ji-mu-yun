"""Deterministic Q4 implementation and Q6 refactor gates."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from current_router import profile_contract, validate_expected_red, validate_write_delta
from runtime_evidence import current_snapshot, selector_identity_from_descriptor, sha256_value, validate_descriptor


def begin_q4(*, workspace: Path, snapshot_roots: Sequence[Mapping[str, str]], source_commit: str, red_stage_result: Mapping[str, Any], base_commit: str | None = None) -> dict[str, Any]:
    validate_expected_red(red_stage_result)
    snapshot = current_snapshot(workspace, snapshot_roots, source_commit=source_commit, base_commit=base_commit)
    return {
        "schema": "quick-dev.q4-before.v1",
        "predecessor_red_sha256": sha256_value(dict(red_stage_result)),
        "current_snapshot": snapshot,
    }


def finish_q4(*, workspace: Path, snapshot_roots: Sequence[Mapping[str, str]], source_commit: str, before: Mapping[str, Any], red_stage_result: Mapping[str, Any], changed_paths: Sequence[str], slice_item: Mapping[str, Any], base_commit: str | None = None) -> dict[str, Any]:
    validate_expected_red(red_stage_result)
    if before.get("schema") != "quick-dev.q4-before.v1" or before.get("predecessor_red_sha256") != sha256_value(dict(red_stage_result)):
        raise ValueError("Q4 before snapshot is not bound to RED predecessor")
    prior = before.get("current_snapshot")
    if not isinstance(prior, Mapping) or prior.get("schema") != "current-snapshot-resolver.v1":
        raise ValueError("Q4 before snapshot invalid")
    validate_write_delta(changed_paths, slice_item.get("allowed_write_paths", []))
    snapshots = set(slice_item.get("execution_snapshot_paths", []))
    if any(path in snapshots for path in changed_paths):
        raise ValueError("Q4 changed selector/fixture contract and invalidated RED")
    after = current_snapshot(workspace, snapshot_roots, source_commit=source_commit, base_commit=base_commit)
    return {
        "schema": "quick-dev.q4-result.v1",
        "status": "implementation-successor",
        "predecessor_red_sha256": sha256_value(dict(red_stage_result)),
        "before_snapshot_sha256": prior.get("sha256"),
        "after_snapshot_sha256": after.get("sha256"),
        "changed_paths": list(changed_paths),
    }


def q6_refactor_gate(*, green_stage_result: Mapping[str, Any], green_descriptor: Mapping[str, Any], refactor_descriptor: Mapping[str, Any], changed_paths: Sequence[str], slice_item: Mapping[str, Any], profile: str, regression_results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if green_stage_result.get("stage") != "green" or green_stage_result.get("predicate_result") is not True or green_stage_result.get("verification_outcome") != "pass":
        raise ValueError("Q6 requires current observed GREEN")
    validate_descriptor(green_descriptor); validate_descriptor(refactor_descriptor)
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
    }
