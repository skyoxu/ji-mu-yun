from __future__ import annotations

from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import semantic_feasibility_patch  # noqa: F401  # installs final stable chain
import semantic_worker_v3_source_projection_patch as projection
import semantic_worker_v3_write_set_projection_patch as write_set
import semantic_worker_v3_group_safety_patch as safety


def _source_index() -> dict:
    return {
        "schema": "source-index.v1",
        "sha256": "sha256:" + "1" * 64,
        "entries": [
            {
                "requirement_id": "FR-1",
                "repository_relative_source_path": "requirements.md",
                "source_ref": "requirements.md#FR-1",
                "source_text": "Production owner: src/owner.py\nPlanned fixture: tests/fixtures/new.json",
                "source_sha256": "sha256:" + "2" * 64,
                "text_sha256": "sha256:" + "3" * 64,
                "source_order": 1,
            }
        ],
    }


def test_v3_receives_exact_v0_frozen_source_projection_without_rereading_worktree(tmp_path: Path, monkeypatch) -> None:
    frozen = _source_index()
    projection._FROZEN_SOURCE_INDEX.set(frozen)
    captured: dict = {}

    def fake_base(**kwargs):
        captured.update(kwargs)
        return {"acceptances": [], "failure_intents": [], "slice_hints": []}

    monkeypatch.setattr(projection, "_BASE_NORMATIVE_INVOKE", fake_base)
    payload = {
        "obligations": [
            {
                "obligation_id": "O-1",
                "source_refs": ["requirements.md#FR-1"],
                "subject": "owner contract",
                "status": "active",
            }
        ]
    }
    projection.normative_invoke_worker_with_source_projection(
        root=tmp_path,
        out_dir=tmp_path / "plan",
        stage="v3",
        payload=payload,
        prompt="compile",
        worker_cache=None,
    )
    enriched = captured["payload"]
    assert enriched["frozen_source_index_sha256"] == frozen["sha256"]
    assert enriched["source_contracts"] == [
        {
            "requirement_id": "FR-1",
            "source_ref": "requirements.md#FR-1",
            "repository_relative_source_path": "requirements.md",
            "source_text": frozen["entries"][0]["source_text"],
            "source_sha256": frozen["entries"][0]["source_sha256"],
            "text_sha256": frozen["entries"][0]["text_sha256"],
            "source_order": 1,
        }
    ]
    assert "FROZEN SOURCE CONTRACTS" in captured["prompt"]
    # No requirements.md file exists in tmp_path. Success therefore proves the
    # projection came from the frozen V0 value rather than a worktree reread.
    assert not (tmp_path / "requirements.md").exists()


def test_v3_projection_fails_closed_when_obligation_source_is_not_in_frozen_index(tmp_path: Path, monkeypatch) -> None:
    projection._FROZEN_SOURCE_INDEX.set(_source_index())
    monkeypatch.setattr(projection, "_BASE_NORMATIVE_INVOKE", lambda **kwargs: {})
    payload = {
        "obligations": [
            {
                "obligation_id": "O-X",
                "source_refs": ["requirements.md#FR-999"],
                "subject": "unknown",
                "status": "active",
            }
        ]
    }
    try:
        projection.normative_invoke_worker_with_source_projection(
            root=tmp_path,
            out_dir=tmp_path / "plan",
            stage="v3",
            payload=payload,
            prompt="compile",
            worker_cache=None,
        )
    except ValueError as exc:
        assert "frozen source projection is incomplete" in str(exc)
    else:
        raise AssertionError("missing frozen source ref must fail closed")


def _group_value() -> dict:
    return {
        "groups": [
            {
                "obligation_ids": ["O-1"],
                "acceptance": {
                    "source_refs": ["requirements.md#FR-1"],
                    "given": "state",
                    "when": "operation",
                    "then": "result",
                    "oracle": {"observable": "result", "expected": "ok", "forbidden": []},
                    "assertion_ids": ["ASSERT-1"],
                },
                "failure_intents": [
                    {
                        "failure_family": "expected-red",
                        "selector_intent": "tests/test_owner.py",
                        "expected_outcome": "fail",
                        "failure_id": "OWNER-RED",
                    }
                ],
                "slice_hint": {
                    "production_owners": ["src/owner.py"],
                    "verification_lane": "unit",
                    "behavior_change": "owner behavior",
                    "affected_subjects": ["owner"],
                    "state_transition": "before->after",
                    "rollback_scope": {
                        "production_paths": ["src/owner.py"],
                        "state_or_schema_compatibility": "compatible",
                    },
                    "allowed_write_paths": [],
                    "execution_snapshot_paths": ["tests/test_owner.py"],
                    "planned_new_files": ["tests/test_owner.py"],
                    "terminal_predicate": "assertion passes",
                    "forbidden_paths": ["src/owner.py", "src/unrelated.py"],
                    "validation_commands": [[sys.executable, "-m", "pytest", "tests/test_owner.py", "-q"]],
                },
            }
        ]
    }


def test_repaired_owner_becomes_writable_and_only_owner_overlap_is_removed_from_forbidden() -> None:
    result = write_set.project_with_owner_write_set(_group_value())
    hint = result["slice_hints"][0]
    assert hint["allowed_write_paths"] == ["src/owner.py"]
    assert hint["forbidden_paths"] == ["src/unrelated.py"]


def test_rollback_owner_recovery_removes_only_recovered_owner_from_forbidden(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "owner.py").write_text("VALUE = 1\n", encoding="utf-8")
    hint = {
        "production_owners": ["missing/owner.py"],
        "rollback_scope": {"production_paths": ["src/owner.py"]},
        "allowed_write_paths": [],
        "forbidden_paths": ["src/owner.py", "src/unrelated.py"],
    }
    normalized = safety._normalize_hint(tmp_path, hint)
    assert normalized["production_owners"] == ["src/owner.py"]
    assert normalized["allowed_write_paths"] == ["src/owner.py"]
    assert normalized["forbidden_paths"] == ["src/unrelated.py"]
