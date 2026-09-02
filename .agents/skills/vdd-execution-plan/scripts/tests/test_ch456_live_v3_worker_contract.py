from __future__ import annotations

from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import semantic_compiler_gate as gate
import semantic_feasibility_patch  # noqa: F401  # installs stable worker contract transitively
from semantic_worker_contract_patch import _augment_prompt


def _v3_payload(family: str) -> dict:
    return {
        "acceptances": [
            {
                "obligation_ids": ["O-1"],
                "source_refs": ["req.md#FR-1"],
                "given": "a duplicate claim",
                "when": "the claim is evaluated",
                "then": "duplicate is returned",
                "oracle": {
                    "observable": "claim result",
                    "expected": "duplicate",
                    "forbidden": ["accepted"],
                },
                "assertion_ids": ["ASSERT-DUPLICATE"],
            }
        ],
        "failure_intents": [
            {
                "obligation_ids": ["O-1"],
                "failure_family": family,
                "selector_intent": "tests/test_ledger.py",
                "expected_outcome": "fail",
                "failure_id": "DUPLICATE-RED",
            }
        ],
        "slice_hints": [
            {
                "obligation_ids": ["O-1"],
                "production_owners": ["src/ledger.py"],
                "verification_lane": "unit",
                "behavior_change": "reject duplicate claims",
                "affected_subjects": ["ledger"],
                "state_transition": "active->active",
                "rollback_scope": {
                    "production_paths": ["src/ledger.py"],
                    "state_or_schema_compatibility": "backward-compatible",
                },
                "allowed_write_paths": ["src/ledger.py"],
                "execution_snapshot_paths": ["tests/test_ledger.py"],
                "planned_new_files": ["tests/test_ledger.py"],
                "terminal_predicate": "all assertions pass",
                "forbidden_paths": [],
                "validation_commands": [[sys.executable, "-m", "pytest", "tests/test_ledger.py", "-q"]],
            }
        ],
    }


def test_invalid_failure_family_is_caught_at_worker_boundary() -> None:
    findings = gate._worker_schema_findings("v3", _v3_payload("assertion-failure"))
    assert any("failure_family:invalid" in item for item in findings)
    assert any("expected-red" in item for item in findings)


def test_valid_failure_family_passes_v3_shape_contract() -> None:
    findings = gate._worker_schema_findings("v3", _v3_payload("expected-red"))
    assert findings == []


def test_invalid_v3_family_routes_through_single_repair(tmp_path: Path) -> None:
    invalid = _v3_payload("assertion-failure")
    repaired = _v3_payload("expected-red")
    worker_cache = {
        "v3": invalid,
        "v3-schema-repair": repaired,
    }
    result = gate.normative_invoke_worker(
        root=tmp_path,
        out_dir=tmp_path / "plan",
        stage="v3",
        payload={"obligations": [{"obligation_id": "O-1"}]},
        prompt="Compile observable Acceptance contracts.",
        worker_cache=worker_cache,
    )
    assert result == repaired


def test_v3_prompt_enumerates_failure_taxonomy() -> None:
    prompt = _augment_prompt("v3", "Compile Acceptance contracts.")
    assert "STRICT V3 JSON CONTRACT" in prompt
    assert "expected-red" in prompt
    assert "semantic-contract-gap" in prompt
    assert "Do not invent new failure-family names" in prompt


def test_v1_prompt_makes_array_contract_explicit() -> None:
    prompt = _augment_prompt("v1-FR-1", "Extract obligations.")
    assert "depends_on=[]" in prompt
    assert "unresolved_fragments MUST be []" in prompt
    assert "Never use null" in prompt
