"""Normative registry for the nine independent false-green mutations."""
from __future__ import annotations

FIXTURE_REGISTRY = {
    "FG-01": {"category": "semantic-manifest-drift", "failure_id": "VDD-SEMANTIC-MANIFEST-INCOMPLETE", "validator": "semantic", "mutation": "case_producer_ref", "source_ref": "FR-2"},
    "FG-02": {"category": "descriptor-shell-drift", "failure_id": "QD-DESCRIPTOR-RED", "validator": "descriptor", "mutation": "shell", "source_ref": "FR-4"},
    "FG-03": {"category": "descriptor-source-drift", "failure_id": "QD-DESCRIPTOR-RED", "validator": "descriptor", "mutation": "case_source_refs", "source_ref": "FR-4"},
    "FG-04": {"category": "judge-identity-drift", "failure_id": "JUDGE-INDEPENDENCE-RED", "validator": "judge", "mutation": "judge_id", "source_ref": "FR-11"},
    "FG-05": {"category": "judge-exit-drift", "failure_id": "JUDGE-INDEPENDENCE-UNPROVEN", "validator": "judge", "mutation": "exit_code", "source_ref": "FR-11"},
    "FG-06": {"category": "coverage-edge-missing", "failure_id": "COVERAGE-EXACT-COVER-RED", "validator": "coverage", "mutation": "edge_set", "source_ref": "FR-13"},
    "FG-07": {"category": "coverage-observation-drift", "failure_id": "COVERAGE-EXACT-COVER-RED", "validator": "coverage", "mutation": "observation_id", "source_ref": "FR-13"},
    "FG-08": {"category": "predecessor-binding-drift", "failure_id": "PROMOTION-FALSE-GREEN-RED", "validator": "promotion", "mutation": "predecessor_judge_hash", "source_ref": "FR-8"},
    "FG-09": {"category": "lineage-closure-drift", "failure_id": "PROMOTION-FALSE-GREEN-RED", "validator": "promotion", "mutation": "fixture_lineage", "source_ref": "FR-9"},
}

assert len({item["category"] for item in FIXTURE_REGISTRY.values()}) == 9
