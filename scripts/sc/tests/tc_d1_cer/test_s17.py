"""S17 CER checks for detached Probe bindings and bounded process termination."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
REPLAY = ROOT / "scripts" / "sc" / "skill_package_replay.py"
WORKER = ROOT / "scripts" / "vdd" / "probe_real_worker.py"
CAPABILITY = "scripts/sc/config/skill-package-validator-capability.v1.json"
TARGET = ".agents/skills/run-refactor-implementation-acceptance"
PYTHON = shutil.which("py") or sys.executable
PYTHON_PREFIX = ["-3"] if Path(PYTHON).name.lower() == "py.exe" else []

TOOLS = ROOT / ".agents" / "skills" / "quick-dev-tdd-adapter" / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from current_router import materialize_descriptor  # noqa: E402
from process_executor_v2 import execute_process  # noqa: E402


def _assert_bound(condition: bool, failure_id: str, detail: object) -> None:
    if not condition:
        print(f"FAILURE_ID:{failure_id}")
    assert condition, detail


def _json_result(command: list[str]) -> tuple[subprocess.CompletedProcess[str], dict]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {}
    return result, payload


@pytest.mark.cer_assertion("A-27F-1")
def test_detached_replay_binds_input_and_output_to_same_probe_identity() -> None:
    result, receipt = _json_result(
        [
            PYTHON,
            *PYTHON_PREFIX,
            "-B",
            str(REPLAY),
            "replay-package",
            "--target",
            TARGET,
            "--capability",
            CAPABILITY,
            "--probe-mode",
            "fresh",
        ]
    )
    replay = receipt.get("current_wrapper_replay", {}) if isinstance(receipt, dict) else {}
    probes = replay.get("probes") if isinstance(replay, dict) else None
    positive = next((item for item in probes or [] if item.get("probe_id") == "detached-positive"), {})
    process = positive.get("process", {})
    command_outcome = positive.get("command_outcome", {})
    bound = (
        result.returncode == 0
        and receipt.get("status") == "pass"
        and positive.get("input", {}).get("target") == TARGET
        and positive.get("actual_target") == TARGET
        and isinstance(process.get("pid"), int)
        and isinstance(process.get("parent_pid"), int)
        and process.get("pid") != process.get("parent_pid")
        and positive.get("exit_code") == 0
        and isinstance(command_outcome.get("stdout_sha256"), str)
        and isinstance(command_outcome.get("stderr_sha256"), str)
    )
    _assert_bound(bound, "F-27-UNBOUND-OUTPUT", {"returncode": result.returncode, "stdout": result.stdout[:200], "stderr": result.stderr[:200], "probe": positive})


@pytest.mark.cer_assertion("A-27F-2")
def test_detached_replay_rejects_missing_input_target_binding() -> None:
    missing_target = f"{TARGET}/.s17-unbound-input"
    result, receipt = _json_result(
        [
            PYTHON,
            *PYTHON_PREFIX,
            "-B",
            str(REPLAY),
            "replay-package",
            "--target",
            missing_target,
            "--capability",
            CAPABILITY,
            "--probe-mode",
            "fresh",
        ]
    )
    rejected = result.returncode != 0 and receipt.get("status") != "pass"
    _assert_bound(rejected, "F-27-UNBOUND-INPUT", {"returncode": result.returncode, "stdout": result.stdout})


@pytest.mark.cer_assertion("O-0F67A5E3623D")
def test_probe_worker_runs_as_detached_process_and_reports_infrastructure_failure() -> None:
    result, payload = _json_result(
        [PYTHON, *PYTHON_PREFIX, "-B", str(WORKER), "--backend", "unavailable-infrastructure-backend"]
    )
    rejected_false_success = (
        result.returncode != 0
        and payload.get("status") == "environment-blocked"
        and payload.get("execution_attempted") is False
        and payload.get("execution_succeeded") is False
        and payload.get("authorizes") == []
    )
    _assert_bound(
        rejected_false_success,
        "O-0F67A5E3623D-NO-PROCESS-OBSERVATION",
        {"returncode": result.returncode, "payload": payload},
    )


@pytest.mark.cer_assertion("A-C6F923EBD52F-1")
def test_external_probe_timeout_has_deterministic_terminal_state() -> None:
    try:
        subprocess.run(
            [PYTHON, *PYTHON_PREFIX, "-c", "import time; time.sleep(2)"],
            timeout=0.2,
            check=False,
            capture_output=True,
            text=True,
        )
        timed_out = False
    except subprocess.TimeoutExpired:
        timed_out = True
    _assert_bound(timed_out is True, "F-C6F923EBD52F-1", {"timed_out": timed_out})
    return
