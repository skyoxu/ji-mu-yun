"""CER checks for real Consumer lifecycle transitions."""
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


def _receipt(probe_mode: str) -> dict:
    result = subprocess.run(
        [sys.executable, "-B", str(ENTRY), "replay-package", "--target", TARGET, "--capability", CAPABILITY, "--probe-mode", probe_mode],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"production replay entrypoint did not produce a JSON receipt: {exc}")
    if not isinstance(value, dict):
        pytest.fail("production replay entrypoint did not produce an object receipt")
    return value


def _assert(condition: bool, failure_id: str, message: str) -> None:
    if not condition:
        print(f"FAILURE_ID:{failure_id}")
    assert condition, message


@pytest.mark.cer_assertion("A-FC484EFFC69B-ENABLE-REAL-CONSUMER")
def test_enable_records_real_candidate_route_invocation() -> None:
    replay = _receipt("enable").get("current_wrapper_replay", {})
    invocation = replay.get("consumer_invocation", {})
    _assert(
        invocation.get("transition") == "enable"
        and invocation.get("real_call") is True
        and invocation.get("route") == "Candidate Route",
        "FC484EFFC69B_ENABLE_NO_REAL_CALL",
        "enable must invoke the Candidate Route through a real Consumer call surface",
    )


@pytest.mark.cer_assertion("ASSERT-FR10-REAL-CONSUMER-REENABLE")
def test_reenable_records_real_candidate_route_invocation() -> None:
    replay = _receipt("re-enable").get("current_wrapper_replay", {})
    invocation = replay.get("consumer_invocation", {})
    _assert(
        invocation.get("transition") == "re-enable"
        and invocation.get("real_call") is True
        and invocation.get("route") == "Candidate Route",
        "FR10_REENABLE_REAL_CALL_RED",
        "re-enable must execute through the real Candidate Route call surface",
    )


@pytest.mark.cer_assertion("ASSERT-C36692C61A9F-ROLLBACK-REAL-CALL")
def test_rollback_restores_prior_route_through_real_call() -> None:
    replay = _receipt("rollback").get("current_wrapper_replay", {})
    rollback = replay.get("rollback", {})
    _assert(
        rollback.get("real_call") is True
        and rollback.get("route_identity") == rollback.get("prior_route_identity")
        and rollback.get("verdict") == rollback.get("prior_verdict")
        and rollback.get("diagnostic_category") == rollback.get("prior_diagnostic_category"),
        "ROLLBACK_REAL_CALL_MISSING",
        "rollback must restore the captured Prior Route baseline via a real call",
    )


@pytest.mark.cer_assertion("O-EE26E3809DAA-CONSUMER-MANIFEST-FREEZE")
def test_consumer_manifest_is_complete_reconciled_and_frozen_before_review() -> None:
    replay = _receipt("consumer-manifest").get("current_wrapper_replay", {})
    manifest = replay.get("consumer_manifest", {})
    _assert(
        isinstance(manifest, dict)
        and bool(manifest.get("entries"))
        and bool(manifest.get("version"))
        and manifest.get("bidirectional_reconciled") is True
        and manifest.get("frozen_before_review") is True
        and manifest.get("mutable_after_freeze") is False,
        "CONSUMER_MANIFEST_LIFECYCLE_GAP",
        "Consumer Manifest must be complete, reconciled, and frozen before review",
    )
