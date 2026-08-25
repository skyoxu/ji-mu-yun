from pathlib import Path
def test_false_green_promotion_red() -> None:
    if not (Path(__file__).parents[1] / "probe-state" / "S5.json").is_file():
        raise AssertionError("FAILURE_ID:PROMOTION-FALSE-GREEN-RED")
