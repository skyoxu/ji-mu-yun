"""CER checks for exact source identity reconstruction and fresh replay."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.sc import skill_replay_runtime as runtime


ROOT = Path(__file__).resolve().parents[3]
ENTRY = ROOT / "scripts" / "sc" / "skill_package_replay.py"
CAPABILITY = "scripts/sc/config/skill-package-validator-capability.v1.json"
TARGET = ".agents/skills/run-refactor-implementation-acceptance"


@pytest.mark.cer_assertion("ASSERT-SM6-IDENTITY-RECONSTRUCTION-AND-FRESH-REPLAY")
def test_replay_reconstructs_bound_identity_and_launches_fresh_process() -> None:
    result = runtime.capture_process(
        [sys.executable, "-B", str(ENTRY), "replay-package", "--target", TARGET, "--capability", CAPABILITY, "--probe-mode", "source-identity"],
        ROOT, timeout=180,
    )
    try:
        receipt = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"production replay entrypoint did not produce a JSON receipt: {exc}")
    if not isinstance(receipt, dict):
        pytest.fail("production replay entrypoint did not produce an object receipt")
    replay = receipt.get("current_wrapper_replay", {})
    observed = (
        isinstance(replay.get("reconstructed_identity"), str)
        and bool(replay.get("reconstructed_identity"))
        and replay.get("reconstructed_identity") == replay.get("replay_identity")
        and replay.get("fresh_process") is True
        and replay.get("historical_evidence_rewritten") is False
    )
    if not observed:
        print("FAILURE_ID:SM6_IDENTITY_MISMATCH_RED")
    assert observed, "fresh replay must use the exact reconstructed identity without rewriting history"
