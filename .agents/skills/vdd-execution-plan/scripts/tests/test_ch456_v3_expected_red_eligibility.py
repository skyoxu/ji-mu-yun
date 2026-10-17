from __future__ import annotations

from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import semantic_feasibility_patch  # noqa: F401
import semantic_worker_v3_domain_patch as domain
import semantic_worker_v3_expected_red_eligibility_patch as eligibility


def _obligation(
    oid: str,
    *,
    kind: str,
    requirement_type: str = "Product",
) -> dict:
    return {
        "obligation_id": oid,
        "requirement_id": "FR-301",
        "source_refs": ["requirements.md#FR-301"],
        "subject": "idempotency ledger" if kind != "constraint" else "RED construction",
        "trigger": "the selector exercises the declared contract",
        "state_before": "production behavior is missing",
        "state_after": "the declared contract is observable",
        "expected_behavior": f"preserve {oid}",
        "observable_result": f"observable {oid}",
        "forbidden_result": [],
        "requirement_type": requirement_type,
        "obligation_kind": kind,
        "unresolved_fragments": [],
        "status": "active",
        "depends_on": [],
    }


def _failure(oid: str, family: str, failure_id: str) -> dict:
    return {
        "obligation_ids": [oid],
        "failure_family": family,
        "selector_intent": "tests/test_idempotency_ledger.py",
        "expected_outcome": "fail",
        "failure_id": failure_id,
    }


def test_expected_red_accepts_runtime_behavior_and_quality_obligations() -> None:
    payload = {
        "obligations": [
            _obligation("O-BEHAVIOR", kind="behavior"),
            _obligation("O-QUALITY", kind="quality"),
        ]
    }
    value = {
        "failure_intents": [
            _failure("O-BEHAVIOR", "expected-red", "FAILURE-BEHAVIOR"),
            _failure("O-QUALITY", "expected-red", "FAILURE-QUALITY"),
        ]
    }

    assert eligibility._expected_red_eligibility_findings("v3", payload, value) == []
    assert domain._domain_findings("v3", payload, value) == []


def test_expected_red_rejects_constraint_but_ignores_governance() -> None:
    payload = {
        "obligations": [
            _obligation("O-GUARD", kind="constraint"),
            _obligation("O-GOVERNANCE", kind="behavior", requirement_type="Governance"),
        ]
    }
    value = {
        "failure_intents": [
            _failure("O-GUARD", "expected-red", "FAILURE-RED-GUARD"),
            _failure("O-GOVERNANCE", "expected-red", "FAILURE-GOVERNANCE"),
        ]
    }

    assert eligibility._expected_red_eligibility_findings("v3", payload, value) == [
        "v3-expected-red:failure_intents[0]:runtime-marker-ineligible:"
        "O-GUARD=constraint/Product"
    ]


def test_non_expected_guard_is_preserved_without_entering_runtime_marker_role() -> None:
    payload = {
        "obligations": [
            _obligation("O-BEHAVIOR", kind="behavior"),
            _obligation("O-GUARD", kind="constraint"),
        ]
    }
    failures = [
        _failure("O-BEHAVIOR", "expected-red", "FAILURE-BEHAVIOR"),
        _failure("O-GUARD", "semantic-contract-gap", "FAILURE-RED-GUARD"),
    ]
    value = {"failure_intents": failures}

    assert domain._domain_findings("v3", payload, value) == []
    assert value["failure_intents"] == failures


def test_schema_repair_uses_nested_frozen_obligation_domain() -> None:
    payload = {
        "original_stage": "v3",
        "input": {
            "obligations": [
                _obligation("O-BEHAVIOR", kind="behavior"),
                _obligation("O-GUARD", kind="constraint"),
            ]
        },
        "validator_findings": ["prior output invalid"],
    }
    invalid = {
        "failure_intents": [
            _failure("O-BEHAVIOR", "expected-red", "FAILURE-BEHAVIOR"),
            _failure("O-GUARD", "expected-red", "FAILURE-RED-GUARD"),
        ]
    }
    repaired = {
        "failure_intents": [
            _failure("O-BEHAVIOR", "expected-red", "FAILURE-BEHAVIOR"),
            _failure("O-GUARD", "artifact-integrity", "FAILURE-RED-GUARD"),
        ]
    }

    findings = domain._domain_findings("v3-schema-repair", payload, invalid)
    assert findings == [
        "v3-expected-red:failure_intents[1]:runtime-marker-ineligible:"
        "O-GUARD=constraint/Product"
    ]
    assert domain._domain_findings("v3-schema-repair", payload, repaired) == []
