from pathlib import Path
import importlib.util
import pytest

def test_terminal_boundary_red(tmp_path: Path) -> None:
    validator = Path(__file__).parent / "terminal_validator.py"
    spec = importlib.util.spec_from_file_location("terminal_validator", validator)
    assert spec and spec.loader, "FAILURE_ID:TERMINAL-BOUNDARY-RED"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    plan = Path(__file__).parent.parent
    with pytest.raises(ValueError, match="ambiguous or missing"):
        module.write_manifest(plan, tmp_path / "RUN-1")
