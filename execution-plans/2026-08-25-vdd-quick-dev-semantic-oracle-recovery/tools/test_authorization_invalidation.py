from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).with_name("invalidate_stale_authorization.py")


def _load(tmp_path: Path):
    spec = importlib.util.spec_from_file_location("authorization_invalidation", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.ROOT = tmp_path
    module.PLAN = tmp_path / "execution-plans" / module.PLAN_ID
    module.RECEIPT = module.PLAN / "implementation-authorization-receipt.v3.json"
    return module


def _write(path: Path, value: object) -> dict[str, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    return {"path": path.relative_to(path.parents[2]).as_posix(), "sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()}


def _setup(tmp_path: Path, *, stale: bool):
    module = _load(tmp_path)
    plan = module.PLAN
    contract = _write(plan / "implementation-contract.v1.json", {"version": 2})
    registry = _write(plan / "command-registry.v1.json", {"version": 2})
    authority = _write(plan / "knowledge-context.freeze.v1.json", {"version": 1})
    receipt_contract = dict(contract)
    if stale:
        receipt_contract["sha256"] = "sha256:stale"
    _write(module.RECEIPT, {
        "implementation_contract": receipt_contract,
        "command_registry": registry,
        "authority_manifest": authority,
    })
    _write(plan / "plan-state.v1.json", {
        "plan_id": module.PLAN_ID,
        "state": "implementation-authorized",
        "authorizes": ["implementation-authorized"],
        "canonical_selection_hash": "sha256:selection",
    })
    return module


def test_stale_authorization_is_recorded_and_restores_plan_ready(tmp_path: Path) -> None:
    module = _setup(tmp_path, stale=True)
    module.main()
    state = json.loads((module.PLAN / "plan-state.v1.json").read_text(encoding="utf-8"))
    assert state["state"] == "plan-ready"
    assert state["authorizes"] == ["plan-ready"]
    evidence = module.PLAN / "governance"
    recorded = next(evidence.glob("implementation-authorization-invalidation.v2.*.json"))
    assert json.loads(recorded.read_text(encoding="utf-8"))["stale_bindings"] == ["implementation_contract"]
    module.main()


def test_current_authorization_cannot_be_downgraded(tmp_path: Path) -> None:
    module = _setup(tmp_path, stale=False)
    with pytest.raises(SystemExit, match="must not be invalidated"):
        module.main()
