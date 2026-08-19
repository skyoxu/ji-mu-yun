from scripts.python import skill_input_consumption as consumption

def test_end_to_end_selection_exposes_independent_identity_hashes():
    result = consumption.build_typed_source_selection_v2([])
    assert result["sourceSelectionHash"] != result["sourceContentHash"]
