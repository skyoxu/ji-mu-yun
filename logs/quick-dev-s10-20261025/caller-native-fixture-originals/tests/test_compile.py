import runpy
import pytest
from pathlib import Path
@pytest.mark.cer_assertion("ASSERT-COMPILE")
def test_compile():
    assert runpy.run_path(str(Path(__file__).parents[1]/"src/compiler.py"))["VALUE"] == 1
