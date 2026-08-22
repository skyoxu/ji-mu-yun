from __future__ import annotations

import json
from pathlib import Path

import pytest


def _legacy_request(tmp_path: Path) -> Path:
    path = tmp_path / "legacy-request.json"
    path.write_text(json.dumps({
        "schemaVersion": "acceptance-coordinator-request.v3",
        "candidateBindingHash": "sha256:" + "a" * 64,
        "bundle": {}, "evidence": {}, "authorizes": [],
    }), encoding="utf-8")
    return path


def test_coordinator_rejects_legacy_caller_owned_v3_request(tmp_path: Path) -> None:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import acceptance_cli

    with pytest.raises(acceptance_cli.InputError, match="coordinator bundle is invalid"):
        acceptance_cli.run_coordinator(str(_legacy_request(tmp_path)), str(tmp_path / "result.json"))


def test_coordinator_does_not_accept_caller_route_override(tmp_path: Path) -> None:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import acceptance_cli

    request = _legacy_request(tmp_path)
    value = json.loads(request.read_text(encoding="utf-8"))
    value["route"] = "deterministic_only"
    request.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(acceptance_cli.InputError, match="caller control"):
        acceptance_cli.run_coordinator(str(request), str(tmp_path / "result.json"))


def test_coordinator_executes_dag_and_finalizes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import acceptance_cli

    root = tmp_path
    target = root / "execution-plans" / "target"
    target.mkdir(parents=True)
    (target / "action-dag.v1.json").write_text(json.dumps({"actions": [{
        "actionId": "one", "dependsOn": [], "order": 1, "commandId": "one", "activation": True,
    }]}), encoding="utf-8")
    (target / "command-registry.v1.json").write_text(json.dumps({"schema_version": "ria.command-registry.v1", "commands": []}), encoding="utf-8")
    run_dir = root / "execution-plans" / "target" / "acceptance-runs" / "run-1"
    run_dir.mkdir(parents=True)
    (root / "request.json").write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(acceptance_cli, "REPOSITORY_ROOT", root)
    monkeypatch.setattr(acceptance_cli, "_load_current_coordinator_inputs", lambda *_: {
        "prepared": {"input": {"execution_mode": "evidence_only"}, "inputHash": "sha256:" + "a" * 64, "knowledgeContext": {"sha256": "sha256:" + "b" * 64}},
        "prepared_ref": {"path": "prepared.json", "sha256": "sha256:" + "c" * 64},
        "receipt_ref": {}, "contract_ref": {}, "target_plan": "execution-plans/target",
    })
    monkeypatch.setattr(acceptance_cli, "start_or_resume_target_run", lambda *args: {"runId": "run-1", "runDirectory": "execution-plans/target/acceptance-runs/run-1"})
    monkeypatch.setattr(acceptance_cli, "derive_target_run_identity", lambda *args, **kwargs: {"runId": "run-1", "runDirectory": "execution-plans/target/acceptance-runs/run-1", "runDirectoryPath": run_dir})
    states = iter([
        {"actionStates": {"one": "ready"}, "nextAction": {"actionId": "one"}, "readyActionIds": ["one"]},
        {"actionStates": {"one": "completed"}, "nextAction": None, "readyActionIds": []},
    ])
    monkeypatch.setattr(acceptance_cli, "inspect_persisted_run", lambda *args: next(states))
    calls = []
    monkeypatch.setattr(acceptance_cli, "resume_persisted_run", lambda *args: calls.append(args))
    monkeypatch.setattr(acceptance_cli, "finalize_deterministic_run", lambda *args: {"status": "acceptance-passed", "authorizes": ["acceptance-passed"]})
    result = acceptance_cli.run_coordinator(str(root / "request.json"), str(root / "result.json"))
    assert result["status"] == "completed"
    assert result["executedActionCount"] == 1
    assert result["finalization"]["status"] == "acceptance-passed"
    assert result["telemetry"]["path"] == "coordinator-telemetry.jsonl"
    telemetry = json.loads((run_dir / "coordinator-telemetry.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert telemetry["executedActionCount"] == 1
    assert {"waitMs", "interventionCount", "elapsedMs"}.issubset(telemetry)
    assert len(calls) == 1


def test_coordinator_emits_typed_handoff_without_bootstrap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import acceptance_cli

    target = tmp_path / "execution-plans" / "target"
    target.mkdir(parents=True)
    (target / "action-dag.v1.json").write_text(json.dumps({"actions": [{
        "actionId": "one", "dependsOn": [], "order": 1, "commandId": "one", "activation": False,
    }]}), encoding="utf-8")
    (target / "command-registry.v1.json").write_text(json.dumps({"schema_version": "ria.command-registry.v1", "commands": []}), encoding="utf-8")
    (tmp_path / "request.json").write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(acceptance_cli, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(acceptance_cli, "_load_current_coordinator_inputs", lambda *_: {
        "prepared": {"input": {"execution_mode": "evidence_only", "semantic_review_required": True, "actions": [{"actionId": "one", "dependsOn": [], "order": 1, "commandId": "one", "activation": True}]}, "inputHash": "sha256:" + "a" * 64, "knowledgeContext": {"sha256": "sha256:" + "b" * 64}},
        "prepared_ref": {"path": "prepared.json", "sha256": "sha256:" + "c" * 64}, "receipt_ref": {}, "contract_ref": {}, "target_plan": "execution-plans/target",
    })
    monkeypatch.setattr(acceptance_cli, "start_or_resume_target_run", lambda *args: {"runId": "run-1", "runDirectory": "execution-plans/target/runs/run-1"})
    calls = {"inspect": 0, "resume": 0, "finalize": 0}
    monkeypatch.setattr(acceptance_cli, "inspect_persisted_run", lambda *args: calls.__setitem__("inspect", calls["inspect"] + 1))
    monkeypatch.setattr(acceptance_cli, "resume_persisted_run", lambda *args: calls.__setitem__("resume", calls["resume"] + 1))
    monkeypatch.setattr(acceptance_cli, "finalize_deterministic_run", lambda *args: calls.__setitem__("finalize", calls["finalize"] + 1))
    result = acceptance_cli.run_coordinator(str(tmp_path / "request.json"), str(tmp_path / "result.json"))
    assert result["route"] == "semantic_review_required"
    assert result["typedHandoff"]["schemaVersion"] == "acceptance-semantic-handoff.v2"
    assert result["bootstrapInvoked"] is False
    assert calls == {"inspect": 0, "resume": 0, "finalize": 0}


def test_v4_coordinator_replay_is_idempotent_for_same_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import acceptance_cli

    target = tmp_path / "execution-plans" / "target"
    target.mkdir(parents=True)
    (target / "action-dag.v1.json").write_text(json.dumps({"actions": [{
        "actionId": "one", "dependsOn": [], "order": 1, "commandId": "one", "activation": True,
    }]}), encoding="utf-8")
    (target / "command-registry.v1.json").write_text(json.dumps({"schema_version": "ria.command-registry.v1", "commands": []}), encoding="utf-8")
    (tmp_path / "request.json").write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(acceptance_cli, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(acceptance_cli, "_load_current_coordinator_inputs", lambda *_: {
            "prepared": {"input": {"execution_mode": "evidence_only", "semantic_review_required": False, "actions": [{"actionId": "one", "dependsOn": [], "order": 1, "commandId": "one", "activation": True}]}, "inputHash": "sha256:" + "a" * 64, "knowledgeContext": {"sha256": "sha256:" + "b" * 64}},
        "prepared_ref": {"path": "prepared.json", "sha256": "sha256:" + "c" * 64}, "receipt_ref": {}, "contract_ref": {}, "target_plan": "execution-plans/target",
    })
    run_dir = tmp_path / "execution-plans" / "target" / "acceptance-runs" / "run-1"
    run_dir.mkdir(parents=True)
    monkeypatch.setattr(acceptance_cli, "derive_target_run_identity", lambda *args, **kwargs: {"runId": "run-1", "runDirectory": "execution-plans/target/acceptance-runs/run-1", "runDirectoryPath": run_dir})
    monkeypatch.setattr(acceptance_cli, "start_or_resume_target_run", lambda *args: {"runId": "run-1", "runDirectory": "execution-plans/target/acceptance-runs/run-1"})
    states = iter([
        {"actionStates": {"one": "ready"}, "nextAction": {"actionId": "one"}, "readyActionIds": ["one"]},
        {"actionStates": {"one": "completed"}, "nextAction": None, "readyActionIds": []},
    ])
    monkeypatch.setattr(acceptance_cli, "inspect_persisted_run", lambda *args: next(states))
    monkeypatch.setattr(acceptance_cli, "resume_persisted_run", lambda *args: None)
    monkeypatch.setattr(acceptance_cli, "finalize_deterministic_run", lambda *args: {"status": "acceptance-passed", "authorizes": ["acceptance-passed"]})
    contract_hash = acceptance_cli.canonical_hash({"preparedRunInput": {"path": "prepared.json", "sha256": "sha256:" + "c" * 64}, "skillInputContract": {}})
    (run_dir / "run-state.json").write_text(json.dumps({"runId": "run-1", "runInputHash": "sha256:" + "a" * 64, "contractHash": contract_hash, "knowledgeContextHash": "sha256:" + "b" * 64}), encoding="utf-8")
    first = acceptance_cli.run_coordinator(str(tmp_path / "request.json"), str(tmp_path / "result.json"))
    second = acceptance_cli.run_coordinator(str(tmp_path / "request.json"), str(tmp_path / "result.json"))
    assert first == second
