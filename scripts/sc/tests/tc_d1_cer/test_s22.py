"""CER coverage for substituted target rejection before processing."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
ENTRY = ROOT / "scripts" / "sc" / "skill_package_replay.py"
CAPABILITY = "scripts/sc/config/skill-package-validator-capability.v1.json"


@pytest.mark.cer_assertion("A-EA5137E46B75-1")
def test_substituted_target_is_rejected_before_processing() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(ENTRY),
            "validate-package",
            "--target",
            "scripts",
            "--capability",
            CAPABILITY,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    rejected = (
        result.returncode != 0
        and "target does not match the capability-bound package" in result.stderr
        and not result.stdout.strip()
    )
    if not rejected:
        print("FAILURE_ID:FI-EA5137E46B75-1")
    assert rejected, {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
