"""CER receipt coverage for successful evidence content binding."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
ENTRY = ROOT / "scripts" / "sc" / "skill_package_replay.py"
CAPABILITY = "scripts/sc/config/skill-package-validator-capability.v1.json"
TARGET = ".agents/skills/run-refactor-implementation-acceptance"


@pytest.mark.cer_assertion("assert-platform-specific-declaration")
def test_replay_receipt_declares_active_platform_behavior() -> None:
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
            "fresh",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    receipt = json.loads(result.stdout)
    replay = receipt.get("current_wrapper_replay")
    declaration = replay.get("platform_behavior") if isinstance(replay, dict) else None
    assert (
        result.returncode == 0
        and isinstance(declaration, dict)
        and declaration.get("platform") == sys.platform
        and declaration.get("behavior")
        and receipt.get("authorizes") == []
    ), receipt


def _package_identity(package_root: Path) -> str:
    entries = [
        {
            "path": path.relative_to(package_root).as_posix(),
            "sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in sorted(package_root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    ]
    return "sha256:" + hashlib.sha256(
        json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@pytest.mark.cer_assertion("FR-2-SUCCESSFUL-EVIDENCE-EFFECTIVE-CONTENT-BINDING")
def test_successful_evidence_names_the_identity_of_the_inspected_package() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(ENTRY),
            "validate-package",
            "--target",
            TARGET,
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
    try:
        receipt = json.loads(result.stdout)
    except json.JSONDecodeError:
        receipt = {}
    effective = receipt.get("effective_inspected_content", {}) if isinstance(receipt, dict) else {}
    evidence = receipt.get("successful_evidence", {}) if isinstance(receipt, dict) else {}
    expected_identity = _package_identity(ROOT / TARGET)
    correctly_bound = (
        result.returncode == 0
        and receipt.get("status") == "pass"
        and effective.get("path") == TARGET
        and effective.get("identity") == expected_identity
        and evidence.get("effective_inspected_content_identity") == expected_identity
        and evidence.get("inspection_result") == "pass"
    )
    if not correctly_bound:
        print("FAILURE_ID:FR2_EFFECTIVE_CONTENT_BINDING_MISSING")
    assert correctly_bound, "successful evidence must name the identity of the package actually inspected"
