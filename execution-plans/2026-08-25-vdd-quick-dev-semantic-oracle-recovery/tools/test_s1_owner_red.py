from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
import semantic_oracle


def test_vdd_owner_compiles_run_local_semantic_artifacts() -> None:
    compiler = getattr(semantic_oracle, "compile_run_local_semantic_artifacts", None)
    assert callable(compiler), "FAILURE_ID:VDD-SEMANTIC-PRODUCER-MISSING"
    try:
        result = compiler(Path(__file__).parent.parent / "S1-RED")
    except (FileNotFoundError, ValueError) as exc:
        assert False, f"FAILURE_ID:VDD-SEMANTIC-PRODUCER-MISSING ({exc})"
    assert isinstance(result, dict) and result.get("producer") == "vdd" and result.get("status") == "pass", "FAILURE_ID:VDD-SEMANTIC-PRODUCER-MISSING"
