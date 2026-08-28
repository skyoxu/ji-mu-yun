from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).parent))
import artifact_owners


def test_coverage_owner_computes_run_local_exact_cover(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    (run_root / "semantic-intent-input.v1.json").write_text(json.dumps({"acceptance_ids":["A-SEMANTIC"],"covers_acceptance_ids":["A-SEMANTIC"],"producer":"vdd","coverage":"exact-cover","fixture_class":"positive","taxonomy":["outcome","failure_family","failure_id"],"oracle_id":"semantic-oracle","oracle_class":"contract","test_selector":"tests/semantic.py","subject_role":"sut","required_case_roles":["positive","negative","mutation"],"red_failure_family":"semantic-contract-gap","expected_failure_ids":["VDD-SEMANTIC-MINIMUM-CASES"],"green_expected_observations":["semantic-artifacts.v1.json"],"minimum_executed_cases":3,"independent_judge_required":True,"case_source_refs":["SPEC:FR-1"],"case_producer_ref":"vdd-semantic-fixture-owner","complexity_class":"complex","verification_lane":"self-hosted","context_lookup_required":False,"context_lookup_reason":"repository-owned","minimum_red_scope":"semantic","upgrade_conditions":[]}), encoding="utf-8")
    artifact_owners.compile_run_local_semantic_artifacts(run_root)
    (run_root / "descriptor-input.v1.json").write_text(json.dumps({"descriptor":{"target":"fixture","argv":["py","-3","-c","pass"],"cwd":".","timeout_seconds":30,"shell":False,"case_source_refs":["A-SEMANTIC"],"case_producer_ref":"vdd"}}), encoding="utf-8")
    assert artifact_owners.run(tmp_path, "S2", "green", run_root) == 0
    (run_root / "execution-input.v1.json").write_text(json.dumps({"argv":[sys.executable,"-c","print('judge input')"],"executor_id":"sut-executor","observation_id":"OBS-S4"}), encoding="utf-8")
    assert artifact_owners.run(tmp_path, "S3", "green", run_root) == 0
    (run_root / "coverage-input.v1.json").write_text(json.dumps({"acceptance_ids":["A-SEMANTIC","A-COVER"],"observation_ids":["OBS-S4"],"edges":[{"acceptance_id":"A-SEMANTIC","case_id":"CASE-1","observation_id":"OBS-S4","assertion":"receipt.exit_code == 0"},{"acceptance_id":"A-COVER","case_id":"CASE-1","observation_id":"OBS-S4","assertion":"receipt.exit_code == 0"}]}), encoding="utf-8")
    assert artifact_owners.run(tmp_path, "S4", "green", run_root) == 0, "FAILURE_ID:COVERAGE-PRODUCER-MISSING"
    value = json.loads((run_root / "acceptance-coverage.v1.json").read_text(encoding="utf-8"))
    assert value.get("producer") == "coverage-gate" and value.get("slice_id") == "S4" and value.get("run_id") == run_root.name, "FAILURE_ID:COVERAGE-PRODUCER-MISSING"


def test_coverage_owner_rejects_incomplete_cover(tmp_path: Path) -> None:
    run_root = tmp_path / "run"; run_root.mkdir()
    (run_root / "process-receipt.v1.json").write_text(json.dumps({"producer":"independent-judge","status":"pass","slice_id":"S3","run_id":run_root.name,"evidence_sha256":"sha256:forged"}), encoding="utf-8")
    (run_root / "coverage-input.v1.json").write_text(json.dumps({"acceptance_ids":["A-1"],"observation_ids":["OBS-1"],"edges":[]}), encoding="utf-8")
    assert artifact_owners.run(tmp_path, "S4", "green", run_root) != 0
