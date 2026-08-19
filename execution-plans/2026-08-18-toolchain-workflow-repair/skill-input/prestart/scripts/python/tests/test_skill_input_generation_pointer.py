from scripts.python import skill_input_generation as generation
from scripts.python import skill_input_current as current

def test_current_pointer_is_typed():
    assert callable(getattr(generation, "publish_generation", None))
    assert callable(getattr(current, "resolve_current", None))
