"""CER checks for Consumer disable execution through the replay entrypoint."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
ENTRY = ROOT / "scripts" / "sc" / "skill_package_replay.py"
CAPABILITY = "scripts/sc/config/skill-package-validator-capability.v1.json"
TARGET = ".agents/skills/run-refactor-implementation-acceptance"


def _assert_behavior(condition: bool, failure_id: str, message: str) -> None:
    if not condition:
        print(f"FAILURE_ID:{failure_id}")
    assert condition, message


def _rollback_replay_with_prior_route_trace() -> dict[str, object] | None:
    child_script = "\n".join(
        [
            "import json",
            "import sys",
            "from contextlib import redirect_stdout",
            "from io import StringIO",
            f"sys.path.insert(0, {str(ENTRY.parent)!r})",
            "import skill_package_replay as replay",
            "calls = []",
            "original_run_validator = replay.run_validator",
            "def traced_run_validator(validator, value, target):",
            "    completed = original_run_validator(validator, value, target)",
            "    calls.append({'validator': validator.relative_to(replay.ROOT).as_posix(), 'target': target.relative_to(replay.ROOT).as_posix(), 'exit_code': completed.returncode})",
            "    return completed",
            "replay.run_validator = traced_run_validator",
            f"sys.argv = ['skill_package_replay.py', 'replay-package', '--target', {TARGET!r}, '--capability', {CAPABILITY!r}, '--probe-mode', 'rollback']",
            "receipt_output = StringIO()",
            "with redirect_stdout(receipt_output):",
            "    exit_code = replay.main()",
            "receipt = json.loads(receipt_output.getvalue())",
            "print(json.dumps({'exit_code': exit_code, 'receipt': receipt, 'calls': calls}, sort_keys=True))",
        ]
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", child_script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


@pytest.mark.cer_assertion("A-O-50826FFB04E3-DISABLE-REAL-CALL")
def test_consumer_disable_records_the_real_prior_route_call() -> None:
    payload = _rollback_replay_with_prior_route_trace()
    receipt = payload.get("receipt") if isinstance(payload, dict) else None
    replay = receipt.get("current_wrapper_replay") if isinstance(receipt, dict) else None
    rollback = replay.get("rollback") if isinstance(replay, dict) else None
    validator = replay.get("resolved_validator") if isinstance(replay, dict) else None
    calls = payload.get("calls") if isinstance(payload, dict) else None
    prior_route_call = calls[-1] if isinstance(calls, list) and len(calls) >= 3 else None
    condition = (
        isinstance(payload, dict)
        and payload.get("exit_code") == 0
        and isinstance(rollback, dict)
        and rollback.get("real_call") is True
        and isinstance(validator, dict)
        and rollback.get("prior_route_identity") == validator.get("sha256")
        and rollback.get("route_identity") == rollback.get("prior_route_identity")
        and rollback.get("verdict") == replay.get("status")
        and isinstance(prior_route_call, dict)
        and prior_route_call.get("validator") == validator.get("path")
        and prior_route_call.get("target") == TARGET
        and prior_route_call.get("exit_code") == 0
    )
    _assert_behavior(
        condition,
        "CONSUMER_DISABLE_NO_REAL_CALL",
        "Consumer disable must record the invoked Prior Route and its successful real-call result",
    )
