"""S27 bounded checks for repair evidence integrity and matrix attribution."""
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
MATRIX = ROOT / "execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/stable-candidate-replay-matrix.v1.json"


def _run_matrix(matrix_argument: str) -> tuple[subprocess.CompletedProcess[str], dict]:
    result = subprocess.run(
        [sys.executable, "-B", str(ENTRY), "replay-matrix", "--matrix", matrix_argument],
        cwd=ROOT,
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


def _run_inline_matrix(matrix: dict, virtual_name: str) -> tuple[subprocess.CompletedProcess[str], dict]:
    child = (
        "import runpy,sys\n"
        "from pathlib import Path\n"
        "data=sys.stdin.read(); old=Path.read_text; oldb=Path.read_bytes\n"
        f"Path.read_text=lambda p,*a,**k: data if p.name=={virtual_name!r} else old(p,*a,**k)\n"
        f"Path.read_bytes=lambda p,*a,**k: data.encode() if p.name=={virtual_name!r} else oldb(p,*a,**k)\n"
        f"sys.argv=['{ENTRY.as_posix()}','replay-matrix','--matrix',{virtual_name!r}]\n"
        "runpy.run_path(sys.argv[0], run_name='__main__')\n"
    )
    result = subprocess.run([sys.executable, "-B", "-c", child], cwd=ROOT, input=json.dumps(matrix), capture_output=True, text=True, encoding="utf-8", check=False)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {}
    return result, payload if isinstance(payload, dict) else {}


def _assert_behavior(condition: bool, failure_id: str, message: str) -> None:
    if not condition:
        print(f"FAILURE_ID:{failure_id}")
    assert condition, message


@pytest.mark.cer_assertion("A-8A9DD7306479-1")
def test_repair_evidence_keeps_frozen_target_identity_unchanged() -> None:
    matrix = {
        "schema_version": "jimuyun.stable-candidate-replay-matrix.v2",
        "authorizes": [],
        "cases": [{"case_id": "s27-integrity", "target": TARGET, "capability": CAPABILITY, "expected_exit": 0}],
    }
    result, payload = _run_inline_matrix(matrix, "s27-integrity.json")
    row = (payload.get("case_results") or [{}])[0]
    stable = row.get("stable_subject") or {}
    ok = result.returncode == 0 and payload.get("aggregate_valid") is True and stable.get("pre_identity") == stable.get("post_identity")
    _assert_behavior(ok, "F-8A9DD7306479-1", "frozen target identity changed during repair evidence capture")


@pytest.mark.cer_assertion("A-8A9DD7306479-1")
def test_repair_evidence_rejects_target_outside_declared_boundary() -> None:
    matrix = {
        "schema_version": "jimuyun.stable-candidate-replay-matrix.v2",
        "authorizes": [],
        "cases": [{"case_id": "s27-boundary", "target": "../outside", "capability": CAPABILITY, "expected_exit": 0}],
    }
    result, _ = _run_inline_matrix(matrix, "s27-boundary.json")
    _assert_behavior(result.returncode != 0, "F-8A9DD7306479-2", "out-of-bound repair target was accepted")


@pytest.mark.cer_assertion("A-FR7-ATTR-1")
def test_all_matrix_cases_record_stable_and_candidate_attribution() -> None:
    result, payload = _run_matrix(MATRIX.relative_to(ROOT).as_posix())
    rows = payload.get("case_results") or []
    ok = (
        result.returncode == 0
        and len(rows) == 6
        and all(
            [entry.get("subject") for entry in (row.get("subject_executions") or [])] == ["Stable", "Candidate"]
            and all(entry.get("executed") is True and entry.get("subject") in {"Stable", "Candidate"} for entry in row.get("subject_executions") or [])
            for row in rows
        )
    )
    _assert_behavior(ok, "FI-FR7-ATTR-MISSING", "matrix execution evidence lacks complete Stable/Candidate attribution")


@pytest.mark.cer_assertion("A-FR7-ATTR-1")
def test_matrix_rejects_missing_execution_evidence() -> None:
    matrix = {
        "schema_version": "jimuyun.stable-candidate-replay-matrix.v2",
        "authorizes": [],
        "cases": [{"case_id": "s27-missing", "target": TARGET, "capability": CAPABILITY, "expected_exit": 0, "matrix_evidence": []}],
    }
    result, payload = _run_inline_matrix(matrix, "s27-missing.json")
    row = (payload.get("case_results") or [{}])[0]
    ok = result.returncode != 0 and payload.get("aggregate_valid") is False and row.get("rejection_reason") == "required matrix evidence is missing"
    _assert_behavior(ok, "FI-FR7-ATTR-MISSING", "missing matrix execution evidence was accepted")
