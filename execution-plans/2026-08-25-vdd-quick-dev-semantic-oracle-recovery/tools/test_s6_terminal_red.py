from pathlib import Path

def test_terminal_boundary_red(tmp_path: Path) -> None:
    from validate_all import validate_terminal
    result = validate_terminal(tmp_path, tmp_path / "logs" / "tdd-adapter" / "plan" / "S6" / "run")
    assert result["status"] == "blocked" and result["predicate"] == "implementation-complete" and "missing" in result
