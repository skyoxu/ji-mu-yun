"""Project explicit frozen source path contracts into V3 slice hints.

V0/V0A already freeze and validate the canonical requirement text.  The live V3
worker receives that frozen text, but model-authored path fields can still drift.
This layer deterministically projects only path facts that are stated with
unambiguous contract phrases in the frozen source:

* ``Production owner: `path` `` / ``Production owners: ...``;
* ``must create `path` `` for planned files;
* ``existing fixture `path` `` for already-present fixture identity;
* ``production implementation may modify only the production owner`` for an
  exact production write boundary.

It does not infer paths from prose, directory layout, sibling groups, filenames,
or benchmark identity.  Unrecognized source text is left untouched and the
existing V3 execution-contract remains authoritative/fail-closed.
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Mapping

import semantic_compiler_gate as gate

_BASE_TRANSPORT = gate._ORIGINAL_INVOKE_WORKER
_OWNER_LINE = re.compile(r"^\s*Production owners?\s*:\s*(.+)$", re.IGNORECASE)
_MUST_CREATE = re.compile(r"\bmust create\s+`([^`]+)`", re.IGNORECASE)
_EXISTING_FIXTURE = re.compile(r"\bexisting fixture\s+`([^`]+)`", re.IGNORECASE)
_OWNER_ONLY = re.compile(
    r"production implementation\s+may modify only\s+the production owner(?:s)?(?:\s+above)?",
    re.IGNORECASE,
)
_BACKTICK = re.compile(r"`([^`]+)`")


def _input_payload(stage: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    if stage.startswith("v3-schema-repair"):
        nested = payload.get("input")
        return nested if isinstance(nested, Mapping) else {}
    return payload


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if isinstance(item, str) and item.strip()]


def _source_facts(raw: Mapping[str, Any]) -> dict[str, Any]:
    text = raw.get("source_text")
    source_ref = raw.get("source_ref")
    if not isinstance(text, str) or not text.strip() or not isinstance(source_ref, str) or not source_ref:
        return {"source_ref": source_ref, "owners": [], "planned": [], "existing_fixtures": [], "owner_only": False}

    owners: list[str] = []
    for line in text.splitlines():
        match = _OWNER_LINE.match(line)
        if not match:
            continue
        owners.extend(_BACKTICK.findall(match.group(1)))

    return {
        "source_ref": source_ref,
        "owners": sorted(set(_strings(owners))),
        "planned": sorted(set(match.group(1).strip() for match in _MUST_CREATE.finditer(text) if match.group(1).strip())),
        "existing_fixtures": sorted(set(match.group(1).strip() for match in _EXISTING_FIXTURE.finditer(text) if match.group(1).strip())),
        "owner_only": bool(_OWNER_ONLY.search(text)),
    }


def _contracts_by_ref(stage: str, payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    source = _input_payload(stage, payload)
    contracts = source.get("source_contracts")
    if not isinstance(contracts, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for raw in contracts:
        if not isinstance(raw, Mapping):
            continue
        facts = _source_facts(raw)
        ref = facts.get("source_ref")
        if isinstance(ref, str) and ref:
            result[ref] = facts
    return result


def _refs_by_obligation(stage: str, payload: Mapping[str, Any]) -> dict[str, set[str]]:
    source = _input_payload(stage, payload)
    obligations = source.get("obligations")
    if not isinstance(obligations, list):
        return {}
    result: dict[str, set[str]] = {}
    for raw in obligations:
        if not isinstance(raw, Mapping):
            continue
        oid = raw.get("obligation_id")
        if not isinstance(oid, str) or not oid:
            continue
        refs = {ref for ref in _strings(raw.get("source_refs"))}
        result[oid] = refs
    return result


def _real_file(root: Path, raw: str) -> bool:
    try:
        path = (root / raw).resolve()
        path.relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return path.is_file() and not path.is_symlink()


def _normalize_hint(
    root: Path,
    raw: Mapping[str, Any],
    *,
    refs_by_oid: Mapping[str, set[str]],
    contracts_by_ref: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    hint = dict(raw)
    ids = _strings(hint.get("obligation_ids"))
    refs = {ref for oid in ids for ref in refs_by_oid.get(oid, set())}
    facts = [contracts_by_ref[ref] for ref in sorted(refs) if ref in contracts_by_ref]
    if not facts:
        return hint

    explicit_owners = sorted({path for fact in facts for path in _strings(fact.get("owners"))})
    explicit_planned = sorted({path for fact in facts for path in _strings(fact.get("planned"))})
    explicit_existing = sorted({path for fact in facts for path in _strings(fact.get("existing_fixtures"))})
    owner_only = bool(explicit_owners) and all(bool(fact.get("owner_only")) for fact in facts if _strings(fact.get("owners")))

    # ADR-0041: execution snapshots are immutable RED inputs in Quick Dev.
    # Exact frozen production-write authority must not also freeze that owner.
    # Do not guess roles for other paths or resolve contradictory source facts.
    if owner_only and refs.issubset(contracts_by_ref):
        if set(explicit_owners) & (set(explicit_existing) | set(explicit_planned)):
            raise ValueError("frozen production owner conflicts with explicit RED artifact role")
        snapshots = hint.get("execution_snapshot_paths")
        if isinstance(snapshots, list):
            kept = [path for path in snapshots if path not in explicit_owners]
            if len(kept) != len(snapshots):
                # Owner-only hints still bind the source's explicit immutable
                # fixtures. Never substitute an arbitrary path to satisfy V3.
                kept.extend(path for path in explicit_existing if path not in kept)
            hint["execution_snapshot_paths"] = kept

    if explicit_owners:
        # Frozen source authority outranks a model-authored path guess.  Keep the
        # exact explicit owner set even if a source file is unexpectedly absent;
        # the downstream execution-contract will then fail closed on reality.
        hint["production_owners"] = explicit_owners

        forbidden = set(_strings(hint.get("forbidden_paths")))
        forbidden.difference_update(explicit_owners)
        hint["forbidden_paths"] = sorted(forbidden)

        if owner_only:
            hint["allowed_write_paths"] = explicit_owners
        else:
            allowed = set(_strings(hint.get("allowed_write_paths")))
            allowed.update(explicit_owners)
            hint["allowed_write_paths"] = sorted(allowed)

        rollback = hint.get("rollback_scope")
        if isinstance(rollback, Mapping):
            rollback_value = dict(rollback)
            rollback_paths = set(_strings(rollback_value.get("production_paths")))
            rollback_paths.update(explicit_owners)
            rollback_value["production_paths"] = sorted(rollback_paths)
            hint["rollback_scope"] = rollback_value

    if explicit_planned:
        planned = set(_strings(hint.get("planned_new_files")))
        authorized_planned = set(explicit_planned) - set(explicit_existing)
        planned.update(authorized_planned)
        # A path explicitly identified as already existing by the same frozen
        # source is never promoted to a planned-new file.
        planned.difference_update(explicit_existing)
        hint["planned_new_files"] = sorted(planned)

        # A frozen must-create contract is positive write authority for that
        # exact new path. Preserve every unrelated/model-authored prohibition,
        # but remove this otherwise self-contradictory planned/forbidden overlap
        # before V6 compatibility grouping.
        forbidden = set(_strings(hint.get("forbidden_paths")))
        forbidden.difference_update(authorized_planned)
        hint["forbidden_paths"] = sorted(forbidden)

    return hint


def normalize_explicit_path_contracts(
    root: Path,
    stage: str,
    payload: Mapping[str, Any],
    value: Mapping[str, Any],
) -> Mapping[str, Any]:
    if stage != "v3" and not stage.startswith("v3-schema-repair"):
        return value
    contracts_by_ref = _contracts_by_ref(stage, payload)
    refs_by_oid = _refs_by_obligation(stage, payload)
    if not contracts_by_ref or not refs_by_oid:
        return value
    hints = value.get("slice_hints")
    if not isinstance(hints, list):
        return value
    normalized = dict(value)
    normalized["slice_hints"] = [
        _normalize_hint(root, raw, refs_by_oid=refs_by_oid, contracts_by_ref=contracts_by_ref)
        if isinstance(raw, Mapping)
        else raw
        for raw in hints
    ]
    return normalized


def explicit_path_contract_transport(
    *,
    root,
    out_dir,
    stage: str,
    payload: Mapping[str, Any],
    prompt: str,
    worker_cache: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    value = _BASE_TRANSPORT(
        root=root,
        out_dir=out_dir,
        stage=stage,
        payload=payload,
        prompt=prompt,
        worker_cache=worker_cache,
    )
    return normalize_explicit_path_contracts(Path(root), stage, payload, value)


def install() -> None:
    gate._ORIGINAL_INVOKE_WORKER = explicit_path_contract_transport


install()
