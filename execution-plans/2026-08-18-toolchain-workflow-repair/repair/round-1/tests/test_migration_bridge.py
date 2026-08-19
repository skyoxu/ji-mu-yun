import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[5]
TOOLS = ROOT / "execution-plans/2026-08-18-toolchain-workflow-repair/tools"


def _module():
    spec = importlib.util.spec_from_file_location("migration_bridge", TOOLS / "migration_bridge.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_bridge_declares_behavioral_templates_for_every_slice():
    templates = _module().TEMPLATES
    assert set(templates) == {"W0", "W1", "W2", "W3", "W4", "W5", "W6"}
    assert all("def test_" in source for source in templates.values())


def test_bridge_materializes_only_the_declared_test_in_a_temporary_repository(tmp_path):
    bridge = _module()
    plan = tmp_path / "execution-plans" / "toolchain-workflow-repair"
    plan.mkdir(parents=True)
    contract = json.loads((ROOT / "execution-plans/2026-08-18-toolchain-workflow-repair/implementation-contract.v1.json").read_text(encoding="utf-8"))
    (plan / "implementation-contract.v1.json").write_text(json.dumps(contract), encoding="utf-8")
    target = bridge.materialize(tmp_path, plan, "W0", ["scripts/python/tests/test_skill_input_selection_v2.py"])
    assert target == tmp_path / "scripts/python/tests/test_skill_input_selection_v2.py"
    assert target.read_text(encoding="utf-8") == bridge.TEMPLATES["W0"]
    assert bridge.materialize(tmp_path, plan, "W0", ["scripts/python/tests/test_skill_input_selection_v2.py"]) == target
    assert not (tmp_path / "scripts/python/skill_input_consumption.py").exists()


def test_bridge_rejects_wrong_slice_target_and_conflicting_existing_file(tmp_path):
    bridge = _module()
    plan = tmp_path / "execution-plans" / "toolchain-workflow-repair"
    plan.mkdir(parents=True)
    source = ROOT / "execution-plans/2026-08-18-toolchain-workflow-repair/implementation-contract.v1.json"
    (plan / "implementation-contract.v1.json").write_bytes(source.read_bytes())
    with pytest.raises(ValueError, match="declared RED test"):
        bridge.materialize(tmp_path, plan, "W0", ["scripts/python/tests/test_skill_input_transport_auto.py"])
    conflict = tmp_path / "scripts/python/tests/test_skill_input_selection_v2.py"
    conflict.parent.mkdir(parents=True)
    conflict.write_text("different", encoding="utf-8")
    with pytest.raises(ValueError, match="conflicts"):
        bridge.materialize(tmp_path, plan, "W0", ["scripts/python/tests/test_skill_input_selection_v2.py"])
