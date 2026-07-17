from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from contract_guards import schema_error


EXCLUSIONS = {"protected-handoff", "release-ready"}


def _finding(target: str, message: str) -> dict[str, str]:
    return {"rule_id": "RMAP-ARTIFACT-PROOF", "target": target, "message": message}


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def validate_artifact_proofs(plan_root: Path, registry: dict[str, Any], authority: dict[str, Any]) -> list[dict[str, str]]:
    repository_root = plan_root.parents[1]
    if registry.get("schema_version") != "jimuyun.artifact-proof-registry.v1" or registry.get("plan_id") != "repository-maintenance-tdd-adapter" or registry.get("proof_schema") != "schemas/artifact-proof.v1.schema.json":
        return [_finding("artifact-proof-registry", "registry identity or proof schema owner is invalid")]
    schema = json.loads((plan_root / registry["proof_schema"]).read_text(encoding="utf-8"))
    inventory = json.loads((plan_root / "schemas" / "artifact-proof-required.v1.json").read_text(encoding="utf-8"))
    runtime = json.loads((plan_root / "schemas" / "runtime-artifact-type-proof.v1.json").read_text(encoding="utf-8"))
    proofs = registry.get("proofs", [])
    paths = {item.get("artifact_path") for item in proofs if isinstance(item, dict)}
    findings: list[dict[str, str]] = []
    required_paths = set(inventory.get("contract_artifacts", []))
    if paths != required_paths or len(paths) != len(proofs):
        findings.append(_finding("artifact-proof-registry", "proof registry differs from the independent required inventory"))
    authority_hashes = {
        item.get("path"): item.get("sha256")
        for entries in authority.get("categories", {}).values()
        for item in entries if isinstance(item, dict)
    }
    for proof in proofs:
        target = str(proof.get("artifact_path"))
        error = schema_error(proof, schema)
        if error:
            findings.append(_finding(target, error)); continue
        artifact = repository_root / target
        producer_path = proof["schema_producer_authority"]["producer_path"]
        validator_path = proof["independent_recomputation"]["validator_path"]
        producer = repository_root / producer_path
        validator = repository_root / validator_path
        boundary = proof["consumer_authorization_boundary"]
        if not artifact.is_file() or authority_hashes.get(target) != _sha(artifact):
            findings.append(_finding(target, "immutable byte identity is absent or stale in authority manifest"))
        if not producer.is_file() or not validator.is_file() or authority_hashes.get(producer_path) != _sha(producer) or authority_hashes.get(validator_path) != _sha(validator):
            findings.append(_finding(target, "producer or validator lacks current hash-bound authority"))
        source_paths = proof["source_of_truth_derivation"]["source_paths"]
        stale_inputs = proof["staleness_propagation"]["input_paths"]
        if any(not (repository_root / path).exists() for path in {*source_paths, *stale_inputs}):
            findings.append(_finding(target, "source-of-truth or staleness input is missing"))
        if not proof["independent_recomputation"]["rule_ids"] or not proof["recovery_supersession"]["lineage_fields"]:
            findings.append(_finding(target, "recomputation or successor lineage is empty"))
        if boundary.get("predicate") != "artifact-contract-proof" or boundary.get("authorizes") != []:
            findings.append(_finding(target, "static contract artifacts cannot authorize runtime transitions"))
        if set(boundary["authorizes"]) & set(boundary["does_not_authorize"]) or not EXCLUSIONS.issubset(set(boundary["does_not_authorize"])):
            findings.append(_finding(target, "consumer authorization boundary overlaps or omits higher-authority exclusions"))

    registered_consumers = set(inventory.get("registered_consumers", []))
    predicate_authority = inventory.get("predicate_authority", {})
    registered_rules = inventory.get("registered_rules", {})
    runtime_proofs = runtime.get("proofs", [])
    if {item.get("type_id") for item in runtime_proofs} != set(inventory.get("runtime_types", [])) or len(runtime_proofs) != len(inventory.get("runtime_types", [])):
        findings.append(_finding("runtime-artifact-type-proof", "runtime type proof set differs from the independent required inventory"))
    for proof in runtime_proofs:
        target = str(proof.get("type_id"))
        boundary = proof.get("consumer_authorization_boundary", {})
        expected = predicate_authority.get(boundary.get("predicate"))
        if set(boundary.get("consumers", [])) - registered_consumers:
            findings.append(_finding(target, "runtime consumer is not registered"))
        if expected is None or boundary.get("authorizes") != expected.get("authorizes") or boundary.get("does_not_authorize") != expected.get("does_not_authorize"):
            findings.append(_finding(target, "runtime predicate authority differs from the exact permission lattice"))
        if set(boundary.get("authorizes", [])) & set(boundary.get("does_not_authorize", [])) or not EXCLUSIONS.issubset(set(boundary.get("does_not_authorize", []))):
            findings.append(_finding(target, "runtime permission boundary overlaps or escalates to handoff/release"))
        recomputation = proof.get("independent_recomputation", {})
        for rule_id in recomputation.get("rule_ids", []):
            registration = registered_rules.get(rule_id, {})
            negative = repository_root / str(registration.get("negative_test", ""))
            validator = repository_root / str(recomputation.get("validator", ""))
            if registration.get("validator") != recomputation.get("validator") or not validator.is_file() or not negative.is_file():
                findings.append(_finding(target, f"runtime rule {rule_id} lacks a validator/negative-test registration"))
        if not proof.get("immutable_identity_fields") or not proof.get("source_of_truth_derivation") or not proof.get("staleness_propagation") or not proof.get("recovery_supersession"):
            findings.append(_finding(target, "runtime type omits a required proof dimension"))
    if runtime.get("authorizes") != [] or inventory.get("authorizes") != []:
        findings.append(_finding("artifact-proof-inventory", "proof metadata cannot authorize transitions"))
    return findings
