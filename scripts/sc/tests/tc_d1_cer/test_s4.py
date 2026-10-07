"""CER coverage for successful evidence bound to effective inspected content."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.sc import skill_replay_runtime as runtime

_CER_ASSERTION_BINDINGS = [pytest.mark.cer_assertion("A-B4382B18F0CA-1")]


ROOT = Path(__file__).resolve().parents[4]
ENTRY = ROOT / "scripts" / "sc" / "skill_package_replay.py"
CAPABILITY = "scripts/sc/config/skill-package-validator-capability.v1.json"
TARGET = ".agents/skills/run-refactor-implementation-acceptance"


def _package_identity(package_root: Path) -> str:
    entries = [
        {
            "path": path.relative_to(package_root).as_posix(),
            "sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        # Accepted ADR-0058: the independent oracle uses Git's byte order.
        for path in sorted(package_root.rglob("*"), key=lambda p: p.relative_to(package_root).as_posix().encode("utf-8"))
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    ]
    return "sha256:" + hashlib.sha256(
        json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@pytest.mark.cer_assertion("A-B4382B18F0CA-1")
@pytest.mark.cer_assertion("FR-2-SUCCESSFUL-EVIDENCE-EFFECTIVE-CONTENT-BINDING")
def test_successful_evidence_is_bound_to_the_effective_inspected_content() -> None:
    result = runtime.capture_process([sys.executable, '-B', str(ENTRY), 'validate-package', '--target', TARGET, '--capability', CAPABILITY], ROOT, timeout=60)
    try:
        receipt = json.loads(result.stdout)
    except json.JSONDecodeError:
        receipt = {}
    effective = receipt.get("effective_inspected_content", {}) if isinstance(receipt, dict) else {}
    successful_evidence = receipt.get("successful_evidence", {}) if isinstance(receipt, dict) else {}
    evidence = receipt.get("successful_evidence", {}) if isinstance(receipt, dict) else {}
    expected_identity = _package_identity(ROOT / TARGET)
    bound = (
        result.returncode == 0
        and receipt.get("status") == "pass"
        and effective.get("path") == TARGET
        and effective.get("identity") == expected_identity
        and evidence.get("effective_inspected_content_identity") == expected_identity
        and evidence.get("inspection_result") == "pass"
        and successful_evidence.get("effective_inspected_content_identity") == effective["identity"]
        and successful_evidence.get("inspection_result") == "pass"
    )
    if not bound:
        print("FAILURE_ID:FR2_EFFECTIVE_CONTENT_BINDING_MISSING")
    assert bound, "successful validation must bind evidence to the effective inspected content actually inspected"
