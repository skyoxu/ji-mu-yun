from scripts.python import skill_input_coverage as coverage
import pytest

def test_coverage_rejects_missing_required_page():
    result = coverage.evaluate_coverage(required_pages=["p1", "p2"], observed_pages=["p1"])
    assert result["status"] == "insufficient"
    assert result["missing"] == ["p2"]

def test_coverage_rejects_conflicting_duplicate_page():
    result = coverage.evaluate_coverage(required_pages=["p1"], observed_pages=["p1", "p1"])
    assert result["status"] == "insufficient"

def test_coverage_rejects_unexpected_page():
    result = coverage.evaluate_coverage(required_pages=["p1"], observed_pages=["p1", "p3"])
    assert result["status"] == "insufficient"

def test_coverage_rejects_invalid_page_identity():
    with pytest.raises(ValueError):
        coverage.evaluate_coverage(required_pages=["p1"], observed_pages=[None])

def test_coverage_rejects_source_hash_drift():
    result = coverage.evaluate_coverage(required_pages=["p1"], observed_pages=["p1"], source_hash="sha256:" + "a" * 64, observed_source_hash="sha256:" + "b" * 64)
    assert result["status"] == "stale-source"
