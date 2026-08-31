from __future__ import annotations

import json
from pathlib import Path
import sys

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from current_lifecycle import (
    STAGES, current_snapshot, execute_stage, publish_terminal,
    sha256_value,
)


def digest(char: str = "a") -> str:
    return "sha256:" + char * 64


def bundle() -> dict:
    return {
        "schema_version": "vdd.semantic-plan-bundle.v1", "plan_id": "P1",
        "acceptances": [{"acceptance_id": "A-ONE", "assertion_ids": ["AS-1"]}],
        "failure_intents": [{"failure_intent_id": "FI-ONE", "failure_id": "EXPECTED-RED"}],
        "slices": [{"slice_id": "S1", "acceptance_ids": ["A-ONE"], "failure_intent_ids": ["FI-ONE"]}],
        "final_plan_coverage": [{"slice_id": "S1", "acceptance_id": "A-ONE", "stage_scope": list(STAGES)}],
    }


def descriptor(script: str, name: str) -> dict:
    return {"id": name, "executable": sys.executable, "argv": ["-c", script], "cwd": ".", "timeout_seconds": 10, "shell": False}


def prepare_files(root: Path) -> tuple[Path, list[dict[str, str]]]:
    for name in ("candidate.txt", "contract.json", "fixture.txt", "source.txt", "validator.py", "transition.json"):
        (root / name).write_text(name, encoding="utf-8")
    (root / "plan").mkdir()
    (root / "plan/semantic.json").write_text(json.dumps(bundle()), encoding="utf-8")
    (root / "descriptors").mkdir()
    roots = [
        ("candidate_tree", "candidate.txt"), ("plan", "plan"), ("contract", "contract.json"),
        ("descriptor", "descriptors"), ("fixture", "fixture.txt"), ("source", "source.txt"),
        ("validator_judge", "validator.py"), ("plan_state_transition", "transition.json"),
    ]
    return root / "plan/semantic.json", [{"root_kind": kind, "repository_relative_posix_path": path, "inclusion_reason": "test"} for kind, path in roots]


def test_timeout_does_not_fake_case_count(tmp_path: Path) -> None:
    semantic, _ = prepare_files(tmp_path)
    path = tmp_path / "descriptors/red.json"
    path.write_text(json.dumps(descriptor("import time; time.sleep(2)", "red")), encoding="utf-8")
    value = json.loads(path.read_text(encoding="utf-8")); value["timeout_seconds"] = 1; path.write_text(json.dumps(value), encoding="utf-8")
    try:
        execute_stage(workspace=tmp_path, semantic_plan=semantic, slice_id="S1", run_dir=tmp_path / "RUN-TIMEOUT", stage="red", descriptor_path=path, candidate_hash=digest(), profile_identity="standard", selector="tests/test_one.py", target_refs=["candidate.txt"], fixture_refs=["fixture.txt"])
    except RuntimeError:
        pass
    receipt = json.loads((tmp_path / "RUN-TIMEOUT/canonical-evidence/red/process-receipt.v2.json").read_text(encoding="utf-8"))
    assert receipt["timed_out"] is True
    assert receipt["test_executions"] == 0
    assert receipt["cases"] == 0


def test_terminal_rereads_complete_runtime_closure(tmp_path: Path) -> None:
    semantic, roots = prepare_files(tmp_path)
    run = tmp_path / "RUN-1"
    tuples = []
    descriptors = {}
    for stage in STAGES:
        script = "print('FAILURE_ID:EXPECTED-RED'); raise SystemExit(1)" if stage == "red" else "print('1 passed')"
        path = tmp_path / f"descriptors/{stage}.json"
        path.write_text(json.dumps(descriptor(script, stage)), encoding="utf-8")
        descriptors[stage] = path
        result = execute_stage(workspace=tmp_path, semantic_plan=semantic, slice_id="S1", run_dir=run, stage=stage, descriptor_path=path, candidate_hash=digest(), profile_identity="standard", selector="tests/test_one.py", target_refs=["candidate.txt"], fixture_refs=["fixture.txt"])
        edge_ref = result["runtime_edges"][0]
        tuples.append({
            "tuple_key": f"S1|A-ONE|{stage}", "slice_id": "S1", "acceptance_id": "A-ONE", "stage": stage,
            "runtime_edge_ref": edge_ref["path"], "runtime_edge_sha256": edge_ref["sha256"],
            "selector_identity": result["selector_identity"], "current_snapshot_sha256": "pending",
        })
    snapshot = current_snapshot(tmp_path, roots, source_commit="TEST")
    for item in tuples:
        item["current_snapshot_sha256"] = snapshot["sha256"]
    result = publish_terminal(workspace=tmp_path, semantic_plan=semantic, run_root=run, runtime_tuples=tuples, snapshot_roots=roots, source_commit="TEST", terminal_descriptor=descriptors["terminal"], terminal_stage_result=run / "canonical-evidence/terminal/stage-result.v2.json", out=run / "implementation-complete-result.v2.json")
    assert result["status"] == "pass"
    assert result["predicate"] == "implementation-complete"


def test_current_snapshot_rejects_governance_root(tmp_path: Path) -> None:
    _, roots = prepare_files(tmp_path)
    roots[0] = {"root_kind": "registry", "repository_relative_posix_path": "candidate.txt", "inclusion_reason": "bad"}
    try:
        current_snapshot(tmp_path, roots, source_commit="TEST")
    except ValueError as exc:
        assert "not runtime authority" in str(exc)
    else:
        raise AssertionError("governance root should be rejected")
