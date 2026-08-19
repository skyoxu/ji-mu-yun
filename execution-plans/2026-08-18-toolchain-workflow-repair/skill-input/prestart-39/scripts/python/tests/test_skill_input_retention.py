from scripts.python import skill_input_retention as retention

def test_retention_apply_requires_explicit_approval(tmp_path):
    plan = retention.plan_retention(tmp_path, dry_run=True)
    assert plan["mode"] == "dry-run"
    assert retention.apply_retention(tmp_path, approval=None)["status"] == "approval-required"
