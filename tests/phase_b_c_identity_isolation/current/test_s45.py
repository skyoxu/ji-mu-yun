from pathlib import Path
import pytest
from s45_fixture import run_boundary_case
ROOT=Path(__file__).resolve().parents[3]
@pytest.mark.cer_assertion('A-OF7-1')
def test_o_f7e24ee2dfb2():
 o,e=run_boundary_case(ROOT,'O_F7E24EE2DFB2')
 assert o=='Passed' or 'FAILURE-O-F7E24EE2DFB2' in e
