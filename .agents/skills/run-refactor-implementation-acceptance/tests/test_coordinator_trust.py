from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / ".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py"
sys.path.insert(0, str(SCRIPT.parent))


def _load():
    spec = importlib.util.spec_from_file_location("acceptance_cli_r0", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _request(tmp_path: Path) -> tuple[Path, dict]:
    prepared = tmp_path / "prepared.json"
    skill_receipt = tmp_path / "skill-receipt.json"
    skill_contract = tmp_path / "skill-contract.json"
    prepared.write_text(json.dumps({"schemaVersion": "acceptance-run-input.v1"}), encoding="utf-8")
    skill_receipt.write_text(json.dumps({"ready": True}), encoding="utf-8")
    skill_contract.write_text(json.dumps({"schema_version": "skill-input-contract.v1"}), encoding="utf-8")
    request = {
        "schemaVersion": "jimuyun.acceptance-coordinator-request.v3",
        "targetPlan": "execution-plans/fixture-plan",
        "preparedRunInput": {"path": prepared.name, "sha256": _sha(prepared)},
        "skillInputReceipt": {"path": skill_receipt.name, "sha256": _sha(skill_receipt)},
        "skillInputContract": {"path": skill_contract.name, "sha256": _sha(skill_contract)},
        "authorizes": [],
    }
    path = tmp_path / "request.json"
    path.write_text(json.dumps(request), encoding="utf-8")
    return path, request


@pytest.mark.parametrize("field", [
    "candidateBindingHash", "bundle", "evidence", "deterministicSourceSufficient",
    "semanticReviewRequired", "route", "actionReceipts", "actionDag", "recovery",
    "successor", "telemetry", "publicationAuthorized",
])
def test_coordinator_rejects_caller_control_fields_before_consumption(tmp_path: Path, field: str) -> None:
    module = _load()
    request_path, request = _request(tmp_path)
    request[field] = False
    request_path.write_text(json.dumps(request), encoding="utf-8")
    with pytest.raises(module.InputError, match="caller control"):
        module.run_coordinator(str(request_path), str(tmp_path / "result.json"))


def test_coordinator_derives_route_only_from_persisted_action_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load()
    request_path, _request_value = _request(tmp_path)
    prepared = {"schemaVersion": "acceptance-run-input.v1", "input": {"target": "execution-plans/fixture-plan"}, "inputHash": "sha256:" + "a" * 64, "candidateCustody": {}, "knowledgeContext": {"sha256": "sha256:" + "b" * 64}}
    monkeypatch.setattr(module, "_load_current_coordinator_inputs", lambda *_args: {
        "prepared": prepared,
        "prepared_ref": {"path": "prepared.json", "sha256": "sha256:" + "c" * 64},
        "receipt_ref": {"path": "skill-receipt.json", "sha256": "sha256:" + "d" * 64},
        "contract_ref": {"path": "skill-contract.json", "sha256": "sha256:" + "e" * 64},
        "target_plan": "execution-plans/fixture-plan",
    })
    monkeypatch.setattr(module, "start_or_resume_target_run", lambda *_args, **_kwargs: {"runDirectory": "execution-plans/fixture-plan/acceptance-runs/run-1", "runId": "run-1"})
    monkeypatch.setattr(module, "inspect_persisted_run", lambda *_args, **_kwargs: {"state": "waiting", "authorizes": []})
    result = module.run_coordinator(str(request_path), str(tmp_path / "result.json"))
    assert result["route"] == "waiting_for_persisted_action"
    assert result["authorizes"] == []
    assert result["requestAuthority"] == "none"


def test_coordinator_rejects_prepared_run_hash_mismatch(tmp_path: Path) -> None:
    module = _load()
    request_path, request = _request(tmp_path)
    request["preparedRunInput"]["sha256"] = "sha256:" + "0" * 64
    request_path.write_text(json.dumps(request), encoding="utf-8")
    with pytest.raises(module.InputError, match="prepared run input.*stale"):
        module.run_coordinator(str(request_path), str(tmp_path / "result.json"))
