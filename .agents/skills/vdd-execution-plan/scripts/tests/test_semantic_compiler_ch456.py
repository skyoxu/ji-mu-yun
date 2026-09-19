from __future__ import annotations

import json
from pathlib import Path
import sys
import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from semantic_compiler import (
    _normalize_obligation, _reusable_prior_v1_cache, _worker_cache_key,
    _reusable_predecessor_obligations, build_source_index,
    configure_v1_reuse_predecessor_plan,
)
from semantic_compiler_gate import compile_plan
import semantic_compiler_gate as gate


@pytest.fixture(autouse=True)
def isolate_base_gate_workers(monkeypatch):
    """ADR-0041: these gate tests observe unresolved gaps, not gap-repair policy.

    Other test modules install the optional repair extension on the shared V1
    seam during collection. Restore the base compiler for this test only, so
    standalone and full-suite runs exercise the same gate. Missing injected
    stages must fail here rather than contacting a real backend.
    """
    repair = sys.modules.get("semantic_obligation_gap_repair_patch")
    if repair is not None:
        monkeypatch.setattr(gate.sc, "compile_obligations", repair._BASE_COMPILE_OBLIGATIONS)
    original_transport = gate._ORIGINAL_INVOKE_WORKER

    def injected_only(**kwargs):
        cache = kwargs.get("worker_cache")
        stage = kwargs["stage"]
        if not isinstance(cache, dict) or stage not in cache:
            raise AssertionError(f"Base gate test requested an uninjected worker stage: {stage}")
        return original_transport(**kwargs)

    monkeypatch.setattr(gate, "_ORIGINAL_INVOKE_WORKER", injected_only)


def _repo(tmp_path: Path) -> tuple[Path, Path, str, str]:
    root = tmp_path
    (root / ".agents").mkdir(); (root / "AGENTS.md").write_text("x", encoding="utf-8")
    (root / "src").mkdir(); (root / "tests").mkdir()
    owner = "src/compiler.py"; selector = "tests/test_compile.py"
    (root / owner).write_text("VALUE = 1\n", encoding="utf-8")
    (root / selector).write_text("from src.compiler import VALUE\ndef test_compile():\n    assert VALUE == 1\n", encoding="utf-8")
    req = root / "req.md"; req.write_text("# FR-1\nThe compiler must emit a deterministic plan.\n", encoding="utf-8")
    return root, req, owner, selector


def _worker_cache(source_ref: str, owner: str, selector: str) -> dict:
    raw_obligation = {
        "source_refs": [source_ref], "subject": "compiler", "trigger": "a requirement is compiled",
        "state_before": "uncompiled", "state_after": "compiled", "expected_behavior": "emit a deterministic plan",
        "observable_result": "plan-ready semantic bundle", "forbidden_result": ["future runtime evidence"],
        "requirement_type": "Platform", "obligation_kind": "behavior", "unresolved_fragments": [],
        "status": "active", "depends_on": [],
    }
    oid = _normalize_obligation({"requirement_id":"FR-1","source_ref":source_ref}, raw_obligation)["obligation_id"]
    return {
        "v1-FR-1": {"obligations": [raw_obligation]},
        "v3": {
            "acceptances": [{"obligation_ids":[oid],"source_refs":[source_ref],"given":"a valid requirement","when":"compiled","then":"a deterministic plan is emitted","oracle":{"observable":"semantic bundle","expected":"plan-ready","forbidden":["future runtime evidence"]},"assertion_ids":["ASSERT-COMPILE"]}],
            "failure_intents": [{"obligation_ids":[oid],"failure_family":"expected-red","selector_intent":selector,"expected_outcome":"fail","failure_id":"COMPILE-RED"}],
            "slice_hints": [{"obligation_ids":[oid],"production_owners":[owner],"verification_lane":"unit","behavior_change":"compile deterministic plans","affected_subjects":["compiler"],"state_transition":"uncompiled->compiled","rollback_scope":{"production_paths":[owner],"state_or_schema_compatibility":"backward-compatible"},"allowed_write_paths":[owner],"execution_snapshot_paths":[selector],"planned_new_files":[],"terminal_predicate":"all active Acceptance assertions pass","forbidden_paths":[],"validation_commands":[[sys.executable,"-m","pytest",selector]]}]
        },
        "v4-atomic-recall": {"supported_obligation_ids":[oid],"invented_obligation_ids":[],"source_gap_claims":[]},
        "v4": {"covered_obligation_ids":[oid],"missing_obligation_ids":[],"invented_obligation_ids":[],"misaligned_acceptance_ids":[],"oracle_alignment":{},"repairs":[]}
    }


def test_pending_independent_witness_normalizes_to_active_planned_work() -> None:
    source_ref = "req.md#FR-1"
    raw = {
        "source_refs": [source_ref], "subject": "validator identity", "trigger": "fixture runs",
        "state_before": "fixture is pending", "state_after": "fixture result is recorded",
        "expected_behavior": "reject an invalid validator", "observable_result": "identity-invalid",
        "forbidden_result": ["trusted replay result"], "requirement_type": "Platform",
        "obligation_kind": "behavior", "unresolved_fragments": ["pending independent witness"],
        "status": "deferred", "depends_on": [],
    }
    normalized = _normalize_obligation({"requirement_id": "FR-1", "source_ref": source_ref}, raw)
    assert normalized["status"] == "active"
    assert normalized["unresolved_fragments"] == []


def test_full_v0_to_v7_compilation_with_injected_readonly_workers(tmp_path: Path) -> None:
    root, req, owner, selector = _repo(tmp_path)
    cache = _worker_cache("req.md#FR-1", owner, selector)
    result = compile_plan(requirements=req, out_dir=root / "plan", worker_cache=cache)
    assert result["status"] == "plan-ready"
    assert result["atomic_quality_metrics"]["precision"] == 1.0
    assert result["atomic_quality_metrics"]["recall"] == 1.0
    assert (root / "plan" / "atomic-recall-alignment.v1.json").is_file()
    assert (root / "plan" / "semantic-plan-bundle.v1.json").is_file()
    assert (root / "plan" / "agent-context" / "S1" / "agent-context.json").is_file()


def test_atomic_source_gap_blocks_plan_ready_and_reduces_recall(tmp_path: Path) -> None:
    root, req, owner, selector = _repo(tmp_path)
    req.write_text(
        "# FR-1\nThe compiler must emit a deterministic plan. It must also stop after the second identical deterministic failure fingerprint.\n",
        encoding="utf-8",
    )
    cache = _worker_cache("req.md#FR-1", owner, selector)
    oid = cache["v4-atomic-recall"]["supported_obligation_ids"][0]
    cache["v4-atomic-recall"] = {
        "supported_obligation_ids":[oid],
        "invented_obligation_ids":[],
        "source_gap_claims":[{
            "source_ref":"req.md#FR-1",
            "subject":"compiler retry loop",
            "behavior":"stop after the second identical deterministic failure fingerprint",
            "reason":"V1 obligation set only represents deterministic plan emission",
        }],
    }
    result = compile_plan(requirements=req, out_dir=root / "plan", worker_cache=cache)
    assert result["status"] == "repair-vdd" and result["stage"] == "V4"
    assert result["gate"] == "atomic-source-recall"
    assert result["atomic_quality_metrics"]["precision"] == 1.0
    assert result["atomic_quality_metrics"]["recall"] == 0.5
    assert len(result["source_gap_claims"]) == 1
    assert not (root / "plan" / "semantic-plan-bundle.v1.json").exists()
    assert not (root / "plan" / "compiler-state.v1.json").exists()


def test_invented_obligation_blocks_atomic_precision(tmp_path: Path) -> None:
    root, req, owner, selector = _repo(tmp_path)
    cache = _worker_cache("req.md#FR-1", owner, selector)
    oid = cache["v4-atomic-recall"]["supported_obligation_ids"][0]
    cache["v4-atomic-recall"] = {
        "supported_obligation_ids":[],
        "invented_obligation_ids":[oid],
        "source_gap_claims":[{
            "source_ref":"req.md#FR-1",
            "subject":"compiler",
            "behavior":"emit a deterministic plan",
            "reason":"the proposed obligation is judged unsupported and the actual source behavior remains uncovered",
        }],
    }
    result = compile_plan(requirements=req, out_dir=root / "plan", worker_cache=cache)
    assert result["status"] == "repair-vdd" and result["stage"] == "V4"
    assert result["atomic_quality_metrics"]["precision"] == 0.0
    assert result["atomic_quality_metrics"]["recall"] == 0.0
    assert not (root / "plan" / "semantic-plan-bundle.v1.json").exists()


def test_recommendation_only_calls_no_worker_and_writes_nothing(tmp_path: Path) -> None:
    root, req, _owner, _selector = _repo(tmp_path)
    result = compile_plan(requirements=req, out_dir=root / "plan", recommendation_only=True)
    assert result["status"] == "recommendation-only"
    assert result["model_called"] is False
    assert not (root / "plan").exists()


def test_v1_reuses_peer_cache_when_only_another_requirement_anchor_changed(tmp_path: Path) -> None:
    """A full requirements-file digest change must not rerun an unchanged V1 anchor."""
    out_dir = tmp_path / "repair" / "s1-selector-repair" / "current-plan"
    cache_dir = out_dir / ".compiler-cache"; cache_dir.mkdir(parents=True)
    entry = {
        "requirement_id": "FR-1", "source_ref": "requirements.md#FR-1",
        "text_sha256": "sha256:unchanged-fr-1",
    }
    prior_index = out_dir.parents[1] / "current-plan" / "source-index.v1.json.stale-source-refresh"
    prior_index.parent.mkdir(parents=True)
    prior_index.write_text(json.dumps({"entries": [entry]}), encoding="utf-8")
    cached = {"obligations": [{"source_refs": ["requirements.md#FR-1"]}]}
    (cache_dir / _worker_cache_key("v1-FR-1", {"source": entry})).write_text(json.dumps(cached), encoding="utf-8")

    assert _reusable_prior_v1_cache(cache_dir, "v1-FR-1", {"source": entry}, out_dir) == cached


def test_v1_peer_reuse_rejects_unbound_same_ref_cache_variant(tmp_path: Path) -> None:
    """A source-ref match alone cannot select among historical V1 variants."""
    out_dir = tmp_path / "repair" / "s1-selector-repair" / "current-plan"
    cache_dir = out_dir / ".compiler-cache"; cache_dir.mkdir(parents=True)
    entry = {
        "requirement_id": "FR-1", "source_ref": "requirements.md#FR-1",
        "text_sha256": "sha256:unchanged-fr-1",
    }
    prior_index = out_dir.parents[1] / "current-plan" / "source-index.v1.json.stale-source-refresh"
    prior_index.parent.mkdir(parents=True)
    prior_index.write_text(json.dumps({"entries": [entry]}), encoding="utf-8")
    (prior_index.parent / ".compiler-cache").mkdir()
    (prior_index.parent / ".compiler-cache" / "v1-FR-1-unbound-variant.json").write_text(
        json.dumps({"obligations": [{"source_refs": [entry["source_ref"]], "subject": "wrong variant"}]}),
        encoding="utf-8",
    )

    assert _reusable_prior_v1_cache(cache_dir, "v1-FR-1", {"source": entry}, out_dir) is None


def test_v1_does_not_reuse_peer_cache_when_anchor_text_changed(tmp_path: Path) -> None:
    out_dir = tmp_path / "repair" / "s1-selector-repair" / "current-plan"
    cache_dir = out_dir / ".compiler-cache"; cache_dir.mkdir(parents=True)
    entry = {
        "requirement_id": "FR-1", "source_ref": "requirements.md#FR-1",
        "text_sha256": "sha256:current",
    }
    prior_index = out_dir.parents[1] / "current-plan" / "source-index.v1.json"
    prior_index.parent.mkdir(parents=True)
    prior_index.write_text(json.dumps({"entries": [{**entry, "text_sha256": "sha256:old"}]}), encoding="utf-8")
    (cache_dir / "v1-FR-1-prior.json").write_text(
        json.dumps({"obligations": [{"source_refs": ["requirements.md#FR-1"]}]}), encoding="utf-8",
    )

    assert _reusable_prior_v1_cache(cache_dir, "v1-FR-1", {"source": entry}, out_dir) is None


def test_v1_rebinds_only_proven_identical_anchor_text_from_prior_plan(tmp_path: Path) -> None:
    out_dir = tmp_path / "repair" / "s1-selector-repair" / "current-plan"
    cache_dir = out_dir / ".compiler-cache"; cache_dir.mkdir(parents=True)
    current = {
        "requirement_id": "FR-1", "source_ref": "new-requirements.md#FR-1",
        "text_sha256": "sha256:same-anchor-text",
    }
    prior_root = out_dir.parents[1] / "current-plan"; (prior_root / ".compiler-cache").mkdir(parents=True)
    prior_ref = "old-requirements.md#FR-1"
    (prior_root / "source-index.v1.json").write_text(
        json.dumps({"entries": [{"source_ref": prior_ref, "text_sha256": current["text_sha256"]}]}), encoding="utf-8",
    )
    prior_entry = {"source_ref": prior_ref, "text_sha256": current["text_sha256"]}
    (prior_root / ".compiler-cache" / _worker_cache_key("v1-FR-1", {"source": prior_entry})).write_text(
        json.dumps({"obligations": [{"source_refs": [prior_ref], "subject": "same semantic input"}]}), encoding="utf-8",
    )

    reused = _reusable_prior_v1_cache(cache_dir, "v1-FR-1", {"source": current}, out_dir)
    assert reused is not None
    assert reused["obligations"][0]["source_refs"] == [current["source_ref"]]


def _published_v1_predecessor(tmp_path: Path, entries: list[dict], obligations: list[dict], *, valid: bool = True) -> Path:
    plan = tmp_path / "predecessor"; plan.mkdir(parents=True)
    (plan / "compiler-state.v1.json").write_text(json.dumps({"state": "plan-ready"}), encoding="utf-8")
    supported = [item["obligation_id"] for item in obligations if item["status"] == "active"]
    (plan / "atomic-recall-alignment.v1.json").write_text(
        json.dumps({"valid": valid, "worker": {"supported_obligation_ids": supported}}), encoding="utf-8"
    )
    (plan / "source-index.v1.json").write_text(json.dumps({"entries": entries}), encoding="utf-8")
    (plan / "obligations.v1.json").write_text(json.dumps(obligations), encoding="utf-8")
    return plan


def _raw_obligation(source_ref: str, subject: str = "subject", depends_on: list[str] | None = None) -> dict:
    return {
        "source_refs": [source_ref], "subject": subject, "trigger": "when triggered",
        "state_before": "before", "state_after": "after", "expected_behavior": "does work",
        "observable_result": "observable", "forbidden_result": [], "requirement_type": "Platform",
        "obligation_kind": "behavior", "unresolved_fragments": [], "status": "active",
        "depends_on": depends_on or [],
    }


def test_v1_plan_reuse_rebinds_only_matching_plan_ready_v4_anchor(tmp_path: Path) -> None:
    old_ref = "old.md#FR-1"; current_ref = "new.md#FR-1"
    old = _raw_obligation(old_ref)
    old_entry = {"requirement_id": "FR-1", "source_ref": old_ref, "text_sha256": "sha256:same"}
    old["obligation_id"] = _normalize_obligation(old_entry, old)["obligation_id"]
    configure_v1_reuse_predecessor_plan(_published_v1_predecessor(tmp_path, [old_entry], [old]))
    current = {"requirement_id": "FR-1", "source_ref": current_ref, "text_sha256": "sha256:same"}
    reused = _reusable_predecessor_obligations({"entries": [current]})
    assert reused["FR-1"][0]["source_refs"] == [current_ref]
    assert reused["FR-1"][0]["obligation_id"] != old["obligation_id"]


def test_v1_plan_reuse_rejects_changed_or_unverified_predecessor(tmp_path: Path) -> None:
    old_ref = "old.md#FR-1"; old = _raw_obligation(old_ref)
    old_entry = {"requirement_id": "FR-1", "source_ref": old_ref, "text_sha256": "sha256:old"}
    old["obligation_id"] = _normalize_obligation(old_entry, old)["obligation_id"]
    plan = _published_v1_predecessor(tmp_path, [old_entry], [old], valid=False)
    with pytest.raises(ValueError, match="atomic recall"):
        configure_v1_reuse_predecessor_plan(plan)
    plan = _published_v1_predecessor(tmp_path / "second", [old_entry], [old])
    configure_v1_reuse_predecessor_plan(plan)
    assert _reusable_predecessor_obligations({"entries": [{
        "requirement_id": "FR-1", "source_ref": "new.md#FR-1", "text_sha256": "sha256:changed",
    }]}) == {}


def test_v1_plan_reuse_fails_closed_for_dependency_outside_reused_anchor(tmp_path: Path) -> None:
    old_ref = "old.md#FR-1"; old = _raw_obligation(old_ref, depends_on=["O-UNAVAILABLE"])
    old_entry = {"requirement_id": "FR-1", "source_ref": old_ref, "text_sha256": "sha256:same"}
    old["obligation_id"] = _normalize_obligation(old_entry, old)["obligation_id"]
    configure_v1_reuse_predecessor_plan(_published_v1_predecessor(tmp_path, [old_entry], [old]))
    assert _reusable_predecessor_obligations({"entries": [{
        "requirement_id": "FR-1", "source_ref": "new.md#FR-1", "text_sha256": "sha256:same",
    }]}) == {}


def test_source_index_excludes_selector_repair_context_from_v1_semantics(tmp_path: Path) -> None:
    (tmp_path / ".agents").mkdir(); (tmp_path / "AGENTS.md").write_text("x", encoding="utf-8")
    requirements = tmp_path / "requirements.md"
    requirements.write_text(
        "# FR-1\nSemantic requirement.\n<!-- selector-repair-binding-start -->\n"
        "Selector: tests/test_contract.py\n<!-- selector-repair-binding-end -->\n",
        encoding="utf-8",
    )
    entry = build_source_index(tmp_path, requirements)["entries"][0]
    assert entry["source_text"] == "# FR-1\nSemantic requirement."
    assert "tests/test_contract.py" not in entry["source_text"]
    assert "tests/test_contract.py" in entry["execution_context_text"]


def test_missing_requirement_anchor_fails_closed(tmp_path: Path) -> None:
    root = tmp_path; (root / ".agents").mkdir(); (root / "AGENTS.md").write_text("x", encoding="utf-8")
    req = root / "req.md"; req.write_text("No canonical requirement id.\n", encoding="utf-8")
    try:
        compile_plan(requirements=req, out_dir=root / "plan", recommendation_only=True)
    except ValueError as exc:
        assert "requirement" in str(exc).lower()
    else:
        raise AssertionError("missing requirement anchor must fail")


def test_compiler_rejects_unconsumable_cer_handoff(tmp_path: Path) -> None:
    root, req, owner, selector = _repo(tmp_path)
    cache = _worker_cache("req.md#FR-1", owner, selector)
    cache["v3"]["slice_hints"][0]["validation_commands"] = [[sys.executable, owner, "--help"]]
    result = compile_plan(requirements=req, out_dir=root / "plan", worker_cache=cache)
    assert result["status"] == "repair-vdd"
    assert result["stage"] == "quick-dev-handoff"
    assert not (root / "plan" / "compiler-state.v1.json").exists()
