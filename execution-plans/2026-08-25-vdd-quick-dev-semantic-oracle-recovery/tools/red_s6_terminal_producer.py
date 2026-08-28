from pathlib import Path
from terminal_validator import write_manifest

def test_terminal_requires_closed_lineage(tmp_path: Path) -> None:
    result = write_manifest(tmp_path, tmp_path / "RUN-S6")
    assert result.is_file(), "FAILURE_ID:TERMINAL-LINEAGE-NOT-CLOSED"
