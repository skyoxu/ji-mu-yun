from scripts.python import skill_input_consumption as consumption

def test_end_to_end_workflow_has_typed_entrypoint():
    assert callable(getattr(consumption, "build_typed_source_selection_v2", None))
