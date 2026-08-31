from __future__ import annotations

import json
from pathlib import Path
import sys

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from current_lifecycle import STAGES, current_snapshot, execute_stage, sha256_value
from coverage_predicates import publish_implementation_complete, validate_slice_ready


def digest() -> str:
    return "sha256:" + "b" * 64


def semantic_bundle() -> dict:
    return {
        "schema_version": "vdd.semantic-plan-bundle.v1", "plan_id": "P1",
        "acceptances": [{"acceptance_id": "A-ONE", "assertion_ids": ["AS-1", "AS-2"]}],
        "failure_intents": [{"failure_intent_id": "FI-ONE", "failure_id": "EXPECTED-RED"}],
        "slices": [{"slice_id": "S1", "acceptance_ids": ["A-ONE"], "failure_intent_ids": ["FI-ONE"]}],
        "final_plan_coverage": [{"slice_id": "S1", "acceptance_id": "A-ONE", "stage_scope": list(STAGES)}],
    }


def prepare(root: Path):
    for name in ("candidate.txt", "contract.json", "fixture.txt", "source.txt", "validator.py", "transition.json"):
        (root / name).write_text(name, encoding="utf-8")
    (root / "plan").mkdir(); semantic = root / "plan/semantic.json"; semantic.write_text(json.dumps(semantic_bundle()), encoding="utf-8")
    (root / "descriptors").mkdir()
    roots = [{"root_kind": kind, "repository_relative_posix_path": path, "inclusion_reason": "test"} for kind, path in (
        ("candidate_tree", "candidate.txt"), ("plan", "plan"), ("contract", "contract.json"), ("descriptor", "descriptors"),
        ("fixture", "fixture.txt"), ("source", "source.txt"), ("validator_judge", "validator.py"), ("plan_state_transition", "transition.json"),
    )]
    return semantic, roots


def test_q7_and_q8_cover_all_assertions_and_same_selector(tmp_path: Path) -> None:
    semantic, roots = prepare(tmp_path)
    run = tmp_path / "RUN-1"
    for stage in STAGES:
        script = "print('FAILURE_ID:EXPECTED-RED'); raise SystemExit(1)" if stage == "red" else "print('2 passed')"
        descriptor = {"id": stage, "executable": sys.executable, "argv": ["-c", script], "cwd": ".", "timeout_seconds": 10, "shell": False}
        path = tmp_path / f"descriptors/{stage}.json"; path.write_text(json.dumps(descriptor), encoding="utf-8")
        execute_stage(workspace=tmp_path, semantic_plan=semantic, slice_id="S1", run_dir=run, stage=stage, descriptor_path=path, candidate_hash=digest(), profile_identity="standard", selector="tests/test_one.py", target_refs=["candidate.txt"], fixture_refs=["fixture.txt"])
    ready_path = run / "slice-ready-result.v2.json"
    ready = validate_slice_ready(workspace=tmp_path, semantic_plan=semantic, run_root=run, slice_id="S1", snapshot_roots=roots, source_commit="TEST", out=ready_path)
    assert len(ready["assertion_coverage"]["green"]["A-ONE"]) == 2
    predecessor = {"slice_id": "S1", "run_root": "RUN-1", "result_ref": "RUN-1/slice-ready-result.v2.json", "result_sha256": sha256_value(ready)}
    result = publish_implementation_complete(workspace=tmp_path, semantic_plan=semantic, predecessors=[predecessor], snapshot_roots=roots, source_commit="TEST", out=run / "implementation-complete-result.v2.json")
    assert result["status"] == "pass"
    assert len(result["runtime_closure_tuples"]) == 4


def test_q7_rejects_selector_drift(tmp_path: Path) -> None:
    semantic, roots = prepare(tmp_path)
    run = tmp_path / "RUN-2"
    selectors = {"red": "tests/test_one.py", "green": "tests/test_other.py", "refactor": "tests/test_one.py"}
    for stage in ("red", "green", "refactor"):
        script = "print('FAILURE_ID:EXPECTED-RED'); raise SystemExit(1)" if stage == "red" else "print('2 passed')"
        descriptor = {"id": stage, "executable": sys.executable, "argv": ["-c", script], "cwd": ".", "timeout_seconds": 10, "shell": False}
        path = tmp_path / f"descriptors/{stage}.json"; path.write_text(json.dumps(descriptor), encoding="utf-8")
        execute_stage(workspace=tmp_path, semantic_plan=semantic, slice_id="S1", run_dir=run, stage=stage, descriptor_path=path, candidate_hash=digest(), profile_identity="standard", selector=selectors[stage], target_refs=["candidate.txt"], fixture_refs=["fixture.txt"])
    try:
        validate_slice_ready(workspace=tmp_path, semantic_plan=semantic, run_root=run, slice_id="S1", snapshot_roots=roots, source_commit="TEST", out=run / "ready.json")
    except ValueError as exc:
        assert "selector identity drifted" in str(exc)
    else:
        raise AssertionError("selector drift should be rejected")
