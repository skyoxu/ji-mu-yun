"""ADR-0041: resolved judgments survive repair without another model vote."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import semantic_compiler_gate as gate


def payload():
    return {"source_index": {"entries": [{"source_ref": "req#FR-1"}]},
            "obligations": [{"obligation_id": "O-1", "status": "active"}]}


def result(gap=False):
    return {"supported_obligation_ids": ["O-1"], "invented_obligation_ids": [],
            "source_gap_claims": ([{"source_ref": "req#FR-1", "subject": "validation",
              "behavior": "Reject implicit history", "reason": "Rejection is independently observable"}] if gap else [])}


@pytest.mark.parametrize("gap", [False, True])
def test_timeout_repair_result_is_reused_even_when_it_reports_a_gap(tmp_path, monkeypatch, gap):
    calls = []

    def transport(**kwargs):
        calls.append(kwargs["stage"])
        if len(calls) == 1:
            raise RuntimeError("codex exec timeout")
        assert len(calls) == 2, "same input must not invoke another independent vote"
        return result(gap)

    monkeypatch.setattr(gate, "_ORIGINAL_INVOKE_WORKER", transport)
    monkeypatch.setattr(gate.sc, "invoke_worker", gate.normative_invoke_worker)
    monkeypatch.setattr(gate, "_write_worker_receipt", lambda **kw: None)
    kw = {"root": tmp_path, "out_dir": tmp_path / "plan", "worker_cache": None, **payload()}
    first = gate.atomic_recall_alignment(**kw)
    second = gate.atomic_recall_alignment(**kw)
    assert calls == ["v4-atomic-recall", "v4-atomic-recall-schema-repair"]
    assert first == second
    assert first["valid"] is (not gap)
    if gap:
        assert "atomic-recall:source-gap-count:1" in first["findings"]


def test_changed_input_or_prompt_requires_new_judgment(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(gate.sc, "invoke_worker", lambda **kw: calls.append(kw) or result())
    kw = {"root": tmp_path, "out_dir": tmp_path, "worker_cache": None,
          "payload": payload(), "prompt": "judge"}
    gate._resolved_atomic_recall_worker(**kw)
    gate._resolved_atomic_recall_worker(**{**kw, "prompt": "revised judge"})
    changed = payload()
    changed["obligations"][0]["expected_behavior"] = "changed behavior"
    gate._resolved_atomic_recall_worker(**{**kw, "payload": changed})
    assert len(calls) == 3


def test_tampered_resolved_result_fails_without_new_vote(tmp_path, monkeypatch):
    monkeypatch.setattr(gate.sc, "invoke_worker", lambda **kw: result())
    kw = {"root": tmp_path, "out_dir": tmp_path, "worker_cache": None,
          "payload": payload(), "prompt": "judge"}
    gate._resolved_atomic_recall_worker(**kw)
    path = next((tmp_path / ".compiler-work/resolved-atomic-recall").glob("*.json"))
    receipt = json.loads(path.read_text())
    receipt["result"] = result(True)
    path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="hash mismatch"):
        gate._resolved_atomic_recall_worker(**kw)


def test_injected_fixture_does_not_reuse_resolved_live_result(tmp_path, monkeypatch):
    monkeypatch.setattr(gate.sc, "invoke_worker", lambda **kw: result(bool(kw["worker_cache"])))
    kw = {"root": tmp_path, "out_dir": tmp_path, "worker_cache": None,
          "payload": payload(), "prompt": "judge"}
    gate._resolved_atomic_recall_worker(**kw)
    assert gate._resolved_atomic_recall_worker(**{**kw, "worker_cache": {"fixture": True}})["source_gap_claims"]


def test_old_repair_success_does_not_override_current_gap(tmp_path, monkeypatch):
    old = tmp_path / ".compiler-cache/v4-atomic-recall-schema-repair-old.json"
    old.parent.mkdir()
    old.write_text(json.dumps(result()))
    calls = []
    monkeypatch.setattr(gate.sc, "invoke_worker", lambda **kw: calls.append(kw) or result(True))
    kw = {"root": tmp_path, "out_dir": tmp_path, "worker_cache": None,
          "payload": payload(), "prompt": "judge"}
    assert gate._resolved_atomic_recall_worker(**kw)["source_gap_claims"]
    assert len(calls) == 1
