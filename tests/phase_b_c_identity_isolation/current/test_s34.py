from pathlib import Path

import pytest

from s34_fixture import assert_boundary, run_boundary_case


ROOT = Path(__file__).resolve().parents[3]


def _check(method: str, failure_id: str) -> None:
    assert_boundary(run_boundary_case(ROOT, method), method, failure_id)


@pytest.mark.cer_assertion("A-O049-1")
@pytest.mark.cer_assertion("A-O049-2")
def test_o_049f0e7e8cde(): _check("O_049F0E7E8CDE", "FAILURE-O-049F0E7E8CDE")

@pytest.mark.cer_assertion("A-O0C1-1")
@pytest.mark.cer_assertion("A-O0C1-2")
def test_o_0c1bf91bc308(): _check("O_0C1BF91BC308", "FAILURE-O-0C1BF91BC308")

@pytest.mark.cer_assertion("A-O39C-1")
@pytest.mark.cer_assertion("A-O39C-2")
def test_o_39c25a1e9fa2(): _check("O_39C25A1E9FA2", "FAILURE-O-39C25A1E9FA2")

@pytest.mark.cer_assertion("A-O-3B1FE89486EA-SECRET-EXCLUSION")
def test_o_3b1fe89486ea(): _check("O_3B1FE89486EA", "FAILURE-O-3B1FE89486EA")

@pytest.mark.cer_assertion("A-O-3D17BC6660AC-ACTION")
def test_o_3d17bc6660ac(): _check("O_3D17BC6660AC", "FAILURE-O-3D17BC6660AC")

@pytest.mark.cer_assertion("A-4067-preserve-accounts")
def test_o_4067d06649d3(): _check("O_4067D06649D3", "FAILURE-O-4067D06649D3")

@pytest.mark.cer_assertion("A-O-486B2FEAA661-RESTORE-EVENTS")
def test_o_486b2feaa661(): _check("O_486B2FEAA661", "FAILURE-O-486B2FEAA661")

@pytest.mark.cer_assertion("A-O-72735DA2286C-WORKSPACE")
def test_o_72735da2286c(): _check("O_72735DA2286C", "FAILURE-O-72735DA2286C")

@pytest.mark.cer_assertion("A-O-8826288FBF5D-1")
def test_o_8826288fbf5d(): _check("O_8826288FBF5D", "FAILURE-O-8826288FBF5D")

@pytest.mark.cer_assertion("A-O-9E636F2A131D-1")
def test_o_9e636f2a131d(): _check("O_9E636F2A131D", "FAILURE-O-9E636F2A131D")

@pytest.mark.cer_assertion("A-OD069-1")
def test_o_d069b01b8c84(): _check("O_D069B01B8C84", "FAILURE-O-D069B01B8C84")
