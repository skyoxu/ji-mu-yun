from pathlib import Path
import pytest
from s64_fixture import run_boundary_case
ROOT=Path(__file__).resolve().parents[3]
@pytest.mark.cer_assertion('A-OE7-1')
def test_o_e7279108688a():
 o,e=run_boundary_case(ROOT,'O_E7279108688A'); assert o=='Passed' or 'FAILURE-O-E7279108688A' in e
