from __future__ import annotations

import json
from pathlib import Path
import sys

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path: sys.path.insert(0, str(TOOLS))

from current_router import materialize_descriptor, successor_descriptor
from recovery_resolver import recover_explicit_run
from runtime_evidence import create_json, execute_process, judge_receipt, selector_identity_from_descriptor, sha256_value


def _bundle() -> dict:
    return {"plan_id":"PLAN-X","acceptances":[{"acceptance_id":"A-X","assertion_ids":["ASSERT-X"]}],"slices":[{"slice_id":"S1","acceptance_ids":["A-X"],"failure_intent_ids":[],"execution_snapshot_paths":["tests/selector.py","tests/fixture.txt"],"allowed_write_paths":["src/value.txt"]}]}


def _descriptor(root: Path, *, run_id: str = "R1", stage: str = "red") -> dict:
    bundle = _bundle()
    return materialize_descriptor(bundle=bundle,slice_id="S1",stage=stage,run_id=run_id,candidate_hash="sha256:"+"1"*64,argv=[sys.executable,"tests/selector.py"],cwd=".",timeout_seconds=5,target_refs=["tests/selector.py"],fixture_refs=["tests/fixture.txt"])


def test_wrong_target_classifies_target_binding(tmp_path: Path) -> None:
    (tmp_path/"tests").mkdir(); (tmp_path/"runs"/"R1").mkdir(parents=True)
    (tmp_path/"tests"/"fixture.txt").write_text("x",encoding="utf-8")
    descriptor = _descriptor(tmp_path); descriptor["target_refs"] = ["tests/missing.py"]; descriptor["acceptance_assertions"][0]["target_ref"] = "tests/missing.py"
    receipt = execute_process(tmp_path,tmp_path/"runs"/"R1","red",descriptor,profile_identity="standard")
    observation = judge_receipt(tmp_path/"runs"/"R1","red",descriptor,receipt,expected_failure_ids=["EXPECTED"])
    assert observation["failure_family"] == "target-binding-failure" and observation["predicate_result"] is False


def test_repo_noise_and_unexpected_green_never_satisfy_red(tmp_path: Path) -> None:
    (tmp_path/"tests").mkdir(); (tmp_path/"runs"/"R1").mkdir(parents=True)
    (tmp_path/"tests"/"fixture.txt").write_text("x",encoding="utf-8")
    (tmp_path/"tests"/"selector.py").write_text("print('TEST_EXECUTIONS:1')\nprint('CASES:1')\nprint('REPO_NOISE: dirty unrelated file')\nprint('FAILURE_ID:EXPECTED')\nraise SystemExit(1)\n",encoding="utf-8")
    descriptor = _descriptor(tmp_path); receipt = execute_process(tmp_path,tmp_path/"runs"/"R1","red",descriptor,profile_identity="standard"); obs = judge_receipt(tmp_path/"runs"/"R1","red",descriptor,receipt,expected_failure_ids=["EXPECTED"])
    assert obs["failure_family"] == "repo-noise" and obs["predicate_result"] is False
    root2 = tmp_path/"second"; (root2/"tests").mkdir(parents=True); (root2/"runs"/"R1").mkdir(parents=True)
    (root2/"tests"/"fixture.txt").write_text("x",encoding="utf-8"); (root2/"tests"/"selector.py").write_text("print('TEST_EXECUTIONS:1')\nprint('CASES:1')\n",encoding="utf-8")
    descriptor2 = _descriptor(root2); receipt2 = execute_process(root2,root2/"runs"/"R1","red",descriptor2,profile_identity="standard"); obs2 = judge_receipt(root2/"runs"/"R1","red",descriptor2,receipt2,expected_failure_ids=["EXPECTED"])
    assert obs2["failure_family"] == "unexpected-green" and obs2["predicate_result"] is False


def test_artifact_integrity_detects_mutated_output(tmp_path: Path) -> None:
    (tmp_path/"tests").mkdir(); (tmp_path/"runs"/"R1").mkdir(parents=True)
    (tmp_path/"tests"/"fixture.txt").write_text("x",encoding="utf-8"); (tmp_path/"tests"/"selector.py").write_text("print('TEST_EXECUTIONS:1')\nprint('CASES:1')\nprint('FAILURE_ID:EXPECTED')\nraise SystemExit(1)\n",encoding="utf-8")
    descriptor = _descriptor(tmp_path); receipt = execute_process(tmp_path,tmp_path/"runs"/"R1","red",descriptor,profile_identity="standard")
    (tmp_path/"runs"/"R1"/"canonical-evidence"/"red"/"stdout.bin").write_bytes(b"mutated")
    obs = judge_receipt(tmp_path/"runs"/"R1","red",descriptor,receipt,expected_failure_ids=["EXPECTED"])
    assert obs["evidence_state"] == "invalid-run" and obs["failure_family"] == "artifact-integrity"


def test_nonterminal_selector_drift_is_rejected() -> None:
    descriptor = {"run_id":"R1","plan_id":"PLAN-X","slice_id":"S1","stage":"red","candidate_hash":"sha256:"+"1"*64,"argv":[sys.executable,"tests/a.py"],"cwd":".","shell":False,"timeout_seconds":5,"target_refs":["tests/a.py"],"fixture_refs":["tests/f.txt"],"acceptance_assertions":[{"acceptance_id":"A-X","assertion_id":"ASSERT-X","case_source_ref":"tests/a.py","target_ref":"tests/a.py","fixture_ref":"tests/f.txt"}]}
    green = successor_descriptor(descriptor,stage="green",run_id="R2",candidate_hash="sha256:"+"2"*64)
    assert selector_identity_from_descriptor(green) == selector_identity_from_descriptor(descriptor)
    descriptor["argv"] = [sys.executable,"tests/other.py"]
    try:
        successor_descriptor(descriptor,stage="green",run_id="R3",candidate_hash="sha256:"+"3"*64)
    except ValueError:
        pass


def test_recovery_reads_only_explicit_run_and_rejects_stale_hash(tmp_path: Path) -> None:
    run = tmp_path/"R-good"; (run/"e").mkdir(parents=True)
    candidate = "sha256:"+"1"*64; selector = "selector-x"; receipt = {"schema":"quick-dev.process-receipt.v2","stage":"green","candidate_hash":candidate}; receipt_sha = sha256_value(receipt)
    observation = {"schema":"quick-dev.observation.v2","stage":"green","evidence_state":"observed-run","verification_outcome":"pass","receipt_sha256":receipt_sha,"failure_family":None,"failure_id":None}; obs_sha = sha256_value(observation)
    edge = {"slice_id":"S1","run_id":"R-good","stage":"green","candidate_hash":candidate,"selector_identity":selector,"receipt_sha256":receipt_sha,"observation_sha256":obs_sha,"acceptance_id":"A-X","assertion_id":"ASSERT-X","predicate_result":True,"observed":True}; edge_sha = sha256_value(edge)
    create_json(run/"e"/"receipt.json",receipt); create_json(run/"e"/"observation.json",observation); create_json(run/"e"/"edge.json",edge)
    malicious = tmp_path/"R-newer"; malicious.mkdir(); (malicious/"latest-success.json").write_text("{}",encoding="utf-8")
    recovery_input = {"schema":"quick-dev.recovery-input.v1","slice_id":"S1","run_id":"R-good","stage":"green","candidate_hash":candidate,"selector_identity":selector,"receipt_ref":"e/receipt.json","receipt_sha256":receipt_sha,"observation_ref":"e/observation.json","observation_sha256":obs_sha,"runtime_edges":[{"ref":"e/edge.json","sha256":edge_sha}],"current_snapshot_sha256":"sha256:"+"a"*64}
    recovered = recover_explicit_run(run_root=run,recovery_input=recovery_input)
    assert recovered["source_run_id"] == "R-good" and recovered["reclassified"] is False
    recovery_input["receipt_sha256"] = "sha256:"+"b"*64
    try:
        recover_explicit_run(run_root=run,recovery_input=recovery_input)
    except ValueError as exc:
        assert "receipt" in str(exc)
    else:
        raise AssertionError("stale recovery receipt must fail")
