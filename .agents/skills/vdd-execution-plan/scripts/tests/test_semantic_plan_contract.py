from __future__ import annotations

from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from semantic_plan_contract import STAGE_SCOPE, validate_semantic_bundle


def _bundle() -> dict:
    return {
        "schema_version": "vdd.semantic-plan-bundle.v1",
        "obligations": [{
            "obligation_id": "O-ONE", "requirement_id": "FR-1",
            "source_refs": ["SPEC:FR-1"], "subject": "runner", "trigger": "execute",
            "state_before": "planned", "state_after": "verified",
            "expected_behavior": "execute real process", "observable_result": "receipt",
            "forbidden_result": ["fabricated pass"], "requirement_type": "Platform",
            "obligation_kind": "behavior", "unresolved_fragments": [], "status": "active",
            "depends_on": [],
        }],
        "acceptances": [{
            "acceptance_id": "A-ONE", "obligation_ids": ["O-ONE"], "source_refs": ["SPEC:FR-1"],
            "given": "a descriptor", "when": "executed", "then": "receipt exists",
            "oracle": {"observable": "receipt", "expected": "process-derived", "forbidden": ["fabricated"]},
            "assertion_ids": ["AS-1"], "red_intent_ids": ["FI-ONE"],
        }],
        "failure_intents": [{
            "failure_intent_id": "FI-ONE", "acceptance_ids": ["A-ONE"],
            "failure_id": "EXPECTED-RED", "failure_family": "expected-red",
            "selector_intent": "tests/test_one.py", "expected_outcome": "fail",
        }],
        "pre_slice_coverage": [{
            "requirement_id": "FR-1", "obligation_id": "O-ONE", "acceptance_id": "A-ONE",
            "source_ref": "SPEC:FR-1", "failure_intent_id": "FI-ONE",
        }],
        "slices": [{
            "slice_id": "S1", "obligation_ids": ["O-ONE"], "acceptance_ids": ["A-ONE"],
            "failure_intent_ids": ["FI-ONE"], "production_owners": ["runner"],
            "verification_lane": "unit", "behavior_change": "execute process",
            "affected_subjects": ["runner"], "state_transition": "planned->verified",
            "proof": {"acceptance_ids": ["A-ONE"], "selector_intents": ["tests/test_one.py"], "assertion_ids": ["AS-1"]},
            "rollback_scope": {"production_paths": ["runner.py"], "state_or_schema_compatibility": "none"},
            "allowed_write_paths": ["runner.py"], "execution_snapshot_paths": ["runner.py"],
            "planned_new_files": [], "terminal_predicate": "all acceptance closed",
        }],
        "final_plan_coverage": [{
            "requirement_id": "FR-1", "obligation_id": "O-ONE", "acceptance_id": "A-ONE",
            "source_ref": "SPEC:FR-1", "failure_intent_id": "FI-ONE", "slice_id": "S1",
            "verification_lane": "unit", "terminal_predicate": "all acceptance closed",
            "stage_scope": list(STAGE_SCOPE),
        }],
        "agent_contexts": [{
            "slice_id": "S1", "requirement_ids": ["FR-1"], "obligation_ids": ["O-ONE"],
            "acceptance_ids": ["A-ONE"], "source_refs": ["SPEC:FR-1"], "contracts": ["SPEC"],
            "allowed_paths": ["runner.py"], "forbidden_paths": [], "selector_intents": ["tests/test_one.py"],
            "validation_commands": [["py", "-3", "-m", "pytest", "tests/test_one.py"]],
        }],
    }


def test_valid_staged_bundle() -> None:
    valid, findings = validate_semantic_bundle(_bundle())
    assert valid is True, findings


def test_v5_rejects_future_slice_identity() -> None:
    bundle = _bundle()
    bundle["pre_slice_coverage"][0]["slice_id"] = "S1"
    valid, findings = validate_semantic_bundle(bundle)
    assert valid is False
    assert "v5-edge[0]:shape" in findings
    assert "v5-edge[0]:future-field" in findings


def test_v6a_requires_exact_ordered_stage_scope() -> None:
    bundle = _bundle()
    bundle["final_plan_coverage"][0]["stage_scope"] = ["red", "green", "terminal"]
    valid, findings = validate_semantic_bundle(bundle)
    assert valid is False
    assert "v6a-edge[0]:stage-scope" in findings


def test_vdd_rejects_runtime_evidence() -> None:
    bundle = _bundle()
    bundle["slices"][0]["run_id"] = "RUN-1"
    valid, findings = validate_semantic_bundle(bundle)
    assert valid is False
    assert "slice:S1:contains-runtime-evidence" in findings
