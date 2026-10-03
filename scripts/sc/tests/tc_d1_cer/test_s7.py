"""CER checks for S7 aggregate and validator rejection paths."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_CER_ASSERTION_BINDINGS = [pytest.mark.cer_assertion("A-FR5-HISTORICAL-NONAUT")]


ROOT = Path(__file__).resolve().parents[4]
ENTRY = ROOT / "scripts" / "sc" / "skill_package_replay.py"
CAPABILITY = "scripts/sc/config/skill-package-validator-capability.v1.json"
TARGET = ".agents/skills/run-refactor-implementation-acceptance"


def _matrix_result(case: dict) -> dict:
    matrix = {
        "schema_version": "jimuyun.stable-candidate-replay-matrix.v2",
        "cases": [case],
        "authorizes": [],
    }
    with tempfile.TemporaryDirectory(dir=ROOT) as directory:
        path = Path(directory) / "matrix.json"
        path.write_text(json.dumps(matrix), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "-B", str(ENTRY), "replay-matrix", "--matrix", str(path.relative_to(ROOT))],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"production replay entrypoint did not produce a JSON receipt: {exc}")
    if not isinstance(value, dict):
        pytest.fail("production replay entrypoint did not produce an object receipt")
    return value


def _assert_rejected(condition: bool, failure_id: str, message: str) -> None:
    if not condition:
        print(f"FAILURE_ID:{failure_id}")
    assert condition, message


def _case(**extra: object) -> dict:
    value = {
        "case_id": "s7-case",
        "target": TARGET,
        "capability": CAPABILITY,
        "expected_exit": 0,
    }
    value.update(extra)
    return value


@pytest.mark.cer_assertion("A-FR5-HISTORICAL-NONAUT")
@pytest.mark.cer_assertion("ASSERT-O-BBD73A1FB59F-01")
@pytest.mark.parametrize("probe_mode", ["stable-no-provenance", "stable-temporary-package"])
def test_stable_eligibility_requires_verified_provenance(probe_mode: str) -> None:
    result = subprocess.run(
        [sys.executable, "-B", str(ENTRY), "replay-package", "--target", TARGET, "--capability", CAPABILITY, "--probe-mode", probe_mode],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    try:
        receipt = json.loads(result.stdout)
    except json.JSONDecodeError:
        receipt = {}
    eligibility = receipt.get("stable_eligibility", {}) if isinstance(receipt, dict) else {}
    _assert_rejected(
        isinstance(eligibility, dict)
        and eligibility.get("eligible") is False
        and bool(eligibility.get("rejection_reason")),
        "STABLE-PROVENANCE-ABSENT",
        "Stable eligibility must require source-supported verified provenance",
    )


@pytest.mark.cer_assertion("A-O-2C811F501475-ADVERSARIAL-DEPENDENCY-REJECTS-SUCCESS")
def test_adversarial_dependency_case_is_non_success_with_reason() -> None:
    receipt = _matrix_result(_case(adversarial_dependency=True))
    row = (receipt.get("case_results") or [{}])[0]
    _assert_rejected(
        row.get("status") != "pass" and bool(row.get("rejection_reason")),
        "ADVERSARIAL_DEPENDENCY_SUCCESS_ACCEPTED",
        "adversarial dependency cases must be rejected with a reason",
    )


@pytest.mark.cer_assertion("A-O-F1B89B76738E-1")
def test_adversarial_validator_case_is_non_success_with_diagnostic() -> None:
    receipt = _matrix_result(_case(adversarial_validator=True))
    row = (receipt.get("case_results") or [{}])[0]
    _assert_rejected(
        row.get("status") != "pass" and bool(row.get("diagnostic")),
        "FI_O-F1B89B76738E_ADVERSARIAL_ACCEPTED",
        "adversarial validator cases must return a non-success diagnostic",
    )


@pytest.mark.cer_assertion("ASSERT-FR8-MISSING-MATRIX-INVALIDATES-AGGREGATE")
def test_missing_matrix_evidence_invalidates_aggregate() -> None:
    receipt = _matrix_result(_case(matrix_evidence=[]))
    _assert_rejected(
        receipt.get("status") != "pass" and receipt.get("aggregate_valid") is False,
        "MISSING_MATRIX_EVIDENCE_INVALIDATES_AGGREGATE",
        "missing required matrix evidence must invalidate the aggregate",
    )


@pytest.mark.cer_assertion("ASSERT-O-85124C301540-MISLABELED-MATRIX-EVIDENCE-INVALIDATES")
def test_mislabeled_matrix_evidence_invalidates_aggregate() -> None:
    receipt = _matrix_result(_case(matrix_case_id="other-case"))
    _assert_rejected(
        receipt.get("status") != "pass" and receipt.get("aggregate_valid") is False,
        "MISLABELED_MATRIX_EVIDENCE_ACCEPTED",
        "mislabeled matrix evidence must invalidate the aggregate",
    )


@pytest.mark.cer_assertion("ASSERT-O-B3386BF4E61D-01")
def test_copied_matrix_evidence_invalidates_aggregate() -> None:
    receipt = _matrix_result(_case(evidence_origin="copied"))
    _assert_rejected(
        receipt.get("status") != "pass" and receipt.get("aggregate_valid") is False,
        "COPIED-MATRIX-EVIDENCE",
        "copied matrix evidence must not produce an acceptance-eligible aggregate",
    )


@pytest.mark.cer_assertion("FR-8-WRONG-TARGET-INVALIDATES-AGGREGATE")
def test_wrong_target_matrix_evidence_invalidates_aggregate() -> None:
    receipt = _matrix_result(_case(bound_target=TARGET, evidence_target="scripts"))
    _assert_rejected(
        receipt.get("status") != "pass" and receipt.get("aggregate_valid") is False,
        "WRONG_TARGET_AGGREGATE_INVALID",
        "wrong-target matrix evidence must invalidate the aggregate",
    )


@pytest.mark.cer_assertion("FR-1-SUBSTITUTED-TARGET-FAILS-CLOSED")
def test_substituted_target_is_rejected_before_target_dependent_execution() -> None:
    result = subprocess.run(
        [sys.executable, "-B", str(ENTRY), "validate-package", "--target", "scripts", "--capability", CAPABILITY],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    _assert_rejected(
        result.returncode != 0,
        "FR1_SUBSTITUTED_TARGET_ACCEPTED",
        "a substituted target must be rejected before inspection",
    )
