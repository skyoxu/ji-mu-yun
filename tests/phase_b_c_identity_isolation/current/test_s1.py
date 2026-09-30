from pathlib import Path
import pytest
from s1_fixture import run_boundary_case,assert_boundary
ROOT=Path(__file__).resolve().parents[3]
@pytest.mark.cer_assertion('A-OD3-1')
def test_o_d3e322003eab(): assert_boundary(run_boundary_case(ROOT,'O_D3E322003EAB'),'FAILURE-O-D3E322003EAB')
