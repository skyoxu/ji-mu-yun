from __future__ import annotations

from pathlib import Path
import subprocess
import sys

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from current_router import materialize_descriptor, stop_loss, successor_descriptor
from independent_judge_v2 import judge_receipt
from process_executor_v2 import execute_process
from recovery_resolver import recover_explicit_run
from runtime_evidence import create_json, selector_identity_from_descriptor, sha256_value
from stage_pipeline import validate_nonterminal_successor


def _bundle() -> dict:
    return {"failure_intents":[{"failure_intent_id":"FI-X","failure_family":"expected-red","failure_id":"EXPECTED","acceptance_ids":["A-X"]}],"plan_id":"PLAN-X","acceptances":[{"acceptance_id":"A-X","assertion_ids":["ASSERT-X"]}],"slices":[{"slice_id":"S1","acceptance_ids":["A-X"],"failure_intent_ids":["FI-X"],"execution_snapshot_paths":["tests/selector.py","tests/fixture.txt"],"allowed_write_paths":["src/value.txt"]}]}


def _descriptor(*, run_id: str = "R1", stage: str = "red", argv: list[str] | None = None, timeout_seconds: int = 30) -> dict:
    bundle = _bundle()
    return materialize_descriptor(
        bundle=bundle,
        slice_id="S1",
        stage=stage,
        run_id=run_id,
        candidate_hash="sha256:"+"1"*64,
        argv=argv or [sys.executable,"-m","pytest","tests/selector.py","-q"],
        cwd=".",
        timeout_seconds=timeout_seconds,
        target_refs=["tests/selector.py"],
        fixture_refs=["tests/fixture.txt"],
    )


def _prepare(root: Path, selector_source: str, *, run_ids: tuple[str, ...] = ("R1",)) -> None:
    (root/"tests").mkdir(parents=True)
    for run_id in run_ids:
        (root/"runs"/run_id).mkdir(parents=True)
    (root/"tests"/"fixture.txt").write_text("fixture\n",encoding="utf-8")
    (root/"tests"/"selector.py").write_text("import pytest\npytestmark = pytest.mark.cer_assertion('ASSERT-X')\n" + selector_source,encoding="utf-8")


def _git_init(root: Path) -> None:
    subprocess.run(["git","init"],cwd=root,check=True,capture_output=True,text=True)
    subprocess.run(["git","config","user.email","ch456@example.invalid"],cwd=root,check=True)
    subprocess.run(["git","config","user.name","CH456 Harness"],cwd=root,check=True)
    subprocess.run(["git","add","tests"],cwd=root,check=True)
    subprocess.run(["git","commit","-m","fixture baseline"],cwd=root,check=True,capture_output=True,text=True)


def test_wrong_target_classifies_target_binding(tmp_path: Path) -> None:
    _prepare(tmp_path,"def test_placeholder():\n    assert True\n")
    descriptor = _descriptor()
    descriptor["target_refs"] = ["tests/missing.py"]
    descriptor["acceptance_assertions"][0]["target_ref"] = "tests/missing.py"
    receipt = execute_process(tmp_path,tmp_path/"runs"/"R1","red",descriptor,profile_identity="standard")
    observation = judge_receipt(tmp_path/"runs"/"R1","red",descriptor,receipt,expected_failure_ids=["EXPECTED"])
    assert observation["failure_family"] == "target-binding-failure" and observation["predicate_result"] is False


def test_sut_self_reported_test_counts_are_ignored(tmp_path: Path) -> None:
    _prepare(tmp_path,"print('TEST_EXECUTIONS:999')\nprint('CASES:999')\nprint('FAILURE_ID:EXPECTED')\nraise SystemExit(1)\n")
    descriptor = _descriptor(argv=[sys.executable,"tests/selector.py"])
    receipt = execute_process(tmp_path,tmp_path/"runs"/"R1","red",descriptor,profile_identity="standard")
    observation = judge_receipt(tmp_path/"runs"/"R1","red",descriptor,receipt,expected_failure_ids=["EXPECTED"])
    assert receipt["test_executions"] == 0 and receipt["cases"] == 0
    assert observation["failure_family"] == "test-harness-failure" and observation["predicate_result"] is False


def test_timeout_never_counts_as_red_or_test_failure(tmp_path: Path) -> None:
    _prepare(tmp_path,"import time\ndef test_slow():\n    time.sleep(5)\n    print('FAILURE_ID:EXPECTED')\n    assert False\n")
    descriptor = _descriptor(timeout_seconds=1)
    receipt = execute_process(tmp_path,tmp_path/"runs"/"R1","red",descriptor,profile_identity="standard")
    observation = judge_receipt(tmp_path/"runs"/"R1","red",descriptor,receipt,expected_failure_ids=["EXPECTED"])
    assert receipt["timed_out"] is True and receipt["exit_code"] is None
    assert receipt["test_executions"] == 0 and receipt["cases"] == 0
    assert observation["failure_family"] == "timeout-no-observation" and observation["predicate_result"] is False


def test_pytest_collection_failure_is_harness_failure(tmp_path: Path) -> None:
    _prepare(tmp_path,"import module_that_does_not_exist_ch456\ndef test_never_collected():\n    assert False\n")
    descriptor = _descriptor()
    receipt = execute_process(tmp_path,tmp_path/"runs"/"R1","red",descriptor,profile_identity="standard")
    observation = judge_receipt(tmp_path/"runs"/"R1","red",descriptor,receipt,expected_failure_ids=["EXPECTED"])
    assert receipt["exit_code"] != 0
    assert observation["failure_family"] == "test-harness-failure" and observation["predicate_result"] is False


def test_repo_noise_and_unexpected_green_never_satisfy_red(tmp_path: Path) -> None:
    _prepare(
        tmp_path,
        "from pathlib import Path\ndef test_behavior():\n    root=Path(__file__).resolve().parents[1]\n    (root/'noise.txt').write_text('dirty',encoding='utf-8')\n    print('FAILURE_ID:EXPECTED')\n    assert False\n",
    )
    _git_init(tmp_path)
    descriptor = _descriptor()
    receipt = execute_process(tmp_path,tmp_path/"runs"/"R1","red",descriptor,profile_identity="standard")
    obs = judge_receipt(tmp_path/"runs"/"R1","red",descriptor,receipt,expected_failure_ids=["EXPECTED"])
    assert "noise.txt" in receipt["repo_noise_paths"]
    assert obs["failure_family"] == "repo-noise" and obs["predicate_result"] is False

    root2 = tmp_path/"second"
    _prepare(root2,"def test_behavior():\n    assert True\n")
    descriptor2 = _descriptor()
    receipt2 = execute_process(root2,root2/"runs"/"R1","red",descriptor2,profile_identity="standard")
    obs2 = judge_receipt(root2/"runs"/"R1","red",descriptor2,receipt2,expected_failure_ids=["EXPECTED"])
    assert receipt2["test_executions"] == 1 and receipt2["cases"] == 1
    assert obs2["failure_family"] == "unexpected-green" and obs2["predicate_result"] is False


def test_artifact_integrity_detects_mutated_output(tmp_path: Path) -> None:
    _prepare(tmp_path,"def test_behavior():\n    print('FAILURE_ID:EXPECTED')\n    assert False\n")
    descriptor = _descriptor()
    receipt = execute_process(tmp_path,tmp_path/"runs"/"R1","red",descriptor,profile_identity="standard")
    (tmp_path/"runs"/"R1"/"canonical-evidence"/"red"/"stdout.bin").write_bytes(b"mutated")
    obs = judge_receipt(tmp_path/"runs"/"R1","red",descriptor,receipt,expected_failure_ids=["EXPECTED"])
    assert obs["evidence_state"] == "invalid-run" and obs["failure_family"] == "artifact-integrity"


def test_repeated_deterministic_failure_fingerprint_is_stable_and_stops(tmp_path: Path) -> None:
    _prepare(tmp_path,"def test_behavior():\n    print('FAILURE_ID:EXPECTED')\n    assert False\n",run_ids=("R1","R2"))
    first_descriptor = _descriptor(run_id="R1")
    second_descriptor = _descriptor(run_id="R2")
    first_receipt = execute_process(tmp_path,tmp_path/"runs"/"R1","red",first_descriptor,profile_identity="standard")
    first = judge_receipt(tmp_path/"runs"/"R1","red",first_descriptor,first_receipt,expected_failure_ids=["EXPECTED"])
    second_receipt = execute_process(tmp_path,tmp_path/"runs"/"R2","red",second_descriptor,profile_identity="standard")
    second = judge_receipt(tmp_path/"runs"/"R2","red",second_descriptor,second_receipt,expected_failure_ids=["EXPECTED"])
    assert first["failure_family"] == second["failure_family"] == "expected-red"
    assert first["failure_fingerprint"] == second["failure_fingerprint"]
    assert first["failure_id"] == second["failure_id"]
    decision = stop_loss([first["failure_fingerprint"]], second["failure_fingerprint"])
    assert decision == {"stop":True,"failure_family":"repeated-deterministic-failure","action":"stop"}


def _write_clean_red_predecessor(run: Path, red: dict) -> None:
    root = run.parents[1]
    _prepare(root, "def test_behavior():\n    print('FAILURE_ID:EXPECTED')\n    assert False\n", run_ids=())
    create_json(run/"descriptors"/"red.json",red)
    receipt = execute_process(root, run, "red", red, profile_identity="standard")
    observation = judge_receipt(run, "red", red, receipt, expected_failure_ids=["EXPECTED"])
    assert observation["predicate_result"] is True
    create_json(run/"canonical-evidence"/"red"/"stage-result.v2.json",{
        "schema":"quick-dev.stage-result.v2",
        "plan_id":red["plan_id"],
        "slice_id":red["slice_id"],
        "run_id":red["run_id"],
        "stage":"red",
        "receipt_sha256":sha256_value(receipt),
        "descriptor_sha256":sha256_value(red),
        "selector_identity":selector_identity_from_descriptor(red),
        "predicate_result":True,
        "verification_outcome":"fail",
        "failure_family":"expected-red",
    })


def test_nonterminal_selector_drift_and_red_predecessor_mutation_are_rejected(tmp_path: Path) -> None:
    run=tmp_path/"runs"/"R1"
    (run/"descriptors").mkdir(parents=True)
    red=_descriptor(run_id="R1")
    _write_clean_red_predecessor(run,red)
    green=successor_descriptor(red,stage="green",run_id="R1",candidate_hash="sha256:"+"2"*64)
    binding=validate_nonterminal_successor(run,green)
    assert binding["selector_identity"]==selector_identity_from_descriptor(red)

    drifted=dict(green)
    drifted["argv"]=[sys.executable,"-m","pytest","tests/other.py","-q"]
    try:
        validate_nonterminal_successor(run,drifted)
    except ValueError as exc:
        assert "selector drift" in str(exc)
    else:
        raise AssertionError("GREEN selector drift must be rejected")

    red_path=run/"descriptors"/"red.json"
    red_path.write_text("{}\n",encoding="utf-8")
    try:
        validate_nonterminal_successor(run,green)
    except ValueError:
        pass
    else:
        raise AssertionError("mutated frozen RED descriptor must be rejected")


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
