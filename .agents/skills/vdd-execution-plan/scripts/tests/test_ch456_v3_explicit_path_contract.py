from __future__ import annotations

from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import semantic_feasibility_patch  # noqa: F401  # installs final stable chain
import semantic_worker_v3_explicit_path_contract_patch as path_contract
from semantic_worker_v3_execution_contract_patch import _findings


OWNER = "benchmarks/task/src/ledger.py"
RED_TEST = "benchmarks/task/tests/test_ledger.py"
FIXTURE = "benchmarks/task/tests/cases.json"
SOURCE_REF = "benchmarks/task/requirements.md#FR-301"


def _payload(source_text: str) -> dict:
    return {
        "obligations": [
            {
                "obligation_id": "O-1",
                "requirement_id": "FR-301",
                "source_refs": [SOURCE_REF],
                "subject": "duplicate claim",
                "status": "active",
            },
            {
                "obligation_id": "O-2",
                "requirement_id": "FR-301",
                "source_refs": [SOURCE_REF],
                "subject": "invalid ttl",
                "status": "active",
            },
        ],
        "source_contracts": [
            {
                "requirement_id": "FR-301",
                "source_ref": SOURCE_REF,
                "repository_relative_source_path": "benchmarks/task/requirements.md",
                "source_text": source_text,
                "source_sha256": "sha256:" + "1" * 64,
                "text_sha256": "sha256:" + "2" * 64,
                "source_order": 1,
            }
        ],
    }


def _value() -> dict:
    return {
        "acceptances": [
            {"obligation_ids": ["O-1"]},
            {"obligation_ids": ["O-2"]},
        ],
        "failure_intents": [],
        "slice_hints": [
            {
                "obligation_ids": ["O-1"],
                "production_owners": ["tests/not-production.py"],
                "allowed_write_paths": ["tests/not-production.py"],
                "forbidden_paths": [OWNER, RED_TEST, "src/unrelated.py"],
                "rollback_scope": {
                    "production_paths": ["tests/not-production.py"],
                    "state_or_schema_compatibility": "compatible",
                },
                "planned_new_files": [],
                "execution_snapshot_paths": [RED_TEST],
            },
            {
                "obligation_ids": ["O-2"],
                "production_owners": ["missing/owner.py"],
                "allowed_write_paths": [],
                "forbidden_paths": [RED_TEST],
                "rollback_scope": {
                    "production_paths": [],
                    "state_or_schema_compatibility": "compatible",
                },
                "planned_new_files": [FIXTURE],
                "execution_snapshot_paths": [RED_TEST],
            },
        ],
    }


def test_explicit_frozen_paths_override_guessed_owner_and_plan_required_red_test(tmp_path: Path) -> None:
    owner = tmp_path / OWNER
    owner.parent.mkdir(parents=True)
    owner.write_text("VALUE = 1\n", encoding="utf-8")
    fixture = tmp_path / FIXTURE
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text("{}\n", encoding="utf-8")

    source = f"""# FR-301
Production owner: `{OWNER}`.
The RED author must create `{RED_TEST}` and may use the existing fixture `{FIXTURE}`.
The production implementation may modify only the production owner above.
"""
    payload = _payload(source)
    normalized = path_contract.normalize_explicit_path_contracts(tmp_path, "v3", payload, _value())

    for hint in normalized["slice_hints"]:
        assert hint["production_owners"] == [OWNER]
        assert hint["allowed_write_paths"] == [OWNER]
        assert OWNER not in hint["forbidden_paths"]
        assert RED_TEST not in hint["forbidden_paths"]
        assert RED_TEST in hint["planned_new_files"]
        assert FIXTURE not in hint["planned_new_files"]
        assert OWNER in hint["rollback_scope"]["production_paths"]
    assert "src/unrelated.py" in normalized["slice_hints"][0]["forbidden_paths"]

    findings = _findings(tmp_path, "v3", payload, normalized)
    assert not any("no-real-production-entry" in finding for finding in findings)
    assert not any("selector-target-missing-not-planned" in finding for finding in findings)


def test_schema_repair_inherits_nested_frozen_path_contracts(tmp_path: Path) -> None:
    owner = tmp_path / OWNER
    owner.parent.mkdir(parents=True)
    owner.write_text("VALUE = 1\n", encoding="utf-8")
    source = f"Production owner: `{OWNER}`.\nThe RED author must create `{RED_TEST}`.\n"
    original = _payload(source)
    repair_payload = {
        "original_stage": "v3",
        "input": original,
        "validator_findings": ["repair"],
    }
    normalized = path_contract.normalize_explicit_path_contracts(
        tmp_path, "v3-schema-repair", repair_payload, _value()
    )
    assert all(hint["production_owners"] == [OWNER] for hint in normalized["slice_hints"])
    assert all(RED_TEST in hint["planned_new_files"] for hint in normalized["slice_hints"])


def test_unrecognized_source_prose_does_not_invent_or_replace_paths(tmp_path: Path) -> None:
    payload = _payload("Implement the ledger safely and test it thoroughly.")
    value = _value()
    normalized = path_contract.normalize_explicit_path_contracts(tmp_path, "v3", payload, value)
    assert normalized == value


@pytest.mark.parametrize("stage", ["v3", "v3-schema-repair"])
def test_frozen_production_owner_is_writable_while_red_inputs_stay_frozen(tmp_path, stage):
    # ADR-0041: reproduce the Q5 allowed/snapshot self-conflict, not a GREEN result.
    source = (f"Production owner: `{OWNER}`.\n"
              f"The RED author must create `{RED_TEST}` and use the existing fixture `{FIXTURE}`.\n"
              "The production implementation may modify only the production owner above.")
    payload = _payload(source)
    if stage != "v3":
        payload = {"input": payload}
    value = _value()
    for hint in value["slice_hints"]:
        hint["execution_snapshot_paths"] = [OWNER, RED_TEST, FIXTURE, OWNER + ".fixture"]
    normalized = path_contract.normalize_explicit_path_contracts(tmp_path, stage, payload, value)
    for hint in normalized["slice_hints"]:
        assert hint["allowed_write_paths"] == [OWNER]
        assert hint["production_owners"] == [OWNER]
        assert hint["execution_snapshot_paths"] == [RED_TEST, FIXTURE, OWNER + ".fixture"]
    assert normalized["acceptances"] == value["acceptances"]
    assert normalized["failure_intents"] == value["failure_intents"]
    assert all(OWNER in hint["execution_snapshot_paths"] for hint in value["slice_hints"])


def test_model_write_claim_alone_cannot_remove_snapshot_protection(tmp_path):
    value = _value()
    value["slice_hints"][0].update(production_owners=[OWNER], allowed_write_paths=[OWNER], execution_snapshot_paths=[OWNER, RED_TEST])
    result = path_contract.normalize_explicit_path_contracts(tmp_path, "v3", _payload(f"Production owner: `{OWNER}`."), value)
    assert result["slice_hints"][0]["execution_snapshot_paths"] == [OWNER, RED_TEST]


def test_conflicting_frozen_owner_and_fixture_roles_are_rejected(tmp_path):
    source = (f"Production owner: `{OWNER}`.\nUse the existing fixture `{OWNER}`.\n"
              "The production implementation may modify only the production owner above.")
    with pytest.raises(ValueError, match="conflicts with explicit RED artifact"):
        path_contract.normalize_explicit_path_contracts(tmp_path, "v3", _payload(source), _value())


def test_owner_only_snapshot_uses_explicit_fixture_not_invented_target(tmp_path):
    source = (f"Production owner: `{OWNER}`.\nUse the existing fixture `{FIXTURE}`.\n"
              "The production implementation may modify only the production owner above.")
    value = _value()
    value["slice_hints"][0]["execution_snapshot_paths"] = [OWNER]
    result = path_contract.normalize_explicit_path_contracts(tmp_path, "v3", _payload(source), value)
    assert result["slice_hints"][0]["execution_snapshot_paths"] == [FIXTURE]
