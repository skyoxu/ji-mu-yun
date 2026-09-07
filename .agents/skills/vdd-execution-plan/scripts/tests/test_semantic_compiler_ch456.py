from __future__ import annotations

from pathlib import Path
import sys
import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from semantic_compiler import _normalize_obligation
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
    (root / selector).write_text("print('selector')\n", encoding="utf-8")
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
            "failure_intents": [{"obligation_ids":[oid],"failure_family":"semantic-contract-gap","selector_intent":selector,"expected_outcome":"fail","failure_id":"COMPILE-RED"}],
            "slice_hints": [{"obligation_ids":[oid],"production_owners":[owner],"verification_lane":"unit","behavior_change":"compile deterministic plans","affected_subjects":["compiler"],"state_transition":"uncompiled->compiled","rollback_scope":{"production_paths":[owner],"state_or_schema_compatibility":"backward-compatible"},"allowed_write_paths":[owner],"execution_snapshot_paths":[selector],"planned_new_files":[],"terminal_predicate":"all active Acceptance assertions pass","forbidden_paths":[],"validation_commands":[[sys.executable,selector]]}]
        },
        "v4-atomic-recall": {"supported_obligation_ids":[oid],"invented_obligation_ids":[],"source_gap_claims":[]},
        "v4": {"covered_obligation_ids":[oid],"missing_obligation_ids":[],"invented_obligation_ids":[],"misaligned_acceptance_ids":[],"oracle_alignment":{},"repairs":[]}
    }


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


def test_missing_requirement_anchor_fails_closed(tmp_path: Path) -> None:
    root = tmp_path; (root / ".agents").mkdir(); (root / "AGENTS.md").write_text("x", encoding="utf-8")
    req = root / "req.md"; req.write_text("No canonical requirement id.\n", encoding="utf-8")
    try:
        compile_plan(requirements=req, out_dir=root / "plan", recommendation_only=True)
    except ValueError as exc:
        assert "requirement" in str(exc).lower()
    else:
        raise AssertionError("missing requirement anchor must fail")
