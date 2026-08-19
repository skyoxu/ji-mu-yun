from scripts.python import skill_input_transport as transport

def test_transport_has_deterministic_resume_contract():
    assert callable(getattr(transport, "plan_transport", None))
    assert callable(getattr(transport, "resume_transport", None))
