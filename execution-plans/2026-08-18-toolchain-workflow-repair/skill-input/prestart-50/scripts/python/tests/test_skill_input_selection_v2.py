from scripts.python import skill_input_consumption as consumption

def test_typed_selection_keeps_selection_and_content_identity_separate():
    source = [{"role": "normative_source", "path": "docs/input.md", "module": "plan", "resource_set": "core", "sha256": "sha256:" + "a" * 64}]
    result = consumption.build_typed_source_selection_v2(source)
    assert result["sourceSelectionHash"].startswith("sha256:")
    assert result["sourceContentHash"].startswith("sha256:")

def test_successor_generation_id_does_not_change_selection_hash():
    base = {"consumer": "quick-dev-tdd-adapter", "operation": "execute", "target": "plan", "source_roles": {"target_files": ["requirements.md"]}}
    first = consumption.source_selection_hash({**base, "route_identity": "quick-dev.self_hosted.plan.prestart-45"})
    successor = consumption.source_selection_hash({**base, "route_identity": "other-route.prestart-46"})
    assert first == successor

def test_equivalent_source_role_order_does_not_change_selection_hash():
    base = {"consumer": "quick-dev-tdd-adapter", "operation": "execute", "target": "plan"}
    first = consumption.source_selection_hash({**base, "source_roles": {"target_files": ["requirements.md", "AGENTS.md"]}})
    equivalent = consumption.source_selection_hash({**base, "source_roles": {"target_files": ["AGENTS.md", "requirements.md"]}})
    assert first == equivalent
