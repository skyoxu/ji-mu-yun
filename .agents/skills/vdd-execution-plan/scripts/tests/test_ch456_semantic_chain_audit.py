from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from semantic_chain_audit import audit_bundle


def _obligation(oid: str, rid: str, source: str, subject: str) -> dict:
    return {
        "obligation_id": oid,
        "requirement_id": rid,
        "source_refs": [source],
        "subject": subject,
        "trigger": "trigger",
        "state_before": "before",
        "state_after": "after",
        "expected_behavior": f"behavior {oid}",
        "observable_result": f"observable {oid}",
        "forbidden_result": [],
        "requirement_type": "Platform",
        "obligation_kind": "behavior",
        "unresolved_fragments": [],
        "status": "active",
        "depends_on": [],
    }


def _bundle() -> dict:
    obligations = [
        _obligation("O-UNIT", "FR-1", "SPEC:FR-1", "compiler"),
        _obligation("O-RUNTIME", "FR-2", "SPEC:FR-2", "runtime"),
    ]
    acceptances = [
        {
            "acceptance_id": "A-UNIT",
            "obligation_ids": ["O-UNIT"],
            "source_refs": ["SPEC:FR-1"],
            "assertion_ids": ["AS-UNIT"],
            "red_intent_ids": ["FI-UNIT"],
            "verification_lane": "unit",
        },
        {
            "acceptance_id": "A-RUNTIME",
            "obligation_ids": ["O-RUNTIME"],
            "source_refs": ["SPEC:FR-2"],
            "assertion_ids": ["AS-RUNTIME"],
            "red_intent_ids": ["FI-RUNTIME"],
            "verification_lane": "runtime",
        },
    ]
    failures = [
        {"failure_intent_id": "FI-UNIT", "acceptance_ids": ["A-UNIT"], "selector_intent": "tests/test_unit.py"},
        {"failure_intent_id": "FI-RUNTIME", "acceptance_ids": ["A-RUNTIME"], "selector_intent": "tests/test_runtime.py"},
    ]
    v5 = [
        {"requirement_id": "FR-1", "obligation_id": "O-UNIT", "acceptance_id": "A-UNIT", "source_ref": "SPEC:FR-1", "failure_intent_id": "FI-UNIT"},
        {"requirement_id": "FR-2", "obligation_id": "O-RUNTIME", "acceptance_id": "A-RUNTIME", "source_ref": "SPEC:FR-2", "failure_intent_id": "FI-RUNTIME"},
    ]
    slices = [
        {
            "slice_id": "S1",
            "obligation_ids": ["O-UNIT"],
            "acceptance_ids": ["A-UNIT"],
            "failure_intent_ids": ["FI-UNIT"],
            "verification_lane": "unit",
            "terminal_predicate": "all unit assertions pass",
            "proof": {"acceptance_ids": ["A-UNIT"], "assertion_ids": ["AS-UNIT"], "selector_intents": ["tests/test_unit.py"]},
        },
        {
            "slice_id": "S2",
            "obligation_ids": ["O-RUNTIME"],
            "acceptance_ids": ["A-RUNTIME"],
            "failure_intent_ids": ["FI-RUNTIME"],
            "verification_lane": "runtime",
            "terminal_predicate": "all runtime assertions pass",
            "proof": {"acceptance_ids": ["A-RUNTIME"], "assertion_ids": ["AS-RUNTIME"], "selector_intents": ["tests/test_runtime.py"]},
        },
    ]
    v6a = [
        {**v5[0], "slice_id": "S1", "verification_lane": "unit", "terminal_predicate": "all unit assertions pass", "stage_scope": ["red", "green", "refactor", "terminal"]},
        {**v5[1], "slice_id": "S2", "verification_lane": "runtime", "terminal_predicate": "all runtime assertions pass", "stage_scope": ["red", "green", "refactor", "terminal"]},
    ]
    return {
        "obligations": obligations,
        "acceptances": acceptances,
        "failure_intents": failures,
        "pre_slice_coverage": v5,
        "slices": slices,
        "final_plan_coverage": v6a,
    }


def test_exact_chain_reports_one_hundred_percent_cover() -> None:
    result = audit_bundle(_bundle())
    assert result["valid"] is True, result["findings"]
    assert result["metrics"]["obligation_chain_coverage"] == 1.0
    assert result["metrics"]["fully_chained_obligation_count"] == 2


def test_source_ref_drift_is_rejected_before_quick_dev() -> None:
    bundle = _bundle()
    bundle["acceptances"][0]["source_refs"] = ["SPEC:FR-999"]
    result = audit_bundle(bundle)
    assert result["valid"] is False
    assert "chain:acceptance:A-UNIT:source-ref-drift" in result["findings"]
    assert "chain:v5:semantic-edge-exact-cover" in result["findings"]


def test_deleted_v5_edge_breaks_obligation_chain_cover() -> None:
    bundle = _bundle()
    bundle["pre_slice_coverage"] = bundle["pre_slice_coverage"][:1]
    result = audit_bundle(bundle)
    assert result["valid"] is False
    assert "chain:v5:semantic-edge-exact-cover" in result["findings"]
    assert result["metrics"]["obligation_chain_coverage"] < 1.0


def test_terminal_swallowing_stage_scope_is_rejected() -> None:
    bundle = _bundle()
    bundle["final_plan_coverage"][0]["stage_scope"] = ["terminal"]
    result = audit_bundle(bundle)
    assert result["valid"] is False
    assert "chain:v6a:semantic-edge-exact-cover" in result["findings"]


def test_incompatible_verification_lanes_cannot_be_forced_into_one_slice() -> None:
    bundle = deepcopy(_bundle())
    first = bundle["slices"][0]
    first["obligation_ids"].append("O-RUNTIME")
    first["acceptance_ids"].append("A-RUNTIME")
    first["failure_intent_ids"].append("FI-RUNTIME")
    first["proof"]["acceptance_ids"].append("A-RUNTIME")
    first["proof"]["assertion_ids"].append("AS-RUNTIME")
    first["proof"]["selector_intents"].append("tests/test_runtime.py")
    bundle["slices"] = [first]
    bundle["final_plan_coverage"][1].update({
        "slice_id": "S1",
        "verification_lane": "unit",
        "terminal_predicate": first["terminal_predicate"],
    })
    result = audit_bundle(bundle)
    assert result["valid"] is False
    assert "chain:slice:S1:incompatible-verification-lanes" in result["findings"]
