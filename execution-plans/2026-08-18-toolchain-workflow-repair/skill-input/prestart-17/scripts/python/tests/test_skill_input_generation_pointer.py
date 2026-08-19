from scripts.python import skill_input_generation as generation
from scripts.python import skill_input_current as current

def test_failed_generation_does_not_advance_current_pointer(tmp_path):
    before = current.resolve_current(tmp_path)
    generation.publish_generation(tmp_path, generation_id="g1", content=b"x")
    after = current.resolve_current(tmp_path)
    assert before == after
