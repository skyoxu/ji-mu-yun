"""S31-R2 CER check for per-transition Consumer route identities."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
ENTRY = ROOT / "scripts" / "sc" / "skill_package_replay.py"
TARGET = ".agents/skills/run-refactor-implementation-acceptance"
CAPABILITY = "scripts/sc/config/skill-package-validator-capability.v1.json"
FAILURE_ID = "FR10-EA625B1D3DFB-DRIFT"


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
        timeout=180,
        check=False,
    )
    try:
        receipt = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"Replay entry did not return JSON: {exc}; stderr={result.stderr[:500]}")
    if not isinstance(receipt, dict):
        pytest.fail("Replay entry did not return an object")
    return result.returncode, receipt


def _assert_behavior(condition: bool, detail: object) -> None:
    if not condition:
        print(f"FAILURE_ID:{FAILURE_ID}")
    assert condition, detail


@pytest.mark.cer_assertion("FR10-EA625B1D3DFB")
def test_each_consumer_transition_receipt_binds_route_identity() -> None:
    rollback_code, rollback_receipt = _run_replay("rollback")
    reenable_code, reenable_receipt = _run_replay("re-enable")

    rollback_replay = rollback_receipt.get("current_wrapper_replay") or {}
    reenable_replay = reenable_receipt.get("current_wrapper_replay") or {}
    rollback = rollback_replay.get("rollback")
    reenable = reenable_replay.get("consumer_invocation")

    prior = rollback.get("prior_route_identity") if isinstance(rollback, dict) else None
    rollback_identity = rollback.get("route_identity") if isinstance(rollback, dict) else None
    candidate = reenable.get("route_identity") if isinstance(reenable, dict) else None

    _assert_behavior(
        rollback_code == 0
        and reenable_code == 0
        and isinstance(rollback, dict)
        and rollback.get("real_call") is True
        and isinstance(prior, str)
        and prior.startswith("sha256:")
        and rollback_identity == prior
        and isinstance(reenable, dict)
        and reenable.get("real_call") is True
        and reenable.get("transition") == "re-enable"
        and reenable.get("route") == "Candidate Route"
        and isinstance(candidate, str)
        and candidate.startswith("sha256:")
        and candidate != prior,
        (rollback_receipt, reenable_receipt),
    )
