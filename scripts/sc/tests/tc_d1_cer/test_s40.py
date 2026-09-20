"""CER checks for S40 infrastructure-failure Probe handling."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
PROBE = ROOT / "scripts" / "vdd" / "probe_real_worker.py"


def _assert_failed_outcome(condition: bool) -> None:
    if not condition:
        print("FAILURE_ID:INFRASTRUCTURE_FALSE_NEGATIVE_PASSES")
    assert condition, "an infrastructure-blocked detached Probe must report a failed outcome"


@pytest.mark.cer_assertion("A-INFRASTRUCTURE_FALSE_NEGATIVE_FAILS")
def test_detached_probe_rejects_an_infrastructure_failure_false_negative() -> None:
    result = subprocess.run(
        [sys.executable, "-B", str(PROBE), "--backend", "unavailable-infrastructure-backend"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    payload = json.loads(result.stdout)

    assert payload["availability"]["available"] is False
    _assert_failed_outcome(result.returncode != 0)
