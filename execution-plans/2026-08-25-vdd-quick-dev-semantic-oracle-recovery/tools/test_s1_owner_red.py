from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
import semantic_oracle


def test_vdd_owner_compiles_run_local_semantic_artifacts(tmp_path: Path) -> None:
    compiler = getattr(semantic_oracle, "compile_run_local_semantic_artifacts", None)
    assert callable(compiler), "FAILURE_ID:VDD-SEMANTIC-PRODUCER-MISSING"
    try:
        (tmp_path / "semantic-intent-input.v1.json").write_text('{"acceptance_ids":["A-SEMANTIC"],"covers_acceptance_ids":["A-SEMANTIC"],"producer":"vdd","coverage":"exact-cover","fixture_class":"positive","taxonomy":["outcome","failure_family","failure_id"],"oracle_id":"semantic-oracle","oracle_class":"contract","test_selector":"tests/semantic.py","subject_role":"sut","required_case_roles":["positive","negative","mutation"],"red_failure_family":"semantic-contract-gap","expected_failure_ids":["VDD-SEMANTIC-MINIMUM-CASES"],"green_expected_observations":["semantic-artifacts.v1.json"],"minimum_executed_cases":3,"independent_judge_required":true,"case_source_refs":["SPEC:FR-1","SPEC:FR-2","SPEC:FR-10"],"case_producer_ref":"vdd-semantic-fixture-owner","complexity_class":"complex","verification_lane":"self-hosted","context_lookup_required":false,"context_lookup_reason":"repository-owned","minimum_red_scope":"semantic","upgrade_conditions":[]}\n', encoding="utf-8")
        result = compiler(tmp_path)
    except (FileNotFoundError, ValueError) as exc:
        assert False, f"FAILURE_ID:VDD-SEMANTIC-PRODUCER-MISSING ({exc})"
    assert isinstance(result, dict) and result.get("producer") == "vdd" and result.get("status") == "pass" and result.get("run_id") == tmp_path.name, "FAILURE_ID:VDD-SEMANTIC-PRODUCER-MISSING"
