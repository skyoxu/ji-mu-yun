from __future__ import annotations

import json
from pathlib import Path
import sys

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import stable_runner
from runtime_evidence import create_json, sha256_value


def _bundle() -> dict:
    return {
        "schema_version": "vdd.semantic-plan-bundle.v1",
        "plan_id": "PLAN-CLI",
        "acceptances": [{
            "acceptance_id": "A-CLI",
            "assertion_ids": ["ASSERT-CLI"],
            "complexity_class": "simple",
            "verification_lane": "unit",
            "context_lookup_required": False,
            "context_lookup_reason": "single owner",
            "minimum_red_scope": "one bound Acceptance group",
            "upgrade_conditions": ["multiple roots"],
        }],
        "failure_intents": [{"failure_intent_id": "FI-CLI", "failure_id": "CLI-RED"}],
        "slices": [{
            "slice_id": "S1",
            "acceptance_ids": ["A-CLI"],
            "failure_intent_ids": ["FI-CLI"],
            "production_owners": ["src/value.py"],
            "planned_new_files": [],
            "allowed_write_paths": ["src/value.py"],
            "execution_snapshot_paths": ["tests/test_value.py", "tests/fixture.txt"],
            "terminal_predicate": "all active Acceptance assertions pass",
            "complexity_class": "simple",
            "verification_lane": "unit",
            "context_lookup_required": False,
            "context_lookup_reason": "single owner",
            "minimum_red_scope": "one bound Acceptance group",
            "upgrade_conditions": ["multiple roots"],
        }],
    }


def _repo(tmp_path: Path) -> tuple[Path, Path, list[dict[str, str]]]:
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "plan").mkdir()
    (tmp_path / "src" / "value.py").write_text("VALUE=0\n", encoding="utf-8")
    (tmp_path / "tests" / "test_value.py").write_text("def test_value():\n    assert True\n", encoding="utf-8")
    (tmp_path / "tests" / "fixture.txt").write_text("fixture\n", encoding="utf-8")
    (tmp_path / "requirements.md").write_text("# FR-1\nvalue\n", encoding="utf-8")
    (tmp_path / "plan" / "contract.txt").write_text("contract\n", encoding="utf-8")
    (tmp_path / "descriptor-root.txt").write_text("planned-only\n", encoding="utf-8")
    (tmp_path / "validators.txt").write_text("validator\n", encoding="utf-8")
    (tmp_path / "state.json").write_text("{}\n", encoding="utf-8")
    semantic = tmp_path / "plan" / "semantic-plan-bundle.v1.json"
    semantic.write_text(json.dumps(_bundle()), encoding="utf-8")
    roots = [
        {"root_kind": "candidate_tree", "repository_relative_posix_path": "src", "inclusion_reason": "candidate"},
        {"root_kind": "plan", "repository_relative_posix_path": "plan/semantic-plan-bundle.v1.json", "inclusion_reason": "plan"},
        {"root_kind": "contract", "repository_relative_posix_path": "plan/contract.txt", "inclusion_reason": "contract"},
        {"root_kind": "descriptor", "repository_relative_posix_path": "descriptor-root.txt", "inclusion_reason": "descriptor state"},
        {"root_kind": "fixture", "repository_relative_posix_path": "tests/fixture.txt", "inclusion_reason": "fixture"},
        {"root_kind": "source", "repository_relative_posix_path": "requirements.md", "inclusion_reason": "source"},
        {"root_kind": "validator_judge", "repository_relative_posix_path": "validators.txt", "inclusion_reason": "validator"},
        {"root_kind": "plan_state_transition", "repository_relative_posix_path": "state.json", "inclusion_reason": "state"},
    ]
    return tmp_path, semantic, roots


def test_candidate_identity_changes_only_with_slice_product_execution_bytes(tmp_path: Path) -> None:
    root, _semantic, _roots = _repo(tmp_path)
    bundle = _bundle()
    first = stable_runner.candidate_identity(root, bundle, "S1")
    (root / "notes.txt").write_text("governance note\n", encoding="utf-8")
    second = stable_runner.candidate_identity(root, bundle, "S1")
    assert first["candidate_hash"] == second["candidate_hash"]
    (root / "src" / "value.py").write_text("VALUE=1\n", encoding="utf-8")
    third = stable_runner.candidate_identity(root, bundle, "S1")
    assert third["candidate_hash"] != first["candidate_hash"]


def test_default_preflight_and_recommendation_only_are_distinct(tmp_path: Path, monkeypatch) -> None:
    root, semantic, roots = _repo(tmp_path)
    monkeypatch.setattr(stable_runner, "ROOT", root)
    pre = stable_runner.q1_preflight(semantic=semantic, slice_id="S1", profile="standard")
    assert pre["status"] == "preflight-passed"
    assert pre["candidate_identity"]["candidate_hash"].startswith("sha256:")
    rec = stable_runner.q0_recommendation(
        semantic=semantic,
        slice_id="S1",
        profile="standard",
        state_path=None,
        changed_paths=[],
        change_kinds=[],
        snapshot_roots=roots,
        source_commit="TEST",
        base_commit=None,
        observation_index=[],
    )
    assert rec["recommended_action"] == "run-preflight"
    assert rec["current_snapshot_sha256"].startswith("sha256:")
    assert rec["candidate_identity"]["candidate_hash"].startswith("sha256:")
    assert rec["model_called"] is False and rec["tests_executed"] is False and rec["writes_performed"] is False


def test_recommendation_fails_closed_without_snapshot_inputs(tmp_path: Path, monkeypatch) -> None:
    root, semantic, _roots = _repo(tmp_path)
    monkeypatch.setattr(stable_runner, "ROOT", root)
    rec = stable_runner.q0_recommendation(
        semantic=semantic,
        slice_id="S1",
        profile="standard",
        state_path=None,
        changed_paths=[],
        change_kinds=[],
        snapshot_roots=None,
        source_commit=None,
        base_commit=None,
        observation_index=[],
    )
    assert rec["recommended_action"] == "repair-vdd"
    assert rec["reason_code"] == "current-snapshot-input-missing"


def test_implementation_handoff_requires_clean_expected_red_and_binds_before_snapshot(tmp_path: Path, monkeypatch) -> None:
    from test_coverage_predicates import prepare
    from current_router import materialize_descriptor
    from stage_pipeline import execute_stage
    semantic, roots = prepare(tmp_path)
    root = tmp_path
    monkeypatch.setattr(stable_runner, "ROOT", root)
    run = root / "RUN-1"
    descriptor = materialize_descriptor(
        bundle=json.loads(semantic.read_text()), slice_id="S1", stage="red", run_id="RUN-1",
        candidate_hash="sha256:" + "1" * 64,
        argv=[sys.executable, "-m", "pytest", "tests/test_one.py", "-q"], cwd=".",
        timeout_seconds=30, target_refs=["tests/test_one.py"], fixture_refs=["fixture.txt"])
    create_json(run / "descriptors/red.json", descriptor)
    red = execute_stage(workspace=root, semantic_plan=semantic, run_dir=run,
                        descriptor_path=run / "descriptors/red.json", profile_identity="standard")
    handoff = stable_runner.q4_handoff(
        semantic=semantic,
        slice_id="S1",
        run_dir=run,
        snapshot_roots=roots,
        source_commit="TEST",
        base_commit=None,
    )
    assert handoff["status"] == "implementation-worker-required"
    assert handoff["predecessor_red_sha256"] == sha256_value(red)
    assert handoff["allowed_production_paths"] == ["candidate.txt"]
    assert handoff["before"]["current_snapshot"]["sha256"].startswith("sha256:")
    assert handoff["authorizes_evidence"] is False and handoff["authorizes"] == []
    red["failure_family"] = "unexpected-green"
    (run / "canonical-evidence" / "red" / "stage-result.v2.json").write_text(json.dumps(red), encoding="utf-8")
    try:
        stable_runner.q4_handoff(
            semantic=semantic,
            slice_id="S1",
            run_dir=run,
            snapshot_roots=roots,
            source_commit="TEST",
            base_commit=None,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Q4 handoff must reject non-expected RED")
