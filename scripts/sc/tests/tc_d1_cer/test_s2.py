"""CER coverage for successful evidence bound to inspected content."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_CER_ASSERTION_BINDINGS = [pytest.mark.cer_assertion("assert-platform-specific-declaration")]


ROOT = Path(__file__).resolve().parents[4]
ENTRY = ROOT / "scripts" / "sc" / "skill_package_replay.py"
CAPABILITY = "scripts/sc/config/skill-package-validator-capability.v1.json"
TARGET = ".agents/skills/run-refactor-implementation-acceptance"
FAILURE_ID = "FR2_EFFECTIVE_CONTENT_BINDING_MISSING"


def _validation_receipt() -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
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
        value = json.loads(result.stdout)
    except json.JSONDecodeError:
        value = {}
    return result, value if isinstance(value, dict) else {}


@pytest.mark.cer_assertion("FR-2-SUCCESSFUL-EVIDENCE-EFFECTIVE-CONTENT-BINDING")
@pytest.mark.cer_assertion("assert-platform-specific-declaration")
def test_successful_evidence_names_the_effective_inspected_content() -> None:
    result, receipt = _validation_receipt()
    effective = receipt.get("effective_inspected_content", {})
    evidence = receipt.get("successful_evidence", {})
    bound = (
        result.returncode == 0
        and receipt.get("status") in {"success", "pass"}
        and isinstance(effective, dict)
        and effective.get("path") == TARGET
        and isinstance(effective.get("identity"), str)
        and effective["identity"].startswith("sha256:")
        and isinstance(evidence, dict)
        and evidence.get("effective_inspected_content_identity") == effective["identity"]
        and evidence.get("inspection_result") == "pass"
    )
    if not bound:
        print(f"FAILURE_ID:{FAILURE_ID}")
    assert bound, "successful evidence must name and match the effective inspected content"
