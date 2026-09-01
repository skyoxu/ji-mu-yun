"""Deterministic planned-descriptor contract gate for Quick Dev Q1.

Q1 runs before RED materialization, so target/fixture files may legitimately be
planned rather than present.  This gate validates the *planned* execution
contract from the VDD semantic bundle and agent-context projection without
running tests or invoking a model.  The public stable entrypoint runs this gate
before the runtime/environment preflight.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from runtime_evidence import safe_relative, sha256_bytes, sha256_value

_CODE_SUFFIXES = {".py", ".cs", ".gd", ".js", ".ts"}


def _one(items: Any, key: str, value: str, label: str) -> Mapping[str, Any]:
    if not isinstance(items, list):
        raise ValueError(f"{label} collection missing")
    matches = [item for item in items if isinstance(item, Mapping) and item.get(key) == value]
    if len(matches) != 1:
        raise ValueError(f"{label} identity missing or ambiguous")
    return matches[0]


def _string_list(value: Any, label: str, *, nonempty: bool = True) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        raise ValueError(f"{label} must be non-empty list")
    result: list[str] = []
    for raw in value:
        if not isinstance(raw, str) or not raw:
            raise ValueError(f"{label} contains invalid value")
        result.append(raw)
    return result


def _candidate_identity(workspace: Path, bundle: Mapping[str, Any], slice_item: Mapping[str, Any]) -> dict[str, Any]:
    refs: set[str] = set()
    for field in ("production_owners", "planned_new_files", "execution_snapshot_paths"):
        raw = slice_item.get(field, [])
        if not isinstance(raw, list):
            raise ValueError(f"slice {field} invalid")
        for item in raw:
            refs.add(safe_relative(str(item)))
    state: dict[str, str | None] = {}
    root = workspace.resolve()
    for ref in sorted(refs):
        path = (root / ref).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError("candidate path escapes repository") from exc
        state[ref] = sha256_bytes(path.read_bytes()) if path.is_file() and not path.is_symlink() else None
    material = {
        "schema": "quick-dev.slice-candidate-identity.v1",
        "plan_id": bundle.get("plan_id"),
        "plan_sha256": sha256_value(dict(bundle)),
        "slice_id": slice_item.get("slice_id"),
        "paths": state,
    }
    return {"candidate_hash": sha256_value(material), "paths": state}


def validate_planned_preflight(
    *,
    workspace: Path,
    bundle: Mapping[str, Any],
    slice_id: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Validate Q1's planned command/identity contract without side effects."""
    if not isinstance(bundle.get("plan_id"), str) or not bundle["plan_id"]:
        raise ValueError("plan identity missing")
    if not isinstance(timeout_seconds, int) or timeout_seconds <= 0:
        raise ValueError("planned timeout must be positive")

    selected = _one(bundle.get("slices"), "slice_id", slice_id, "slice")
    context = _one(bundle.get("agent_contexts"), "slice_id", slice_id, "agent-context")

    acceptance_ids = _string_list(selected.get("acceptance_ids"), "slice acceptance_ids")
    if context.get("acceptance_ids") != acceptance_ids:
        raise ValueError("agent-context Acceptance projection drift")

    allowed = _string_list(selected.get("allowed_write_paths"), "production write set")
    planned = _string_list(selected.get("planned_new_files", []), "planned new files", nonempty=False)
    snapshots = _string_list(selected.get("execution_snapshot_paths"), "execution snapshot paths")
    owners = _string_list(selected.get("production_owners"), "production owners")
    for raw in [*allowed, *planned, *snapshots, *owners]:
        safe_relative(raw)
    if any(owner not in set(allowed) and owner not in set(planned) for owner in owners):
        raise ValueError("production owner outside planned GREEN write set")

    commands = context.get("validation_commands")
    if not isinstance(commands, list) or not commands:
        raise ValueError("agent-context validation_commands missing")
    normalized_commands: list[list[str]] = []
    for index, raw in enumerate(commands):
        if not isinstance(raw, list) or not raw or any(not isinstance(item, str) or not item for item in raw):
            raise ValueError(f"validation command[{index}] must be non-empty argv array")
        normalized_commands.append(list(raw))
    argv = normalized_commands[0]

    proof = selected.get("proof")
    if not isinstance(proof, Mapping):
        raise ValueError("slice proof missing")
    selector_intents = _string_list(proof.get("selector_intents"), "selector intents")
    if context.get("selector_intents") != selector_intents:
        raise ValueError("agent-context selector projection drift")

    selector_text = " ".join([*argv, *selector_intents])
    target_refs = [ref for ref in snapshots if ref in selector_text]
    if not target_refs:
        target_refs = [ref for ref in snapshots if Path(ref).suffix.lower() in _CODE_SUFFIXES]
    if not target_refs:
        target_refs = [snapshots[0]]
    fixture_refs = [ref for ref in snapshots if ref not in target_refs]
    if not fixture_refs:
        fixture_refs = [target_refs[0]]

    planned_or_existing = set(planned)
    root = workspace.resolve()
    unresolved: list[str] = []
    for ref in sorted(set(target_refs + fixture_refs)):
        path = (root / ref).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError("planned target/fixture escapes repository") from exc
        if not path.is_file() and ref not in planned_or_existing:
            unresolved.append(ref)
    if unresolved:
        raise ValueError("planned target/fixture is neither materialized nor declared planned: " + ",".join(unresolved))

    candidate = _candidate_identity(workspace, bundle, selected)
    return {
        "schema": "quick-dev.q1-planned-preflight.v1",
        "status": "planned-contract-valid",
        "plan_id": bundle["plan_id"],
        "plan_sha256": sha256_value(dict(bundle)),
        "slice_id": slice_id,
        "candidate_hash": candidate["candidate_hash"],
        "argv": argv,
        "cwd": ".",
        "shell": False,
        "timeout_seconds": min(timeout_seconds, 600),
        "target_refs": target_refs,
        "fixture_refs": fixture_refs,
        "required_next_action": "author-red",
        "model_called": False,
        "tests_executed": False,
        "writes_performed": False,
        "authorizes": [],
    }
