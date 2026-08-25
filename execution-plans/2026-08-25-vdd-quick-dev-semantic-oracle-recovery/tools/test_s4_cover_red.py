from pathlib import Path
def test_exact_cover_red() -> None:
    if not (Path(__file__).parents[1] / "probe-state" / "S4.json").is_file():
        raise AssertionError("FAILURE_ID:COVERAGE-EXACT-COVER-RED")
