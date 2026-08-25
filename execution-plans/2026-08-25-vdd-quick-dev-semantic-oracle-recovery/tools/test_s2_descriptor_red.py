from pathlib import Path
def test_descriptor_boundary_red() -> None:
    if not (Path(__file__).parents[1] / "probe-state" / "S2.json").is_file():
        raise AssertionError("FAILURE_ID:QD-DESCRIPTOR-RED")
