from pathlib import Path
from terminal_validator import write_manifest

def test_terminal_requires_closed_lineage(tmp_path: Path) -> None:
    try:
        write_manifest(tmp_path, tmp_path / "RUN-S6")
    except (FileNotFoundError, ValueError, OSError):
        return
    raise AssertionError("FAILURE_ID:TERMINAL-LINEAGE-NOT-CLOSED")
