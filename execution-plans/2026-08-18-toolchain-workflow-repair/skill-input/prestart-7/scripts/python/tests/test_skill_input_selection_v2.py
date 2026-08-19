from scripts.python import skill_input_consumption as consumption

def test_typed_selection_keeps_selection_and_content_identity_separate():
    source = [{"role": "normative_source", "path": "docs/input.md", "module": "plan", "resource_set": "core", "sha256": "sha256:a"}]
    result = consumption.build_typed_source_selection_v2(source)
    assert result["sourceSelectionHash"].startswith("sha256:")
    assert result["sourceContentHash"].startswith("sha256:")
