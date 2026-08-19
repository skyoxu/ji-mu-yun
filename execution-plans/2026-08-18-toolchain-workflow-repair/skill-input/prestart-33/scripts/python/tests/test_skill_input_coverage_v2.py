from scripts.python import skill_input_coverage as coverage

def test_coverage_rejects_missing_required_page():
    result = coverage.evaluate_coverage(required_pages=["p1", "p2"], observed_pages=["p1"])
    assert result["status"] == "insufficient"
    assert result["missing"] == ["p2"]
