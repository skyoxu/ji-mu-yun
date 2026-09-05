"""ADR-0041: V4 covers active proof targets, retaining non-active context."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS)) if str(SCRIPTS) not in sys.path else None
import semantic_compiler_authority  # noqa: E402,F401
import semantic_alignment_repair_patch as alignment  # noqa: E402

sc = alignment.sc


@pytest.mark.parametrize("recheck", [False, True])
@pytest.mark.parametrize("missing", [None, "O-ACTIVE", "O-DEFERRED"])
def test_alignment_scopes_worker_input_without_filtering_judgment(monkeypatch, tmp_path, recheck, missing):
    obligations = [
        {"obligation_id": "O-ACTIVE", "status": "active", "expected_behavior": "bounded ledger"},
        {"obligation_id": "O-DEFERRED", "status": "deferred", "expected_behavior": "bounded ledger",
         "unresolved_fragments": ["meaning of bounded"]},
    ]
    original = deepcopy(obligations)
    acceptances = [{"acceptance_id": "A-1", "obligation_ids": ["O-ACTIVE"]}]
    sources = {"entries": [{"source_ref": "requirements.md#FR-301"}]}
    calls = []

    def worker(**kwargs):
        calls.append(kwargs)
        payload = kwargs["payload"]
        assert payload["obligations"] == original[:1]
        assert payload["non_active_obligation_context"] == original[1:]
        assert payload["source_index"] == sources
        assert payload["acceptances"] == acceptances
        old_payload = {"source_index": sources, "obligations": original, "acceptances": acceptances, "failure_intents": []}
        assert sc._worker_cache_key(kwargs["stage"], payload) != sc._worker_cache_key(kwargs["stage"], old_payload)
        return {"covered_obligation_ids": [] if missing == "O-ACTIVE" else ["O-ACTIVE"],
                "missing_obligation_ids": [missing] if missing else [], "invented_obligation_ids": [],
                "misaligned_acceptance_ids": [], "oracle_alignment": {}, "repairs": []}

    monkeypatch.setattr(sc, "invoke_worker", worker)
    target = alignment._independent_recheck if recheck else alignment._BASE_SEMANTIC_ALIGN
    result = target(root=tmp_path, out_dir=tmp_path / "plan", source_index=sources,
                    obligations=obligations, acceptances=acceptances, failures=[], worker_cache=None)
    assert len(calls) == 1
    assert calls[0]["stage"] == ("v4-recheck" if recheck else "v4")
    assert obligations == original
    assert result["valid"] is (missing is None)
    if missing:
        assert f"v4:missing:{missing}" in result["findings"]
        assert result["worker"]["missing_obligation_ids"] == [missing]
