"""S1 RED selector for compiler manifest binding."""
import json
from pathlib import Path
from semantic_oracle import compile_run_local_semantic_artifacts

def test_semantic_compiler_binds_active_manifest(tmp_path: Path) -> None:
    intent = {"acceptance_ids":["A-SEMANTIC"],"covers_acceptance_ids":["A-SEMANTIC"],"producer":"vdd","coverage":"exact-cover","fixture_class":"positive","taxonomy":["outcome","failure_family","failure_id"],"oracle_id":"semantic-oracle","oracle_class":"contract","test_selector":"tests/semantic.py","subject_role":"sut","required_case_roles":["positive","negative","mutation"],"red_failure_family":"semantic-contract-gap","expected_failure_ids":["VDD-SEMANTIC-COVERAGE-MISMATCH"],"green_expected_observations":["semantic-artifacts.v1.json"],"minimum_executed_cases":3,"independent_judge_required":True,"case_source_refs":["SPEC:FR-1"],"case_producer_ref":"vdd-semantic-fixture-owner","complexity_class":"complex","verification_lane":"self-hosted","context_lookup_required":False,"context_lookup_reason":"repository-owned","minimum_red_scope":"semantic","upgrade_conditions":[]}
    (tmp_path / "semantic-intent-input.v1.json").write_text(json.dumps(intent), encoding="utf-8")
    (tmp_path / "active-acceptance-manifest.v1.json").write_text(json.dumps({"acceptance_ids":["A-SEMANTIC","A-DESCRIPTOR","A-JUDGE","A-COVER","A-PROMOTION","A-TERMINAL","A-BOUNDARY"]}), encoding="utf-8")
    (tmp_path / "semantic-verification-input.v1.json").write_text(json.dumps({"oracle_id":"A-SEMANTIC","covers_acceptance_ids":["A-SEMANTIC"]}), encoding="utf-8")
    try:
        compile_run_local_semantic_artifacts(tmp_path)
    except ValueError as exc:
        assert str(exc) == "VDD-SEMANTIC-COVERAGE-MISMATCH", f"FAILURE_ID:{exc}"
        return
    raise AssertionError("FAILURE_ID:VDD-SEMANTIC-COVERAGE-MISMATCH")
