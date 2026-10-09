"""S7 CER selector for the detached-Probe and disable-transition checks."""

import pytest
from scripts.sc import skill_replay_runtime as runtime

from test_s10 import (
    test_always_success_validator_is_reported_as_a_failed_probe_outcome as _always_success_probe,
)
from test_s10 import (
    test_detached_positive_probe_binds_input_target_outcome_and_output as _bound_probe,
)
from test_s10 import (
    test_detached_positive_probe_records_a_distinct_child_process as _process_probe,
)
from test_s4_cer import test_rollback_restores_prior_route_through_real_call as _disable_probe

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ENTRY = ROOT / "scripts" / "sc" / "skill_package_replay.py"
CAPABILITY = "scripts/sc/config/skill-package-validator-capability.v1.json"
TARGET = ".agents/skills/run-refactor-implementation-acceptance"


@pytest.mark.cer_assertion("A-FR5-HISTORICAL-NONAUT")
def test_reused_historical_evidence_cannot_authorize_current_replay() -> None:
    result = runtime.capture_process([sys.executable, '-B', str(ENTRY), 'replay-package', '--target', TARGET, '--capability', CAPABILITY, '--probe-mode', 'reused-evidence'], ROOT, timeout=runtime.PROCESS_TRANSPORT_SECONDS)
    receipt = json.loads(result.stdout)
    assert (
        result.returncode != 0
        and receipt.get("status") == "rejected"
        and receipt.get("diagnostic") == "reused evidence is not eligible for a successful replay"
        and receipt.get("authorizes") == []
    ), receipt


@pytest.mark.cer_assertion("ASSERT-O-2B7C47734A05-PROBE-PROCESS")
def test_s7_detached_probe_records_a_distinct_child_process() -> None:
    _process_probe()


@pytest.mark.cer_assertion("ASSERT-O-2B7C47734A05-PROBE-BINDINGS")
def test_s7_detached_probe_binds_input_target_outcome_and_output() -> None:
    _bound_probe()


@pytest.mark.cer_assertion("ASSERT-O-833C8FA8A239-ALWAYS-SUCCESS-FALSE-NEGATIVE")
def test_s7_always_success_validator_is_a_failed_probe_outcome() -> None:
    _always_success_probe()


@pytest.mark.cer_assertion("A-O-50826FFB04E3-DISABLE-REAL-CALL")
def test_s7_consumer_disable_records_the_real_prior_route_call() -> None:
    _disable_probe()
