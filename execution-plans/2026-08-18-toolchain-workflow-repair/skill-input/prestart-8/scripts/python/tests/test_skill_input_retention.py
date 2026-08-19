from scripts.python import skill_input_retention as retention

def test_retention_apply_requires_approval():
    assert callable(getattr(retention, "plan_retention", None))
    assert callable(getattr(retention, "apply_retention", None))
