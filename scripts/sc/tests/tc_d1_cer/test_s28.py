"""S28 matrix checks for effective evidence identity reuse."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_CER_ASSERTION_BINDINGS = [pytest.mark.cer_assertion("A-7817-distinct-inputs")]


ROOT = Path(__file__).resolve().parents[4]
ENTRY = ROOT / "scripts/sc/skill_package_replay.py"
TARGET = ".agents/skills/run-refactor-implementation-acceptance"
CAPABILITY = "scripts/sc/config/skill-package-validator-capability.v1.json"


def _run_matrix(cases: list[dict]) -> tuple[int, dict]:
    matrix = {"schema_version": "jimuyun.stable-candidate-replay-matrix.v2", "cases": cases, "authorizes": []}
    child = (
        "import json, runpy, sys\n"
        "from pathlib import Path\n"
        "payload = sys.stdin.read()\n"
        "original_text, original_bytes = Path.read_text, Path.read_bytes\n"
        "def fixture_text(path, *args, **kwargs):\n"
        "    return payload if path.name == 's28-matrix.json' else original_text(path, *args, **kwargs)\n"
        "def fixture_bytes(path, *args, **kwargs):\n"
        "    return payload.encode('utf-8') if path.name == 's28-matrix.json' else original_bytes(path, *args, **kwargs)\n"
        "Path.read_text, Path.read_bytes = fixture_text, fixture_bytes\n"
        "sys.argv = [sys.argv[1], 'replay-matrix', '--matrix', 's28-matrix.json']\n"
        "runpy.run_path(sys.argv[0], run_name='__main__')\n"
    )
    process = subprocess.run(
        [sys.executable, "-B", "-c", child, str(ENTRY)], cwd=ROOT,
        input=json.dumps(matrix), capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=60, check=False,
    )
    try:
        receipt = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"Matrix entry did not return JSON: {exc}; stderr={process.stderr[:500]}")
    if not isinstance(receipt, dict):
        pytest.fail("Matrix entry did not return an object")
    return process.returncode, receipt


def _case(case_id: str, evidence_identity: str) -> dict:
    return {"case_id": case_id, "target": TARGET, "capability": CAPABILITY, "expected_exit": 0,
            "matrix_evidence": [{"effective_evidence_identity": evidence_identity}],
            "effective_evidence_identity": evidence_identity}


def _assert_behavior(condition: bool, failure_id: str, detail: object) -> None:
    if not condition:
        print(f"FAILURE_ID:{failure_id}")
    assert condition, detail


@pytest.mark.cer_assertion("A-7817-distinct-inputs")
@pytest.mark.cer_assertion("A-7051147536AB-1")
def test_duplicate_effective_evidence_identity_rejects_aggregate_with_both_cases() -> None:
    duplicate = "sha256:duplicate-effective-evidence"
    code, receipt = _run_matrix([_case("duplicate-one", duplicate), _case("duplicate-two", duplicate),
                                 _case("unique-control", "sha256:unique-control-evidence")])
    rows = {row.get("case_id"): row for row in receipt.get("case_results", []) if isinstance(row, dict)}
    duplicate_rows = [rows.get("duplicate-one", {}), rows.get("duplicate-two", {})]
    reasons = " ".join(str(row.get("rejection_reason", "")) for row in duplicate_rows).lower()
    named = all(
        row.get("case_id") == case_id
        and ("duplic" in str(row.get("rejection_reason", "")).lower()
             or "reus" in str(row.get("rejection_reason", "")).lower())
        for case_id, row in zip(("duplicate-one", "duplicate-two"), duplicate_rows)
    )
    _assert_behavior(
        code != 0 and receipt.get("status") != "pass" and receipt.get("aggregate_valid") is False
        and all(row.get("status") != "pass" for row in duplicate_rows) and named
        and rows.get("unique-control", {}).get("status") == "pass",
        "F-7051147536AB-DUPLICATE-EVIDENCE-ACCEPTED", receipt,
    )


@pytest.mark.cer_assertion("SM2-EFFECTIVE-IDENTITY-REUSE")
def test_reused_effective_identity_is_not_silently_deduplicated() -> None:
    shared = "sha256:shared-effective-evidence"
    code, receipt = _run_matrix([_case("case-a", shared), _case("case-b", shared),
                                 _case("independent-control", "sha256:independent-effective-evidence")])
    rows = receipt.get("case_results") or []
    rejected_ids = {row.get("case_id") for row in rows if row.get("status") != "pass"}
    reasons = " ".join(str(row.get("rejection_reason", "")) for row in rows).lower()
    _assert_behavior(
        code != 0 and receipt.get("aggregate_valid") is False
        and {"case-a", "case-b"}.issubset(rejected_ids)
        and ("reus" in reasons or "duplic" in reasons or "copied" in reasons)
        and any(row.get("case_id") == "independent-control" and row.get("status") == "pass" for row in rows),
        "SM2-REUSED-EVIDENCE-ACCEPTED", receipt,
    )
