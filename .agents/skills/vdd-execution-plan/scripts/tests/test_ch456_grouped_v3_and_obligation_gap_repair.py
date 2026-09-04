from __future__ import annotations

from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import semantic_compiler_gate as gate
import semantic_worker_v3_group_repair_patch as group_patch
import semantic_obligation_gap_repair_patch as gap_patch


def _group() -> dict:
    return {
        "obligation_ids": ["O-1"],
        "acceptance": {
            "source_refs": ["req.md#FR-1"],
            "given": "an implementation change",
            "when": "the change is made",
            "then": "the owner boundary is preserved",
            "oracle": {
                "observable": "changed paths",
                "expected": "only owner path changed",
                "forbidden": ["non-owner path changed"],
            },
            "assertion_ids": ["ASSERT-OWNER-BOUNDARY"],
        },
        "failure_intents": [
            {
                "failure_family": "artifact-integrity",
                "selector_intent": "tests/test_owner_boundary.py",
                "expected_outcome": "fail",
                "failure_id": "OWNER-BOUNDARY-GUARD",
            }
        ],
        "slice_hint": {
            "production_owners": ["src/owner.py"],
            "verification_lane": "unit",
            "behavior_change": "enforce owner-only modifications",
            "affected_subjects": ["implementation changes"],
            "state_transition": "candidate->candidate",
            "rollback_scope": {
                "production_paths": ["src/owner.py"],
                "state_or_schema_compatibility": "backward-compatible",
            },
            "allowed_write_paths": ["src/owner.py"],
            "execution_snapshot_paths": ["tests/test_owner_boundary.py"],
            "planned_new_files": ["tests/test_owner_boundary.py"],
            "terminal_predicate": "owner boundary assertion passes",
            "forbidden_paths": [],
            "validation_commands": [[sys.executable, "-m", "pytest", "tests/test_owner_boundary.py", "-q"]],
        },
    }


def _exact_output() -> dict:
    group = _group()
    group_id = group.pop("obligation_ids")[0]
    group["group_id"] = group_id
    return {
        "groups": [group],
        "obligation_group_assignments": {"O-1": group_id},
    }


def test_group_first_projection_cannot_drift_obligation_sets() -> None:
    projected = group_patch._project({"groups": [_group()]})
    assert projected["acceptances"][0]["obligation_ids"] == ["O-1"]
    assert projected["failure_intents"][0]["obligation_ids"] == ["O-1"]
    assert projected["slice_hints"][0]["obligation_ids"] == ["O-1"]


def test_injected_v3_schema_repair_projects_group_before_domain_validation(tmp_path: Path) -> None:
    payload = {
        "original_stage": "v3",
        "input": {
            "obligations": [
                {
                    "obligation_id": "O-1",
                    "source_refs": ["req.md#FR-1"],
                    "requirement_type": "Product",
                    "obligation_kind": "constraint",
                }
            ]
        },
        "validator_findings": ["v3-domain:acceptances[0]:unknown-obligation:O-UNKNOWN"],
    }
    result = group_patch.group_repair_transport(
        root=tmp_path,
        out_dir=tmp_path / "plan",
        stage="v3-schema-repair",
        payload=payload,
        prompt="Repair V3.",
        worker_cache={"v3-schema-repair": _exact_output()},
    )
    assert set(result) == {"acceptances", "failure_intents", "slice_hints"}
    assert result["acceptances"][0]["source_refs"] == ["req.md#FR-1"]


def test_proven_source_gap_gets_one_bounded_obligation_addition(monkeypatch, tmp_path: Path) -> None:
    original = {
        "obligation_id": "O-1",
        "requirement_id": "FR-1",
        "source_refs": ["req.md#FR-1"],
        "subject": "owner path",
        "trigger": "during GREEN",
        "state_before": "implementation pending",
        "state_after": "implementation changed",
        "expected_behavior": "GREEN changes stay in owner file",
        "observable_result": "GREEN diff is owner-only",
        "forbidden_result": [],
        "requirement_type": "Product",
        "obligation_kind": "constraint",
        "unresolved_fragments": [],
        "status": "active",
        "depends_on": [],
    }
    added = {
        **original,
        "obligation_id": "O-2",
        "trigger": "throughout implementation",
        "expected_behavior": "all implementation changes stay in owner file",
        "observable_result": "the complete implementation diff is owner-only",
    }
    recalls = iter([
        {
            "valid": False,
            "findings": ["atomic-recall:source-gap-count:1"],
            "source_gap_claims": [
                {
                    "source_ref": "req.md#FR-1",
                    "subject": "production modification boundary",
                    "behavior": "changes stay owner-only throughout implementation",
                    "reason": "GREEN-only coverage narrows the source scope",
                }
            ],
        },
        {"valid": True, "findings": [], "source_gap_claims": []},
    ])
    monkeypatch.setattr(gap_patch, "_BASE_COMPILE_OBLIGATIONS", lambda **_kwargs: [dict(original)])
    monkeypatch.setattr(gate, "atomic_recall_alignment", lambda **_kwargs: next(recalls))
    monkeypatch.setattr(gap_patch, "_additional_obligations", lambda **_kwargs: [dict(added)])
    monkeypatch.setattr(gap_patch.sc, "guard_obligations", lambda *_args, **_kwargs: {"valid": True, "findings": []})

    result = gap_patch.compile_obligations_with_gap_repair(
        root=tmp_path,
        out_dir=tmp_path / "plan",
        source_index={"entries": [{"source_ref": "req.md#FR-1"}]},
        worker_cache=None,
    )
    assert [item["obligation_id"] for item in result] == ["O-1", "O-2"]


def test_non_gap_v4_failure_never_starts_obligation_repair(monkeypatch, tmp_path: Path) -> None:
    original = {"obligation_id": "O-1", "requirement_id": "FR-1", "status": "active"}
    monkeypatch.setattr(gap_patch, "_BASE_COMPILE_OBLIGATIONS", lambda **_kwargs: [dict(original)])
    monkeypatch.setattr(
        gate,
        "atomic_recall_alignment",
        lambda **_kwargs: {
            "valid": False,
            "findings": ["atomic-recall:invented-obligation:O-1"],
            "source_gap_claims": [],
        },
    )
    monkeypatch.setattr(
        gap_patch,
        "_additional_obligations",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("repair must not run")),
    )
    result = gap_patch.compile_obligations_with_gap_repair(
        root=tmp_path,
        out_dir=tmp_path / "plan",
        source_index={"entries": []},
        worker_cache=None,
    )
    assert result == [original]
