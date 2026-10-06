"""S41 CER tests with one executable binding per Acceptance assertion."""
from __future__ import annotations

import json
import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
ENTRY = ROOT / "scripts" / "sc" / "skill_package_replay.py"
CAPABILITY = "scripts/sc/config/skill-package-validator-capability.v1.json"
TARGET = ".agents/skills/run-refactor-implementation-acceptance"
MATRIX = "execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/stable-candidate-replay-matrix.v1.json"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-B", str(ENTRY), *args], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8", check=False)


def _replay() -> tuple[subprocess.CompletedProcess[str], dict, dict]:
    result = _run("replay-package", "--target", TARGET, "--capability", CAPABILITY, "--probe-mode", "fresh")
    payload = json.loads(result.stdout)
    return result, payload, payload.get("current_wrapper_replay", {})


def _matrix(*cases: dict) -> tuple[subprocess.CompletedProcess[str], dict]:
    matrix = {"schema_version": "jimuyun.stable-candidate-replay-matrix.v2", "cases": list(cases), "authorizes": []}
    child = (
        "import json,runpy,sys\n"
        "from pathlib import Path\n"
        "payload=sys.stdin.read(); old=Path.read_text; oldb=Path.read_bytes\n"
        "Path.read_text=lambda p,*a,**k: payload if p.name=='s41-matrix.json' else old(p,*a,**k)\n"
        "Path.read_bytes=lambda p,*a,**k: payload.encode() if p.name=='s41-matrix.json' else oldb(p,*a,**k)\n"
        f"sys.argv=[{str(ENTRY)!r},'replay-matrix','--matrix','s41-matrix.json']; runpy.run_path(sys.argv[0],run_name='__main__')\n"
    )
    result = subprocess.run([sys.executable, "-B", "-c", child], cwd=ROOT, input=json.dumps(matrix),
                            capture_output=True, text=True, encoding="utf-8", check=False)
    return result, json.loads(result.stdout)


def _case(case_id: str, **facts: object) -> dict:
    return {"case_id": case_id, "target": TARGET, "capability": CAPABILITY, "expected_exit": 0, **facts}


@pytest.mark.cer_assertion("A-429F-1")
def test_effective_inspection_has_independent_identity() -> None:
    result, _payload, replay = _replay()
    verification = replay.get("target_verification", {})
    assert result.returncode == 0 and verification.get("independent") is True
    assert verification.get("identity_match") is True and verification.get("target") == TARGET


@pytest.mark.cer_assertion("A-42BC-output-1")
def test_successful_replay_has_independent_output_verification() -> None:
    result, _payload, replay = _replay()
    verification = replay.get("output_verification", {})
    assert result.returncode == 0 and verification.get("independent") is True
    assert verification.get("status") == "passed"
    assert verification.get("output_sha256", "").startswith("sha256:")
    assert verification.get("identity_match") is True
    material = replay["effective_read_witness"]
    expected = "sha256:" + hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert verification.get("output_sha256") == expected


@pytest.mark.cer_assertion("A-6DA5F4052C6D-1")
def test_target_identity_contains_independent_content_digest() -> None:
    result, _payload, replay = _replay()
    inspected = replay.get("effective_inspected_content", {})
    witness = replay.get("effective_read_witness", {})
    assert result.returncode == 0 and inspected.get("identity", "").startswith("sha256:")
    assert witness.get("target_identity") == inspected.get("identity")


@pytest.mark.cer_assertion("A-MATRIX-COUNT-6")
def test_matrix_has_exactly_six_executed_cases(native_skill_replay_matrix) -> None:
    _matrix, payload = native_skill_replay_matrix
    rows = payload.get("case_results", [])
    assert payload.get("status") == "pass" and len(rows) == 6 and all(row.get("executed") is True for row in rows)


@pytest.mark.cer_assertion("A-MATRIX-DISTINCT")
def test_matrix_cases_have_distinct_ids_and_inputs(native_skill_replay_matrix) -> None:
    matrix, payload = native_skill_replay_matrix
    rows = payload.get("case_results", [])
    ids = [row.get("case_id") for row in rows]
    assert payload.get("status") == "pass" and len(ids) == 6 and len(set(ids)) == 6
    assert len({case["fixture"]["sha256"] for case in matrix["cases"]}) == 6
    assert all([entry["subject"] for entry in row["subject_executions"]] == ["Stable", "Candidate"] for row in rows)


@pytest.mark.cer_assertion("A-O-108EF1A37200")
def test_escaping_target_fails_closed() -> None:
    result = _run("replay-package", "--target", "..", "--capability", CAPABILITY, "--probe-mode", "fresh")
    assert result.returncode != 0 and "escapes the repository" in result.stderr


@pytest.mark.cer_assertion("A-O-392B52C3CA23-unsupported-fails-closed")
def test_unsupported_target_fails_before_processing() -> None:
    result = _run("validate-package", "--target", "scripts", "--capability", CAPABILITY)
    assert result.returncode != 0 and "target does not match" in result.stderr


@pytest.mark.cer_assertion("A-O-3D7C2B729F95-independent-consumer-verification")
def test_successful_result_has_independent_consumer_verification() -> None:
    result, _payload, replay = _replay()
    verification = replay.get("consumer_verification", {})
    assert result.returncode == 0 and verification.get("independent") is True
    assert verification.get("executed") is True and verification.get("target") == TARGET


@pytest.mark.cer_assertion("A-O-3E035D737A50-missing-facts-block-success")
def test_missing_identity_facts_block_success() -> None:
    result, payload = _matrix(_case("missing-facts", identity_status="unverifiable"))
    row = payload["case_results"][0]
    assert result.returncode != 0 and row.get("status") != "pass" and "identity" in row.get("rejection_reason", "")


@pytest.mark.cer_assertion("FR-8-aggregate-invalid-on-copied-evidence")
def test_copied_matrix_evidence_invalidates_aggregate() -> None:
    result, payload = _matrix(_case("copied", evidence_origin="copied"))
    assert result.returncode != 0 and payload.get("aggregate_valid") is False
    assert "copied" in str(payload.get("invalid_reasons", [])).lower()


@pytest.mark.cer_assertion("FR1-ILLEGAL-TARGET-FAILS-CLOSED")
def test_illegal_target_is_rejected_before_validator() -> None:
    result = _run("validate-package", "--target", "scripts", "--capability", CAPABILITY)
    refusal = json.loads(result.stdout)
    assert result.returncode != 0 and refusal.get("status") == "execution-failed"
    assert "target does not match" in refusal.get("diagnostic", "")
    assert refusal.get("authorizes") == [] and "successful_evidence" not in refusal


@pytest.mark.cer_assertion("SM2-INVALID-PACKAGE-REJECTS-SUCCESS")
def test_invalid_package_control_cannot_become_success() -> None:
    result, payload = _matrix(_case("invalid-package", adversarial_validator=True))
    assert result.returncode != 0 and payload.get("aggregate_valid") is False
