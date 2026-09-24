from pathlib import Path

import pytest

from s6_fixture import assert_boundary_observation, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.cer_assertion("A-O-026DB292EA9A-1")
def test_o_026db292ea9a() -> None:
    assert_boundary_observation(
        run_boundary_case(REPOSITORY_ROOT, "O_026DB292EA9A"),
        "S6-OBSERVATION O-026DB292EA9A pre-restore-lease-rejected-at-current-publication-boundary",
        "FAILURE-O-026DB292EA9A",
    )


@pytest.mark.cer_assertion("A-O-BA014C1EB184-1")
def test_o_ba014c1eb184() -> None:
    assert_boundary_observation(
        run_boundary_case(REPOSITORY_ROOT, "O_BA014C1EB184"),
        "S6-OBSERVATION O-BA014C1EB184 retry-appended-history-and-reached-terminal-state",
        "FAILURE-O-BA014C1EB184",
    )


@pytest.mark.cer_assertion("A-DE045-BINDINGS")
def test_o_de0452fc4b15() -> None:
    assert_boundary_observation(
        run_boundary_case(REPOSITORY_ROOT, "O_DE0452FC4B15"),
        "S6-OBSERVATION O-DE0452FC4B15 six-restore-bindings-read-back-and-remained-immutable",
        "FAILURE-O-DE0452FC4B15",
    )
