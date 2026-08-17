"""Controlled-validation command, write-boundary, and recovery guards."""

from __future__ import annotations

import json
import hashlib
import os
import re
import signal
import subprocess
from concurrent.futures import ThreadPoolExecutor
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
_LEGACY_ENVIRONMENT_ALLOWLIST = [
    "PATH",
    "PATHEXT",
    "SystemRoot",
    "WINDIR",
    "TEMP",
    "TMP",
    "TMPDIR",
    "HOME",
    "HOMEDRIVE",
    "HOMEPATH",
    "USERPROFILE",
    "APPDATA",
    "LOCALAPPDATA",
    "PROGRAMFILES",
    "PROGRAMFILES(X86)",
    "PROGRAMW6432",
    "DOTNET_ROOT",
    "LOGNAME",
    "USER",
    "LNAME",
    "USERNAME",
]


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


def _normalize_repository_artifact_path(repository_root: Path, raw_path: str) -> tuple[Path, str]:
    if not isinstance(raw_path, str) or not raw_path or "\\" in raw_path:
        raise ControlError("Skill input context path is invalid")
    supplied = PurePosixPath(raw_path)
    if supplied.is_absolute() or ".." in supplied.parts:
        raise ControlError("Skill input context path must be repository-relative")
    root = repository_root.resolve()
    if not root.is_dir():
        raise ControlError("Skill input context repository root is invalid")
    joined = root.joinpath(*supplied.parts)
    current = joined
    while current != root and current != current.parent:
        if current.is_symlink():
            raise ControlError("Skill input context artifact may not use symlinks")
        current = current.parent
    resolved = joined.resolve()
    try:
        normalized = resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise ControlError("Skill input context path escapes repository") from exc
    return resolved, normalized


def _read_repository_artifact(
    repository_root: Path,
    raw_path: str,
    expected_hash: str,
) -> tuple[bytes, str]:
    resolved, normalized = _normalize_repository_artifact_path(repository_root, raw_path)
    if resolved.is_symlink() or not resolved.is_file():
        raise ControlError("Skill input context artifact is missing")
    try:
        payload = resolved.read_bytes()
    except OSError as exc:
        raise ControlError("Skill input context artifact is unreadable") from exc
    actual_hash = "sha256:" + hashlib.sha256(payload).hexdigest()
    if actual_hash != expected_hash:
        raise ControlError("Skill input context artifact hash is stale")
    return payload, normalized


def _verify_skill_input_custody(run_dir: Path, state: dict[str, Any]) -> Path | None:
    binding = state.get("skillInputBindingHash")
    context_hash = state.get("skillInputContextHash")
    custody_path = state.get("skillInputContextPath")
    source_path = state.get("skillInputContextSourcePath")
    values = (binding, context_hash, custody_path, source_path)
    if all(value is None for value in values):
        return None
    if any(value is None for value in values):
        raise ControlError("persisted run Skill input custody is incomplete")
    if not isinstance(binding, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", binding):
        raise ControlError("persisted run Skill input binding hash is invalid")
    if not isinstance(context_hash, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", context_hash):
        raise ControlError("persisted run Skill input context hash is invalid")
    if not isinstance(source_path, str) or not source_path or "\\" in source_path:
        raise ControlError("persisted run Skill input source path is invalid")
    source_relative = PurePosixPath(source_path)
    if source_relative.is_absolute() or ".." in source_relative.parts:
        raise ControlError("persisted run Skill input source path is invalid")
    if not isinstance(custody_path, str) or not custody_path or "\\" in custody_path:
        raise ControlError("persisted run Skill input custody path is invalid")
    relative = PurePosixPath(custody_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ControlError("persisted run Skill input custody path is invalid")
    artifact = run_dir.joinpath(*relative.parts)
    current = artifact
    while current != run_dir and current != current.parent:
        if current.is_symlink():
            raise ControlError("persisted run Skill input custody path uses a symlink")
        current = current.parent
    resolved_artifact = artifact.resolve()
    try:
        resolved_artifact.relative_to(run_dir.resolve())
    except ValueError as exc:
        raise ControlError("persisted run Skill input custody path escapes run") from exc
    if artifact.is_symlink() or not artifact.is_file():
        raise ControlError("persisted run Skill input custody artifact is missing")
    actual_hash = "sha256:" + hashlib.sha256(artifact.read_bytes()).hexdigest()
    if actual_hash != context_hash:
        raise ControlError("persisted run Skill input custody artifact is stale")
    return artifact


def create_persisted_run(
    root: Path,
    run_id: str,
    run_input_hash: str,
    contract_hash: str,
    *,
    predecessor_run_id: str | None = None,
    knowledge_context_hash: str | None = None,
    skill_input_binding_hash: str | None = None,
    skill_input_context_hash: str | None = None,
    skill_input_context_path: str | None = None,
    repository_root: Path | None = None,
) -> Path:
    """Create one append-only run root with hash-bound non-authorizing state."""
    for value, label in ((run_input_hash, "run input"), (contract_hash, "contract")):
        if not isinstance(value, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", value):
            raise ControlError(label + " hash is invalid")
    if knowledge_context_hash is not None and (
        not isinstance(knowledge_context_hash, str)
        or not re.fullmatch(r"sha256:[a-f0-9]{64}", knowledge_context_hash)
    ):
        raise ControlError("knowledge context hash is invalid")
    for value, label in (
        (skill_input_binding_hash, "Skill input binding"),
        (skill_input_context_hash, "Skill input context"),
    ):
        if value is not None and (not isinstance(value, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", value)):
            raise ControlError(label + " hash is invalid")
    supplied_skill_input = (skill_input_binding_hash, skill_input_context_hash, skill_input_context_path)
    if any(value is None for value in supplied_skill_input) and any(value is not None for value in supplied_skill_input):
        raise ControlError("Skill input binding, context hash, and context path must be supplied together")
    context_payload: bytes | None = None
    normalized_context_source: str | None = None
    if skill_input_context_path is not None:
        if repository_root is None:
            raise ControlError("Skill input context repository root is required")
        context_payload, normalized_context_source = _read_repository_artifact(
            repository_root,
            skill_input_context_path,
            skill_input_context_hash,
        )
    run_dir = create_run_directory(root, run_id)
    state: dict[str, Any] = {
        "schemaVersion": "acceptance-execution-run.v1", "runId": run_id,
        "runInputHash": run_input_hash, "contractHash": contract_hash,
        "createdUtc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "authorizes": [],
    }
    if knowledge_context_hash is not None:
        state["knowledgeContextHash"] = knowledge_context_hash
    if skill_input_binding_hash is not None:
        state["skillInputBindingHash"] = skill_input_binding_hash
    if skill_input_context_hash is not None:
        state["skillInputContextHash"] = skill_input_context_hash
    if context_payload is not None and normalized_context_source is not None:
        custody_relative = "skill-input/skill-input-context.v1.json"
        custody_path = run_dir / "skill-input" / "skill-input-context.v1.json"
        custody_path.parent.mkdir()
        with custody_path.open("xb") as handle:
            handle.write(context_payload)
            handle.flush()
            os.fsync(handle.fileno())
        state["skillInputContextPath"] = custody_relative
        state["skillInputContextSourcePath"] = normalized_context_source
    if predecessor_run_id is not None:
        if not isinstance(predecessor_run_id, str) or _RUN_ID.fullmatch(predecessor_run_id) is None:
            raise ControlError("predecessor run identity is invalid")
        state["predecessorRunId"] = predecessor_run_id
        state["recoveryReason"] = "stale_predecessor"
    (run_dir / "run-state.json").write_text(json.dumps(state, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    (run_dir / "action-events.jsonl").write_text("", encoding="utf-8", newline="\n")
    (run_dir / "acceptance-events.jsonl").write_text("", encoding="utf-8", newline="\n")
    return run_dir


def start_or_resume_target_run(
    repository_root: Path,
    target_plan: str,
    run_input_hash: str,
    contract_hash: str,
    knowledge_context_hash: str,
    *,
    run_id: str | None = None,
    skill_input_binding_hash: str | None = None,
    skill_input_context_hash: str | None = None,
    skill_input_context_path: str | None = None,
) -> dict[str, Any]:
    """Create or resume one target-owned run without inventing a second lifecycle."""
    for value, label in (
        (run_input_hash, "run input"),
        (contract_hash, "contract"),
        (knowledge_context_hash, "knowledge context"),
    ):
        if not isinstance(value, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", value):
            raise ControlError(label + " hash is invalid")
    for value, label in (
        (skill_input_binding_hash, "Skill input binding"),
        (skill_input_context_hash, "Skill input context"),
    ):
        if value is not None and (not isinstance(value, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", value)):
            raise ControlError(label + " hash is invalid")
    supplied_skill_input = (skill_input_binding_hash, skill_input_context_hash, skill_input_context_path)
    if any(value is None for value in supplied_skill_input) and any(value is not None for value in supplied_skill_input):
        raise ControlError("Skill input binding, context hash, and context path must be supplied together")
    root = repository_root.resolve()
    if not root.is_dir() or not isinstance(target_plan, str) or not target_plan.strip():
        raise ControlError("target plan is invalid")
    supplied_target = Path(target_plan)
    if supplied_target.is_absolute():
        raise ControlError("target plan must be repository-relative")
    target = (root / supplied_target).resolve()
    try:
        relative_target = target.relative_to(root)
    except ValueError as exc:
        raise ControlError("target plan escapes repository") from exc
    if (
        len(relative_target.parts) < 2
        or relative_target.parts[0].lower() != "execution-plans"
        or not target.is_dir()
    ):
        raise ControlError("target plan must be an execution-plans directory")

    normalized_context_path: str | None = None
    if skill_input_context_path is not None:
        supplied_context = Path(skill_input_context_path)
        if supplied_context.is_absolute():
            raise ControlError("Skill input context path must be repository-relative")
        _context_artifact, normalized_context_path = _normalize_repository_artifact_path(
            root, supplied_context.as_posix()
        )

    binding_parts = [run_input_hash, contract_hash, knowledge_context_hash]
    if skill_input_binding_hash is not None:
        binding_parts.append(skill_input_binding_hash)
    if skill_input_context_hash is not None:
        binding_parts.append(skill_input_context_hash)
    if normalized_context_path is not None:
        binding_parts.append(normalized_context_path)
    binding_id = hashlib.sha256("\0".join(binding_parts).encode("utf-8")).hexdigest()[:16]
    selected_run_id = run_id or "acceptance-" + binding_id
    if _RUN_ID.fullmatch(selected_run_id) is None:
        raise ControlError("run identity is invalid")
    run_root = target / "acceptance-runs"
    try:
        run_root.mkdir(exist_ok=True)
    except OSError as exc:
        raise ControlError("acceptance run root cannot be created") from exc
    if run_root.is_symlink() or not run_root.is_dir():
        raise ControlError("acceptance run root is invalid")
    resolved_run_root = run_root.resolve()
    try:
        resolved_run_root.relative_to(target)
    except ValueError as exc:
        raise ControlError("acceptance run root escapes target plan") from exc
    run_root = resolved_run_root

    run_dir = run_root / selected_run_id
    if run_dir.exists():
        if run_dir.is_symlink():
            raise ControlError("persisted run directory is invalid")
        if not (run_dir / "run-state.json").is_file():
            raise ControlError(
                "legacy artifact-only run cannot be resumed; create a new binding-derived run"
            )
        _verify_persisted_binding(
            run_dir,
            run_input_hash,
            contract_hash,
            knowledge_context_hash,
            skill_input_binding_hash,
            skill_input_context_hash,
            normalized_context_path,
            require_skill_input_binding=True,
        )
        state, _events_path = _load_persisted_run(run_dir)
        if state.get("runId") != selected_run_id:
            raise ControlError("persisted run identity is stale")
        disposition = "resumed"
    else:
        # ADR-0041/ADR-0052: reuse the existing append-only run state; this entry is not authority.
        run_dir = create_persisted_run(
            run_root,
            selected_run_id,
            run_input_hash,
            contract_hash,
            knowledge_context_hash=knowledge_context_hash,
            skill_input_binding_hash=skill_input_binding_hash,
            skill_input_context_hash=skill_input_context_hash,
            skill_input_context_path=normalized_context_path,
            repository_root=root,
        )
        disposition = "created"
    result = {
        "schemaVersion": "acceptance-run-entry.v1",
        "runId": selected_run_id,
        "runDirectory": run_dir.relative_to(root).as_posix(),
        "disposition": disposition,
        "runInputHash": run_input_hash,
        "contractHash": contract_hash,
        "knowledgeContextHash": knowledge_context_hash,
        "authorizes": [],
    }
    if skill_input_binding_hash is not None:
        result["skillInputBindingHash"] = skill_input_binding_hash
    if skill_input_context_hash is not None:
        result["skillInputContextHash"] = skill_input_context_hash
    if normalized_context_path is not None:
        state, _ = _load_persisted_run(run_dir)
        custody = _verify_skill_input_custody(run_dir, state)
        assert custody is not None
        result["skillInputContextPath"] = custody.relative_to(root).as_posix()
        result["skillInputContextSourcePath"] = normalized_context_path
    return result


def create_stale_linked_successor(
    root: Path,
    run_id: str,
    predecessor_run_dir: Path,
    run_input_hash: str,
    contract_hash: str,
    *,
    knowledge_context_hash: str | None = None,
) -> Path:
    """Create a new run bound to a stale predecessor without changing its evidence."""
    predecessor_state, _ = _load_persisted_run(predecessor_run_dir)
    predecessor_id = predecessor_state.get("runId")
    if not isinstance(predecessor_id, str) or _RUN_ID.fullmatch(predecessor_id) is None:
        raise ControlError("predecessor run identity is invalid")
    predecessor_context = _verify_skill_input_custody(predecessor_run_dir, predecessor_state)
    successor = create_persisted_run(
        root,
        run_id,
        run_input_hash,
        contract_hash,
        predecessor_run_id=predecessor_id,
        knowledge_context_hash=(
            knowledge_context_hash
            if knowledge_context_hash is not None
            else predecessor_state.get("knowledgeContextHash")
        ),
        skill_input_binding_hash=predecessor_state.get("skillInputBindingHash"),
        skill_input_context_hash=predecessor_state.get("skillInputContextHash"),
        skill_input_context_path=(
            predecessor_context.relative_to(predecessor_run_dir).as_posix()
            if predecessor_context is not None
            else None
        ),
        repository_root=predecessor_run_dir if predecessor_context is not None else None,
    )
    state, _ = _load_persisted_run(successor)
    lifecycle_inputs = {
        "runInputHash": state["runInputHash"],
        "contractHash": state["contractHash"],
    }
    if "knowledgeContextHash" in state:
        lifecycle_inputs["knowledgeContextHash"] = state["knowledgeContextHash"]
    if "skillInputBindingHash" in state:
        lifecycle_inputs["skillInputBindingHash"] = state["skillInputBindingHash"]
    if "skillInputContextHash" in state:
        lifecycle_inputs["skillInputContextHash"] = state["skillInputContextHash"]
    record_lifecycle_event(
        successor,
        action_id="recovery",
        attempt_id="supersede-001",
        action_type="run-recovery",
        event_type="run-superseded",
        input_hashes=lifecycle_inputs,
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
    result_receipt: dict[str, str] | None = None,
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
    if result_receipt is not None:
        if (
            not isinstance(result_receipt, dict)
            or set(result_receipt) != {"path", "sha256"}
            or not isinstance(result_receipt["path"], str)
            or not result_receipt["path"]
            or not re.fullmatch(r"sha256:[a-f0-9]{64}", result_receipt["sha256"])
        ):
            raise ControlError("lifecycle result receipt binding is invalid")
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
    if result_receipt is not None:
        event["resultReceipt"] = result_receipt
    if event_type in {"action-reserved", "run-superseded"}:
        request_path.write_text(json.dumps(event, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    with event_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
    return event


def _verify_persisted_binding(
    run_dir: Path,
    run_input_hash: str,
    contract_hash: str,
    knowledge_context_hash: str | None = None,
    skill_input_binding_hash: str | None = None,
    skill_input_context_hash: str | None = None,
    skill_input_context_path: str | None = None,
    *,
    require_skill_input_binding: bool = False,
) -> None:
    state, _ = _load_persisted_run(run_dir)
    _verify_skill_input_custody(run_dir, state)
    if state.get("runInputHash") != run_input_hash or state.get("contractHash") != contract_hash:
        raise ControlError("persisted run binding is stale")
    persisted_context_hash = state.get("knowledgeContextHash")
    if persisted_context_hash is not None and knowledge_context_hash is None:
        raise ControlError("persisted run knowledge context binding is required")
    if persisted_context_hash != knowledge_context_hash:
        raise ControlError("persisted run knowledge context binding is stale")
    for field, supplied, label in (
        ("skillInputBindingHash", skill_input_binding_hash, "Skill input binding"),
        ("skillInputContextHash", skill_input_context_hash, "Skill input context"),
        ("skillInputContextSourcePath", skill_input_context_path, "Skill input context source path"),
    ):
        persisted = state.get(field)
        if require_skill_input_binding and persisted is not None and supplied is None:
            raise ControlError(f"persisted run {label} is required")
        if supplied is not None and persisted != supplied:
            raise ControlError(f"persisted run {label} is stale")


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


def release_persisted_action(claim_path: Path) -> None:
    """Release the transient action lock after its terminal lifecycle event."""
    try:
        claim_path.unlink()
    except FileNotFoundError as exc:
        raise ControlError("persisted action claim is missing") from exc
    except OSError as exc:
        raise ControlError("persisted action claim cannot be released") from exc


def _process_is_running(process_id: int) -> bool:
    if not isinstance(process_id, int) or isinstance(process_id, bool) or process_id <= 0:
        raise ControlError("stale action process identity is invalid")
    if os.name != "nt":
        try:
            os.kill(process_id, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(0x1000, False, process_id)
    if not handle:
        return ctypes.get_last_error() not in {87, 1168}
    kernel32.CloseHandle(handle)
    return True


def recover_stale_persisted_action(
    run_dir: Path,
    action_id: str,
    run_input_hash: str,
    contract_hash: str,
    knowledge_context_hash: str | None = None,
    *,
    minimum_age_seconds: int = 60,
) -> dict[str, Any]:
    """Close one dead-process attempt as stale and release only its transient claim."""
    _verify_persisted_binding(run_dir, run_input_hash, contract_hash, knowledge_context_hash)
    if not isinstance(action_id, str) or _RUN_ID.fullmatch(action_id) is None:
        raise ControlError("stale action identity is invalid")
    if not isinstance(minimum_age_seconds, int) or isinstance(minimum_age_seconds, bool) or minimum_age_seconds < 60:
        raise ControlError("stale action minimum age is invalid")
    claim_path = run_dir / "action-claims" / (action_id + ".json")
    if not claim_path.is_file():
        raise ControlError("stale action claim is missing")
    try:
        claim = json.loads(claim_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ControlError("stale action claim is malformed") from exc
    if (
        not isinstance(claim, dict)
        or claim.get("schemaVersion") != "acceptance-action-claim.v1"
        or claim.get("actionId") != action_id
        or not isinstance(claim.get("commandId"), str)
        or claim.get("authorizes") != []
    ):
        raise ControlError("stale action claim is malformed")
    try:
        claimed_utc = datetime.fromisoformat(str(claim["claimedUtc"]).replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError) as exc:
        raise ControlError("stale action claim time is invalid") from exc
    age_seconds = (datetime.now(timezone.utc) - claimed_utc).total_seconds()
    if age_seconds < minimum_age_seconds:
        raise ControlError("stale action claim is not old enough")

    events_path = run_dir / "acceptance-events.jsonl"
    try:
        events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
    except (OSError, json.JSONDecodeError) as exc:
        raise ControlError("stale action lifecycle is malformed") from exc
    matching = [event for event in events if event.get("actionId") == action_id]
    if not matching or matching[-1].get("eventType") != "action-started":
        raise ControlError("stale action is not an active started attempt")
    started = matching[-1]
    if started.get("commandId") != claim["commandId"]:
        raise ControlError("stale action command binding is inconsistent")
    if _process_is_running(started.get("processId")):
        raise ControlError("stale action process is still running")
    record_lifecycle_event(
        run_dir,
        action_id=action_id,
        attempt_id=started["attemptId"],
        action_type=started["actionType"],
        event_type="action-stale",
        input_hashes=started["inputHashes"],
        owner_token=started["ownerToken"],
        formal_write_set=started["formalWriteSet"],
        command_id=started["commandId"],
    )
    release_persisted_action(claim_path)
    return {
        "schemaVersion": "acceptance-stale-action-recovery.v1",
        "runId": _load_persisted_run(run_dir)[0]["runId"],
        "actionId": action_id,
        "attemptId": started["attemptId"],
        "status": "stale-recovered",
        "authorizes": [],
    }


def _next_attempt_id(run_dir: Path, action_id: str) -> str:
    events_path = run_dir / "acceptance-events.jsonl"
    if not events_path.is_file():
        raise ControlError("lifecycle event log is missing")
    attempts: set[str] = set()
    for line in events_path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ControlError("lifecycle event is malformed") from exc
        if event.get("actionId") == action_id and isinstance(event.get("attemptId"), str):
            attempts.add(event["attemptId"])
    number = 1
    while f"attempt-{number:03d}" in attempts:
        number += 1
    return f"attempt-{number:03d}"


def inspect_persisted_run(
    run_dir: Path,
    actions: Any,
    run_input_hash: str,
    contract_hash: str,
    knowledge_context_hash: str | None = None,
) -> dict[str, Any]:
    _verify_persisted_binding(
        run_dir, run_input_hash, contract_hash, knowledge_context_hash
    )
    inspection = inspect_run(actions, reconstruct_closed_actions(run_dir))
    return {**inspection, "runId": _load_persisted_run(run_dir)[0]["runId"], "authorizes": []}


def resume_persisted_run(
    repository_root: Path, run_dir: Path, actions: Any, command_registry: Any,
    run_input_hash: str, contract_hash: str,
    knowledge_context_hash: str | None = None,
) -> dict[str, Any]:
    _verify_persisted_binding(
        run_dir, run_input_hash, contract_hash, knowledge_context_hash
    )
    completed = reconstruct_completed_actions(run_dir)
    action = next_action(actions, completed, _command_registry_order(command_registry))
    claim_path = claim_persisted_action(run_dir, action["actionId"], action["commandId"])
    state, _ = _load_persisted_run(run_dir)
    attempt_id = _next_attempt_id(run_dir, action["actionId"])
    lifecycle_inputs = {"runInputHash": state["runInputHash"], "contractHash": state["contractHash"]}
    if "knowledgeContextHash" in state:
        lifecycle_inputs["knowledgeContextHash"] = state["knowledgeContextHash"]
    lifecycle_args = {
        "action_id": action["actionId"], "attempt_id": attempt_id, "action_type": "run-command",
        "input_hashes": lifecycle_inputs, "owner_token": "owner-" + state["runId"],
        "formal_write_set": [], "command_id": action["commandId"],
    }
    record_lifecycle_event(run_dir, event_type="action-reserved", **lifecycle_args)
    record_lifecycle_event(run_dir, event_type="action-started", **lifecycle_args)
    try:
        result = resume_run(repository_root, actions, completed, command_registry)
        receipt_path = run_dir / "actions" / action["actionId"] / attempt_id / "result.json"
        try:
            with receipt_path.open("x", encoding="utf-8", newline="\n") as handle:
                json.dump(result["receipt"], handle, sort_keys=True, indent=2)
                handle.write("\n")
        except FileExistsError as exc:
            raise ControlError("persisted action result receipt is not append-only") from exc
        receipt_binding = {
            "path": receipt_path.relative_to(run_dir).as_posix(),
            "sha256": "sha256:" + hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
        }
        if result["receipt"].get("exitCode") != 0:
            record_lifecycle_event(
                run_dir, event_type="action-failed", result_receipt=receipt_binding,
                **lifecycle_args,
            )
            return {
                "schemaVersion": "acceptance-persisted-resume-result.v1", "runId": state["runId"],
                "actionId": action["actionId"], "commandId": action["commandId"], "receipt": result["receipt"],
                "resultReceipt": receipt_binding,
                "actionEvent": None, "authorizes": [],
            }
        record_lifecycle_event(
            run_dir, event_type="action-completed", result_receipt=receipt_binding,
            **lifecycle_args,
        )
        event = append_action_event(run_dir, {"actionId": result["actionId"], "status": "completed", "commandId": result["commandId"]})
    except Exception:
        record_lifecycle_event(run_dir, event_type="action-failed", **lifecycle_args)
        raise
    finally:
        release_persisted_action(claim_path)
    return {
        "schemaVersion": "acceptance-persisted-resume-result.v1", "runId": _load_persisted_run(run_dir)[0]["runId"],
        "actionId": result["actionId"], "commandId": result["commandId"], "receipt": result["receipt"],
        "resultReceipt": receipt_binding,
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


def _native_path(path: Path) -> Path:
    """Use Windows extended paths while retaining repository-relative identities."""
    if os.name != "nt":
        return path
    rendered = os.path.abspath(str(path))
    if rendered.startswith("\\\\?\\"):
        return Path(rendered)
    if rendered.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + rendered[2:])
    return Path("\\\\?\\" + rendered)


def _hash_repository_file(path: Path) -> str:
    digest = hashlib.sha256()
    with _native_path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _expand_ignored_evidence_directories(root: Path, paths: set[str]) -> set[str]:
    """Expand nested repositories that Git reports as one ignored directory sentinel."""
    expanded = {relative for relative in paths if not relative.endswith("/")}
    for sentinel in sorted(relative for relative in paths if relative.endswith("/")):
        pure = PurePosixPath(sentinel)
        stack = [(_native_path(root.joinpath(*pure.parts)), pure)]
        while stack:
            directory, relative_directory = stack.pop()
            try:
                entries = list(os.scandir(directory))
            except OSError as exc:
                raise ControlError("repository content manifest path is stale") from exc
            for entry in entries:
                relative = (relative_directory / entry.name).as_posix()
                try:
                    if entry.is_dir(follow_symlinks=False):
                        stack.append((Path(entry.path), relative_directory / entry.name))
                    elif entry.is_file(follow_symlinks=False):
                        expanded.add(relative)
                    elif entry.is_symlink():
                        # Path.rglob(), used by the original guard, included file
                        # links but did not recurse through linked directories.
                        if Path(entry.path).is_file():
                            expanded.add(relative)
                    else:
                        raise ControlError("repository content manifest path is stale")
                except OSError as exc:
                    raise ControlError("repository content manifest path is stale") from exc
    return expanded


class _WindowsRepositoryChangeWatch:
    """Fail-closed recursive NTFS change observation for one read-only command."""

    def __init__(self, root: Path) -> None:
        import ctypes
        from ctypes import wintypes

        ulong_ptr = ctypes.c_size_t

        class Overlapped(ctypes.Structure):
            _fields_ = [
                ("Internal", ulong_ptr), ("InternalHigh", ulong_ptr),
                ("Offset", wintypes.DWORD), ("OffsetHigh", wintypes.DWORD),
                ("hEvent", wintypes.HANDLE),
            ]

        self._ctypes = ctypes
        self._wintypes = wintypes
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._overlapped_type = Overlapped
        self._root = root
        self._directory_handle: Any = None
        self._event_handle: Any = None
        self._overlapped: Any = None
        self._buffer: Any = None

    def start(self) -> None:
        ctypes = self._ctypes
        wintypes = self._wintypes
        kernel32 = self._kernel32
        kernel32.CreateFileW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
        ]
        kernel32.CreateFileW.restype = wintypes.HANDLE
        kernel32.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateEventW.restype = wintypes.HANDLE
        kernel32.ReadDirectoryChangesW.argtypes = [
            wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD, wintypes.BOOL,
            wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(self._overlapped_type), wintypes.LPVOID,
        ]
        kernel32.ReadDirectoryChangesW.restype = wintypes.BOOL
        kernel32.CancelIoEx.argtypes = [wintypes.HANDLE, wintypes.LPVOID]
        kernel32.CancelIoEx.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        self._directory_handle = kernel32.CreateFileW(
            str(_native_path(self._root)), 0x0001, 0x0001 | 0x0002 | 0x0004,
            None, 3, 0x02000000 | 0x40000000, None,
        )
        if self._directory_handle == wintypes.HANDLE(-1).value:
            self.close()
            raise ControlError("repository change observation is unavailable")
        self._event_handle = kernel32.CreateEventW(None, True, False, None)
        if not self._event_handle:
            self.close()
            raise ControlError("repository change observation is unavailable")
        self._overlapped = self._overlapped_type()
        self._overlapped.hEvent = self._event_handle
        self._buffer = ctypes.create_string_buffer(65536)
        returned = wintypes.DWORD()
        accepted = kernel32.ReadDirectoryChangesW(
            self._directory_handle, self._buffer, len(self._buffer), True,
            0x0001 | 0x0002 | 0x0004 | 0x0008 | 0x0010 | 0x0040 | 0x0100,
            ctypes.byref(returned), ctypes.byref(self._overlapped), None,
        )
        if not accepted and ctypes.get_last_error() != 997:
            self.close()
            raise ControlError("repository change observation is unavailable")

    def changed(self) -> bool:
        wintypes = self._wintypes
        kernel32 = self._kernel32
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        wait_result = kernel32.WaitForSingleObject(self._event_handle, 100)
        if wait_result == 0:
            return True
        if wait_result != 258:
            raise ControlError("repository change observation failed closed")
        return False

    def close(self) -> None:
        if self._directory_handle not in (None, self._wintypes.HANDLE(-1).value):
            if self._overlapped is not None:
                self._kernel32.CancelIoEx(self._directory_handle, self._ctypes.byref(self._overlapped))
            self._kernel32.CloseHandle(self._directory_handle)
        if self._event_handle:
            self._kernel32.CloseHandle(self._event_handle)
        self._directory_handle = None
        self._event_handle = None


def _repository_content_manifest(root: Path, *, include_ignored_evidence: bool = True) -> dict[str, str]:
    """Hash reviewable worktree bytes and ignored evidence for read-only commands."""
    root = root.resolve()

    def git_output(*arguments: str) -> bytes:
        completed = subprocess.run(
            ["git", "-c", "core.longpaths=true", "-C", str(root), *arguments],
            shell=False, capture_output=True, check=False, timeout=120,
        )
        if completed.returncode != 0:
            raise ControlError("repository content manifest is unavailable")
        return completed.stdout

    def decode_paths(payload: bytes) -> set[str]:
        try:
            return {item.decode("utf-8") for item in payload.split(b"\0") if item}
        except UnicodeDecodeError as exc:
            raise ControlError("repository content manifest contains a non-UTF-8 path") from exc

    index_entries: dict[str, str] = {}
    try:
        stage_records = [item for item in git_output("ls-files", "--cached", "--stage", "-z").split(b"\0") if item]
        for record in stage_records:
            metadata, encoded_path = record.split(b"\t", 1)
            mode, object_id, stage = metadata.decode("ascii").split(" ")
            relative = encoded_path.decode("utf-8")
            if stage != "0" or relative in index_entries:
                raise ControlError("repository content manifest has unresolved index entries")
            index_entries[relative] = f"git-index:{mode}:{object_id}"
    except (UnicodeDecodeError, UnicodeEncodeError, ValueError) as exc:
        raise ControlError("repository content manifest contains malformed index data") from exc

    dirty = decode_paths(git_output("diff-files", "--name-only", "--no-ext-diff", "-z"))
    untracked = decode_paths(git_output("ls-files", "--others", "--exclude-standard", "-z"))
    ignored_evidence = (
        _expand_ignored_evidence_directories(
            root,
            decode_paths(
                git_output("ls-files", "--others", "--ignored", "--exclude-standard", "-z", "--", "logs")
            ),
        )
        if include_ignored_evidence else set()
    )
    tracked = set(index_entries)
    actual_byte_paths = dirty | untracked | ignored_evidence
    all_paths = tracked | actual_byte_paths

    resolved_paths: dict[str, Path] = {}
    tombstones: set[str] = set()
    ignored_directory_links: set[str] = set()
    native_root = _native_path(root).resolve()
    for relative in sorted(all_paths):
        pure = PurePosixPath(relative)
        if pure.is_absolute() or not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
            raise ControlError("repository content manifest path is stale")
        path = _native_path(root.joinpath(*pure.parts))
        try:
            path.resolve().relative_to(native_root)
        except ValueError as exc:
            raise ControlError("repository content manifest path escapes root") from exc
        if path.is_file():
            resolved_paths[relative] = path
        elif relative in tracked and not path.exists():
            tombstones.add(relative)
        elif relative in tracked and relative not in actual_byte_paths:
            # Clean submodules are represented by their index commit identity.
            continue
        elif relative in ignored_evidence and path.is_symlink() and path.is_dir():
            ignored_directory_links.add(relative)
        else:
            raise ControlError("repository content manifest path is stale")

    manifest = {
        relative: index_entries[relative]
        for relative in sorted(tracked - actual_byte_paths - tombstones)
    }
    for relative in sorted(tombstones):
        manifest[relative] = "tracked-tombstone"

    paths_to_hash = sorted(actual_byte_paths - tombstones - ignored_directory_links)
    worker_count = min(32, max(4, (os.cpu_count() or 1) * 2))
    try:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            digests = executor.map(
                _hash_repository_file,
                (resolved_paths[relative] for relative in paths_to_hash),
            )
            for relative, digest in zip(paths_to_hash, digests, strict=True):
                manifest[relative] = digest
    except OSError as exc:
        raise ControlError("repository content manifest path is stale") from exc
    return manifest


def _validate_read_only_status_delta(before: dict[str, str], after: dict[str, str]) -> dict[str, list[str]]:
    if before != after:
        raise ControlError("read-only command changed repository bytes")
    return {"added": [], "deleted": [], "modified": [], "changedPaths": []}


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
    input_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Run one typed local command and return non-authorizing process evidence."""
    validate_command_descriptor(descriptor)
    root = repository_root.resolve()
    if not root.is_dir():
        raise ControlError("repository root is invalid")
    raw_inputs = input_paths or []
    if not isinstance(raw_inputs, list):
        raise ControlError("controlled command input paths are invalid")
    input_bindings: list[dict[str, str]] = []
    seen_inputs: set[str] = set()
    for relative in raw_inputs:
        if not isinstance(relative, str):
            raise ControlError("controlled command input path is invalid")
        candidate = (root / relative).resolve()
        try:
            normalized = candidate.relative_to(root).as_posix()
        except ValueError as exc:
            raise ControlError("controlled command input escapes repository root") from exc
        if normalized != relative.replace("\\", "/") or not candidate.is_file():
            raise ControlError("controlled command input is missing or non-canonical")
        if normalized in seen_inputs:
            raise ControlError("controlled command input paths are duplicated")
        seen_inputs.add(normalized)
        input_bindings.append(
            {
                "path": normalized,
                "sha256": "sha256:" + hashlib.sha256(candidate.read_bytes()).hexdigest(),
            }
        )
    input_bindings.sort(key=lambda item: item["path"])
    allowed_write_roots = descriptor["allowed_write_roots"]
    forbidden_write_roots = descriptor["forbidden_write_roots"]
    resolved_argv = resolve_typed_argv(
        descriptor["argv"], descriptor["typed_placeholders"], descriptor["placeholder_values"], root, allowed_write_roots
    )
    read_only = not allowed_write_roots and (root / ".git").exists()
    evidence_root = root / "logs"
    change_watch = (
        _WindowsRepositoryChangeWatch(evidence_root)
        if read_only and os.name == "nt" and evidence_root.is_dir() else None
    )
    if change_watch is not None:
        change_watch.start()
    try:
        before_manifest = (
            _repository_content_manifest(root, include_ignored_evidence=change_watch is None)
            if read_only else build_write_manifest(root)
        )
    except Exception:
        if change_watch is not None:
            change_watch.close()
        raise
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
            "stderr": stderr.decode("utf-8", errors="replace"),
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
    if input_bindings:
        current_bindings = [
            {
                "path": item["path"],
                "sha256": "sha256:" + hashlib.sha256((root / item["path"]).read_bytes()).hexdigest(),
            }
            for item in input_bindings
        ]
        if current_bindings != input_bindings:
            raise ControlError("controlled command inputs changed during execution")
        receipt["inputBindings"] = input_bindings
        receipt["inputBindingsHash"] = _canonical_hash(input_bindings)
    try:
        after_manifest = (
            _repository_content_manifest(root, include_ignored_evidence=change_watch is None)
            if read_only else build_write_manifest(root)
        )
        if change_watch is not None and change_watch.changed():
            raise ControlError("read-only command changed repository bytes")
        delta = (
            _validate_read_only_status_delta(before_manifest, after_manifest)
            if read_only
            else validate_write_manifest_delta(before_manifest, after_manifest, allowed_write_roots, forbidden_write_roots)
        )
    finally:
        if change_watch is not None:
            change_watch.close()
    receipt["writeManifestDelta"] = delta
    receipt["writeManifestDeltaHash"] = _canonical_hash(delta)
    return receipt


def resolve_registered_command(registry: Any, command_id: str) -> dict[str, Any]:
    """Resolve exactly one immutable descriptor from a hash-bound registry.

    This is deliberately separate from descriptor-shape validation: public
    callers must never turn an arbitrary JSON descriptor into an executable
    command merely by supplying syntactically valid fields.
    """
    if not isinstance(command_id, str) or not command_id:
        raise ControlError("command registry identity is invalid")
    if isinstance(registry, dict) and set(registry) == {"schema_version", "commands"}:
        return _resolve_legacy_registered_command(registry, command_id)
    if not isinstance(registry, dict) or set(registry) != {"schemaVersion", "commands", "registryHash"}:
        raise ControlError("command registry fields are invalid")
    if registry.get("schemaVersion") != "acceptance-command-registry.v1":
        raise ControlError("command registry identity is invalid")
    commands = registry.get("commands")
    if not isinstance(commands, list):
        raise ControlError("command registry commands are invalid")
    # registry_hash appears inside each descriptor to bind its receipt.  Hash
    # the registry material with that derived field omitted, avoiding a
    # self-referential digest while still binding every executable argument.
    material_commands = [
        {key: value for key, value in command.items() if key != "registry_hash"}
        if isinstance(command, dict) else command
        for command in commands
    ]
    material = {"schemaVersion": registry["schemaVersion"], "commands": material_commands}
    if registry.get("registryHash") != _canonical_hash(material):
        raise ControlError("command registry hash is stale")
    matches = [item for item in commands if isinstance(item, dict) and item.get("id") == command_id]
    if len(matches) != 1:
        raise ControlError("command registry command must resolve uniquely")
    descriptor = matches[0]
    validate_command_descriptor(descriptor)
    if descriptor["registry_hash"] != registry["registryHash"]:
        raise ControlError("command descriptor is not bound to its registry")
    return descriptor


def _resolve_legacy_registered_command(registry: dict[str, Any], command_id: str) -> dict[str, Any]:
    """Project the plan-owned v1 registry into the current descriptor contract."""
    if registry.get("schema_version") != "ria.command-registry.v1" or not isinstance(registry.get("commands"), list):
        raise ControlError("legacy command registry identity is invalid")
    matches = [item for item in registry["commands"] if isinstance(item, dict) and item.get("id") == command_id]
    if len(matches) != 1:
        raise ControlError("legacy command registry command must resolve uniquely")
    command = matches[0]
    if set(command) != {"id", "executable", "argv", "cwd", "timeout_seconds", "shell"}:
        raise ControlError("legacy command registry descriptor fields are invalid")
    cwd = command.get("cwd")
    if cwd == ".":
        normalized_cwd = "."
    elif isinstance(cwd, dict) and cwd == {"type": "repo_path", "value": "."}:
        normalized_cwd = "."
    else:
        raise ControlError("legacy command registry cwd is invalid")
    descriptor = {
        "id": command["id"], "executable": command["executable"], "argv": command["argv"],
        "cwd": normalized_cwd, "timeout_seconds": command["timeout_seconds"], "shell": command["shell"],
        "allowed_write_roots": [], "forbidden_write_roots": [
            "logs/phase-a-innernet/**", "runtime/phase-a/**", "PhaseA.Platform/**", "PhaseA.Platform.Tests/**",
        ],
        "registry_hash": _canonical_hash(registry),
        "environment_allowlist": _LEGACY_ENVIRONMENT_ALLOWLIST.copy(),
        "typed_placeholders": {}, "placeholder_values": {},
    }
    validate_command_descriptor(descriptor)
    return descriptor


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
    order = _command_registry_order(command_registry)
    action = next_action(actions, completed_action_ids, order)
    if set(command_registry) in (
        {"schema_version", "commands"},
        {"schemaVersion", "commands", "registryHash"},
    ):
        descriptor = resolve_registered_command(command_registry, action["commandId"])
    else:
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


def _command_registry_order(command_registry: Any) -> dict[str, int]:
    if not isinstance(command_registry, dict):
        raise ControlError("command registry is invalid")
    if set(command_registry) in (
        {"schema_version", "commands"},
        {"schemaVersion", "commands", "registryHash"},
    ):
        commands = command_registry.get("commands")
        if not isinstance(commands, list):
            raise ControlError("command registry commands are invalid")
        command_ids = [
            command.get("id") if isinstance(command, dict) else None
            for command in commands
        ]
        if (
            any(not isinstance(command_id, str) or not command_id for command_id in command_ids)
            or len(command_ids) != len(set(command_ids))
        ):
            raise ControlError("command registry identities are invalid")
        return {command_id: index for index, command_id in enumerate(command_ids)}
    if any(
        not isinstance(command_id, str)
        or not command_id
        or not isinstance(descriptor, dict)
        for command_id, descriptor in command_registry.items()
    ):
        raise ControlError("command registry is invalid")
    return {command_id: index for index, command_id in enumerate(command_registry)}


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
