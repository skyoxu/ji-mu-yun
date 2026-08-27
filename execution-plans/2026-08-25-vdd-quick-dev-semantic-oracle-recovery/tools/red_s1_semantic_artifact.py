"""S1 semantic contract cases; the positive case is intentionally RED pre-implementation."""
from pathlib import Path
import json
import os
import sys

sys.path.insert(0, str(Path(__file__).parent))
from semantic_oracle import compile_run_local_semantic_artifacts, validate_semantic_intent


def test_semantic_positive_compiles_complete_verification_artifact(tmp_path: Path) -> None:
    run_root = os.environ.get("QD_RUN_ROOT")
    if run_root:
        root = Path(run_root)
        assert (root / "semantic-artifacts.v1.json").is_file() and (root / "implementation-successor.v1.json").is_file(), "FAILURE_ID:VDD-SEMANTIC-ARTIFACT-SET-INCOMPLETE"
        return
    root = Path(run_root) if run_root else tmp_path
    root.mkdir(parents=True, exist_ok=True)
    intent = {"acceptance_ids": ["A-SEMANTIC"], "producer": "vdd", "coverage": "exact-cover", "fixture_class": "positive", "taxonomy": ["outcome", "failure_family", "failure_id"], "case_source_refs": ["SPEC:FR-1", "SPEC:FR-10"], "case_producer_ref": "vdd-semantic-fixture-owner"}
    (root / "semantic-intent-input.v1.json").write_text(json.dumps(intent) + "\n", encoding="utf-8")
    result = compile_run_local_semantic_artifacts(root)
    failure_id = "VDD-SEMANTIC-ARTIFACT-SET-INCOMPLETE"
    print(f"FAILURE_ID:{failure_id}")
    assert (root / "implementation-successor.v1.json").is_file() and {"semantic_verification", "verification_cases"}.issubset(result), f"FAILURE_ID:{failure_id}"
    assert all({"outcome", "failure_family", "failure_id", "evidence_state"}.issubset(case) for case in result["verification_cases"]), "FAILURE_ID:VDD-SEMANTIC-ARTIFACT-SET-INCOMPLETE"


def test_semantic_negative_rejects_downstream_execution_fields() -> None:
    accepted, failure_id = validate_semantic_intent({"acceptance_ids": ["A-SEMANTIC"], "producer": "vdd", "coverage": "exact-cover", "fixture_class": "negative", "taxonomy": ["semantic"], "executable": "pytest", "argv": []})
    assert not accepted and failure_id == "VDD-RED-BOUNDARY"


def test_semantic_mutation_rejects_missing_taxonomy() -> None:
    accepted, failure_id = validate_semantic_intent({"acceptance_ids": ["A-SEMANTIC"], "producer": "vdd", "coverage": "exact-cover", "fixture_class": "mutation", "taxonomy": []})
    assert not accepted and failure_id == "VDD-RED-BOUNDARY"
