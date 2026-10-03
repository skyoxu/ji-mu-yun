"""S31 CER checks for non-executed matrix evidence and Consumer route identity."""
from __future__ import annotations

import json
import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

_CER_ASSERTION_BINDINGS = [
    pytest.mark.cer_assertion("A-VERDICT-REAL-EXECUTION"),
    pytest.mark.cer_assertion("A-VERDICT-SOURCE-IDENTITY-TRACE"),
]


ROOT = Path(__file__).resolve().parents[4]
ENTRY = ROOT / "scripts" / "sc" / "skill_package_replay.py"
TARGET = ".agents/skills/run-refactor-implementation-acceptance"
CAPABILITY = "scripts/sc/config/skill-package-validator-capability.v1.json"
SOURCE_PATH = ENTRY.relative_to(ROOT).as_posix()
CURRENT_SOURCE = {
    "path": SOURCE_PATH,
    "sha256": "sha256:" + hashlib.sha256(ENTRY.read_bytes()).hexdigest(),
}


def _run_inline_matrix(matrix: dict) -> tuple[int, dict]:
    child = (
        "import runpy,sys\n"
        "from pathlib import Path\n"
        "payload=sys.stdin.read(); old=Path.read_text; oldb=Path.read_bytes\n"
        "Path.read_text=lambda p,*a,**k: payload if p.name=='s31-matrix.json' else old(p,*a,**k)\n"
        "Path.read_bytes=lambda p,*a,**k: payload.encode('utf-8') if p.name=='s31-matrix.json' else oldb(p,*a,**k)\n"
        f"sys.argv=['{ENTRY.as_posix()}','replay-matrix','--matrix','s31-matrix.json']\n"
        "runpy.run_path(sys.argv[0], run_name='__main__')\n"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", child],
        cwd=ROOT,
        input=json.dumps(matrix),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"Matrix entry did not return JSON: {exc}; stderr={result.stderr[:500]}")
    if not isinstance(payload, dict):
        pytest.fail("Matrix entry did not return an object")
    return result.returncode, payload


def _run_replay(mode: str) -> tuple[int, dict]:
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(ENTRY),
            "replay-package",
            "--target",
            TARGET,
            "--capability",
            CAPABILITY,
            "--probe-mode",
            mode,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"Replay entry did not return JSON: {exc}; stderr={result.stderr[:500]}")
    if not isinstance(payload, dict):
        pytest.fail("Replay entry did not return an object")
    return result.returncode, payload


def _run_identity_matrix(case: dict) -> tuple[int, dict]:
    matrix = {
        "schema_version": "jimuyun.stable-candidate-replay-matrix.v2",
        "authorizes": [],
        "cases": [case],
    }
    child = (
        "import runpy,sys\n"
        "from pathlib import Path\n"
        "payload=sys.stdin.read(); old=Path.read_text; oldb=Path.read_bytes\n"
        "Path.read_text=lambda p,*a,**k: payload if p.name=='s31-identity-matrix.json' else old(p,*a,**k)\n"
        "Path.read_bytes=lambda p,*a,**k: payload.encode('utf-8') if p.name=='s31-identity-matrix.json' else oldb(p,*a,**k)\n"
        f"sys.argv=['{ENTRY.as_posix()}','replay-matrix','--matrix','s31-identity-matrix.json']\n"
        "runpy.run_path(sys.argv[0], run_name='__main__')\n"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", child], cwd=ROOT,
        input=json.dumps(matrix), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=60, check=False,
    )
    try:
        receipt = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"Replay entry did not return JSON: {exc}; stderr={result.stderr[:500]}")
    return result.returncode, receipt


def _assert_behavior(condition: bool, failure_id: str, detail: object) -> None:
    if not condition:
        print(f"FAILURE_ID:{failure_id}")
    assert condition, detail


@pytest.mark.cer_assertion("A-VERDICT-REAL-EXECUTION")
def test_verdict_binds_current_source_identity_to_real_execution_command() -> None:
    result = subprocess.run(
        [sys.executable, "-B", str(ENTRY), "replay-package",
         "--target", TARGET, "--capability", CAPABILITY,
         "--probe-mode", "source-identity"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=60, check=False,
    )
    receipt = json.loads(result.stdout)
    replay = receipt.get("current_wrapper_replay") or {}
    snapshot = replay.get("current_snapshot") or {}
    roots = snapshot.get("roots") or []
    source = next((row for row in roots if isinstance(row, dict) and row.get("root_kind") == "source"), {})
    command = replay.get("command") or []
    probes = replay.get("probes") or []
    _assert_behavior(
        result.returncode == 0
        and receipt.get("status") == "pass"
        and source.get("path") == SOURCE_PATH
        and source.get("sha256") == CURRENT_SOURCE["sha256"]
        and snapshot.get("complete") is True
        and command[3:5] == [SOURCE_PATH, "replay-package"]
        and replay.get("command_verification", {}).get("command") == command
        and replay.get("fresh_process") is True
        and len(probes) == 2
        and all(isinstance(row.get("process", {}).get("pid"), int) for row in probes),
        "A-VERDICT-REAL-EXECUTION",
        "verdict must bind current source identity to a real command execution",
    )


@pytest.mark.parametrize(
    "case",
    [
        pytest.param({"source_identity": None, "execution_evidence": None}, id="missing", marks=pytest.mark.cer_assertion("A-VERDICT-SOURCE-IDENTITY-TRACE")),
        pytest.param({"source_identity": CURRENT_SOURCE, "execution_evidence": None}, id="missing-execution", marks=pytest.mark.cer_assertion("A-VERDICT-REAL-EXECUTION")),
        pytest.param({"source_identity": {"path": SOURCE_PATH, "sha256": "sha256:" + "0" * 64}, "execution_evidence": {"command": ["stale-command"], "exit_code": 0}}, id="stale", marks=pytest.mark.cer_assertion("A-VERDICT-SOURCE-IDENTITY-TRACE")),
        pytest.param({"source_identity": {"path": "other.py", "sha256": CURRENT_SOURCE["sha256"]}, "execution_evidence": {"command": ["other.py"], "exit_code": 0}}, id="mismatched", marks=pytest.mark.cer_assertion("A-VERDICT-SOURCE-IDENTITY-TRACE")),
    ],
)
def test_verdict_rejects_missing_stale_or_mismatched_source_identity(case: dict) -> None:
    code, receipt = _run_identity_matrix({"case_id": "invalid-source-identity", "target": TARGET, "capability": CAPABILITY, "expected_exit": 0, **case})
    row = (receipt.get("case_results") or [{}])[0]
    _assert_behavior(
        code != 0 and receipt.get("aggregate_valid") is False
        and row.get("status") != "pass"
        and any(word in str(row.get("rejection_reason", "")).lower() for word in ("source", "evidence", "identity")),
        "A-VERDICT-SOURCE-IDENTITY-TRACE",
        "invalid source identity or execution evidence must fail closed",
    )


@pytest.mark.cer_assertion("FR8-NONEXECUTED-EVIDENCE")
def test_present_nonexecuted_matrix_evidence_invalidates_named_case() -> None:
    matrix = {
        "schema_version": "jimuyun.stable-candidate-replay-matrix.v2",
        "authorizes": [],
        "cases": [
            {
                "case_id": "nonexecuted-case",
                "target": TARGET,
                "capability": CAPABILITY,
                "expected_exit": 0,
                "matrix_evidence": [{"case_id": "nonexecuted-case", "executed": False}],
            }
        ],
    }
    code, receipt = _run_inline_matrix(matrix)
    rows = receipt.get("case_results") or []
    row = rows[0] if len(rows) == 1 and isinstance(rows[0], dict) else {}
    _assert_behavior(
        code != 0
        and receipt.get("aggregate_valid") is False
        and row.get("case_id") == "nonexecuted-case"
        and row.get("status") != "pass"
        and "execut" in str(row.get("rejection_reason", "")).lower(),
        "FR8-NONEXECUTED-ACCEPTED",
        receipt,
    )


@pytest.mark.cer_assertion("FR10-EA625B1D3DFB")
def test_disable_rollback_and_reenable_receipts_bind_prior_and_candidate_identity() -> None:
    rollback_code, rollback_receipt = _run_replay("rollback")
    reenable_code, reenable_receipt = _run_replay("re-enable")
    rollback = (rollback_receipt.get("current_wrapper_replay") or {}).get("rollback")
    reenable = (reenable_receipt.get("current_wrapper_replay") or {}).get("consumer_invocation")
    prior = rollback.get("prior_route_identity") if isinstance(rollback, dict) else None
    rollback_route = rollback.get("route_identity") if isinstance(rollback, dict) else None
    candidate = reenable.get("route_identity") if isinstance(reenable, dict) else None
    condition = (
        rollback_code == 0
        and reenable_code == 0
        and isinstance(prior, str)
        and prior.startswith("sha256:")
        and rollback_route == prior
        and isinstance(candidate, str)
        and candidate.startswith("sha256:")
        and candidate != prior
    )
    _assert_behavior(
        condition,
        "FR10-EA625B1D3DFB-DRIFT",
        (rollback_receipt, reenable_receipt),
    )
