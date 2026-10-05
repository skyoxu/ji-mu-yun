"""S35 red checks for Matrix Case identity and aggregate completeness gates."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
ENTRY = ROOT / "scripts/sc/skill_package_replay.py"
TARGET = ".agents/skills/run-refactor-implementation-acceptance"
CAPABILITY = "scripts/sc/config/skill-package-validator-capability.v1.json"


def _run_inline_matrix(matrix: dict, virtual_name: str) -> tuple[subprocess.CompletedProcess[str], dict]:
    child = (
        "import json,runpy,sys\n"
        "from pathlib import Path\n"
        "data=sys.stdin.read(); old=Path.read_text; oldb=Path.read_bytes\n"
        f"Path.read_text=lambda p,*a,**k: data if p.name=={virtual_name!r} else old(p,*a,**k)\n"
        f"Path.read_bytes=lambda p,*a,**k: data.encode() if p.name=={virtual_name!r} else oldb(p,*a,**k)\n"
        f"sys.argv=[{str(ENTRY)!r},'replay-matrix','--matrix',{virtual_name!r}]\n"
        "runpy.run_path(sys.argv[0],run_name='__main__')\n"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", child],
        cwd=ROOT,
        input=json.dumps(matrix),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {}
    return result, payload if isinstance(payload, dict) else {}


def _assert_behavior(condition: bool, failure_id: str, message: str) -> None:
    if not condition:
        print(f"FAILURE_ID:{failure_id}")
    assert condition, message


def _case(case_id: str, **extra: object) -> dict:
    value = {
        "case_id": case_id,
        "target": TARGET,
        "capability": CAPABILITY,
        "expected_exit": 0,
    }
    value.update(extra)
    return value


@pytest.mark.cer_assertion("A-DEFC156FA96B-1")
def test_matrix_case_rejects_identical_stable_and_candidate_fixture_state() -> None:
    matrix = {
        "schema_version": "jimuyun.stable-candidate-replay-matrix.v2",
        "authorizes": [],
        "cases": [
            _case(
                "s35-identical-fixture-state",
                fixture_state_assignments={
                    "Stable": {"fixture_id": "fixture-1", "state_id": "state-1"},
                    "Candidate": {"fixture_id": "fixture-1", "state_id": "state-1"},
                },
            )
        ],
    }
    result, payload = _run_inline_matrix(matrix, "s35-identical.json")
    row = (payload.get("case_results") or [{}])[0]
    ok = (
        result.returncode != 0
        and payload.get("aggregate_valid") is False
        and row.get("status") != "pass"
    )
    _assert_behavior(ok, "F-DEFC156FA96B-1", "identical Stable and Candidate fixture-state identities were accepted")


@pytest.mark.cer_assertion("A-DEFC156FA96B-1")
def test_matrix_case_rejects_missing_subject_fixture_state_assignment() -> None:
    matrix = {
        "schema_version": "jimuyun.stable-candidate-replay-matrix.v2",
        "authorizes": [],
        "cases": [
            _case(
                "s35-missing-fixture-state",
                fixture_state_assignments={
                    "Stable": {"fixture_id": "fixture-stable", "state_id": "state-stable"},
                },
            )
        ],
    }
    result, payload = _run_inline_matrix(matrix, "s35-missing.json")
    row = (payload.get("case_results") or [{}])[0]
    ok = (
        result.returncode != 0
        and payload.get("aggregate_valid") is False
        and row.get("status") != "pass"
    )
    _assert_behavior(ok, "F-DEFC156FA96B-2", "Matrix Case missing a subject fixture-state assignment was accepted")


def _six_case_records(count: int) -> list[dict]:
    return [_case(f"matrix-case-{index}") for index in range(1, count + 1)]


@pytest.mark.cer_assertion("A-E9FF07C7AD8D-1")
def test_aggregate_missing_matrix_case_is_invalid_and_lists_missing_case() -> None:
    matrix = {
        "schema_version": "jimuyun.stable-candidate-replay-matrix.v2",
        "authorizes": [],
        "required_matrix_cases": [f"matrix-case-{index}" for index in range(1, 7)],
        "cases": _six_case_records(5),
    }
    result, payload = _run_inline_matrix(matrix, "s35-missing-case.json")
    missing = payload.get("missing_cases")
    ok = (
        result.returncode != 0
        and payload.get("status") == "invalid"
        and payload.get("aggregate_valid") is False
        and isinstance(missing, list)
        and "matrix-case-6" in missing
    )
    _assert_behavior(ok, "FI-E9FF07C7AD8D-1", "missing Matrix Case did not invalidate aggregate with a missing-case list")


def test_canonical_matrix_executes_distinct_stable_and_candidate_fixture_states() -> None:
    matrix = json.loads((ROOT / "execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/stable-candidate-replay-matrix.v1.json").read_text(encoding="utf-8"))
    result, payload = _run_inline_matrix(matrix, "stable-candidate-replay-matrix.v1.json")
    assert result.returncode == 0
    assert payload["aggregate_valid"] is True
    for row in payload["case_results"]:
        assert row["stable_subject"]["target"] != row["candidate_subject"]["target"]
        assert row["stable_subject"]["fixture_identity"] != row["candidate_subject"]["fixture_identity"]
        assert row["stable_subject"]["invocation"]["executed"] is True
        assert row["candidate_subject"]["invocation"]["executed"] is True
@pytest.mark.cer_assertion("SM-3-A1")
def test_six_case_aggregate_missing_execution_is_failed_with_missing_cases() -> None:
    matrix = {
        "schema_version": "jimuyun.stable-candidate-replay-matrix.v2",
        "authorizes": [],
        "required_matrix_cases": [f"matrix-case-{index}" for index in range(1, 7)],
        "cases": _six_case_records(5),
    }
    result, payload = _run_inline_matrix(matrix, "s35-missing-execution.json")
    missing = payload.get("missing_cases")
    ok = (
        result.returncode != 0
        and payload.get("status") == "failed"
        and isinstance(missing, list)
        and "matrix-case-6" in missing
    )
    _assert_behavior(ok, "FI-3EEEFEC1FAFE-MISSING-CASE-GREEN", "partial six-case execution was accepted as a complete aggregate")
