from __future__ import annotations

import json
from pathlib import Path
import sys

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from evidence_pipeline import (
    execute_descriptor,
    judge_receipt,
    runtime_assertion_edges,
    validate_runtime_closure,
)


def _descriptor(script: str) -> dict:
    return {
        "id": "case",
        "executable": sys.executable,
        "argv": ["-c", script],
        "cwd": ".",
        "timeout_seconds": 10,
        "shell": False,
    }


def _hash() -> str:
    return "sha256:" + "1" * 64


def test_executor_and_judge_have_separate_artifacts(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    fixture = tmp_path / "fixture.txt"
    target.write_text("target", encoding="utf-8")
    fixture.write_text("fixture", encoding="utf-8")
    run_dir = tmp_path / "run"
    descriptor = _descriptor("print('FAILURE_ID:EXPECTED-RED'); raise SystemExit(1)")

    receipt = execute_descriptor(
        tmp_path,
        run_dir,
        "red",
        descriptor,
        candidate_hash=_hash(),
        profile_identity="standard",
        target_refs=["target.txt"],
        fixture_refs=["fixture.txt"],
    )
    receipt_path = run_dir / "canonical-evidence/red/process-receipt.v1.json"
    assert receipt_path.is_file()
    assert "verification_outcome" not in json.loads(receipt_path.read_text(encoding="utf-8"))

    observation = judge_receipt(
        run_dir,
        "red",
        descriptor,
        receipt,
        expected_failure_ids=["EXPECTED-RED"],
        expected_exit="nonzero",
    )
    assert observation["predicate_result"] is True
    assert observation["verification_outcome"] == "fail"
    assert observation["failure_family"] == "expected-red"
    assert (run_dir / "canonical-evidence/red/observation.v1.json").is_file()


def test_runtime_edge_binds_receipt_and_observation(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    fixture = tmp_path / "fixture.txt"
    target.write_text("target", encoding="utf-8")
    fixture.write_text("fixture", encoding="utf-8")
    run_dir = tmp_path / "run"
    descriptor = _descriptor("print('ok')")
    receipt = execute_descriptor(
        tmp_path, run_dir, "green", descriptor,
        candidate_hash=_hash(), profile_identity="standard",
        target_refs=["target.txt"], fixture_refs=["fixture.txt"],
    )
    observation = judge_receipt(run_dir, "green", descriptor, receipt, expected_exit="zero")
    edges = runtime_assertion_edges(
        plan_id="P1", plan_hash=_hash(), slice_id="S1", run_id="RUN-1",
        candidate_hash=_hash(), stage="green", descriptor=descriptor,
        receipt=receipt, observation=observation,
        assertions=[{"acceptance_id": "A-ONE", "assertion_id": "AS-1", "case_source_ref": "tests/test_one.py"}],
        selector_identity=_hash(),
    )
    assert len(edges) == 1
    assert edges[0]["verification_outcome"] == "pass"
    assert edges[0]["failure_id"] is None


def test_runtime_closure_rejects_duplicate_tuple_key() -> None:
    key = "S1|A-ONE|red"
    row = {
        "tuple_key": key,
        "slice_id": "S1",
        "acceptance_id": "A-ONE",
        "stage": "red",
        "runtime_edge_sha256": _hash(),
        "current_snapshot_sha256": _hash(),
    }
    valid, findings = validate_runtime_closure([row, dict(row)], {key})
    assert valid is False
    assert "tuple-key-duplicate" in findings
    assert "tuple-cardinality-mismatch" in findings
