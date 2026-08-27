import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[5]
PUBLISHER = (
    ROOT
    / "execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery"
    / "tools/publish_candidate_authorization.py"
)
PLAN_NAME = "2026-08-25-vdd-quick-dev-semantic-oracle-recovery"


def _load():
    spec = importlib.util.spec_from_file_location("plan_scoped_authorization_publisher", PUBLISHER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write(root: Path, relative: str, value: dict) -> dict[str, str]:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return {
        "path": relative,
        "sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _inputs(root: Path) -> tuple[object, dict[str, Path]]:
    plan = root / "execution-plans" / PLAN_NAME
    governance = plan / "governance"
    contract = _write(root, f"execution-plans/{PLAN_NAME}/implementation-contract.v1.json", {"plan_id": "target"})
    registry = _write(root, f"execution-plans/{PLAN_NAME}/command-registry.v1.json", {"commands": []})
    _write(root, f"execution-plans/{PLAN_NAME}/knowledge-context.freeze.v1.json", {"status": "frozen"})
    _write(root, f"execution-plans/{PLAN_NAME}/plan-state.v1.json", {"canonical_selection_hash": "sha256:selection"})
    freeze = _write(root, f"execution-plans/{PLAN_NAME}/governance/freeze.json", {"status": "frozen"})
    mapping = _write(root, f"execution-plans/{PLAN_NAME}/governance/mapping.json", {"status": "reviewed"})
    required = {
        "semantic_handoff_hash": None,
        "source_manifest_hash": freeze["sha256"],
        "requirements_manifest_hash": mapping["sha256"],
        "ambiguity_ids": [],
        "affected_requirement_ids": [],
    }
    conformance = _write(root, f"execution-plans/{PLAN_NAME}/governance/conformance.json", {
        "status": "conformant",
        "errors": [],
        "authorizes": [],
        "source_manifest_hash": required["source_manifest_hash"],
        "requirements_manifest_hash": required["requirements_manifest_hash"],
    })
    review_input = _write(root, f"execution-plans/{PLAN_NAME}/governance/input.json", {
        "schema_version": "vdd-external-semantic-review-input.v1",
        "profile": "bootstrap-upstream-plan",
        "required_output": "vdd-review-run.v1",
        "authorizes": [],
        "candidate": {
            "head_commit": "candidate-1",
            "implementation_contract": contract,
            "command_registry": registry,
        },
        "source_freeze": freeze,
        "requirements_mapping": mapping,
        "required_review_bindings": required,
    })
    review = _write(root, f"execution-plans/{PLAN_NAME}/governance/review.json", {
        "schema_version": "vdd-review-run.v1",
        "status": "accepted",
        "decision": "accepted",
        "authorizes": [],
        "profile": "bootstrap-upstream-plan",
        **required,
    })
    binding = _write(root, f"execution-plans/{PLAN_NAME}/governance/binding.json", {
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
    module = _load()
    module.ROOT = root
    module.PLAN = plan
    return module, {
        "review_input": root / review_input["path"],
        "review": root / review["path"],
        "binding": root / binding["path"],
        "conformance": root / conformance["path"],
    }


def _argv(paths: dict[str, Path]) -> list[str]:
    return [
        "publish_candidate_authorization.py",
        "--review-input",
        str(paths["review_input"]),
        "--review-run",
        str(paths["review"]),
        "--review-binding",
        str(paths["binding"]),
        "--conformance",
        str(paths["conformance"]),
    ]


def test_publisher_accepts_only_an_exact_current_review(monkeypatch, tmp_path: Path) -> None:
    module, paths = _inputs(tmp_path)
    monkeypatch.setattr(sys, "argv", _argv(paths))
    module.main()
    receipt = json.loads((module.PLAN / "implementation-authorization-receipt.v3.json").read_text(encoding="utf-8"))
    assert receipt["schema_version"] == "quick-dev-tdd-adapter.implementation-authorization.v3"
    assert receipt["authorizes"] == ["implementation-authorized"]


def test_publisher_rejects_a_stale_reviewed_contract(monkeypatch, tmp_path: Path) -> None:
    module, paths = _inputs(tmp_path)
    review_input = json.loads(paths["review_input"].read_text(encoding="utf-8"))
    review_input["candidate"]["implementation_contract"]["sha256"] = "sha256:stale"
    paths["review_input"].write_text(
        json.dumps(review_input, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    monkeypatch.setattr(sys, "argv", _argv(paths))
    with pytest.raises(SystemExit, match="external review input is stale"):
        module.main()
