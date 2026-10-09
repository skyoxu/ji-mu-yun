import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
VALIDATOR = ROOT / "execution-plans" / "2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed" / "tools" / "validate_implementation.py"
REPLAY = ROOT / "scripts" / "sc" / "skill_package_replay.py"
PLAN = "execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed"
CAPABILITY = "scripts/sc/config/skill-package-validator-capability.v1.json"


def assert_slice_ready(slice_id: str, failure_id: str) -> None:
    try:
        result = subprocess.run(
            [sys.executable, "-B", str(VALIDATOR), "--slice", slice_id],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired:
        print(f"FAILURE_ID:{failure_id}")
        pytest.fail(f"{slice_id} validator exceeded 120 seconds")
    if result.returncode != 0:
        print(f"FAILURE_ID:{failure_id}")
        try:
            payload = json.loads(result.stdout)
            print(json.dumps({"status": payload.get("status"), "errors": payload.get("errors", [])}, sort_keys=True))
        except json.JSONDecodeError:
            print(result.stdout[-2000:])
            print(result.stderr[-2000:])
    assert result.returncode == 0


def run_replay(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(REPLAY), *args], cwd=ROOT,
        capture_output=True, text=True, encoding="utf-8", check=False,
    )


@pytest.mark.cer_assertion("RMAP-R6-S0")
def test_s0_repository_owned_validator_capability() -> None:
    assert_slice_ready("RMAP-S0", "RMAP-R6-S0-NOT-READY")


@pytest.mark.cer_assertion("RMAP-R6-S1")
def test_s1_historical_compatibility_replay() -> None:
    result = run_replay("replay-package", "--target", ".agents/skills/run-refactor-implementation-acceptance", "--capability", CAPABILITY, "--probe-mode", "detached-positive-negative")
    if result.returncode != 0:
        print("FAILURE_ID:RMAP-R6-S1-NOT-READY")
    assert result.returncode == 0
    receipt = json.loads(result.stdout)
    assert receipt["status"] == "pass" and receipt["authorizes"] == []
    # The current replay contract records the detached positive control before
    # the detached negative control; retain the historical compatibility
    # assertion while accounting for the explicit positive probe.
    assert [row["exit_code"] for row in receipt["current_wrapper_replay"]["probes"]] == [0, 0, 1]


@pytest.mark.cer_assertion("RMAP-R6-S2")
def test_s2_evaluation_seeds_and_matrix() -> None:
    result = run_replay("replay-matrix", "--matrix", f"{PLAN}/stable-candidate-replay-matrix.v1.json")
    if result.returncode != 0:
        print("FAILURE_ID:RMAP-R6-S2-NOT-READY")
    assert result.returncode == 0
    receipt = json.loads(result.stdout)
    rows = receipt["case_results"]
    assert len(rows) == 6 and all(row["executed"] and row["status"] == "pass" for row in rows)
    assert {row["category"] for row in rows} == {"positive", "negative", "historical_compatibility", "dirty_baseline", "knowledge_read_set", "closed_policy"}


@pytest.mark.cer_assertion("RMAP-R6-S3")
def test_s3_consumer_and_terminal_integration() -> None:
    commands = [
        [sys.executable, "-B", str(REPLAY), "validate-package", "--target", ".agents/skills/run-refactor-implementation-acceptance", "--capability", CAPABILITY],
        [sys.executable, "-B", "scripts/sc/tests/test_workflow_model_routing.py"],
        [sys.executable, "-B", ".agents/skills/run-refactor-implementation-acceptance/tests/test_skill_replay_contract.py"],
    ]
    for command in commands:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=120, check=False)
        if result.returncode != 0:
            print("FAILURE_ID:RMAP-R6-S3-NOT-READY")
            print(result.stdout[-2000:])
            print(result.stderr[-2000:])
        assert result.returncode == 0
