from pathlib import Path

import pytest

from s73_fixture import assert_boundary_observation, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.cer_assertion("A-O-E443F1B126A1-1")
def test_o_e443f1b126a1() -> None:
    assert_boundary_observation(
        run_boundary_case(REPOSITORY_ROOT, "O_E443F1B126A1"),
        "S73-OBSERVATION O-E443F1B126A1 durable-lease-read-after-restart-fenced-publication",
        "FAILURE-O-E443F1B126A1",
    )


@pytest.mark.cer_assertion("A-O-1E153CD67F3B-1")
def test_o_1e153cd67f3b() -> None:
    assert_boundary_observation(
        run_boundary_case(REPOSITORY_ROOT, "O_1E153CD67F3B"),
        "S73-OBSERVATION O-1E153CD67F3B superseding-lease-has-greater-durable-fence",
        "FAILURE-O-1E153CD67F3B",
    )
