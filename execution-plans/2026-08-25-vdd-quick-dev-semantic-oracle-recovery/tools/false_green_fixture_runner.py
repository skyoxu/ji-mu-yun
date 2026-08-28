"""Independent false-green fixture cases for the promotion gate."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from coverage_gate import validate_many_to_many_cover
from descriptor_compiler import validate_descriptor
from independent_judge import validate_judge
from promotion_gate import validate_promotion
from semantic_oracle import validate_semantic_intent


def _blocked(fixture_id: str) -> bool:
    valid_manifest = {"acceptance_ids":["A"],"covers_acceptance_ids":["A"],"producer":"vdd","coverage":"exact-cover","fixture_class":"positive","taxonomy":["outcome","failure_family","failure_id"],"oracle_id":"oracle","oracle_class":"contract","test_selector":"test","subject_role":"sut","required_case_roles":["positive","negative","mutation"],"red_failure_family":"gap","expected_failure_ids":["X"],"green_expected_observations":["x"],"minimum_executed_cases":1,"independent_judge_required":True,"case_source_refs":["SPEC:X"],"case_producer_ref":"owner","complexity_class":"complex","verification_lane":"self-hosted","context_lookup_required":False,"context_lookup_reason":"owned","minimum_red_scope":"semantic","upgrade_conditions":[]}
    cases = {
        "FG-01": lambda: validate_semantic_intent({**valid_manifest, "case_source_refs": []})[0],
        "FG-02": lambda: validate_descriptor({"target":"x","argv":["py"],"cwd":".","timeout_seconds":1,"shell":True,"case_source_refs":["A"],"case_producer_ref":"vdd"})[0],
        "FG-03": lambda: validate_descriptor({"target":"x","argv":["py"],"cwd":".","timeout_seconds":1,"shell":False,"case_source_refs":[],"case_producer_ref":"vdd"})[0],
        "FG-04": lambda: validate_judge({"executor_id":"sut","judge_id":"sut","descriptor_hash":"sha256:x","candidate_hash":"sha256:y","run_id":"R","exit_code":0,"actual_argv":["py"]},{"run_id":"R","descriptor_argv":["py"],"executions":1})[0],
        "FG-05": lambda: validate_judge({"executor_id":"sut","judge_id":"judge","descriptor_hash":"sha256:x","candidate_hash":"sha256:y","run_id":"R","exit_code":0,"actual_argv":["py"]},{"run_id":"R","descriptor_argv":["py"],"expected_exit":"nonzero","executions":0})[0],
        "FG-06": lambda: validate_many_to_many_cover([], {"A"}, set())[0],
        "FG-07": lambda: validate_many_to_many_cover([{"acceptance_id":"A","case_id":"C","observation_id":"OBS-1"}], {"A"}, {"OBS-1"})[0],
        "FG-08": lambda: validate_promotion([], "sha256:judge", "coverage-gate")[0],
        "FG-09": lambda: validate_promotion([{ "fixture_id": f"FG-{i:02d}", "blocked": True, "corrected_pair_pass": True } for i in range(1, 9)], "sha256:judge", "coverage-gate")[0],
    }
    return cases[fixture_id]()


def main() -> int:
    fixture_id, variant = sys.argv[1:3]
    rejected = not _blocked(fixture_id)
    if variant == "blocked":
        return 1 if rejected else 0
    return 0 if rejected else 1


if __name__ == "__main__":
    raise SystemExit(main())
