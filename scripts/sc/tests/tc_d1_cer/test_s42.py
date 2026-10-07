"""S42 matrix checks for six distinct input executions."""
from __future__ import annotations

import json
import copy
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.sc import skill_replay_runtime as runtime

_CER_ASSERTION_BINDINGS = [
    pytest.mark.cer_assertion("A-70341EC7ADE8-1"),
    pytest.mark.cer_assertion("A-7051147536AB-1"),
    pytest.mark.cer_assertion("A-FR4-ASF-1"),
    pytest.mark.cer_assertion("FR5-PATH-MEMBERSHIP"),
]


ROOT = Path(__file__).resolve().parents[4]
ENTRY = ROOT / "scripts/sc/skill_package_replay.py"
TARGET = ".agents/skills/run-refactor-implementation-acceptance"
CAPABILITY = "scripts/sc/config/skill-package-validator-capability.v1.json"


@pytest.mark.cer_assertion("A-FR4-ASF-1")
def test_s42_always_success_validator_is_rejected() -> None:
    """Bind S42's FR-4 assertion to the real replay negative control."""
    from scripts.sc.tests.tc_d1_cer.test_s10 import (
        test_always_success_validator_is_reported_as_a_failed_probe_outcome,
    )
    test_always_success_validator_is_reported_as_a_failed_probe_outcome()


@pytest.mark.cer_assertion("A-70341EC7ADE8-1")
def test_s42_historical_membership_changes_are_rejected() -> None:
    """Bind the historical membership assertion to the real Git snapshot test."""
    from scripts.sc.tests.tc_d1_cer.test_s32_cer import (
        test_repository_relative_path_membership_is_preserved_or_rejected,
    )
    for mutation in ("unchanged", "added", "deleted", "renamed"):
        test_repository_relative_path_membership_is_preserved_or_rejected(mutation)


def _run_matrix(cases: list[dict]) -> tuple[int, dict]:
    matrix = {"schema_version": "jimuyun.stable-candidate-replay-matrix.v2", "cases": cases, "authorizes": []}
    child = (
        "import json, runpy, sys\n"
        "from pathlib import Path\n"
        "payload = sys.stdin.read()\n"
        "original_text, original_bytes = Path.read_text, Path.read_bytes\n"
        "def fixture_text(path, *args, **kwargs):\n"
        "    return payload if path.name == 's42-matrix.json' else original_text(path, *args, **kwargs)\n"
        "def fixture_bytes(path, *args, **kwargs):\n"
        "    return payload.encode('utf-8') if path.name == 's42-matrix.json' else original_bytes(path, *args, **kwargs)\n"
        "Path.read_text, Path.read_bytes = fixture_text, fixture_bytes\n"
        "sys.argv = [sys.argv[1], 'replay-matrix', '--matrix', 's42-matrix.json']\n"
        "runpy.run_path(sys.argv[0], run_name='__main__')\n"
    )
    process = runtime.capture_process([sys.executable, '-B', '-c', child, str(ENTRY)], ROOT, timeout=90, input_data=(json.dumps(matrix)).encode("utf-8"))
    try:
        receipt = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"Matrix entry did not return JSON: {exc}; stderr={process.stderr[:500]}")
    if not isinstance(receipt, dict):
        pytest.fail("Matrix entry did not return an object")
    return process.returncode, receipt


def _case(case_id: str, input_id: str) -> dict:
    return {"case_id": case_id, "target": TARGET, "capability": CAPABILITY, "expected_exit": 0,
            "matrix_input": {"input_id": input_id, "case_payload": f"payload-{input_id}"}}


def _assert_behavior(condition: bool, failure_id: str, detail: object) -> None:
    if not condition:
        print(f"FAILURE_ID:{failure_id}")
    assert condition, detail


def _six_cases(input_ids: list[str]) -> list[dict]:
    return [_case(f"case-{index}", value) for index, value in enumerate(input_ids, start=1)]


@pytest.mark.cer_assertion("A-7817-distinct-inputs")
def test_six_matrix_cases_require_distinct_recorded_inputs_and_both_subjects(native_skill_replay_matrix) -> None:
    matrix, receipt = native_skill_replay_matrix
    rows = receipt.get("case_results") or []
    recorded = [row.get("fixture") for row in matrix["cases"]]
    subjects_complete = all(
        {entry.get("subject") for entry in row.get("subject_executions", [])} == {"Stable", "Candidate"}
        and all(entry.get("executed") is True for entry in row.get("subject_executions", [])) for row in rows
    )
    _assert_behavior(
        receipt.get("status") == "pass" and len(rows) == 6
        and all(isinstance(item, dict) and item.get("sha256") for item in recorded)
        and len({item["sha256"] for item in recorded}) == 6 and subjects_complete,
        "F-7817-MISSING-OR-DUPLICATE-INPUT", receipt,
    )


@pytest.mark.cer_assertion("A-7817-distinct-inputs")
@pytest.mark.cer_assertion("A-7051147536AB-1")
def test_duplicate_matrix_input_rejects_six_case_aggregate(native_skill_replay_matrix, native_matrix_rejection) -> None:
    matrix, control = native_skill_replay_matrix
    fault = copy.deepcopy(matrix)
    first, second = fault["cases"][2:4]
    second["fixture"] = copy.deepcopy(first["fixture"])
    code, receipt = native_matrix_rejection(fault)
    rows = receipt.get("case_results") or []
    reasons = " ".join(str(row.get("rejection_reason", "")) for row in rows).lower()
    _assert_behavior(
        code != 0 and receipt.get("status") != "pass" and receipt.get("aggregate_valid") is False
        and "duplicate" in reasons and first["case_id"] in reasons and second["case_id"] in reasons
        and all(row.get("executed") is False for row in rows)
        and control.get("status") == "pass" and all(row.get("executed") is True for row in control["case_results"]),
        "F-7817-MISSING-OR-DUPLICATE-INPUT", receipt,
    )
