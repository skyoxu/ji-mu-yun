from scripts.python import skill_input_coverage as coverage

def test_coverage_is_adapter_owned():
    assert callable(getattr(coverage, "evaluate_coverage", None))
