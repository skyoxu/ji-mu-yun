from __future__ import annotations

from pathlib import Path
import sys
import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from semantic_compiler import _normalize_obligation, build_source_index, source_preflight
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


def test_repair_case_table_owns_atomic_ids_and_companions_are_frozen_context(tmp_path: Path) -> None:
    root = tmp_path
    (root / ".agents").mkdir()
    (root / "AGENTS.md").write_text("x", encoding="utf-8")
    requirements = root / "repair.md"
    requirements.write_text(
        "# Repair\n\n"
        "| Case | PIWR parents | Acceptance | Lane | Source | Behavior |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| I01 | PIWR-001 | PIWR-A01 | S0 | identity.md | Resolve server context. |\n"
        "| W03 | PIWR-023 | PIWR-A09 | S2 | recovery.md | Retain immutable bytes. |\n"
        "\nNFR-001 and FR-001 remain normative companion references.\n",
        encoding="utf-8",
    )
    spec = root / "SPEC.md"
    spec.write_text("# Canonical\nFR-001 and NFR-001 are normative.\n", encoding="utf-8")
    companion = root / "identity.md"
    companion.write_text("PIWR-001 binds server identity.\n", encoding="utf-8")

    index = build_source_index(root, requirements, [spec, companion])

    assert [entry["requirement_id"] for entry in index["entries"]][:3] == [
        "SM-I01", "SM-W03", "SM-REPAIR-CONSTRAINTS"
    ]
    assert len(index["entries"]) == 3
    assert "NFR-001 and FR-001" in index["entries"][2]["source_text"]
    assert [entry["repository_relative_source_path"] for entry in index["companions"]] == [
        "SPEC.md",
        "identity.md",
    ]
    assert index["companions"][0]["source_text"].startswith("# Canonical")
    assert source_preflight(root, index)["valid"] is True


def test_companion_byte_change_invalidates_source_preflight(tmp_path: Path) -> None:
    root = tmp_path
    (root / ".agents").mkdir()
    (root / "AGENTS.md").write_text("x", encoding="utf-8")
    requirements = root / "repair.md"
    requirements.write_text("| I01 | PIWR-001 | PIWR-A01 | S0 | source | behavior |\n", encoding="utf-8")
    companion = root / "SPEC.md"
    companion.write_text("FR-001 initial\n", encoding="utf-8")
    index = build_source_index(root, requirements, [companion])

    companion.write_text("FR-001 changed\n", encoding="utf-8")

    result = source_preflight(root, index)
    assert result["valid"] is False
    assert "companion[0]:stale-source-hash" in result["findings"]


def test_v1_wrong_source_ref_uses_one_schema_repair(tmp_path: Path, monkeypatch) -> None:
    payload = {"source": {"source_ref": "repair.md#SM-I11"}}
    calls: list[str] = []

    def worker(**kwargs):
        calls.append(kwargs["stage"])
        ref = "PIWR-A03" if len(calls) == 1 else "repair.md#SM-I11"
        return {"obligations": [{"source_refs": [ref], "subject": "subject", "trigger": "trigger",
            "state_before": "before", "state_after": "after", "expected_behavior": "behavior",
            "observable_result": "result", "forbidden_result": [], "unresolved_fragments": [],
            "depends_on": [], "requirement_type": "Product"}]}

    monkeypatch.setattr(gate, "_ORIGINAL_INVOKE_WORKER", worker)
    result = gate.normative_invoke_worker(
        root=tmp_path,
        out_dir=tmp_path / "plan",
        stage="v1-SM-I11",
        payload=payload,
        prompt="compile",
    )

    assert calls == ["v1-SM-I11", "v1-SM-I11-schema-repair"]
    assert result["obligations"][0]["source_refs"] == ["repair.md#SM-I11"]
