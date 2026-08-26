from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
import semantic_oracle


def test_vdd_owner_compiles_run_local_semantic_artifacts(tmp_path: Path) -> None:
    compiler = getattr(semantic_oracle, "compile_run_local_semantic_artifacts", None)
    assert callable(compiler), "FAILURE_ID:VDD-SEMANTIC-PRODUCER-MISSING"
    try:
        (tmp_path / "semantic-intent-input.v1.json").write_text('{"acceptance_ids":["A-SEMANTIC"],"producer":"vdd","coverage":"exact-cover","fixture_class":"positive","taxonomy":["semantic"]}\n', encoding="utf-8")
        result = compiler(tmp_path)
    except (FileNotFoundError, ValueError) as exc:
        assert False, f"FAILURE_ID:VDD-SEMANTIC-PRODUCER-MISSING ({exc})"
    assert isinstance(result, dict) and result.get("producer") == "vdd" and result.get("status") == "pass" and result.get("run_id") == tmp_path.name, "FAILURE_ID:VDD-SEMANTIC-PRODUCER-MISSING"
