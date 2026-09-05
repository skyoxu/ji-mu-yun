"""ADR-0041: normative source-role guidance reaches workers without stale reuse.

These transport tests do not claim a live semantic classification result.
"""
import json
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import semantic_worker_transport_patch as transport


@pytest.mark.parametrize("stage", ["v1-FR-1", "v1-source-gap-repair", "v4-atomic-recall", "v4-atomic-recall-schema-repair"])
def test_source_role_contract_reaches_worker_and_invalidates_old_cache(stage, tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS.parents[3] / "scripts/sc"))
    import _llm_backend
    payload = {"source": "The existing stub returns success. Reject invalid input. Before changes, record the baseline output."}
    out_dir = tmp_path / "plan"
    old_path = out_dir / ".compiler-cache" / transport.sc._worker_cache_key(stage, payload)
    transport.sc.atomic_json(old_path, {"old": "judgment without source-role contract"})
    old_bytes = old_path.read_bytes()
    calls = []
    def worker(**kwargs):
        calls.append(kwargs)
        prompt, raw_input = kwargs["prompt"].rsplit("\n\nINPUT:\n", 1)
        assert json.loads(raw_input) == payload  # no keyword-based source deletion
        assert transport._source_role_contract(stage) in prompt
        assert "explicit requirement to capture or verify a baseline IS an obligation" in prompt
        kwargs["output_last_message"].write_text('{"fresh":true}', encoding="utf-8")
        return 0, "OK", []
    monkeypatch.setattr(_llm_backend, "resolve_llm_backend", lambda _: "codex-cli")
    monkeypatch.setattr(_llm_backend, "run_llm_exec", worker)
    args = dict(root=tmp_path, out_dir=out_dir, stage=stage, payload=payload, prompt="Judge the supplied source.")
    assert transport.transport_invoke_worker(**args) == {"fresh": True}
    assert transport.transport_invoke_worker(**args) == {"fresh": True}
    assert len(calls) == 1
    assert old_path.read_bytes() == old_bytes


def test_unrelated_v3_cache_and_injected_fixture_are_not_reclassified(tmp_path):
    out_dir = tmp_path / "plan"
    payload = {"obligations": []}
    cached = {"acceptances": [], "failure_intents": [], "slice_hints": []}
    path = out_dir / ".compiler-cache" / transport.sc._worker_cache_key("v3", payload)
    transport.sc.atomic_json(path, cached)
    assert transport.transport_invoke_worker(root=tmp_path, out_dir=out_dir, stage="v3", payload=payload, prompt="Compile.") == cached
    assert transport._source_role_contract("v3") == ""
    historical = {"invented_obligation_ids": [], "supported_obligation_ids": ["O-1"], "source_gap_claims": []}
    assert transport.transport_invoke_worker(root=tmp_path, out_dir=out_dir, stage="v4-atomic-recall",
        payload=payload, prompt="Replay.", worker_cache={"v4-atomic-recall": historical}) == historical
