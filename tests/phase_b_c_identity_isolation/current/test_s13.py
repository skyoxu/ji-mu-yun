import pytest

from s13_fixture import assert_behavior, invoke_boundary_test


CASE_PREFIX = "PhaseA.Platform.Tests.PhaseB.Repair.S13BoundaryTests"


@pytest.mark.cer_assertion("A-O-14E737AA22E2-1")
def test_o_14e737aa22e2() -> None:
    result = invoke_boundary_test(f"{CASE_PREFIX}.O_14E737AA22E2")
    assert_behavior(
        result,
        "S13-OBSERVATION O-14E737AA22E2 pre-restore-secret-rejected",
        "FAILURE-O-14E737AA22E2",
    )


@pytest.mark.parametrize(
    "assertion_id,expected_observation",
    [
        pytest.param(
            "A-O-6D37E601F3EB-1",
            "S13-OBSERVATION O-6D37E601F3EB drift-blocked",
            marks=pytest.mark.cer_assertion("A-O-6D37E601F3EB-1"),
        ),
        pytest.param(
            "A-O-6D37E601F3EB-2",
            "S13-OBSERVATION O-6D37E601F3EB repaired-published",
            marks=pytest.mark.cer_assertion("A-O-6D37E601F3EB-2"),
        ),
    ],
    ids=["drift-blocked", "repaired-published"],
)
def test_o_6d37e601f3eb(assertion_id: str, expected_observation: str) -> None:
    suffix = "DriftBlocked" if assertion_id.endswith("-1") else "RepairedPublished"
    result = invoke_boundary_test(f"{CASE_PREFIX}.O_6D37E601F3EB_{suffix}")
    assert_behavior(result, expected_observation, "FAILURE-O-6D37E601F3EB")


@pytest.mark.parametrize(
    "assertion_id,expected_observation",
    [
        pytest.param(
            "A-O-8736D23A1BAF-1",
            "S13-OBSERVATION O-8736D23A1BAF drift-blocked",
            marks=pytest.mark.cer_assertion("A-O-8736D23A1BAF-1"),
        ),
        pytest.param(
            "A-O-8736D23A1BAF-2",
            "S13-OBSERVATION O-8736D23A1BAF repaired-published",
            marks=pytest.mark.cer_assertion("A-O-8736D23A1BAF-2"),
        ),
    ],
    ids=["drift-blocked", "repaired-published"],
)
def test_o_8736d23a1baf(assertion_id: str, expected_observation: str) -> None:
    suffix = "DriftBlocked" if assertion_id.endswith("-1") else "RepairedPublished"
    result = invoke_boundary_test(f"{CASE_PREFIX}.O_8736D23A1BAF_{suffix}")
    assert_behavior(result, expected_observation, "FAILURE-O-8736D23A1BAF")


@pytest.mark.cer_assertion("A-O-F17C15697A79-1")
def test_o_f17c15697a79() -> None:
    result = invoke_boundary_test(f"{CASE_PREFIX}.O_F17C15697A79")
    assert_behavior(
        result,
        "S13-OBSERVATION O-F17C15697A79 stale-lease-publication-denied",
        "FAILURE-O-F17C15697A79",
    )
