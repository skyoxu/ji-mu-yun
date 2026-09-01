"""Explicit run-local recovery resolver. Never scans history."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from runtime_evidence import HASH_RE, load_json, resolve_file, sha256_value


def _hash(value: Any, label: str) -> str:
    if not isinstance(value, str) or not HASH_RE.fullmatch(value):
        raise ValueError(f"{label} must be sha256")
    return value


def recover_explicit_run(*, run_root: Path, recovery_input: Mapping[str, Any]) -> dict[str, Any]:
    if recovery_input.get("schema") != "quick-dev.recovery-input.v1":
        raise ValueError("recovery input schema invalid")
    required = {
        "slice_id", "run_id", "stage", "candidate_hash", "selector_identity",
        "receipt_ref", "receipt_sha256", "observation_ref", "observation_sha256",
        "runtime_edges", "current_snapshot_sha256",
    }
    if not required.issubset(recovery_input):
        raise ValueError("recovery input incomplete")
    if run_root.name != recovery_input["run_id"]:
        raise ValueError("recovery run root mismatch")
    stage = recovery_input["stage"]
    if stage not in {"red", "green", "refactor", "terminal"}:
        raise ValueError("recovery stage invalid")
    candidate = _hash(recovery_input["candidate_hash"], "candidate_hash")
    _hash(recovery_input["current_snapshot_sha256"], "current_snapshot_sha256")
    selector = recovery_input["selector_identity"]
    if not isinstance(selector, str) or not selector:
        raise ValueError("recovery selector identity invalid")

    receipt = load_json(resolve_file(run_root, recovery_input["receipt_ref"]))
    observation = load_json(resolve_file(run_root, recovery_input["observation_ref"]))
    if sha256_value(receipt) != _hash(recovery_input["receipt_sha256"], "receipt_sha256"):
        raise ValueError("recovery receipt hash stale")
    if sha256_value(observation) != _hash(recovery_input["observation_sha256"], "observation_sha256"):
        raise ValueError("recovery observation hash stale")
    if observation.get("receipt_sha256") != recovery_input["receipt_sha256"]:
        raise ValueError("recovery observation/receipt lineage stale")
    if receipt.get("stage") != stage or observation.get("stage") != stage:
        raise ValueError("recovery stage lineage stale")
    if receipt.get("candidate_hash") != candidate:
        raise ValueError("recovery candidate lineage stale")
    if observation.get("evidence_state") not in {"observed-run", "recovered-run"}:
        raise ValueError("recovery predecessor evidence state invalid")

    refs = recovery_input["runtime_edges"]
    if not isinstance(refs, list) or not refs:
        raise ValueError("recovery runtime edges missing")
    recovered_edges: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for index, ref in enumerate(refs):
        if not isinstance(ref, Mapping) or set(ref) != {"ref", "sha256"}:
            raise ValueError(f"recovery runtime edge ref[{index}] invalid")
        edge = load_json(resolve_file(run_root, ref["ref"]))
        if sha256_value(edge) != _hash(ref["sha256"], f"runtime edge[{index}] hash"):
            raise ValueError("recovery runtime edge hash stale")
        if edge.get("slice_id") != recovery_input["slice_id"] or edge.get("run_id") != recovery_input["run_id"] or edge.get("stage") != stage:
            raise ValueError("recovery runtime edge identity stale")
        if edge.get("candidate_hash") != candidate or edge.get("selector_identity") != selector:
            raise ValueError("recovery runtime edge candidate/selector stale")
        if edge.get("receipt_sha256") != recovery_input["receipt_sha256"] or edge.get("observation_sha256") != recovery_input["observation_sha256"]:
            raise ValueError("recovery runtime edge predecessor hash stale")
        if edge.get("predicate_result") is not True or edge.get("observed") is not True:
            raise ValueError("recovery runtime edge is not admissible observed evidence")
        key = (str(edge.get("acceptance_id")), str(edge.get("assertion_id")))
        if key in seen:
            raise ValueError("recovery runtime edge duplicate")
        seen.add(key)
        recovered_edges.append({"ref": ref["ref"], "sha256": ref["sha256"]})

    return {
        "schema": "quick-dev.recovered-run.v1",
        "evidence_state": "recovered-run",
        "source_run_id": recovery_input["run_id"],
        "slice_id": recovery_input["slice_id"],
        "stage": stage,
        "candidate_hash": candidate,
        "selector_identity": selector,
        "current_snapshot_sha256": recovery_input["current_snapshot_sha256"],
        "receipt_ref": recovery_input["receipt_ref"],
        "receipt_sha256": recovery_input["receipt_sha256"],
        "observation_ref": recovery_input["observation_ref"],
        "observation_sha256": recovery_input["observation_sha256"],
        "runtime_edges": recovered_edges,
        "verification_outcome": observation.get("verification_outcome"),
        "failure_family": observation.get("failure_family"),
        "failure_id": observation.get("failure_id"),
        "reclassified": False,
    }
