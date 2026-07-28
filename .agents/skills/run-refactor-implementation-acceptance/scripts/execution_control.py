"""Controlled-validation command, write-boundary, and recovery guards."""

from __future__ import annotations

import json
import hashlib
import os
import re
import signal
import subprocess
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


class ControlError(ValueError):
    pass


_RUN_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._-]{2,95}$")
_TERMINAL_ACTION_STATES = {"completed", "failed", "not_applicable", "stale"}
_LIFECYCLE_EVENT_TYPES = {
    "action-reserved", "action-started", "action-completed", "action-failed",
    "action-not-applicable", "action-waiting-external", "action-stale", "run-superseded",
}
_PLACEHOLDER = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")


def create_run_directory(root: Path, run_id: str) -> Path:
    if not isinstance(run_id, str) or _RUN_ID.fullmatch(run_id) is None:
        raise ControlError("run identity is invalid")
    root = root.resolve()
    if not root.is_dir():
        raise ControlError("run root is invalid")
    path = root / run_id
    try:
        path.resolve().relative_to(root)
    except ValueError as exc:
        raise ControlError("run directory escapes root") from exc
    try:
        path.mkdir()
    except FileExistsError as exc:
        raise ControlError("run directory already exists") from exc
    return path


def create_persisted_run(
    root: Path,
    run_id: str,
    run_input_hash: str,
    contract_hash: str,
    *,
    predecessor_run_id: str | None = None,
) -> Path:
    """Create one append-only run root with hash-bound non-authorizing state."""
    for value, label in ((run_input_hash, "run input"), (contract_hash, "contract")):
        if not isinstance(value, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", value):
            raise ControlError(label + " hash is invalid")
    run_dir = create_run_directory(root, run_id)
    state: dict[str, Any] = {
        "schemaVersion": "acceptance-execution-run.v1", "runId": run_id,
        "runInputHash": run_input_hash, "contractHash": contract_hash,
        "createdUtc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "authorizes": [],
    }
    if predecessor_run_id is not None:
        if not isinstance(predecessor_run_id, str) or _RUN_ID.fullmatch(predecessor_run_id) is None:
            raise ControlError("predecessor run identity is invalid")
        state["predecessorRunId"] = predecessor_run_id
        state["recoveryReason"] = "stale_predecessor"
    (run_dir / "run-state.json").write_text(json.dumps(state, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    (run_dir / "action-events.jsonl").write_text("", encoding="utf-8", newline="\n")
    (run_dir / "acceptance-events.jsonl").write_text("", encoding="utf-8", newline="\n")
    return run_dir


def create_stale_linked_successor(
    root: Path,
    run_id: str,
    predecessor_run_dir: Path,
    run_input_hash: str,
    contract_hash: str,
) -> Path:
    """Create a new run bound to a stale predecessor without changing its evidence."""
    predecessor_state, _ = _load_persisted_run(predecessor_run_dir)
    predecessor_id = predecessor_state.get("runId")
    if not isinstance(predecessor_id, str) or _RUN_ID.fullmatch(predecessor_id) is None:
        raise ControlError("predecessor run identity is invalid")
    successor = create_persisted_run(
        root,
        run_id,
        run_input_hash,
        contract_hash,
        predecessor_run_id=predecessor_id,
    )
    state, _ = _load_persisted_run(successor)
    record_lifecycle_event(
        successor,
        action_id="recovery",
        attempt_id="supersede-001",
        action_type="run-recovery",
        event_type="run-superseded",
        input_hashes={"runInputHash": state["runInputHash"], "contractHash": state["contractHash"]},
        owner_token="owner-" + state["runId"],
        formal_write_set=[],
    )
    return successor


def _load_persisted_run(run_dir: Path) -> tuple[dict[str, Any], Path]:
    state_path = run_dir / "run-state.json"
    events_path = run_dir / "action-events.jsonl"
    if not run_dir.is_dir() or not state_path.is_file() or not events_path.is_file():
        raise ControlError("persisted run is incomplete")
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ControlError("persisted run state is unreadable") from exc
    if not isinstance(state, dict) or state.get("schemaVersion") != "acceptance-execution-run.v1" or state.get("authorizes") != []:
        raise ControlError("persisted run state is invalid")
    return state, events_path


def _read_action_events(run_dir: Path) -> list[dict[str, Any]]:
    _, events_path = _load_persisted_run(run_dir)
    events: list[dict[str, Any]] = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ControlError("persisted action event is malformed") from exc
        if not isinstance(event, dict):
            raise ControlError("persisted action event is invalid")
        events.append(event)
    return events


def reconstruct_completed_actions(run_dir: Path) -> set[str]:
    completed: set[str] = set()
    terminal: set[str] = set()
    for sequence, event in enumerate(_read_action_events(run_dir), start=1):
        if set(event) != {"schemaVersion", "sequence", "actionId", "status", "commandId", "recordedUtc", "authorizes"}:
            raise ControlError("persisted action event fields are invalid")
        if event.get("schemaVersion") != "acceptance-action-event.v1" or event.get("sequence") != sequence or event.get("authorizes") != []:
            raise ControlError("persisted action event binding is invalid")
        action_id, status = event.get("actionId"), event.get("status")
        if not isinstance(action_id, str) or not action_id or status not in _TERMINAL_ACTION_STATES:
            raise ControlError("persisted action event state is invalid")
        if action_id in terminal:
            raise ControlError("duplicate terminal action event")
        terminal.add(action_id)
        if status == "completed":
            completed.add(action_id)
    return completed


def reconstruct_closed_actions(run_dir: Path) -> set[str]:
    """Return actions whose persisted terminal state closes a dependency edge."""
    closed: set[str] = set()
    for event in _read_action_events(run_dir):
        if event.get("status") in {"completed", "not_applicable"}:
            closed.add(event["actionId"])
    return closed


def append_action_event(run_dir: Path, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"actionId", "status", "commandId"}:
        raise ControlError("new action event is invalid")
    if not isinstance(value.get("actionId"), str) or not value["actionId"] or value.get("status") not in _TERMINAL_ACTION_STATES or not isinstance(value.get("commandId"), str) or not value["commandId"]:
        raise ControlError("new action event state is invalid")
    existing = _read_action_events(run_dir)
    if any(event.get("actionId") == value["actionId"] and event.get("status") in _TERMINAL_ACTION_STATES for event in existing):
        raise ControlError("duplicate terminal action event")
    event = {
        "schemaVersion": "acceptance-action-event.v1", "sequence": len(existing) + 1,
        "actionId": value["actionId"], "status": value["status"], "commandId": value["commandId"],
        "recordedUtc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "authorizes": [],
    }
    _, events_path = _load_persisted_run(run_dir)
    with events_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
    return event


def record_lifecycle_event(
    run_dir: Path,
    *,
    action_id: str,
    attempt_id: str,
    action_type: str,
    event_type: str,
    input_hashes: Any,
    owner_token: str,
    formal_write_set: Any,
    command_id: str | None = None,
) -> dict[str, Any]:
    """Append an authoritative lifecycle event and preserve immutable attempt input."""
    state, _ = _load_persisted_run(run_dir)
    if not all(isinstance(value, str) and _RUN_ID.fullmatch(value) for value in (action_id, attempt_id)):
        raise ControlError("lifecycle action identity is invalid")
    if not isinstance(action_type, str) or not action_type or event_type not in _LIFECYCLE_EVENT_TYPES:
        raise ControlError("lifecycle event type is invalid")
    if not isinstance(owner_token, str) or not owner_token or not isinstance(input_hashes, dict) or not input_hashes or any(not isinstance(key, str) or not key or not isinstance(value, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", value) for key, value in input_hashes.items()):
        raise ControlError("lifecycle event binding is invalid")
    validate_write_set(formal_write_set, formal_write_set, [])
    if command_id is not None and (not isinstance(command_id, str) or not command_id):
        raise ControlError("lifecycle command identity is invalid")
    event_path = run_dir / "acceptance-events.jsonl"
    if not event_path.is_file():
        raise ControlError("lifecycle event log is missing")
    attempt_dir = run_dir / "actions" / action_id / attempt_id
    request_path = attempt_dir / "request.json"
    if event_type in {"action-reserved", "run-superseded"}:
        try:
            attempt_dir.mkdir(parents=True)
        except FileExistsError as exc:
            raise ControlError("attempt evidence is append-only") from exc
    elif not request_path.is_file():
        raise ControlError("lifecycle attempt is missing its request")
    existing = event_path.read_text(encoding="utf-8").splitlines()
    event = {
        "schemaVersion": "acceptance-lifecycle-event.v1", "sequence": len(existing) + 1,
        "runId": state["runId"], "actionId": action_id, "attemptId": attempt_id,
        "actionType": action_type, "eventType": event_type, "inputHashes": input_hashes,
        "recordedUtc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "processId": __import__("os").getpid(), "ownerToken": owner_token,
        "formalWriteSet": formal_write_set, "commandId": command_id, "authorizes": [],
    }
    if event_type in {"action-reserved", "run-superseded"}:
        request_path.write_text(json.dumps(event, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    with event_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
    return event


def _verify_persisted_binding(run_dir: Path, run_input_hash: str, contract_hash: str) -> None:
    state, _ = _load_persisted_run(run_dir)
    if state.get("runInputHash") != run_input_hash or state.get("contractHash") != contract_hash:
        raise ControlError("persisted run binding is stale")


def claim_persisted_action(run_dir: Path, action_id: str, command_id: str) -> Path:
    if not isinstance(action_id, str) or not _RUN_ID.fullmatch(action_id) or not isinstance(command_id, str) or not command_id:
        raise ControlError("persisted action claim identity is invalid")
    _load_persisted_run(run_dir)
    claim_dir = run_dir / "action-claims"
    claim_dir.mkdir(exist_ok=True)
    claim_path = claim_dir / (action_id + ".json")
    payload = {
        "schemaVersion": "acceptance-action-claim.v1", "actionId": action_id,
        "commandId": command_id, "claimedUtc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "authorizes": [],
    }
    try:
        with claim_path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, sort_keys=True)
            handle.write("\n")
    except FileExistsError as exc:
        raise ControlError("persisted action is already claimed") from exc
    return claim_path


def inspect_persisted_run(run_dir: Path, actions: Any, run_input_hash: str, contract_hash: str) -> dict[str, Any]:
    _verify_persisted_binding(run_dir, run_input_hash, contract_hash)
    inspection = inspect_run(actions, reconstruct_closed_actions(run_dir))
    return {**inspection, "runId": _load_persisted_run(run_dir)[0]["runId"], "authorizes": []}


def resume_persisted_run(
    repository_root: Path, run_dir: Path, actions: Any, command_registry: Any,
    run_input_hash: str, contract_hash: str,
) -> dict[str, Any]:
    _verify_persisted_binding(run_dir, run_input_hash, contract_hash)
    completed = reconstruct_completed_actions(run_dir)
    action = next_action(actions, completed, {key: index for index, key in enumerate(command_registry)} if isinstance(command_registry, dict) else None)
    claim_persisted_action(run_dir, action["actionId"], action["commandId"])
    state, _ = _load_persisted_run(run_dir)
    attempt_id = "attempt-001"
    lifecycle_inputs = {"runInputHash": state["runInputHash"], "contractHash": state["contractHash"]}
    lifecycle_args = {
        "action_id": action["actionId"], "attempt_id": attempt_id, "action_type": "run-command",
        "input_hashes": lifecycle_inputs, "owner_token": "owner-" + state["runId"],
        "formal_write_set": [], "command_id": action["commandId"],
    }
    record_lifecycle_event(run_dir, event_type="action-reserved", **lifecycle_args)
    record_lifecycle_event(run_dir, event_type="action-started", **lifecycle_args)
    result = resume_run(repository_root, actions, completed, command_registry)
    status = "completed" if result["receipt"].get("exitCode") == 0 else "failed"
    record_lifecycle_event(
        run_dir,
        event_type="action-completed" if status == "completed" else "action-failed",
        **lifecycle_args,
    )
    event = append_action_event(run_dir, {"actionId": result["actionId"], "status": status, "commandId": result["commandId"]})
    return {
        "schemaVersion": "acceptance-persisted-resume-result.v1", "runId": _load_persisted_run(run_dir)[0]["runId"],
        "actionId": result["actionId"], "commandId": result["commandId"], "receipt": result["receipt"],
        "actionEvent": event, "authorizes": [],
    }


def _canonical_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def build_write_manifest(root: Path) -> dict[str, str]:
    """Create a deterministic recursive file manifest for an isolated write root."""
    resolved_root = root.resolve()
    if not resolved_root.is_dir():
        raise ControlError("write manifest root is invalid")
    manifest: dict[str, str] = {}
    for path in sorted(resolved_root.rglob("*")):
        if not path.is_file():
            continue
        try:
            relative = path.resolve().relative_to(resolved_root).as_posix()
        except ValueError as exc:
            raise ControlError("write manifest path escapes root") from exc
        manifest[relative] = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    return manifest


def validate_write_manifest_delta(
    before: Any,
    after: Any,
    allowed_roots: Any,
    forbidden_roots: Any,
) -> dict[str, list[str]]:
    """Fail closed when an observed write is outside its declared isolated roots."""
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise ControlError("write manifest is invalid")
    if any(not isinstance(path, str) or not isinstance(digest, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", digest) for manifest in (before, after) for path, digest in manifest.items()):
        raise ControlError("write manifest entry is invalid")
    added = sorted(set(after) - set(before))
    deleted = sorted(set(before) - set(after))
    modified = sorted(path for path in set(before) & set(after) if before[path] != after[path])
    changed = added + deleted + modified
    validate_write_set(changed, allowed_roots, forbidden_roots)
    return {"added": added, "deleted": deleted, "modified": modified, "changedPaths": changed}


def resolve_typed_argv(
    argv: Any,
    typed_placeholders: Any,
    placeholder_values: Any,
    repository_root: Path,
    allowed_write_roots: Any,
) -> list[str]:
    """Resolve only declared path placeholders into paths under an allowed write root."""
    if not isinstance(argv, list) or any(not isinstance(value, str) for value in argv) or not isinstance(typed_placeholders, dict) or not isinstance(placeholder_values, dict):
        raise ControlError("typed placeholder inputs are invalid")
    root = repository_root.resolve()
    if not root.is_dir() or set(typed_placeholders) != set(placeholder_values):
        raise ControlError("typed placeholder binding is invalid")
    resolved: list[str] = []
    for argument in argv:
        match = _PLACEHOLDER.fullmatch(argument)
        if match is None:
            if "${" in argument:
                raise ControlError("typed placeholder token is invalid")
            resolved.append(argument)
            continue
        name = match.group(1)
        if typed_placeholders.get(name) != "path:allowed-write-root" or not isinstance(placeholder_values.get(name), str):
            raise ControlError("typed placeholder declaration is invalid")
        candidate = (root / placeholder_values[name]).resolve()
        try:
            relative = candidate.relative_to(root).as_posix()
        except ValueError as exc:
            raise ControlError("typed placeholder escapes repository root") from exc
        try:
            validate_write_set([relative], allowed_write_roots, [])
        except ControlError as exc:
            raise ControlError("typed placeholder is outside an allowed write root") from exc
        resolved.append(str(candidate))
    return resolved


def run_controlled_command(
    repository_root: Path,
    descriptor: Any,
) -> dict[str, Any]:
    """Run one typed local command and return non-authorizing process evidence."""
    validate_command_descriptor(descriptor)
    root = repository_root.resolve()
    if not root.is_dir():
        raise ControlError("repository root is invalid")
    allowed_write_roots = descriptor["allowed_write_roots"]
    forbidden_write_roots = descriptor["forbidden_write_roots"]
    resolved_argv = resolve_typed_argv(
        descriptor["argv"], descriptor["typed_placeholders"], descriptor["placeholder_values"], root, allowed_write_roots
    )
    before_manifest = build_write_manifest(root)
    invocation = {
        "commandId": descriptor["id"],
        "executable": descriptor["executable"],
        "argv": resolved_argv,
        "cwd": descriptor["cwd"],
        "timeoutSeconds": descriptor["timeout_seconds"],
        "shell": False,
        "environmentAllowlist": descriptor["environment_allowlist"],
    }
    environment = {name: os.environ[name] for name in descriptor["environment_allowlist"] if name in os.environ}
    process: subprocess.Popen[bytes] | None = None
    try:
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        process = subprocess.Popen(
            [descriptor["executable"], *resolved_argv],
            cwd=root,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            creationflags=creationflags,
            start_new_session=os.name != "nt",
        )
        stdout, stderr = process.communicate(timeout=descriptor["timeout_seconds"])
        result = {
            "commandId": descriptor["id"],
            "exitCode": process.returncode,
            "stdoutSha256": "sha256:" + hashlib.sha256(stdout).hexdigest(),
            "stderrSha256": "sha256:" + hashlib.sha256(stderr).hexdigest(),
            "stdout": stdout.decode("utf-8", errors="replace"),
        }
    except subprocess.TimeoutExpired as exc:
        terminated = False
        if process is not None:
            try:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], shell=False, capture_output=True, check=False, timeout=10)
                else:
                    os.killpg(process.pid, signal.SIGKILL)
                process.communicate(timeout=10)
                terminated = True
            except (OSError, subprocess.SubprocessError):
                terminated = False
        result = {"commandId": descriptor["id"], "exitCode": None, "timedOut": True, "processTreeTerminated": terminated, "launchError": str(exc)}
    except OSError as exc:
        result = {"commandId": descriptor["id"], "exitCode": None, "launchError": str(exc)}
    receipt = {
        "schemaVersion": "acceptance-controlled-command-receipt.v1",
        "commandId": descriptor["id"],
        "commandRegistryHash": descriptor["registry_hash"],
        "environmentIdentity": {"names": sorted(environment), "hash": _canonical_hash(sorted(environment))},
        "invocation": invocation,
        "invocationHash": _canonical_hash(invocation),
        "processResult": result,
        "processResultHash": _canonical_hash(result),
        "exitCode": result["exitCode"],
        "authorizes": [],
    }
    after_manifest = build_write_manifest(root)
    delta = validate_write_manifest_delta(before_manifest, after_manifest, allowed_write_roots, forbidden_write_roots)
    receipt["writeManifestDelta"] = delta
    receipt["writeManifestDeltaHash"] = _canonical_hash(delta)
    return receipt


def publish_receipt(path: Path, receipt: Any) -> None:
    """Publish one receipt once; failed and successful evidence are never overwritten."""
    if not isinstance(receipt, dict) or receipt.get("authorizes") != []:
        raise ControlError("receipt is invalid or claims authority")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(receipt, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
    except FileExistsError as exc:
        raise ControlError("receipt publication is append-only") from exc


def _validated_actions(actions: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(actions, list) or not actions:
        raise ControlError("action DAG is invalid")
    by_id: dict[str, dict[str, Any]] = {}
    for action in actions:
        if not isinstance(action, dict):
            raise ControlError("action is invalid")
        action_id, dependencies = action.get("actionId"), action.get("dependsOn")
        if not isinstance(action_id, str) or not action_id or action_id in by_id:
            raise ControlError("action identity is invalid")
        if not isinstance(dependencies, list) or any(not isinstance(value, str) or not value for value in dependencies):
            raise ControlError("action dependencies are invalid")
        if not isinstance(action.get("order"), int) or isinstance(action["order"], bool):
            raise ControlError("action order is invalid")
        if not isinstance(action.get("commandId"), str) or not action["commandId"]:
            raise ControlError("action command identity is invalid")
        if action.get("activation") not in {True, False, "external"}:
            raise ControlError("action activation is invalid")
        by_id[action_id] = action
    for action in by_id.values():
        if any(dependency not in by_id for dependency in action["dependsOn"]):
            raise ControlError("action has an unknown dependency")
    return by_id


def project_action_states(actions: Any, completed_action_ids: Any) -> dict[str, str]:
    """Project all declared actions without letting external readiness become local authority."""
    by_id = _validated_actions(actions)
    if not isinstance(completed_action_ids, set) or not completed_action_ids.issubset(set(by_id)):
        raise ControlError("completed action identity is invalid")
    states: dict[str, str] = {}
    visiting: set[str] = set()

    def project(action_id: str) -> str:
        if action_id in states:
            return states[action_id]
        if action_id in visiting:
            raise ControlError("action DAG has a cycle")
        visiting.add(action_id)
        action = by_id[action_id]
        activation = action["activation"]
        if activation is False:
            state = "not-applicable"
        elif activation == "external":
            state = "waiting-external"
        elif action_id in completed_action_ids:
            state = "completed"
        elif all(project(dependency) in {"completed", "not-applicable"} for dependency in action["dependsOn"]):
            state = "ready"
        else:
            state = "blocked"
        visiting.remove(action_id)
        states[action_id] = state
        return state

    for action_id in by_id:
        project(action_id)
    return states


def next_action(actions: Any, completed_action_ids: Any, command_registry_order: dict[str, int] | None = None) -> dict[str, Any]:
    by_id = _validated_actions(actions)
    states = project_action_states(actions, completed_action_ids)
    ready = [action for action_id, action in by_id.items() if states[action_id] == "ready"]
    if not ready:
        raise ControlError("no unique ready action")
    registry = command_registry_order or {}
    if not isinstance(registry, dict) or any(not isinstance(key, str) or not isinstance(value, int) for key, value in registry.items()):
        raise ControlError("command registry order is invalid")
    def key(action: dict[str, Any]) -> tuple[int, int, str]:
        return (action["order"], registry.get(action["commandId"], 2**31 - 1), action["commandId"])
    ready.sort(key=key)
    if len(ready) > 1 and key(ready[0]) == key(ready[1]):
        raise ControlError("ready action sorting collision")
    return {**ready[0], "state": "ready"}


def inspect_run(actions: Any, completed_action_ids: Any, command_registry_order: dict[str, int] | None = None) -> dict[str, Any]:
    by_id = _validated_actions(actions)
    states = project_action_states(actions, completed_action_ids)
    registry = command_registry_order or {}
    ready_ids = sorted(
        (action_id for action_id, state in states.items() if state == "ready"),
        key=lambda action_id: (
            by_id[action_id]["order"],
            registry.get(by_id[action_id]["commandId"], 2**31 - 1),
            by_id[action_id]["commandId"],
        ),
    )
    missing = {
        action_id: [dependency for dependency in action["dependsOn"] if states[dependency] not in {"completed", "not-applicable"}]
        for action_id, action in by_id.items()
    }
    try:
        next_ready = next_action(actions, completed_action_ids, command_registry_order)
    except ControlError as exc:
        if str(exc) != "no unique ready action":
            raise
        next_ready = None
    return {
        "schemaVersion": "acceptance-run-inspection.v1",
        "actionStates": states,
        "dependencyClosed": {action_id: not values for action_id, values in missing.items()},
        "missingDependencies": missing,
        "readyActionIds": ready_ids,
        "sortingBasis": "dependency-topology,action-order,command-registry-order,command-id",
        "nextAction": next_ready,
        "authorizes": [],
    }


def resume_run(repository_root: Path, actions: Any, completed_action_ids: Any, command_registry: Any) -> dict[str, Any]:
    if not isinstance(command_registry, dict):
        raise ControlError("command registry is invalid")
    order = {command_id: index for index, command_id in enumerate(command_registry)}
    action = next_action(actions, completed_action_ids, order)
    descriptor = command_registry.get(action["commandId"])
    if descriptor is None:
        raise ControlError("ready action command is absent from registry")
    receipt = run_controlled_command(repository_root, descriptor)
    return {
        "schemaVersion": "acceptance-run-resume-result.v1",
        "actionId": action["actionId"],
        "commandId": action["commandId"],
        "receipt": receipt,
        "authorizes": [],
    }


def validate_command_descriptor(value: Any) -> None:
    required = {"id", "executable", "argv", "cwd", "timeout_seconds", "shell", "allowed_write_roots", "forbidden_write_roots", "registry_hash", "environment_allowlist", "typed_placeholders", "placeholder_values"}
    if not isinstance(value, dict) or set(value) != required:
        raise ControlError("command descriptor fields are invalid")
    if value.get("shell") is not False or value.get("cwd") != ".":
        raise ControlError("command descriptor must be shell-free and repository-rooted")
    if not isinstance(value.get("id"), str) or not value["id"] or not isinstance(value.get("executable"), str) or not value["executable"]:
        raise ControlError("command descriptor identity is invalid")
    if not isinstance(value.get("argv"), list) or any(not isinstance(item, str) for item in value["argv"]):
        raise ControlError("command descriptor argv is invalid")
    if "${" in value["executable"]:
        raise ControlError("command descriptor has an untyped placeholder")
    if not isinstance(value.get("timeout_seconds"), int) or value["timeout_seconds"] <= 0:
        raise ControlError("command descriptor timeout is invalid")
    if not isinstance(value.get("allowed_write_roots"), list) or not isinstance(value.get("forbidden_write_roots"), list):
        raise ControlError("command descriptor write boundaries are invalid")
    if not isinstance(value.get("registry_hash"), str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", value["registry_hash"]):
        raise ControlError("command descriptor registry hash is invalid")
    if not isinstance(value.get("environment_allowlist"), list) or any(not isinstance(name, str) or not name or "=" in name for name in value["environment_allowlist"]) or len(value["environment_allowlist"]) != len(set(value["environment_allowlist"])):
        raise ControlError("command descriptor environment allowlist is invalid")
    placeholders, values = value.get("typed_placeholders"), value.get("placeholder_values")
    if not isinstance(placeholders, dict) or not isinstance(values, dict) or set(placeholders) != set(values) or any(not isinstance(name, str) or _PLACEHOLDER.fullmatch("${" + name + "}") is None or kind != "path:allowed-write-root" or not isinstance(values[name], str) for name, kind in placeholders.items()):
        raise ControlError("command descriptor typed placeholders are invalid")
    for argument in value["argv"]:
        if "${" in argument:
            match = _PLACEHOLDER.fullmatch(argument)
            if match is None or match.group(1) not in placeholders:
                raise ControlError("command descriptor has an untyped placeholder")
    validate_write_set([], value["allowed_write_roots"], value["forbidden_write_roots"])


def validate_write_set(paths: Any, allowed_roots: Any, forbidden_roots: Any) -> None:
    if not isinstance(paths, list) or not isinstance(allowed_roots, list) or not isinstance(forbidden_roots, list):
        raise ControlError("write boundary values are invalid")
    for path in paths:
        if not isinstance(path, str):
            raise ControlError("write path is invalid")
        normalized = PurePosixPath(path.replace("\\", "/"))
        if normalized.is_absolute() or ".." in normalized.parts:
            raise ControlError("write path escapes its declared root")
        rendered = normalized.as_posix()
        def matches(root: str) -> bool:
            root = root.replace("\\", "/")
            if root.endswith("/**"):
                base = root[:-3]
                return rendered == base or rendered.startswith(base + "/")
            return rendered == root
        if any(matches(root) for root in forbidden_roots) or not any(matches(root) for root in allowed_roots):
            raise ControlError("write set violates declared boundary")


def acquire_lock(path: Path, run_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump({"run_id": run_id}, handle, sort_keys=True)
    except FileExistsError as exc:
        raise ControlError("controlled-validation lock is already held") from exc


def validate_recovery_state(value: Any, current_contract_hash: str) -> None:
    if not isinstance(value, dict) or value.get("contract_hash") != current_contract_hash:
        raise ControlError("recovery state is stale")
    if value.get("state") not in {"active", "completed", "failed"}:
        raise ControlError("recovery state is invalid")
