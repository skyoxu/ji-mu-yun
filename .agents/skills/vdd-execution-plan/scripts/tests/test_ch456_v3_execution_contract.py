from __future__ import annotations

from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import semantic_compiler_gate as gate
import semantic_feasibility_patch  # noqa: F401  # installs stable V3 repair chain
from semantic_worker_v3_execution_contract_patch import _findings


def _obligation(oid: str, *, subject: str = "ledger") -> dict:
    return {
        "obligation_id": oid,
        "requirement_id": "FR-1",
        "source_refs": ["req.md#FR-1"],
        "subject": subject,
        "trigger": "operation",
        "state_before": "before",
        "state_after": "after",
        "expected_behavior": f"behavior {oid}",
        "observable_result": f"observable {oid}",
        "forbidden_result": [],
        "requirement_type": "Product",
        "obligation_kind": "behavior",
        "unresolved_fragments": [],
        "status": "active",
        "depends_on": [],
    }


def _acceptance(ids: list[str]) -> dict:
    return {
        "obligation_ids": ids,
        "source_refs": ["req.md#FR-1"],
        "given": "ledger state",
        "when": "the operation runs",
        "then": "the required behavior is observable",
        "oracle": {"observable": "result", "expected": "required", "forbidden": ["wrong"]},
        "assertion_ids": ["ASSERT-LEDGER"],
    }


def _failure(ids: list[str]) -> dict:
    return {
        "obligation_ids": ids,
        "failure_family": "expected-red",
        "selector_intent": "tests/test_owner.py",
        "expected_outcome": "fail",
        "failure_id": "LEDGER-RED",
    }


def _hint(ids: list[str], *, allowed: list[str], planned: list[str]) -> dict:
    return {
        "obligation_ids": ids,
        "production_owners": ["src/owner.py"],
        "verification_lane": "unit",
        "behavior_change": "implement ledger behavior",
        "affected_subjects": ["ledger"],
        "state_transition": "before->after",
        "rollback_scope": {
            "production_paths": ["src/owner.py"],
            "state_or_schema_compatibility": "backward-compatible",
        },
        "allowed_write_paths": allowed,
        "execution_snapshot_paths": ["tests/test_owner.py"],
        "planned_new_files": planned,
        "terminal_predicate": "all bound assertions pass",
        "forbidden_paths": [],
        "validation_commands": [[sys.executable, "-m", "pytest", "tests/test_owner.py", "-q"]],
    }


def test_v3_contract_routes_missing_coverage_and_path_defects_through_one_grouped_repair(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "owner.py").write_text("VALUE = 1\n", encoding="utf-8")
    obligations = [_obligation("O-1"), _obligation("O-2")]
    initial = {
        "acceptances": [_acceptance(["O-1"])],
        "failure_intents": [_failure(["O-1"])],
        "slice_hints": [_hint(["O-1"], allowed=[], planned=[])],
    }
    repaired = {
        "groups": [
            {
                "obligation_ids": ["O-1", "O-2"],
                "acceptance": {key: value for key, value in _acceptance(["O-1", "O-2"]).items() if key != "obligation_ids"},
                "failure_intents": [{key: value for key, value in _failure(["O-1", "O-2"]).items() if key != "obligation_ids"}],
                "slice_hint": {key: value for key, value in _hint(["O-1", "O-2"], allowed=["src/owner.py"], planned=["tests/test_owner.py"]).items() if key != "obligation_ids"},
            }
        ]
    }
    result = gate.normative_invoke_worker(
        root=tmp_path,
        out_dir=tmp_path / "plan",
        stage="v3",
        payload={"obligations": obligations},
        prompt="Compile Acceptance, RED intent and slice hints.",
        worker_cache={"v3": initial, "v3-schema-repair": repaired},
    )
    assert result["acceptances"][0]["obligation_ids"] == ["O-1", "O-2"]
    assert result["failure_intents"][0]["obligation_ids"] == ["O-1", "O-2"]
    assert result["slice_hints"][0]["allowed_write_paths"] == ["src/owner.py"]
    assert result["slice_hints"][0]["planned_new_files"] == ["tests/test_owner.py"]


def test_v3_contract_catches_overbroad_subject_before_v3a(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "owner.py").write_text("VALUE = 1\n", encoding="utf-8")
    obligations = [_obligation("O-1", subject="ledger"), _obligation("O-2", subject="unrelated audit")]
    candidate = {
        "acceptances": [_acceptance(["O-1", "O-2"])],
        "failure_intents": [_failure(["O-1", "O-2"])],
        "slice_hints": [_hint(["O-1", "O-2"], allowed=["src/owner.py"], planned=["tests/test_owner.py"])],
    }
    findings = _findings(tmp_path, "v3", {"obligations": obligations}, candidate)
    assert any("overbroad-subject" in item for item in findings)
