from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from contract_guards import schema_error


PROVED_ARTIFACTS = {
    ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-finalized-run-validation.v1.schema.json",
    ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-p2-dispositions.v1.schema.json",
    ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-successor-policy-decision.v1.schema.json",
    "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/artifact-proof.v1.schema.json",
    "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/artifact-proof-registry.v1.json",
    "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/candidate-lineage-manifest.v1.schema.json",
    "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/candidate-slice-effect.v1.schema.json",
    "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/candidate-supersession-proof.v1.schema.json",
    "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/review-policy-reentry.v1.json",
    "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/review-policy-reentry.v1.schema.json",
    "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/artifact_proof_guards.py",
    "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/candidate_lineage_guards.py",
}
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
    proofs = registry.get("proofs", [])
    paths = {item.get("artifact_path") for item in proofs if isinstance(item, dict)}
    findings: list[dict[str, str]] = []
    if paths != PROVED_ARTIFACTS or len(paths) != len(proofs):
        findings.append(_finding("artifact-proof-registry", "proof registry omits, duplicates, or adds an unowned repair artifact"))
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
        producer = repository_root / proof["schema_producer_authority"]["producer_path"]
        validator = repository_root / proof["independent_recomputation"]["validator_path"]
        source_paths = proof["source_of_truth_derivation"]["source_paths"]
        stale_inputs = proof["staleness_propagation"]["input_paths"]
        boundary = proof["consumer_authorization_boundary"]
        if not artifact.is_file() or authority_hashes.get(target) != _sha(artifact):
            findings.append(_finding(target, "immutable byte identity is absent or stale in authority manifest"))
        if not producer.is_file() or not validator.is_file():
            findings.append(_finding(target, "producer or independent recomputation validator is missing"))
        if any(not (repository_root / path).exists() for path in {*source_paths, *stale_inputs}):
            findings.append(_finding(target, "source-of-truth or staleness input is missing"))
        if not proof["independent_recomputation"]["rule_ids"] or not proof["recovery_supersession"]["lineage_fields"]:
            findings.append(_finding(target, "recomputation or successor lineage is empty"))
        if set(boundary["authorizes"]) & set(boundary["does_not_authorize"]) or not EXCLUSIONS.issubset(set(boundary["does_not_authorize"])):
            findings.append(_finding(target, "consumer authorization boundary overlaps or omits higher-authority exclusions"))
    return findings
