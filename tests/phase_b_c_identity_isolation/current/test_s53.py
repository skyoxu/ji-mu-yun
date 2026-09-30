from pathlib import Path

import pytest

from s53_fixture import assert_behavior, invoke_boundary_test


ROOT = Path(__file__).resolve().parents[3]


def _assert(method: str, accepted: bool, reason: str, artifact: str | None, failure_id: str) -> None:
    assert_behavior(invoke_boundary_test(ROOT, method), method, accepted, reason, artifact, failure_id)


@pytest.mark.cer_assertion("A-O1758-EVIDENCE-MISSING-REJECT")
def test_o_1758d7fa26d7() -> None: _assert("O_1758D7FA26D7", False, "missing_required_evidence", None, "FAILURE-O-1758D7FA26D7")
@pytest.mark.cer_assertion("A-O184-EVIDENCE-STALE-REJECT")
def test_o_184c7201648b() -> None: _assert("O_184C7201648B", False, "stale_evidence", None, "FAILURE-O-184C7201648B")
@pytest.mark.cer_assertion("A-O6BE-INDEPENDENT-VALIDATION")
def test_o_6be8dc802311() -> None: _assert("O_6BE8DC802311", True, "accepted", "snapshot", "FAILURE-O-6BE8DC802311")
@pytest.mark.cer_assertion("A-O8A-DECLARATION-NOT-SUFFICIENT")
def test_o_8a188783399e() -> None: _assert("O_8A188783399E", False, "missing_required_evidence", None, "FAILURE-O-8A188783399E")
@pytest.mark.cer_assertion("A-O-8FF9DCF91EDE-1")
def test_o_8ff9dcf91ede() -> None: _assert("O_8FF9DCF91EDE", False, "integrity_failure", None, "FAILURE-O-8FF9DCF91EDE")
@pytest.mark.cer_assertion("A-O-AD7298625129-1")
def test_o_ad7298625129() -> None: _assert("O_AD7298625129", True, "accepted", "permission", "FAILURE-O-AD7298625129")
@pytest.mark.cer_assertion("A-O-B2296F39A759-1")
def test_o_b2296f39a759() -> None: _assert("O_B2296F39A759", True, "accepted", "fault", "FAILURE-O-B2296F39A759")
@pytest.mark.cer_assertion("A-O-C1832CCFAB00-1")
def test_o_c1832ccfab00() -> None: _assert("O_C1832CCFAB00", True, "accepted", "redaction", "FAILURE-O-C1832CCFAB00")
@pytest.mark.cer_assertion("A-O-DAA21E146840-1")
def test_o_daa21e146840() -> None: _assert("O_DAA21E146840", False, "verification_not_executed", None, "FAILURE-O-DAA21E146840")
