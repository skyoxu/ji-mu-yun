from __future__ import annotations

from typing import Any


DIMENSION_RULES = {
    "schema_producer_authority": "RMAP-ARTIFACT-PROOF-PRODUCER",
    "immutable_identity": "RMAP-ARTIFACT-PROOF-IDENTITY",
    "source_of_truth_derivation": "RMAP-ARTIFACT-PROOF-DERIVATION",
    "independent_recomputation": "RMAP-ARTIFACT-PROOF-RULE",
    "staleness_propagation": "RMAP-ARTIFACT-PROOF-STALENESS",
    "recovery_supersession": "RMAP-ARTIFACT-PROOF-LINEAGE",
    "consumer_authorization_boundary": "RMAP-ARTIFACT-PROOF-CONSUMER",
}


def pass_dimension_verdicts() -> dict[str, dict[str, Any]]:
    return {
        dimension: {"status": "PASS", "evidence_rule_ids": [rule_id]}
        for dimension, rule_id in DIMENSION_RULES.items()
    }


def verdict_findings(
    proof: dict[str, Any],
    target: str,
    *,
    allowed_na_dimensions: set[str] | None = None,
) -> list[dict[str, str]]:
    allowed = allowed_na_dimensions or set()
    verdicts = proof.get("dimension_verdicts")
    if not isinstance(verdicts, dict) or set(verdicts) != set(DIMENSION_RULES):
        return [{"rule_id": "RMAP-ARTIFACT-PROOF-APPLICABILITY", "target": target, "message": "all seven dimension verdicts are required"}]
    for dimension, rule_id in DIMENSION_RULES.items():
        verdict = verdicts[dimension]
        status = verdict.get("status") if isinstance(verdict, dict) else None
        if status == "PASS" and verdict == {"status": "PASS", "evidence_rule_ids": [rule_id]}:
            continue
        if status == "N/A" and dimension in allowed and set(verdict) == {"status", "reason_code", "reason"} and verdict.get("reason_code") and verdict.get("reason"):
            continue
        return [{"rule_id": "RMAP-ARTIFACT-PROOF-APPLICABILITY", "target": target, "message": f"{dimension} verdict is not an executable PASS or type-authorized N/A"}]
    return []
