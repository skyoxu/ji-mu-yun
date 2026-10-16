from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import sys

SCRIPTS = Path(__file__).resolve().parents[1]
TESTS = Path(__file__).resolve().parent
for path in (SCRIPTS, TESTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from semantic_compiler_authority import compile_plan
import semantic_compiler_gate as gate
from test_ch456_compiler_closure import _cache, _repo


def test_atomic_recall_failure_can_be_repaired_in_same_out_dir_and_resumed(tmp_path: Path, monkeypatch) -> None:
    def unexpected_live_call(*args, **kwargs):
        raise AssertionError("resume regression must not invoke a live backend")

    monkeypatch.setitem(sys.modules, "_llm_backend", SimpleNamespace(
        run_llm_exec=unexpected_live_call, resolve_llm_backend=unexpected_live_call,
    ))
    root, req, owner, selector = _repo(tmp_path)
    out = root / "plan"
    broken = _cache(owner, selector)
    oid = broken["v4-atomic-recall"]["supported_obligation_ids"][0]
    # ADR-0041: pure source gaps now enter automatic bounded repair. This test
    # owns terminal V4 refusal and explicit same-directory resume, so use an
    # independently rejected invented obligation instead of a stale gap worker
    # that recursively requests the same already-added obligation.
    broken["v4-atomic-recall"].update(
        supported_obligation_ids=[], invented_obligation_ids=[oid], source_gap_claims=[],
    )
    first = compile_plan(requirements=req, out_dir=out, worker_cache=broken)
    assert first["status"] == "repair-vdd"
    assert first["stage"] == "V4"
    assert first["gate"] == "atomic-source-recall"
    assert not (out / "atomic-recall-alignment.v1.json").exists()
    assert not (out / "semantic-plan-bundle.v1.json").exists()
    assert list((out / ".compiler-attempts").glob("v4-atomic-recall-*.json"))

    clean = deepcopy(broken)
    clean["v4-atomic-recall"].update(
        supported_obligation_ids=[oid], invented_obligation_ids=[], source_gap_claims=[],
    )
    repaired = compile_plan(
        requirements=req, out_dir=out, worker_cache=clean,
        resume_from="first-failed-stage",
    )
    assert repaired["status"] == "plan-ready"
    assert repaired["resumed"] is True
    assert repaired["resume_from"] == "first-failed-stage"
    assert repaired["resume_strategy"] == "first-failed-stage-cache-replay"
    assert (out / "atomic-recall-alignment.v1.json").is_file()
    assert (out / "semantic-plan-bundle.v1.json").is_file()
    assert (out / "compiler-state.v1.json").is_file()


def test_stale_root_alignment_is_preserved_and_current_recall_is_explicitly_bound(tmp_path: Path, monkeypatch) -> None:
    root, req, owner, selector = _repo(tmp_path)
    out = root / "plan"
    old_alignment = {
        "schema": "vdd.atomic-recall-alignment.v1",
        "valid": True,
        "findings": [],
        "metrics": {"active_obligation_count": 999},
        "source_gap_claims": [],
        "worker": {"supported_obligation_ids": []},
        "authorizes": [],
    }
    old_path = out / "atomic-recall-alignment.v1.json"
    gate.sc.atomic_json(old_path, old_alignment)

    result = compile_plan(requirements=req, out_dir=out, worker_cache=_cache(owner, selector))

    assert result["status"] == "plan-ready"
    assert gate.sc.canonical_bytes(old_alignment) == old_path.read_bytes()
    binding = result["atomic_recall_alignment"]
    assert binding["path"].startswith(".compiler-attempts/v4-atomic-recall-alignment-")
    current_path = out / binding["path"]
    assert current_path.is_file()
    assert binding["sha256"] == gate.sc.sha256_value(json.loads(current_path.read_text(encoding="utf-8")))
    # ADR-0041: both same-plan resume and explicit V1 reuse consume the final
    # bound witness while leaving the historical root publication untouched.
    assert gate.sc.published_recall_path(out) == current_path.resolve()
    monkeypatch.setattr(gate.sc, "_v1_reuse_predecessor_plan", None)
    gate.sc.configure_v1_reuse_predecessor_plan(out)
    monkeypatch.setattr(gate.sc, "invoke_worker", lambda **kw: (_ for _ in ()).throw(AssertionError("unexpected worker call")))
    resumed = compile_plan(requirements=req, out_dir=out, resume_from="first-failed-stage")
    assert resumed["status"] == "plan-ready"
    assert old_path.read_bytes() == gate.sc.canonical_bytes(old_alignment)
    current_path.write_text("{}", encoding="utf-8")
    import pytest
    with pytest.raises(ValueError, match="alignment stale"):
        gate.sc.published_recall_path(out)
