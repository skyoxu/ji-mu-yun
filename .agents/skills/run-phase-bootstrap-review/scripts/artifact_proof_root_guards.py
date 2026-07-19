from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT_PATH = ".agents/skills/run-phase-bootstrap-review/references/artifact-proof-authority-root.v1.json"
ROOT_SHA256 = "sha256:938634680e4e5b7407be923b840bcf0187fc36c4b08fa387b361d1bf47560764"
STANDARD_PATH = ".agents/skills/vdd-execution-plan/references/strict-vdd-standard.md"
STANDARD_SHA256 = "sha256:7d5a73e75a47d25d1752ce128423ff9a8e429b714439931811529603ed6b2140"
PREDECESSOR_SHA256 = "sha256:2c0c297c20fbf46daaea5eca1836c9b3e51ce9699749eae2152cafd57a6b2544"
INVALIDATES = ["artifact-proof-registry", "runtime-artifact-type-proof", "plan-repair-verified", "plan-ready"]
DOES_NOT_AUTHORIZE = ["plan-ready", "slice-ready", "bootstrap-review", "implementation-accepted", "protected-handoff", "release-ready"]
DIMENSION_RULES = {
    "schema_producer_authority": "RMAP-ARTIFACT-PROOF-PRODUCER",
    "immutable_identity": "RMAP-ARTIFACT-PROOF-IDENTITY",
    "source_of_truth_derivation": "RMAP-ARTIFACT-PROOF-DERIVATION",
    "independent_recomputation": "RMAP-ARTIFACT-PROOF-RULE",
    "staleness_propagation": "RMAP-ARTIFACT-PROOF-STALENESS",
    "recovery_supersession": "RMAP-ARTIFACT-PROOF-LINEAGE",
    "consumer_authorization_boundary": "RMAP-ARTIFACT-PROOF-CONSUMER",
}


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load_artifact_proof_root(repository_root: Path) -> tuple[dict[str, Any], str]:
    path = repository_root / ROOT_PATH
    if _sha(path) != ROOT_SHA256:
        raise ValueError("Bootstrap artifact-proof authority root hash is stale")
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema_version") != "jimuyun.artifact-proof-authority-root.v1" or document.get("root_id") != "artifact-proof-root.v1" or not isinstance(document.get("proof"), dict):
        raise ValueError("Bootstrap artifact-proof authority root envelope is invalid")
    proof = document["proof"]
    required = {"artifact_path", "artifact_kind", "proof_scope", "finding_ids", "dimension_verdicts", "schema_producer_authority", "immutable_identity", "source_of_truth_derivation", "independent_recomputation", "staleness_propagation", "recovery_supersession", "consumer_authorization_boundary"}
    if set(proof) != required:
        raise ValueError("Bootstrap artifact-proof authority root does not use the complete proof template")
    expected_verdicts = {
        dimension: {"status": "PASS", "evidence_rule_ids": [rule_id]}
        for dimension, rule_id in DIMENSION_RULES.items()
    }
    if proof.get("proof_scope") != "static-contract" or proof.get("dimension_verdicts") != expected_verdicts:
        raise ValueError("Bootstrap artifact-proof authority root verdicts are not exact executable PASS results")
    producer = proof["schema_producer_authority"]
    if producer.get("authority_path") != STANDARD_PATH or producer.get("authority_sha256") != STANDARD_SHA256 or _sha(repository_root / STANDARD_PATH) != STANDARD_SHA256:
        raise ValueError("Bootstrap artifact-proof producer authority is not pinned")
    identity = proof["immutable_identity"]
    if identity.get("authority_revision") != "sha256:4c807e0e0dd9956c1eecb355825f76789c028b80d26da280ef972d40bf22e202":
        raise ValueError("Bootstrap artifact-proof authority revision is invalid")
    derivation = proof["source_of_truth_derivation"]["rules"]
    if derivation != [{"source": ROOT_PATH, "source_sha256": None, "field": "/proof/immutable_identity/artifact_sha256", "target_field": "$bytes", "derivation": "external-hash-pin"}]:
        raise ValueError("Bootstrap artifact-proof root derivation is invalid")
    stale = proof["staleness_propagation"]
    if stale.get("invalidates") != INVALIDATES or stale.get("regeneration_command_id") != "rmap-refresh-projections" or stale.get("revalidation_command_id") != "rmap-plan-repair-validate":
        raise ValueError("Bootstrap artifact-proof staleness closure is invalid")
    recovery = proof["recovery_supersession"]
    if recovery.get("predecessor_sha256") != PREDECESSOR_SHA256 or recovery.get("lifecycle_status") != "supersedes":
        raise ValueError("Bootstrap artifact-proof predecessor is invalid")
    boundary = proof["consumer_authorization_boundary"]
    if boundary.get("authorizes") != [] or boundary.get("does_not_authorize") != DOES_NOT_AUTHORIZE:
        raise ValueError("Bootstrap artifact-proof permission lattice is not zero-authority")
    recomputation = proof["independent_recomputation"]
    for field in ("validator_path", "negative_test_path"):
        if _sha(repository_root / recomputation[field]) != recomputation[field.replace("_path", "_sha256")]:
            raise ValueError(f"Bootstrap artifact-proof {field} hash is stale")
    return proof, ROOT_SHA256
