import hashlib
import importlib.util
import json
import shutil
import uuid
from pathlib import Path
from unittest import mock

import pytest


ROOT = Path(__file__).resolve().parents[4]
ROUTE = ROOT / ".agents" / "skills" / "quick-dev-tdd-adapter" / "tools" / "route_plan_directory.py"

COMMAND_ASSERTION = "A-O-5769FDE8D98B-native-command-identity-unchanged"
DEPENDENCY_ASSERTION = "A-O-58113F16F6E4-independent-semantic-dependency-closure"


@pytest.fixture
def tmp_path():
    parent = Path(__file__).resolve().parent / "_s39_tmp"
    parent.mkdir(exist_ok=True)
    path = parent / ("case-" + uuid.uuid4().hex)
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _route_module():
    spec = importlib.util.spec_from_file_location("s39_route_plan_directory", ROUTE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _ref(root: Path, name: str, value: dict) -> dict:
    path = root / name
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return {"path": name, "sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()}


def _review_receipt(root: Path) -> dict:
    bindings = {
        "semantic_handoff_hash": None,
        "source_manifest_hash": "sha256:source",
        "requirements_manifest_hash": "sha256:requirements",
        "ambiguity_ids": [],
        "affected_requirement_ids": [],
    }
    review = _ref(root, "review.json", {
        "schema_version": "vdd-review-run.v1",
        "status": "accepted",
        "decision": "accepted",
        "authorizes": [],
        "profile": "bootstrap-upstream-plan",
        **bindings,
    })
    conformance = _ref(root, "conformance.json", {
        "status": "conformant",
        "errors": [],
        "authorizes": [],
        "source_manifest_hash": bindings["source_manifest_hash"],
        "requirements_manifest_hash": bindings["requirements_manifest_hash"],
    })
    contract = _ref(root, "contract.json", {})
    registry = _ref(root, "registry.json", {})
    freeze = _ref(root, "freeze.json", {})
    mapping = _ref(root, "mapping.json", {})
    review_input = _ref(root, "input.json", {
        "schema_version": "vdd-external-semantic-review-input.v1",
        "profile": "bootstrap-upstream-plan",
        "required_output": "vdd-review-run.v1",
        "authorizes": [],
        "required_review_bindings": bindings,
        "candidate": {
            "head_commit": "candidate-1",
            "implementation_contract": contract,
            "command_registry": registry,
        },
        "source_freeze": freeze,
        "requirements_mapping": mapping,
    })
    candidate_binding = _ref(root, "binding.json", {
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
        "review_candidate_binding": candidate_binding,
        "conformance_result": conformance,
        "implementation_contract": contract,
        "command_registry": registry,
        "source_freeze": freeze,
        "requirements_mapping": mapping,
    }


@pytest.mark.cer_assertion(DEPENDENCY_ASSERTION)
@pytest.mark.parametrize("field", [
    "review_input", "review_run", "review_candidate_binding", "conformance_result",
    "implementation_contract", "command_registry", "source_freeze", "requirements_mapping",
])
@pytest.mark.parametrize("mutation", ["missing", "mismatched", "stale"])
def test_s39_independent_dependency_closure_rejects_missing_or_mismatched_binding(
    tmp_path: Path, field: str, mutation: str,
) -> None:
    module = _route_module()
    receipt = _review_receipt(tmp_path)
    assert module._review_and_conformance_authorize(tmp_path, receipt)

    broken = dict(receipt)
    if mutation == "missing":
        del broken[field]
    elif mutation == "mismatched":
        broken[field] = _ref(tmp_path, "substituted.json", {"substituted": True})
    else:
        path = tmp_path / receipt[field]["path"]
        original = json.loads(path.read_text(encoding="utf-8"))
        changed = {**original, "changed": True}
        if field == "review_candidate_binding":
            changed["candidate_commit"] = "stale-candidate"
        path.write_text(json.dumps(changed, sort_keys=True), encoding="utf-8")
        broken[field] = {
            "path": receipt[field]["path"],
            "sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    accepted = module._review_and_conformance_authorize(tmp_path, broken)
    if accepted:
        print("FAILURE_ID:F-O-58113F16F6E4-MISSING-OR-MISMATCHED-DEPENDENCY-BINDING")
    assert not accepted


@pytest.mark.cer_assertion(COMMAND_ASSERTION)
@pytest.mark.parametrize("field, replacement", [
    ("id", "renamed"),
    ("executable", "substituted-python"),
    ("argv", ["-3", "-c", "substituted"]),
])
def test_s39_native_command_identity_change_rejects_historical_reuse(
    tmp_path: Path, field: str, replacement: object,
) -> None:
    module = _route_module()
    plan = tmp_path
    contract = {
        "plan_id": "target",
        "slices": [{
            "slice_id": "S0",
            "depends_on": [],
            "tdd": {"red": {"command_id": "red"}},
        }],
    }
    baseline_registry = {"commands": [{"id": "red", "executable": "py", "argv": ["-3", "-c", "old"], "shell": False}]}
    candidate_registry = {"commands": [{**baseline_registry["commands"][0], field: replacement}]}
    contract_bytes = json.dumps(contract, sort_keys=True).encode("utf-8")
    candidate_registry_bytes = json.dumps(candidate_registry, sort_keys=True).encode("utf-8")
    (plan / "implementation-contract.v1.json").write_bytes(contract_bytes)
    (plan / "command-registry.v1.json").write_bytes(candidate_registry_bytes)

    def current_bytes(_root: Path, relative: Path) -> bytes:
        return contract_bytes if relative.name == "implementation-contract.v1.json" else candidate_registry_bytes

    with mock.patch.object(module, "_head_artifact_bytes", side_effect=current_bytes), mock.patch.object(
        module,
        "_historical_contract_and_registry",
        return_value=(contract_bytes, json.dumps(baseline_registry, sort_keys=True).encode("utf-8")),
    ):
        assert module._unaffected_slice_current(
            tmp_path, plan, contract, baseline_registry,
            {"contract_hash": "sha256:historical"}, "S0",
        )
        reusable = module._unaffected_slice_current(
            tmp_path,
            plan,
            contract,
            candidate_registry,
            {"contract_hash": "sha256:historical"},
            "S0",
        )
    if reusable:
        print("FAILURE_ID:F-O-5769FDE8D98B-COMMAND-IDENTITY-SUBSTITUTION")
    assert not reusable
