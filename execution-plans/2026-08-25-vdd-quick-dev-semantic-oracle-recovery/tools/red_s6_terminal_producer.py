from terminal_validator import prepare_terminal_observation
from pathlib import Path

def test_terminal_requires_closed_lineage(tmp_path: Path) -> None:
    plan_dir = Path(__file__).resolve().parents[1]
    try:
        prepare_terminal_observation(plan_dir, tmp_path / "RUN-S6")
    except (ValueError, OSError) as exc:
        raise AssertionError(f"FAILURE_ID:TERMINAL-LINEAGE-NOT-CLOSED ({exc})") from exc
