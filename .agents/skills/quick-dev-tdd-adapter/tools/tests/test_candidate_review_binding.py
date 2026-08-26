import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
SCRIPT = ROOT / ".agents/skills/quick-dev-tdd-adapter/tools/route_plan_directory.py"


def _module():
    spec = importlib.util.spec_from_file_location("candidate_binding_route", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write(root: Path, name: str, value: dict) -> dict:
    path = root / name
    path.write_text(json.dumps(value), encoding="utf-8")
    return {"path": name, "sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()}


def _receipt(root: Path) -> dict:
    review = _write(root, "review.json", {"schema_version":"vdd-review-run.v1","status":"accepted","decision":"accepted"})
    conformance = _write(root, "conformance.json", {"status":"conformant","errors":[],"authorizes":[]})
    contract = _write(root, "contract.json", {})
    registry = _write(root, "registry.json", {})
    freeze = _write(root, "freeze.json", {})
    mapping = _write(root, "mapping.json", {})
    review_input = _write(root, "input.json", {"candidate":{"head_commit":"candidate-1","implementation_contract":contract,"command_registry":registry},"source_freeze":freeze,"requirements_mapping":mapping})
    binding = _write(root, "binding.json", {"schema_version":"vdd-review-candidate-binding.v1","status":"accepted","decision":"accepted","candidate_commit":"candidate-1","review_input":review_input,"review_run":review,"conformance_result":conformance,"implementation_contract":contract,"command_registry":registry,"source_freeze":freeze,"requirements_mapping":mapping})
    return {"candidate_commit":"candidate-1","review_input":review_input,"review_run":review,"review_candidate_binding":binding,"conformance_result":conformance,"implementation_contract":contract,"command_registry":registry,"source_freeze":freeze,"requirements_mapping":mapping}


def test_candidate_binding_requires_every_link(tmp_path: Path) -> None:
    module = _module(); receipt = _receipt(tmp_path)
    assert module._review_and_conformance_authorize(tmp_path, receipt)
    for field, value in (("review_candidate_binding", None), ("review_input", {"path":"input.json","sha256":"sha256:changed"}), ("conformance_result", {"path":"review.json","sha256":"sha256:x"})):
        broken = dict(receipt); broken[field] = value
        assert not module._review_and_conformance_authorize(tmp_path, broken)


def test_candidate_binding_rejects_reused_or_rejected_review(tmp_path: Path) -> None:
    module = _module(); receipt = _receipt(tmp_path)
    binding_path = tmp_path / "binding.json"; binding = json.loads(binding_path.read_text(encoding="utf-8"))
    binding["candidate_commit"] = "other-candidate"; binding_path.write_text(json.dumps(binding), encoding="utf-8")
    assert not module._review_and_conformance_authorize(tmp_path, receipt)
    binding["candidate_commit"] = "candidate-1"; binding["status"] = "rejected"; binding_path.write_text(json.dumps(binding), encoding="utf-8")
    assert not module._review_and_conformance_authorize(tmp_path, receipt)
