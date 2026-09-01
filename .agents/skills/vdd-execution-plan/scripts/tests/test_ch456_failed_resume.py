from __future__ import annotations

from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1]
TESTS = Path(__file__).resolve().parent
for path in (SCRIPTS, TESTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from semantic_compiler_authority import compile_plan
from test_ch456_compiler_closure import _cache, _repo


def test_atomic_recall_failure_can_be_repaired_in_same_out_dir_and_resumed(tmp_path: Path) -> None:
    root, req, owner, selector = _repo(tmp_path)
    out = root / "plan"

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

    first = compile_plan(requirements=req, out_dir=out, worker_cache=broken)
    assert first["status"] == "repair-vdd"
    assert first["stage"] == "V4"
    assert first["gate"] == "atomic-source-recall"
    assert not (out / "atomic-recall-alignment.v1.json").exists()
    assert not (out / "semantic-plan-bundle.v1.json").exists()
    assert list((out / ".compiler-attempts").glob("v4-atomic-recall-*.json"))

    repaired = compile_plan(
        requirements=req,
        out_dir=out,
        worker_cache=_cache(owner, selector),
        resume_from="first-failed-stage",
    )
    assert repaired["status"] == "plan-ready"
    assert repaired["resumed"] is True
    assert repaired["resume_from"] == "first-failed-stage"
    assert repaired["resume_strategy"] == "first-failed-stage-cache-replay"
    assert (out / "atomic-recall-alignment.v1.json").is_file()
    assert (out / "semantic-plan-bundle.v1.json").is_file()
    assert (out / "compiler-state.v1.json").is_file()
