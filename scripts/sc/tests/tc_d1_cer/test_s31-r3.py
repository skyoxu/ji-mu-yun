"""S31-R3 CER checks for verdict source identity and execution evidence."""
from __future__ import annotations

import json
import hashlib
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.sc import skill_replay_runtime as runtime


ROOT = Path(__file__).resolve().parents[4]
ENTRY = ROOT / "scripts" / "sc" / "skill_package_replay.py"
TARGET = ".agents/skills/run-refactor-implementation-acceptance"
CAPABILITY = "scripts/sc/config/skill-package-validator-capability.v1.json"
FAILURE_ID = "F-VERDICT-MISSING-SOURCE-IDENTITY"
SOURCE_PATH = ENTRY.relative_to(ROOT).as_posix()
CURRENT_SOURCE = {
    "path": SOURCE_PATH,
    "sha256": "sha256:" + hashlib.sha256(ENTRY.read_bytes()).hexdigest(),
}


def _run_matrix(case: dict) -> tuple[int, dict]:
    matrix = {
        "schema_version": "jimuyun.stable-candidate-replay-matrix.v2",
        "authorizes": [],
        "cases": [case],
    }
    child = (
        "import runpy,sys\n"
        "from pathlib import Path\n"
        "payload=sys.stdin.read(); old=Path.read_text; oldb=Path.read_bytes\n"
        "Path.read_text=lambda p,*a,**k: payload if p.name=='s31-r3-matrix.json' else old(p,*a,**k)\n"
        "Path.read_bytes=lambda p,*a,**k: payload.encode('utf-8') if p.name=='s31-r3-matrix.json' else oldb(p,*a,**k)\n"
        f"sys.argv=['{ENTRY.as_posix()}','replay-matrix','--matrix','s31-r3-matrix.json']\n"
        "runpy.run_path(sys.argv[0], run_name='__main__')\n"
    )
    result = runtime.capture_process([sys.executable, '-B', '-c', child], ROOT, timeout=150, input_data=(json.dumps(matrix)).encode("utf-8"))
    try:
        receipt = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"Matrix entry did not return JSON: {exc}; stderr={result.stderr[:500]}")
    if not isinstance(receipt, dict):
        pytest.fail("Matrix entry did not return an object")
    return result.returncode, receipt


def _assert_behavior(condition: bool, detail: object) -> None:
    if not condition:
        print(f"FAILURE_ID:{FAILURE_ID}")
    assert condition, detail


@pytest.mark.cer_assertion("A-VERDICT-REAL-EXECUTION")
def test_verdict_links_current_source_to_validator_processes() -> None:
    result = runtime.capture_process([sys.executable, '-B', str(ENTRY), 'replay-package', '--target', TARGET, '--capability', CAPABILITY, '--probe-mode', 'source-identity'], ROOT, timeout=runtime.PROCESS_TRANSPORT_SECONDS)
    try:
        receipt = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"Replay entry did not return JSON: {exc}; stderr={result.stderr[:500]}")
    replay = receipt.get("current_wrapper_replay") or {}
    snapshot = replay.get("current_snapshot") or {}
    roots = snapshot.get("roots") or []
    source = next((row for row in roots if isinstance(row, dict) and row.get("root_kind") == "source"), {})
    source_hash = "sha256:" + hashlib.sha256(ENTRY.read_bytes()).hexdigest()
    probes = replay.get("probes") or []
    command = replay.get("command") or []
    _assert_behavior(
        result.returncode == 0
        and receipt.get("status") == "pass"
        and source.get("path") == SOURCE_PATH
        and source.get("sha256") == source_hash
        and snapshot.get("complete") is True
        and command[3:5] == [SOURCE_PATH, "replay-package"]
        and replay.get("command_verification", {}).get("command") == command
        and replay.get("fresh_process") is True
        and [row.get("probe_id") for row in probes] == ["requested-target", "detached-positive", "detached-negative"]
        and all(isinstance(row.get("process", {}).get("pid"), int) for row in probes),
        receipt,
    )


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            {"source_identity": None, "execution_evidence": None, "narrative": "Validator passed"},
            id="missing",
            marks=pytest.mark.cer_assertion("A-VERDICT-SOURCE-IDENTITY-TRACE"),
        ),
        pytest.param(
            {"source_identity": CURRENT_SOURCE, "execution_evidence": None},
            id="missing-execution",
            marks=pytest.mark.cer_assertion("A-VERDICT-REAL-EXECUTION"),
        ),
        pytest.param(
            {
                "source_identity": {"path": SOURCE_PATH, "sha256": "sha256:" + "0" * 64},
                "execution_evidence": {"command": ["stale-command"], "exit_code": 0},
            },
            id="stale",
            marks=pytest.mark.cer_assertion("A-VERDICT-SOURCE-IDENTITY-TRACE"),
        ),
        pytest.param(
            {
                "source_identity": {"path": "other.py", "sha256": CURRENT_SOURCE["sha256"]},
                "execution_evidence": {"command": ["other.py"], "exit_code": 0},
            },
            id="mismatched",
            marks=pytest.mark.cer_assertion("A-VERDICT-SOURCE-IDENTITY-TRACE"),
        ),
    ],
)
def test_verdict_rejects_missing_stale_or_mismatched_source_identity(case: dict) -> None:
    case = {
        "case_id": "invalid-source-identity",
        "target": TARGET,
        "capability": CAPABILITY,
        "expected_exit": 0,
        **case,
    }
    code, receipt = _run_matrix(case)
    row = (receipt.get("case_results") or [{}])[0]
    _assert_behavior(
        code != 0
        and receipt.get("aggregate_valid") is False
        and row.get("status") != "pass"
        and any(word in str(row.get("rejection_reason", "")).lower() for word in ("source", "evidence", "identity")),
        receipt,
    )
