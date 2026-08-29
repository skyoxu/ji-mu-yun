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
    required = {
        "semantic_handoff_hash": None,
        "source_manifest_hash": "sha256:source",
        "requirements_manifest_hash": "sha256:requirements",
        "ambiguity_ids": [],
        "affected_requirement_ids": [],
    }
    review = _write(root, "review.json", {
        "schema_version": "vdd-review-run.v1",
        "status": "accepted",
        "decision": "accepted",
        "authorizes": [],
        "profile": "bootstrap-upstream-plan",
        **required,
    })
    conformance = _write(root, "conformance.json", {
        "status": "conformant",
        "errors": [],
        "authorizes": [],
        "source_manifest_hash": required["source_manifest_hash"],
        "requirements_manifest_hash": required["requirements_manifest_hash"],
    })
    contract = _write(root, "contract.json", {})
    registry = _write(root, "registry.json", {})
    freeze = _write(root, "freeze.json", {})
    mapping = _write(root, "mapping.json", {})
    review_input = _write(root, "input.json", {
        "schema_version": "vdd-external-semantic-review-input.v1",
        "profile": "bootstrap-upstream-plan",
        "required_output": "vdd-review-run.v1",
        "authorizes": [],
        "required_review_bindings": required,
        "candidate": {
            "head_commit": "candidate-1",
            "implementation_contract": contract,
            "command_registry": registry,
        },
        "source_freeze": freeze,
        "requirements_mapping": mapping,
    })
    binding = _write(root, "binding.json", {
        "schema_version": "vdd-review-candidate-binding.v1",
        "status": "accepted",
        "decision": "accepted",
        "candidate_commit": "candidate-1",
        "review_input": review_input,
        "review_run": review,
        "conformance_result": conformance,
        "implementation_contract": contract,
        "command_registry": registry,
        "source_freeze": freeze,
        "requirements_mapping": mapping,
    })
    return {
        "candidate_commit": "candidate-1",
        "review_input": review_input,
        "review_run": review,
        "review_candidate_binding": binding,
        "conformance_result": conformance,
        "implementation_contract": contract,
        "command_registry": registry,
        "source_freeze": freeze,
        "requirements_mapping": mapping,
    }


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


def test_plan_scoped_review_still_binds_the_reviewed_contract(tmp_path: Path) -> None:
    module = _module()
    receipt = _receipt(tmp_path)
    receipt["schema_version"] = "quick-dev-tdd-adapter.implementation-authorization.v3"
    assert module._review_and_conformance_authorize(tmp_path, receipt)

    binding_path = tmp_path / "binding.json"
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    binding["implementation_contract"] = _write(tmp_path, "other-contract.json", {"stale": True})
    receipt["review_candidate_binding"] = _write(tmp_path, "binding.json", binding)
    assert not module._review_and_conformance_authorize(tmp_path, receipt)


def test_review_metadata_must_match_the_published_review_input(tmp_path: Path) -> None:
    module = _module()
    receipt = _receipt(tmp_path)
    receipt["schema_version"] = "quick-dev-tdd-adapter.implementation-authorization.v3"
    review_path = tmp_path / "review.json"
    review = json.loads(review_path.read_text(encoding="utf-8"))
    review["source_manifest_hash"] = "sha256:other-source"
    receipt["review_run"] = _write(tmp_path, "review.json", review)

    binding = json.loads((tmp_path / "binding.json").read_text(encoding="utf-8"))
    binding["review_run"] = receipt["review_run"]
    receipt["review_candidate_binding"] = _write(tmp_path, "binding.json", binding)
    assert not module._review_and_conformance_authorize(tmp_path, receipt)


def test_authorization_json_refs_accept_repository_lf_identity_on_crlf_checkout(tmp_path: Path) -> None:
    path = tmp_path / "receipt.json"
    path.write_bytes(b"{\"status\":\"accepted\"}\r\n")
    repository_lf = b"{\"status\":\"accepted\"}\n"
    binding = {
        "path": "receipt.json",
        "sha256": "sha256:" + hashlib.sha256(repository_lf).hexdigest(),
    }
    assert _module()._minimal_authorization_binding_is_current(tmp_path, binding)


def test_candidate_binding_accepts_only_complete_repair_successor_lineage(tmp_path: Path) -> None:
    module = _module()
    receipt = _receipt(tmp_path)
    predecessor_freeze = receipt["source_freeze"]
    predecessor_mapping = receipt["requirements_mapping"]
    review = receipt["review_run"]
    review_input = receipt["review_input"]

    successor_mapping = _write(tmp_path, "successor-mapping.json", {"version": "reviewed"})
    repair = _write(tmp_path, "repair.json", {
        "schema_version": "vdd-repair-input.v1",
        "authorizes": [],
        "frozen_authority": {"source_manifest": predecessor_freeze},
        "prior_requirements_manifest": predecessor_mapping,
        "repaired_requirements_manifest": successor_mapping,
        "review_run": review,
        "semantic_handoff_hash": None,
        "semantic_handoff": {
            "frozen_authority": {"source_manifest_hash": predecessor_freeze["sha256"]},
            "requirements_manifest_hash": predecessor_mapping["sha256"],
        },
    })
    successor_freeze = _write(tmp_path, "successor-freeze.json", {
        "schema_version": "vdd-source-freeze-manifest.v1",
        "authorizes": [],
        "repair_input": repair,
        "requirements_manifest": successor_mapping,
    })
    conformance = _write(tmp_path, "successor-conformance.json", {
        "status": "conformant",
        "errors": [],
        "authorizes": [],
        "source_manifest_hash": successor_freeze["sha256"],
        "requirements_manifest_hash": successor_mapping["sha256"],
    })
    binding = _write(tmp_path, "successor-binding.json", {
        "schema_version": "vdd-review-candidate-binding.v1",
        "status": "accepted",
        "decision": "accepted",
        "candidate_commit": "candidate-1",
        "review_input": review_input,
        "review_run": review,
        "conformance_result": conformance,
        "implementation_contract": receipt["implementation_contract"],
        "command_registry": receipt["command_registry"],
        "source_freeze": successor_freeze,
        "requirements_mapping": successor_mapping,
    })
    successor_receipt = dict(receipt)
    successor_receipt.update({
        "review_candidate_binding": binding,
        "conformance_result": conformance,
        "source_freeze": successor_freeze,
        "requirements_mapping": successor_mapping,
    })

    assert module._review_and_conformance_authorize(tmp_path, successor_receipt)

    repair_path = tmp_path / "repair.json"
    invalid_repair = json.loads(repair_path.read_text(encoding="utf-8"))
    invalid_repair["semantic_handoff_hash"] = "sha256:other"
    repair_path.write_text(json.dumps(invalid_repair), encoding="utf-8")
    assert not module._repair_successor_review_lineage_is_valid(
        tmp_path,
        json.loads((tmp_path / "input.json").read_text(encoding="utf-8")),
        json.loads((tmp_path / "review.json").read_text(encoding="utf-8")),
        json.loads((tmp_path / "successor-conformance.json").read_text(encoding="utf-8")),
        json.loads((tmp_path / "successor-binding.json").read_text(encoding="utf-8")),
        successor_receipt,
    )
