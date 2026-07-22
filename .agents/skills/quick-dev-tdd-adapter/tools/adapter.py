from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any


def _blocked(run: dict[str, Any], rule_id: str, message: str) -> dict[str, Any]:
    result = deepcopy(run)
    result["state"] = "blocked"
    result["diagnostic"] = {"rule_id": rule_id, "message": message}
    return result


def _value_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _within(paths: list[str], allowed: list[str]) -> bool:
    normalized = [path.replace("\\", "/").casefold() for path in paths]
    prefixes = [path.replace("\\", "/").rstrip("*").casefold() for path in allowed]
    return all(any(path.startswith(prefix) for prefix in prefixes) for path in normalized)


def prepare(contract: dict[str, Any], slice_id: str, identities: dict[str, str]) -> dict[str, Any]:
    if contract.get("backend", {}).get("hidden_state") is not False:
        return _blocked({}, "RMAP-PREPARE-INVALID", "adapter must not own hidden state")
    command_registry = contract.get("command_registry")
    if isinstance(command_registry, dict) and command_registry.get("shell") is True:
        return _blocked({}, "RMAP-CMD-SHELL", "shell execution is forbidden")
    selected = next((item for item in contract.get("slices", []) if item.get("slice_id") == slice_id), None)
    if selected is None:
        return _blocked({}, "RMAP-PREPARE-INVALID", "declared slice is missing")
    required = {"contract_hash", "validator_hash"}
    if not required.issubset(identities) or any(not identities[key] for key in required):
        return _blocked({}, "RMAP-HASH-AUTHORITY", "current identities are required")
    return {
        "state": "prepared",
        "slice_id": slice_id,
        "stages": [],
        "identities": dict(identities),
        "allowed_changes": deepcopy(selected.get("allowed_changes", {})),
        "authorizes": [],
        "does_not_authorize": ["acceptance", "handoff", "release"],
    }


def transition(run: dict[str, Any], stage: str, event: dict[str, Any]) -> dict[str, Any]:
    current = deepcopy(run)
    previous = list(current.get("stages", []))
    paths = list(event.get("changed_paths", []))
    allowed = current.get("allowed_changes", {})

    if stage == "red":
        if current.get("state") != "prepared":
            return _blocked(current, "RMAP-TDD-RED-NOT-OBSERVED", "RED requires prepared state")
        if event.get("exit_code") == 0 or not event.get("expected_failure_id"):
            return _blocked(current, "RMAP-TDD-RED-NOT-OBSERVED", "RED must observe the declared failure")
        red_paths = [*allowed.get("tests", []), *allowed.get("documentation", [])]
        if not _within(paths, red_paths):
            return _blocked(current, "RMAP-TDD-IMPLEMENTATION-BEFORE-RED", "RED changed a production path")
        current["state"] = "red-observed"
    elif stage == "green":
        if current.get("state") != "red-observed" or "red" not in previous:
            return _blocked(current, "RMAP-TDD-RED-NOT-OBSERVED", "GREEN requires current observed RED")
        if event.get("exit_code") != 0 or not _within(paths, allowed.get("production", [])):
            return _blocked(current, "RMAP-TDD-EXIT-PROOF", "GREEN must pass inside the production write set")
        current["state"] = "green-observed"
    elif stage == "refactor":
        if current.get("state") != "green-observed" or "green" not in previous:
            return _blocked(current, "RMAP-TDD-EXIT-PROOF", "REFACTOR requires GREEN")
        refactor_paths = [*allowed.get("production", []), *allowed.get("tests", []), *allowed.get("documentation", [])]
        if event.get("exit_code") != 0 or not _within(paths, refactor_paths):
            return _blocked(current, "RMAP-TDD-EXIT-PROOF", "REFACTOR must pass inside the declared write set")
        current["state"] = "refactor-verified"
    else:
        return _blocked(current, "RMAP-PREPARE-INVALID", "unknown transition")

    current["stages"] = [*previous, stage]
    current.pop("diagnostic", None)
    return current


def status(run: dict[str, Any]) -> dict[str, Any]:
    return {"state": run.get("state", "initialized"), "slice_id": run.get("slice_id"), "stages": list(run.get("stages", []))}


def finalize_candidate(run: dict[str, Any]) -> dict[str, Any]:
    """Return a non-authoritative candidate observation after the complete lifecycle."""
    if run.get("state") != "refactor-verified" or run.get("stages") != ["red", "green", "refactor"]:
        return _blocked(run, "RMAP-TDD-EXIT-PROOF", "candidate requires one complete observed lifecycle")
    result = deepcopy(run)
    result["state"] = "implementation-candidate"
    result["authorizes"] = []
    return result


def resume(run: dict[str, Any], identities: dict[str, str]) -> dict[str, Any]:
    if run.get("identities") != identities:
        return _blocked(run, "RMAP-HASH-AUTHORITY", "run identities are stale")
    if run.get("state") in {"failed", "stale", "superseded"}:
        return _blocked(run, "RMAP-RECOVERY-NEW-RUN-STATE", "stale run requires a successor")
    return deepcopy(run)


def _run_path(run_dir: Path, relative: str) -> Path | None:
    candidate = (run_dir / relative).resolve()
    try:
        candidate.relative_to(run_dir.resolve())
    except ValueError:
        return None
    return candidate


def compose_stage_binding(protocol_bundle: dict[str, Any], stage: str) -> dict[str, str]:
    """Derive one non-authoritative stage binding from caller-supplied protocol documents."""
    if stage not in {"red", "green", "refactor"} or protocol_bundle.get("schema_version") != "rmap.capsule-attempt-bundle.v1":
        raise ValueError("protocol bundle or stage is invalid")
    contexts = [item for item in protocol_bundle.get("contexts", []) if isinstance(item, dict) and item.get("context_manifest", {}).get("stage") == stage]
    attempts = [item for item in protocol_bundle.get("attempts", []) if isinstance(item, dict) and item.get("backend_request", {}).get("stage") == stage]
    if len(contexts) != 1 or len(attempts) != 1:
        raise ValueError("protocol stage must have exactly one context and attempt")
    context = contexts[0].get("context_manifest")
    decision = attempts[0].get("adapter_decision")
    request = attempts[0].get("backend_request")
    if not isinstance(context, dict) or not isinstance(decision, dict) or not isinstance(request, dict):
        raise ValueError("protocol stage documents are invalid")
    capsule_ref = context.get("capsule_ref")
    expected_binding = f"STAGE-{stage.upper()}"
    if (
        not isinstance(capsule_ref, dict)
        or decision.get("authorizes") != []
        or request.get("stage_binding_id") != expected_binding
        or decision.get("stage_binding_id") != expected_binding
        or request.get("attempt_id") != decision.get("attempt_id")
        or any(request.get(key) != context.get(key) for key in ("plan_id", "slice_id", "run_id"))
    ):
        raise ValueError("protocol stage binding is inconsistent or authoritative")
    return {
        "stage_binding_id": expected_binding,
        "attempt_id": request["attempt_id"],
        "decision_hash": _value_hash(decision),
        "capsule_hash": capsule_ref["sha256"],
        "context_hash": context["context_hash"],
    }


def persist_protocol_bundle(
    run_dir: Path,
    protocol_bundle: dict[str, Any],
    artifact_store: dict[tuple[str, str], bytes],
) -> None:
    """Write a caller-validated protocol bundle once, with decisions after other attempt records."""
    if not isinstance(protocol_bundle, dict) or protocol_bundle.get("schema_version") != "rmap.capsule-attempt-bundle.v1":
        raise ValueError("protocol bundle identity is invalid")
    if any(not isinstance(key, tuple) or len(key) != 2 or not isinstance(key[0], str) or not isinstance(key[1], str) or not isinstance(value, bytes) for key, value in artifact_store.items()):
        raise ValueError("protocol artifact store is invalid")

    contexts = protocol_bundle.get("contexts")
    attempts = protocol_bundle.get("attempts")
    if not isinstance(contexts, list) or not isinstance(attempts, list):
        raise ValueError("protocol bundle collections are invalid")
    ordered_documents: list[str] = []
    for context in contexts:
        capsule_id = context.get("slice_capsule", {}).get("capsule_id") if isinstance(context, dict) else None
        if not isinstance(capsule_id, str):
            raise ValueError("protocol capsule identity is missing")
        ordered_documents.extend([
            f"context/{capsule_id}/slice-capsule.v1.json",
            f"context/{capsule_id}/context-manifest.v1.json",
        ])
    for attempt in attempts:
        attempt_id = attempt.get("backend_request", {}).get("attempt_id") if isinstance(attempt, dict) else None
        if not isinstance(attempt_id, str):
            raise ValueError("protocol attempt identity is missing")
        ordered_documents.extend([
            f"attempts/{attempt_id}/backend-request.v1.json",
            f"attempts/{attempt_id}/backend-response.v1.json",
            f"attempts/{attempt_id}/diff-manifest.v1.json",
            f"attempts/{attempt_id}/adapter-decision.v1.json",
        ])
    ordered_documents.extend(["run-events.jsonl", "attempt-ledger-manifest.v1.json"])
    payloads = {path: payload for (path_type, path), payload in artifact_store.items() if path_type == "run_path"}
    if any(path not in payloads or _run_path(run_dir, path) is None for path in ordered_documents):
        raise ValueError("protocol artifact set is incomplete or escapes the run")
    for path in run_dir.rglob("*"):
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
        if path.is_symlink() or attributes & 0x400:
            raise ValueError("reparse point prevents protocol persistence")
    existing_paths = {
        path.relative_to(run_dir).as_posix()
        for path in run_dir.rglob("*")
        if path.is_file()
    }
    if existing_paths - set(payloads):
        raise ValueError("undeclared existing artifact prevents protocol persistence")

    for path, payload in payloads.items():
        destination = _run_path(run_dir, path)
        if destination is None:
            raise ValueError("protocol artifact escapes the run")
        if destination.exists() and (not destination.is_file() or destination.read_bytes() != payload):
            raise ValueError("existing protocol artifact conflicts with immutable evidence")

    # All non-decision artifacts exist before a decision is finalized; the run is new, so no write can replace evidence.
    for path in sorted(set(payloads) - set(ordered_documents)):
        destination = _run_path(run_dir, path)
        if destination is None:
            raise ValueError("protocol artifact escapes the run")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            destination.write_bytes(payloads[path])
    for path in ordered_documents:
        destination = _run_path(run_dir, path)
        if destination is None:
            raise ValueError("protocol artifact escapes the run")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            destination.write_bytes(payloads[path])


def execute(
    run_dir: Path,
    contract: dict[str, Any],
    slice_id: str,
    identities: dict[str, str],
    events: list[dict[str, Any]],
    *,
    protocol_bundle: dict[str, Any] | None = None,
    artifact_store: dict[tuple[str, str], bytes] | None = None,
) -> dict[str, Any]:
    """Persist a caller-supplied, deterministic lifecycle without hidden state."""
    if run_dir.exists():
        return _blocked({}, "RMAP-RECOVERY-NEW-RUN-STATE", "existing run requires an explicit successor")
    run_dir.mkdir(parents=True)
    state_path = run_dir / "recovery-state.json"
    if state_path.exists():
        return _blocked({}, "RMAP-RECOVERY-NEW-RUN-STATE", "existing run requires an explicit successor")
    run = prepare(contract, slice_id, identities)
    for event in events:
        stage = event.get("stage")
        if not isinstance(stage, str):
            return _blocked(run, "RMAP-PREPARE-INVALID", "stage event is missing its stage")
        run = transition(run, stage, event)
        if run.get("state") == "blocked":
            return run
    if (protocol_bundle is None) != (artifact_store is None):
        return _blocked(run, "RMAP-PREPARE-INVALID", "protocol bundle and artifact store must be supplied together")
    if protocol_bundle is not None and artifact_store is not None:
        try:
            persist_protocol_bundle(run_dir, protocol_bundle, artifact_store)
        except ValueError as exc:
            return _blocked(run, "RMAP-PREPARE-INVALID", str(exc))
    document = {
        "schema_version": "rmap.recovery-state.v1", "run_id": run_dir.name, "state": run["state"],
        "slice_id": slice_id, "contract_hash": identities["contract_hash"], "validator_hash": identities["validator_hash"],
        "predecessor_run_id": None, "supersedes_run_id": None, "stages": run["stages"], "authorizes": [],
    }
    state_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8", newline="\n")
    return run
