from __future__ import annotations

import json
from pathlib import Path
import sys

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from canonical_lifecycle import execute_stage, terminal_closure


def _hash() -> str:
    return "sha256:" + "2" * 64


def _bundle() -> dict:
    return {
        "schema_version": "vdd.semantic-plan-bundle.v1",
        "plan_id": "P1",
        "acceptances": [{"acceptance_id": "A-ONE", "source_refs": ["tests/test_one.py"], "assertion_ids": ["AS-1"]}],
        "failure_intents": [{"failure_intent_id": "FI-ONE", "failure_id": "EXPECTED-RED"}],
        "slices": [{"slice_id": "S1", "acceptance_ids": ["A-ONE"], "failure_intent_ids": ["FI-ONE"]}],
        "final_plan_coverage": [{"slice_id": "S1", "acceptance_id": "A-ONE", "stage_scope": ["red", "green", "refactor", "terminal"]}],
    }


def _descriptor(script: str) -> dict:
    return {"id": "selector", "executable": sys.executable, "argv": ["-c", script], "cwd": ".", "timeout_seconds": 10, "shell": False}


def test_canonical_red_executes_real_process_and_writes_edges(tmp_path: Path) -> None:
    plan = tmp_path / "semantic-plan.json"
    plan.write_text(json.dumps(_bundle()), encoding="utf-8")
    descriptor = tmp_path / "red.json"
    descriptor.write_text(json.dumps(_descriptor("print('FAILURE_ID:EXPECTED-RED'); raise SystemExit(1)")), encoding="utf-8")
    (tmp_path / "target.py").write_text("target", encoding="utf-8")
    (tmp_path / "fixture.py").write_text("fixture", encoding="utf-8")
    run_dir = tmp_path / "RUN-1"
    result = execute_stage(
        workspace=tmp_path, plan_bundle_path=plan, slice_id="S1", run_dir=run_dir,
        stage="red", descriptor_path=descriptor, candidate_hash=_hash(), profile_identity="standard",
        selector="tests/test_one.py", target_refs=["target.py"], fixture_refs=["fixture.py"],
    )
    assert result["predicate_result"] is True
    assert result["verification_outcome"] == "fail"
    assert len(result["runtime_edges"]) == 1


def test_terminal_closure_requires_all_declared_stages() -> None:
    bundle = _bundle()
    snapshot = _hash()
    tuples = [{"tuple_key": f"S1|A-ONE|{stage}", "slice_id": "S1", "acceptance_id": "A-ONE", "stage": stage, "runtime_edge_sha256": _hash(), "current_snapshot_sha256": snapshot} for stage in ("red", "green", "refactor", "terminal")]
    valid, findings = terminal_closure(bundle=bundle, slice_id="S1", runtime_tuples=tuples, current_snapshot_sha256=snapshot)
    assert valid is True, findings
    valid, findings = terminal_closure(bundle=bundle, slice_id="S1", runtime_tuples=tuples[:-1], current_snapshot_sha256=snapshot)
    assert valid is False
    assert "tuple-key-set-mismatch" in findings
