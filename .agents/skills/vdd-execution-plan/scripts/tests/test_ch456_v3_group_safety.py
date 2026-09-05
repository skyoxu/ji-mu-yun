from __future__ import annotations

from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import semantic_feasibility_patch  # noqa: F401  # installs the stable patch chain
import semantic_worker_v3_group_repair_patch as grouped
import semantic_worker_v3_group_safety_patch as safety
from semantic_worker_v3_execution_contract_patch import _findings


def _obligation(oid: str, subject: str) -> dict:
    return {
        "obligation_id": oid,
        "requirement_id": "FR-1",
        "source_refs": ["requirements.md#FR-1"],
        "subject": subject,
        "status": "active",
    }


def _hint(*, owners: list[str], rollback_paths: list[str], allowed: list[str] | None = None) -> dict:
    return {
        "obligation_ids": ["O-1"],
        "production_owners": owners,
        "verification_lane": "unit",
        "behavior_change": "implement behavior",
        "affected_subjects": ["ledger"],
        "state_transition": "before->after",
        "rollback_scope": {
            "production_paths": rollback_paths,
            "state_or_schema_compatibility": "backward-compatible",
        },
        "allowed_write_paths": list(allowed or []),
        "execution_snapshot_paths": ["tests/test_owner.py"],
        "planned_new_files": ["tests/test_owner.py"],
        "terminal_predicate": "bound assertion passes",
        "forbidden_paths": [],
        "validation_commands": [[sys.executable, "-m", "pytest", "tests/test_owner.py", "-q"]],
    }


def test_group_schema_stays_on_required_frozen_keys_for_codex_transport() -> None:
    payload = {
        "input": {
            "obligations": [
                _obligation("O-1", "ledger"),
                _obligation("O-2", "audit"),
                _obligation("O-3", "ledger"),
            ]
        }
    }
    schema = grouped._group_schema(payload)
    assignments = schema["properties"]["obligation_contracts"]
    assert "oneOf" not in str(schema)
    assert set(schema["properties"]) == {"obligation_contracts"}
    assert set(assignments["properties"]) == {"O-1", "O-2", "O-3"}
    assert set(assignments["required"]) == {"O-1", "O-2", "O-3"}
    assert assignments["additionalProperties"] is False


def test_group_repair_rejects_cross_subject_acceptance_deterministically() -> None:
    payload = {
        "input": {
            "obligations": [
                _obligation("O-1", "ledger"),
                _obligation("O-2", "audit"),
                _obligation("O-3", "ledger"),
            ]
        }
    }
    value = {
        "acceptances": [
            {"obligation_ids": ["O-1", "O-2"]},
            {"obligation_ids": ["O-3"]},
        ],
        "failure_intents": [],
        "slice_hints": [],
    }
    with pytest.raises(ValueError, match="overbroad-subject"):
        safety._validate_subject_domains(payload, value)


def test_group_repair_accepts_same_subject_group_deterministically() -> None:
    payload = {
        "input": {
            "obligations": [
                _obligation("O-1", "ledger"),
                _obligation("O-2", "audit"),
                _obligation("O-3", "ledger"),
            ]
        }
    }
    value = {
        "acceptances": [{"obligation_ids": ["O-1", "O-3"]}],
        "failure_intents": [],
        "slice_hints": [],
    }
    safety._validate_subject_domains(payload, value)


def test_group_repair_recovers_owner_only_from_same_hint_real_rollback_production_path(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "owner.py").write_text("VALUE = 1\n", encoding="utf-8")
    value = {
        "acceptances": [],
        "failure_intents": [],
        "slice_hints": [
            _hint(owners=["missing/owner.py"], rollback_paths=["src/owner.py"])
        ],
    }
    normalized = safety._normalize_repaired_value(tmp_path, value)
    hint = normalized["slice_hints"][0]
    assert hint["production_owners"] == ["src/owner.py"]
    assert "src/owner.py" in hint["allowed_write_paths"]


def test_group_repair_does_not_guess_owner_when_rollback_scope_has_no_real_file(tmp_path: Path) -> None:
    obligations = [_obligation("O-1", "ledger")]
    value = {
        "acceptances": [],
        "failure_intents": [],
        "slice_hints": [
            _hint(owners=["missing/owner.py"], rollback_paths=["missing/rollback.py"])
        ],
    }
    normalized = safety._normalize_repaired_value(tmp_path, value)
    hint = normalized["slice_hints"][0]
    assert hint["production_owners"] == ["missing/owner.py"]
    findings = _findings(
        tmp_path,
        "v3-schema-repair",
        {"input": {"obligations": obligations}},
        {
            "acceptances": [],
            "failure_intents": [],
            "slice_hints": [hint],
        },
    )
    assert any("no-real-production-entry" in finding for finding in findings)
