from pathlib import Path
import importlib.util

def test_terminal_boundary_red(tmp_path: Path) -> None:
    validator = Path(__file__).parent / "validate_all.py"
    spec = importlib.util.spec_from_file_location("terminal_validator", validator)
    assert spec and spec.loader, "FAILURE_ID:TERMINAL-BOUNDARY-RED"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    plan = Path(__file__).parent.parent
    result = module.validate_terminal(plan, tmp_path / "RUN-1")
    assert result.get("status") == "blocked" and "lineage" in str(result.get("reason", "")), "FAILURE_ID:TERMINAL-LINEAGE-NOT-CLOSED"
