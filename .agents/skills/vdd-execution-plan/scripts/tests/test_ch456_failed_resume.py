from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys

SCRIPTS = Path(__file__).resolve().parents[1]
TESTS = Path(__file__).resolve().parent
for path in (SCRIPTS, TESTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from semantic_compiler import _normalize_obligation
from semantic_compiler_authority import compile_plan
from test_ch456_compiler_closure import _cache, _repo


def test_atomic_recall_failure_can_be_repaired_in_same_out_dir_and_resumed(tmp_path: Path, monkeypatch) -> None:
    def unexpected_live_call(*args, **kwargs):
        raise AssertionError("resume regression must not invoke a live backend")

    monkeypatch.setitem(sys.modules, "_llm_backend", SimpleNamespace(
        run_llm_exec=unexpected_live_call, resolve_llm_backend=unexpected_live_call,
    ))
    root, req, owner, selector = _repo(tmp_path)
    out = root / "plan"
    req.write_text(req.read_text(encoding="utf-8") + "The compiler must stop after a repeated deterministic semantic failure.\n", encoding="utf-8")

    broken = _cache(owner, selector)
    oid = broken["v4-atomic-recall"]["supported_obligation_ids"][0]
    broken["v4-atomic-recall"] = {
        "supported_obligation_ids": [oid],
        "invented_obligation_ids": [],
        "source_gap_claims": [{
            "source_ref": "requirements.md#FR-1",
            "subject": "compiler retry loop",
            "behavior": "stop after a repeated deterministic semantic failure",
            "reason": "the extracted obligation set does not contain this source behavior",
        }],
    }

    # ADR-0041: source gaps now trigger a bounded V1 repair before V4 fails.
    # Supply that worker response too; this resume fixture must stay offline.
    addition = deepcopy(broken["v1-FR-1"]["obligations"][0])
    addition.update(
        subject="compiler retry loop",
        expected_behavior="stop after a repeated deterministic semantic failure",
        observable_result="retry loop stops",
        state_after="stopped",
    )
    broken["v1-source-gap-repair"] = {"obligations": [addition]}
    added_oid = _normalize_obligation(
        {"requirement_id": "FR-1", "source_ref": "requirements.md#FR-1"}, addition,
    )["obligation_id"]
    for field in ("acceptances", "failure_intents", "slice_hints"):
        item = deepcopy(broken["v3"][field][0])
        item["obligation_ids"] = [added_oid]
        if field == "acceptances":
            item.update(then="retry loop stops", assertion_ids=["ASSERT-STOP"])
            item["oracle"] = {"observable": "retry loop", "expected": "stopped", "forbidden": ["continued retries"]}
        elif field == "failure_intents":
            item["failure_id"] = "STOP-RED"
        else:
            item.update(affected_subjects=["compiler retry loop"], behavior_change="stop repeated failure", state_transition="retrying->stopped")
        broken["v3"][field].append(item)


    first = compile_plan(requirements=req, out_dir=out, worker_cache=broken)
    assert first["status"] == "repair-vdd"
    assert first["stage"] == "V4"
    assert first["gate"] == "atomic-source-recall"
    assert not (out / "atomic-recall-alignment.v1.json").exists()
    assert not (out / "semantic-plan-bundle.v1.json").exists()
    assert list((out / ".compiler-attempts").glob("v4-atomic-recall-*.json"))

    clean = deepcopy(broken)
    clean["v1-FR-1"]["obligations"].append(addition)
    clean["v4-atomic-recall"].update(
        supported_obligation_ids=[oid, added_oid], source_gap_claims=[],
    )
    clean["v4"]["covered_obligation_ids"] = [oid, added_oid]
    repaired = compile_plan(
        requirements=req,
        out_dir=out,
        worker_cache=clean,
        resume_from="first-failed-stage",
    )
    assert repaired["status"] == "plan-ready"
    assert repaired["resumed"] is True
    assert repaired["resume_from"] == "first-failed-stage"
    assert repaired["resume_strategy"] == "first-failed-stage-cache-replay"
    assert (out / "atomic-recall-alignment.v1.json").is_file()
    assert (out / "semantic-plan-bundle.v1.json").is_file()
    assert (out / "compiler-state.v1.json").is_file()
