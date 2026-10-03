"""S30 CER checks for effective-content binding and rollback baseline coverage."""
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


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(ENTRY), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _json(result: subprocess.CompletedProcess[str]) -> dict:
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest(root: Path) -> str:
    entries = [
        {"path": path.relative_to(root).as_posix(), "sha256": _sha256(path)}
        for path in sorted(root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    ]
    encoded = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _assert_behavior(condition: bool, failure_id: str, message: str) -> None:
    if not condition:
        print(f"FAILURE_ID:{failure_id}")
    assert condition, message


@pytest.mark.cer_assertion("A-6634-1")
def test_successful_evidence_binds_exact_effective_inspected_content() -> None:
    result = _run("validate-package", "--target", TARGET, "--capability", CAPABILITY)
    receipt = _json(result)
    if result.returncode != 0 or not receipt:
        pytest.fail("production validation entrypoint did not return a JSON success receipt")
    effective = receipt.get("effective_inspected_content")
    evidence = receipt.get("successful_evidence")
    target_package = receipt.get("target_package")
    target_root = ROOT / TARGET

    path_ok = isinstance(effective, dict) and effective.get("path") == TARGET and target_root.is_dir()
    digest_ok = (
        isinstance(effective, dict)
        and effective.get("identity") == _manifest(target_root)
        and isinstance(effective.get("identity"), str)
        and effective["identity"].startswith("sha256:")
    )
    evidence_ok = (
        isinstance(evidence, dict)
        and evidence.get("effective_inspected_content_identity") == effective.get("identity")
        and evidence.get("inspection_result") == "pass"
        and isinstance(target_package, dict)
        and target_package.get("manifest_sha256") == effective.get("identity")
    )
    if not path_ok or not digest_ok:
        print("FAILURE_ID:F-6634-UNBOUND-CONTENT")
        assert path_ok and digest_ok, "effective inspected content reference or digest is missing or mismatched"
    _assert_behavior(
        result.returncode == 0 and receipt.get("status") == "pass" and evidence_ok,
        "CER-A-66202D6EB755-BEHAVIOR",
        "successful route evidence must reference and digest the exact effective inspected content",
    )


def _rollback_payload() -> tuple[subprocess.CompletedProcess[str], dict]:
    result = _run(
        "replay-package",
        "--target",
        TARGET,
        "--capability",
        CAPABILITY,
        "--probe-mode",
        "rollback",
    )
    receipt = _json(result)
    if result.returncode != 0 or not receipt:
        pytest.fail("production rollback entrypoint did not return a JSON receipt")
    return result, receipt


def _rollback_coverage(receipt: dict) -> bool:
    rollback = receipt.get("current_wrapper_replay", {}).get("rollback")
    manifest = receipt.get("consumer_manifest", {})
    entries = manifest.get("entries") if isinstance(manifest, dict) else None
    observations = rollback.get("baseline_observations") if isinstance(rollback, dict) else None
    observed_count = rollback.get("observed_count") if isinstance(rollback, dict) else None
    manifest_count = rollback.get("manifest_count") if isinstance(rollback, dict) else None
    coverage_ok = (
        isinstance(entries, list)
        and bool(entries)
        and isinstance(observations, list)
        and len(observations) == len(entries)
        and all(isinstance(item, dict) and item.get("baseline_match") is True for item in observations)
        and observed_count == manifest_count == len(entries)
    )
    return isinstance(rollback, dict) and coverage_ok


@pytest.mark.cer_assertion("A-6BE2-1")
def test_rollback_missing_baseline_observation_is_reported() -> None:
    _, receipt = _rollback_payload()
    if not _rollback_coverage(receipt):
        print("FAILURE_ID:CER-A-72299F00808C-BEHAVIOR")
    assert _rollback_coverage(receipt), "rollback verification must report a baseline observation for every manifest entry"


@pytest.mark.cer_assertion("A-6BE2-1")
def test_rollback_route_satisfies_complete_baseline_coverage_behavior() -> None:
    _, receipt = _rollback_payload()
    _assert_behavior(
        _rollback_coverage(receipt),
        "CER-A-72299F00808C-BEHAVIOR",
        "rollback verification must observe the prior baseline for every manifest entry",
    )
