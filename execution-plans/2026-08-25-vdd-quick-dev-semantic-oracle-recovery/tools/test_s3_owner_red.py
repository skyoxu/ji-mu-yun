from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).parent))
import artifact_owners


def test_judge_owner_executes_and_writes_independent_receipt(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    (run_root / "semantic-intent-input.v1.json").write_text(json.dumps({"acceptance_ids":["A-SEMANTIC"],"producer":"vdd","coverage":"exact-cover","fixture_class":"positive","taxonomy":["semantic"]}), encoding="utf-8")
    artifact_owners.compile_run_local_semantic_artifacts(run_root)
    (run_root / "descriptor-input.v1.json").write_text(json.dumps({"descriptor":{"target":"fixture","argv":["py","-3","-c","pass"],"cwd":".","timeout_seconds":30,"shell":False,"case_source_refs":["A-SEMANTIC"],"case_producer_ref":"vdd"}}), encoding="utf-8")
    assert artifact_owners.run(tmp_path, "S2", "green", run_root) == 0
    (run_root / "execution-input.v1.json").write_text(json.dumps({"argv":[sys.executable,"-c","print('judge input')"],"executor_id":"sut-executor","observation_id":"OBS-S3"}), encoding="utf-8")
    assert artifact_owners.run(tmp_path, "S3", "green", run_root) == 0, "FAILURE_ID:JUDGE-PRODUCER-MISSING"
    value = json.loads((run_root / "process-receipt.v1.json").read_text(encoding="utf-8"))
    assert value.get("producer") == "independent-judge" and value.get("slice_id") == "S3" and value.get("run_id") == run_root.name, "FAILURE_ID:JUDGE-PRODUCER-MISSING"


def test_judge_owner_rejects_non_executable_input(tmp_path: Path) -> None:
    run_root = tmp_path / "run"; run_root.mkdir()
    (run_root / "execution-descriptor.v1.json").write_text(json.dumps({"producer":"quick-dev","status":"pass","slice_id":"S2","run_id":run_root.name,"evidence_sha256":"sha256:forged"}), encoding="utf-8")
    (run_root / "execution-input.v1.json").write_text(json.dumps({"argv":"not-an-argv"}), encoding="utf-8")
    assert artifact_owners.run(tmp_path, "S3", "green", run_root) != 0
