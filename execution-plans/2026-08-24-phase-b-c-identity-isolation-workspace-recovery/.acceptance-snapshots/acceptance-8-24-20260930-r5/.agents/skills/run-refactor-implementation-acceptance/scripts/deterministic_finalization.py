"""Acceptance-owned deterministic-only finalization (ADR-0053)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from acceptance_core import (
    InputError,
    canonical_hash,
    validate_baseline_manifest,
    validate_candidate_manifest,
    validate_run_input,
    verify_manifest_bytes,
)
from execution_control import (
    ControlError,
    inspect_persisted_run,
    reconstruct_completed_actions,
    resolve_registered_command,
)
from semantic_import import finalize_acceptance


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InputError(f"deterministic finalization input is unreadable: {path}") from exc


def _inside(root: Path, value: str, label: str) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise InputError(f"{label} must be repository-relative")
    path = (root / value).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise InputError(f"{label} escapes repository root") from exc
    return path


def _publish(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != encoded:
            raise InputError(f"deterministic finalization output is not append-only: {path.name}")
        return
    path.write_text(encoded, encoding="utf-8", newline="\n")


def _publish_current_pointer(path: Path, value: dict[str, Any]) -> None:
    """Publish the target-owned current projection; finalized runs remain immutable."""
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == encoded:
        return
    path.write_text(encoded, encoding="utf-8", newline="\n")


def _completed_receipts(run_dir: Path, actions: Any, command_registry: Any) -> list[dict[str, Any]]:
    try:
        inspection = inspect_persisted_run(
            run_dir,
            actions,
            _load(run_dir / "run-state.json")["runInputHash"],
            _load(run_dir / "run-state.json")["contractHash"],
            _load(run_dir / "run-state.json").get("knowledgeContextHash"),
        )
    except (ControlError, KeyError, TypeError) as exc:
        raise InputError("persisted Acceptance run cannot be replayed") from exc
    if any(state not in {"completed", "not-applicable"} for state in inspection["actionStates"].values()):
        raise InputError("deterministic finalization requires a closed action DAG")
    # Canonical registries publish a self-exclusion-safe registryHash; legacy
    # registries remain bound by their canonical payload hash.
    expected_registry_hash = (
        command_registry.get("registryHash")
        if isinstance(command_registry, dict) and command_registry.get("schemaVersion") == "acceptance-command-registry.v1"
        else canonical_hash(command_registry)
    )
    declared_commands: dict[str, str] = {}
    for action in actions:
        descriptor = resolve_registered_command(command_registry, action["commandId"])
        declared_commands[action["actionId"]] = descriptor["id"]
    state = _load(run_dir / "run-state.json")
    lifecycle_hashes = {key: state[key] for key in ("runInputHash", "contractHash", "knowledgeContextHash", "skillInputBindingHash", "skillInputContextHash") if key in state}
    events = []
    for line in (run_dir / "acceptance-events.jsonl").read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        if event.get("eventType") == "action-completed":
            if event.get("runId") != state["runId"] or event.get("inputHashes") != lifecycle_hashes:
                raise InputError("completed action lifecycle binding is stale")
            result_ref = event.get("resultReceipt")
            if not isinstance(result_ref, dict) or set(result_ref) != {"path", "sha256"}:
                raise InputError("completed action is missing its result receipt binding")
            receipt_path = _inside(run_dir, result_ref["path"], "result receipt")
            if not receipt_path.is_file() or _sha(receipt_path) != result_ref["sha256"]:
                raise InputError("completed action result receipt is stale")
            receipt = _load(receipt_path)
            if (
                not isinstance(receipt, dict)
                or receipt.get("schemaVersion") != "acceptance-controlled-command-receipt.v1"
                or receipt.get("authorizes") != []
                or receipt.get("exitCode") != 0
                or receipt.get("commandId") != event.get("commandId")
                or receipt.get("commandRegistryHash") != expected_registry_hash
                or declared_commands.get(event.get("actionId")) != event.get("commandId")
            ):
                raise InputError("completed action result receipt is not a passed controlled result")
            process = receipt.get("processResult")
            if not isinstance(process, dict) or process.get("exitCode") != 0:
                raise InputError("completed action process result is not passed")
            events.append({"actionId": event["actionId"], "commandId": event["commandId"], "receipt": result_ref, "receiptValue": receipt})
    if len(events) != len(reconstruct_completed_actions(run_dir)):
        raise InputError("completed action receipt coverage is incomplete")
    events.sort(key=lambda value: value["actionId"])
    return events


def _terminal_machine_result(stdout: Any) -> dict[str, Any]:
    """Extract the last JSON object emitted by a noisy terminal runner."""
    if not isinstance(stdout, str):
        raise InputError("bound terminal receipt has no machine-readable result")
    candidates = []
    try:
        candidates.append(json.loads(stdout))
    except json.JSONDecodeError:
        pass
    candidates.extend(
        json.loads(line.strip())
        for line in reversed(stdout.splitlines())
        if line.strip()
        for _ in [0]
        if _json_object_or_none(line.strip()) is not None
    )
    for value in candidates:
        if (
            isinstance(value, dict)
            and value.get("schema_version") in {
                "acceptance-coordinator-efficiency.terminal-result.v2",
                "jimuyun.tc-d1-implementation-validation.v1",
            }
            and value.get("predicate") == "implementation-complete"
            and value.get("status") == "pass"
            and value.get("authorizes") in ([], ["implementation-complete"])
        ):
            return value
    raise InputError("bound terminal receipt has no machine-readable result")


def _json_object_or_none(value: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _verified_quick_dev_receipt(root: Path, target: Path, prepared: dict[str, Any]) -> dict[str, Any]:
    """Replay the owner-published implementation receipt referenced by the prerequisite bundle."""
    binding = prepared.get("prerequisiteBundle")
    if not isinstance(binding, dict) or set(binding) != {"path", "sha256", "bundleHash", "implementationReceipt"}:
        raise InputError("prepared Acceptance run does not bind a prerequisite bundle")
    bundle_path = _inside(target, binding["path"], "prerequisite bundle")
    if not bundle_path.is_file() or _sha(bundle_path) != binding["sha256"]:
        raise InputError("prepared prerequisite bundle is stale")
    bundle = _load(bundle_path)
    if not isinstance(bundle, dict) or bundle.get("schemaVersion") != "compact-vdd-acceptance-prerequisite-bundle.v1":
        raise InputError("prepared prerequisite bundle is invalid")
    if bundle.get("bundleHash") != binding["bundleHash"] or bundle.get("bundleHash") != canonical_hash({key: value for key, value in bundle.items() if key != "bundleHash"}):
        raise InputError("prepared prerequisite bundle hash is stale")
    receipt_ref = binding["implementationReceipt"]
    if bundle.get("implementationReceipt") != receipt_ref:
        raise InputError("prepared implementation receipt binding is stale")
    if not isinstance(receipt_ref, dict) or set(receipt_ref) != {"path", "sha256", "terminalCommandId"}:
        raise InputError("prepared implementation receipt binding is invalid")
    if "currentQuickDev" in bundle:
        from current_quick_dev_handoff import verify_current_handoff, OWNER
        current = bundle["currentQuickDev"]
        if current.get("receipt") != {"path": receipt_ref["path"], "sha256": receipt_ref["sha256"]}:
            raise InputError("current Quick Dev receipt binding mismatch")
        terminal = bundle.get("terminalRunner", {})
        if terminal.get("sha256") != _sha(OWNER / "coverage_predicates.py"):
            raise InputError("current Quick Dev validator is stale")
        result = verify_current_handoff(root, current, allowed_changed_paths=prepared.get("input", {}).get("changed_paths", []))
        return {**receipt_ref, "currentQuickDevResult": result}
    receipt_path = _inside(target, receipt_ref["path"], "Quick Dev implementation receipt")
    if not receipt_path.is_file() or _sha(receipt_path) != receipt_ref["sha256"]:
        raise InputError("Quick Dev implementation receipt is stale")
    receipt = _load(receipt_path)
    contract_path = target / "implementation-contract.v1.json"
    registry_path = target / "command-registry.v1.json"
    terminal_runner = bundle.get("terminalRunner")
    if not contract_path.is_file() or not registry_path.is_file() or not isinstance(terminal_runner, dict):
        raise InputError("Quick Dev receipt validation inputs are unavailable")
    runner_path = _inside(target, terminal_runner.get("path"), "terminal runner")
    if not runner_path.is_file() or _sha(runner_path) != terminal_runner.get("sha256"):
        raise InputError("Quick Dev terminal runner is stale")
    if (
        not isinstance(receipt, dict)
        or receipt.get("schema_version") != "quick-dev-implementation-complete.v2"
        or receipt.get("predicate") != "implementation-complete"
        or receipt.get("status") != "pass"
        or receipt.get("authorizes") != ["acceptance-handoff"]
        or (receipt.get("implementation_contract") or {}).get("sha256") != _sha(contract_path)
        or (receipt.get("command_registry") or {}).get("sha256") != _sha(registry_path)
        or (receipt.get("terminal_result") or {}).get("command_id") != receipt_ref["terminalCommandId"]
    ):
        raise InputError("Quick Dev implementation receipt does not prove the current terminal contract")
    return {"path": receipt_ref["path"], "sha256": receipt_ref["sha256"], "terminalCommandId": receipt_ref["terminalCommandId"]}


def _verified_native_receipt(target: Path, prepared: dict[str, Any]) -> dict[str, Any]:
    """Validate a plan-owned terminal receipt without imposing a Quick Dev bundle."""
    binding = prepared.get("nativeImplementationReceipt")
    if not isinstance(binding, dict) or set(binding) != {"path", "sha256", "terminalCommandId"}:
        raise InputError("prepared Acceptance run does not bind a supported implementation receipt")
    receipt_path = _inside(target, binding["path"], "plan-native implementation receipt")
    if not receipt_path.is_file() or _sha(receipt_path) != binding["sha256"]:
        raise InputError("plan-native implementation receipt is stale")
    receipt = _load(receipt_path)
    contract_path = target / "implementation-contract.v1.json"
    if not contract_path.is_file():
        raise InputError("plan-native receipt validation contract is unavailable")
    if (
        not isinstance(receipt, dict)
        or receipt.get("schema_version") != "acceptance-coordinator-efficiency.terminal-result.v1"
        or receipt.get("status") != "pass"
        or receipt.get("predicate") != "implementation-complete"
        or receipt.get("authorizes") != ["implementation-complete"]
        or receipt.get("contract_hash") != _sha(contract_path)
        or receipt.get("terminal_command_id") != binding["terminalCommandId"]
        or binding["terminalCommandId"] != "terminal-full"
    ):
        raise InputError("plan-native implementation receipt does not prove the current terminal contract")
    return {"path": binding["path"], "sha256": binding["sha256"], "terminalCommandId": binding["terminalCommandId"]}


def finalize_deterministic_run(
    repository_root: Path,
    run_dir: Path,
    run_input_path: Path,
    actions: Any,
    command_registry: Any,
) -> dict[str, Any]:
    root = repository_root.resolve()
    run_dir = run_dir.resolve()
    run_input_path = run_input_path.resolve()
    for path, label in ((run_dir, "run directory"), (run_input_path, "run input")):
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise InputError(f"{label} escapes repository root") from exc
    state = _load(run_dir / "run-state.json")
    prepared = _load(run_input_path)
    if prepared.get("schemaVersion") != "acceptance-run-input.v1" or prepared.get("authorizes") != []:
        raise InputError("prepared Acceptance run input is invalid")
    input_value = prepared.get("input")
    validate_run_input(input_value)
    if prepared.get("inputHash") != canonical_hash(input_value) or state.get("runInputHash") != prepared["inputHash"]:
        raise InputError("prepared Acceptance run input binding is stale")
    declared_target = input_value.get("target")
    if not isinstance(declared_target, str) or not declared_target:
        raise InputError("acceptance target is invalid")
    target = (
        Path(declared_target).resolve()
        if Path(declared_target).is_absolute()
        else (root / declared_target).resolve()
    )
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise InputError("acceptance target escapes repository root") from exc
    if not Path(declared_target).is_absolute() and ".." in Path(declared_target).parts:
        raise InputError("acceptance target must be repository-relative")
    if Path(declared_target).is_absolute():
        if run_input_path.parent != target:
            raise InputError("absolute-target run input is not stored at its declared target root")
    elif run_input_path.parent != run_dir:
        raise InputError("repository-relative run input must be stored in its persisted run directory")
    baseline = _load(target / input_value["baseline_content_manifest_path"])
    candidate = _load(target / input_value["candidate_content_manifest_path"])
    validate_baseline_manifest(baseline)
    validate_candidate_manifest(candidate, baseline)
    if verify_manifest_bytes(target, input_value, baseline, candidate) != prepared.get("candidateCustody"):
        raise InputError("candidate custody is stale")
    native_mode = "prerequisiteBundle" not in prepared
    if not native_mode:
        implementation_receipt = _verified_quick_dev_receipt(root, target, prepared)
    else:
        implementation_receipt = _verified_native_receipt(target, prepared)
    receipts = _completed_receipts(run_dir, actions, command_registry)
    current_result = implementation_receipt.pop("currentQuickDevResult", None)
    terminal_command_id = implementation_receipt.get("terminalCommandId")
    terminal = [item for item in receipts if item["commandId"] == terminal_command_id]
    if current_result is None and not native_mode and len(terminal) != 1:
        raise InputError("deterministic finalization requires exactly one bound terminal receipt")
    if current_result is not None:
        # Q8 remains implementation proof; Acceptance also verifies its own DAG.
        terminal_result = current_result
    elif native_mode and not terminal:
        terminal_result = _load(_inside(target, implementation_receipt["path"], "plan-native implementation receipt"))
    else:
        try:
            terminal_result = _terminal_machine_result(
                terminal[0]["receiptValue"]["processResult"]["stdout"]
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise InputError("bound terminal receipt has no machine-readable result") from exc
    expected_schemas = {
        "acceptance-coordinator-efficiency.terminal-result.v2",
        "jimuyun.tc-d1-implementation-validation.v1",
    }
    if current_result is None and (
        terminal_result.get("schema_version") not in expected_schemas
        or terminal_result.get("predicate") != "implementation-complete"
        or terminal_result.get("status") != "pass"
        or terminal_result.get("authorizes") not in ([], ["implementation-complete"])
    ):
        raise InputError("bound terminal receipt did not prove implementation-complete")

    state_hashes = {
        "runInputHash": prepared["inputHash"],
        "contractHash": state["contractHash"],
        "knowledgeContextHash": state.get("knowledgeContextHash"),
        "skillInputBindingHash": state.get("skillInputBindingHash"),
        "skillInputContextHash": state.get("skillInputContextHash"),
        "candidateCustodyHash": canonical_hash(prepared["candidateCustody"]),
    }
    state_hashes = {key: value for key, value in state_hashes.items() if value is not None}
    evaluation = {
        "schemaVersion": "acceptance-deterministic-evaluation.v1",
        "status": "passed",
        "route": "deterministic_only",
        "candidateCustodyHash": state_hashes["candidateCustodyHash"],
        "terminalResultHash": canonical_hash(terminal_result),
        "prerequisiteBundle": prepared.get("prerequisiteBundle"),
        "implementationReceiptBinding": implementation_receipt,
        "actionReceipts": [item["receipt"] for item in receipts],
        "inputBindings": state_hashes,
        "authorizes": [],
    }
    evaluation_path = run_dir / "finalization" / "candidate-evaluation.v1.json"
    _publish(evaluation_path, evaluation)
    candidate_result = {
        "schemaVersion": "acceptance-result-candidate.v1",
        "candidateInputHash": canonical_hash(state_hashes),
        "candidate": evaluation,
        "candidateHash": canonical_hash(evaluation),
        "authorizes": [],
    }
    candidate_path = run_dir / "finalization" / "acceptance-result-candidate.v1.json"
    _publish(candidate_path, candidate_result)
    impact = {
        "schemaVersion": "acceptance-deterministic-impact-projection.v1",
        "status": "current",
        "route": "deterministic_only",
        "evaluationHash": canonical_hash(evaluation),
        "candidateResultHash": candidate_result["candidateHash"],
        "requiredCheckStatus": "passed",
        "actionReceiptHashes": [item["receipt"]["sha256"] for item in receipts],
        "authorizes": [],
    }
    impact_path = run_dir / "finalization" / "acceptance-impact-projection.v1.json"
    _publish(impact_path, impact)
    identities = {
        "baselineIdentityHash": canonical_hash(baseline),
        "candidateIdentityHash": canonical_hash(candidate),
        "consumerClosureHash": canonical_hash(input_value["affected_consumer_refs"]),
        "requiredChecksHash": canonical_hash([item["receipt"] for item in receipts]),
        "policyHash": input_value["code_review_policy_hash"],
        "specSelectionHash": state["contractHash"],
    }
    final = finalize_acceptance({
        "acceptanceMode": "unattended",
        "route": "deterministic_only",
        "triggerIds": [],
        "identities": identities,
        "supervisedDecision": None,
        "bootstrapImport": None,
    })
    final_path = run_dir / "finalization" / "acceptance-passed.v1.json"
    _publish(final_path, final)
    wrapper = {
        "schemaVersion": "acceptance-result-final.v1",
        "candidatePath": candidate_path.relative_to(run_dir).as_posix(),
        "candidateHash": candidate_result["candidateHash"],
        "impactProjectionHash": canonical_hash(impact),
        "final": final,
        "authorizes": [],
    }
    wrapper_path = run_dir / "finalization" / "acceptance-result-final.v1.json"
    _publish(wrapper_path, wrapper)
    final_ref = {"path": final_path.relative_to(run_dir).as_posix(), "sha256": _sha(final_path)}
    pointer = {
        "schemaVersion": "acceptance-current.v1",
        "currentRun": run_dir.relative_to(root).as_posix(),
        "finalResult": {"path": final_path.relative_to(root).as_posix(), "sha256": _sha(final_path)},
        "finalWrapper": {"path": wrapper_path.relative_to(root).as_posix(), "sha256": _sha(wrapper_path)},
        "authorizes": [],
    }
    _publish_current_pointer(target / "acceptance-current.v1.json", pointer)
    event_path = run_dir / "acceptance-events.jsonl"
    existing = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    final_events = [event for event in existing if event.get("eventType") == "acceptance-finalized"]
    event = {
        "schemaVersion": "acceptance-lifecycle-event.v1",
        "sequence": final_events[-1]["sequence"] if final_events else len(existing) + 1,
        "runId": state["runId"],
        "eventType": "acceptance-finalized",
        "route": "deterministic_only",
        "finalResult": final_ref,
        "wrapperHash": _sha(wrapper_path),
        "authorizes": [],
    }
    if final_events:
        if final_events[-1] != event:
            raise InputError("deterministic finalization event is not append-only")
    else:
        with event_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
    return {"status": "acceptance-passed", "final": final_ref, "wrapper": {"path": "finalization/acceptance-result-final.v1.json", "sha256": _sha(wrapper_path)}, "authorizes": ["acceptance-passed"]}
