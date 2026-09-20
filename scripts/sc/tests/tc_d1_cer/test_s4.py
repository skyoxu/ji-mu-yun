"""CER coverage for successful evidence bound to effective inspected content."""
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


@pytest.mark.cer_assertion("FR-2-SUCCESSFUL-EVIDENCE-EFFECTIVE-CONTENT-BINDING")
def test_successful_evidence_is_bound_to_the_effective_inspected_content() -> None:
    result = subprocess.run(
        [sys.executable, "-B", str(ENTRY), "validate-package", "--target", TARGET, "--capability", CAPABILITY],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    try:
        receipt = json.loads(result.stdout)
    except json.JSONDecodeError:
        receipt = {}
    effective = receipt.get("effective_inspected_content", {}) if isinstance(receipt, dict) else {}
    bound = (
        result.returncode == 0
        and receipt.get("status") in {"success", "pass"}
        and effective.get("path") == TARGET
        and isinstance(effective.get("identity"), str)
        and effective["identity"].startswith("sha256:")
    )
    if not bound:
        print("FAILURE_ID:FR2_EFFECTIVE_CONTENT_BINDING_MISSING")
    assert bound, "successful validation must bind evidence to the effective inspected content"
