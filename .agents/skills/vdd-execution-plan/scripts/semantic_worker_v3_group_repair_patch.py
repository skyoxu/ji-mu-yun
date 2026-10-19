"""V3 repair with shared implementation context and per-obligation proof.

ADR-0041: each required frozen-obligation key owns its complete proof and
execution context. The live format has no group references to drift. V6 merges
compatible contexts. Historical grouped caches keep their strict projection
checks; malformed references are never guessed or silently repaired.
"""
from __future__ import annotations

from semantic_progress import worker_call, stage_call, emit

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping

import semantic_compiler_gate as gate
import semantic_worker_transport_patch as transport
import semantic_worker_v3_domain_patch as v3_domain
from semantic_worker_v3_path_grounding_patch import ground_v3_paths
from semantic_repository_context import enrich_repository_context, PATH_CONTEXT_PROMPT

sc = gate.sc
_BASE_DOMAIN_TRANSPORT = gate._ORIGINAL_INVOKE_WORKER
# v6 adds explicit planned-new production-owner semantics; v5 cache entries
# were produced under the existing-file-only contract and cannot be reused.
_GROUP_STAGE = "v3-schema-repair-group-v7-planned-production-owner-runtime-test"
# Keep each worker schema bounded while avoiding one network round trip per
# atomic contract. Exact IDs are still enforced by the group schema and the
# frozen-domain merge below.
_MAX_OBLIGATIONS_PER_CALL = 4
_MAX_TRANSIENT_WORKER_ATTEMPTS = 10
_BEFORE_SPLIT_TRANSIENT_ATTEMPTS = 2
_PACKAGE_A_PLANNED_PRODUCTION = {
    "docs/standards/skill-authoring-standard.md",
    "docs/adr/ADR-0062-repository-skill-authoring-contract.md",
    "docs/architecture/ADR_INDEX_PHASE.md",
    "scripts/sc/config/skill-authoring-standard.v1.json",
    "scripts/sc/schemas/skill-quality-contract.v1.schema.json",
    "scripts/sc/schemas/skill-quality-result.v1.schema.json",
    "scripts/sc/validate_skill_quality.py",
    "scripts/sc/skill_quality_examples.py",
}
_PACKAGE_A_PLANNED_TEST_PATHS = {
    "scripts/sc/tests/test_skill_quality_core.py",
    "scripts/sc/tests/test_skill_quality_examples.py",
    "scripts/sc/tests/test_skill_quality_capabilities.py",
    "scripts/sc/tests/test_skill_quality_migration.py",
    "scripts/sc/tests/test_skill_replay_runtime.py",
    "scripts/sc/tests/skill_quality_support.py",
    "scripts/sc/tests/fixtures/skill-quality",
    "scripts/sc/tests/test_validate_skill_quality.py",
    ".agents/skills/vdd-execution-plan/tests/validators/scope_boundary_negative.py",
}


class TransientV3WorkerFailure(RuntimeError):
    """A worker process exited before producing a parseable candidate."""


def _write_refreshable_json(path: Path, value: Mapping[str, Any]) -> None:
    """Preserve an invalid cache as sidecar before publishing its replacement."""
    if path.exists():
        payload = sc.canonical_bytes(value)
        if path.read_bytes() != payload:
            sidecar = path.with_name(path.name + ".stale-p1-round-7-refresh")
            suffix = 1
            while sidecar.exists():
                sidecar = path.with_name(path.name + f".stale-p1-round-7-refresh-{suffix}")
                suffix += 1
            path.rename(sidecar)
    sc.atomic_json(path, value)
# A full TC-D1 package can contain enough independent obligations for one
# exact-key schema to exceed the practical response budget of the read-only
# worker. Each chunk remains exact; the final projection still checks the full
# frozen domain before any result can be published.
_MAX_CONTRACTS_PER_WORKER = 4
_CANDIDATE_FIXTURE = ".agents/skills/quick-dev-tdd-adapter/tools/fixtures/candidate-identity.v1.json"


def _cached_owner_is_admissible(root: Path, owner: object, hint: Mapping[str, Any]) -> bool:
    """Apply the same finite owner admission rule as the final V3 gate.

    Grouped repair runs before the execution-contract normalizer. Its cache
    preflight must allow an exact planned Package A owner (or an exact planned
    write-set entry) to reach that normalizer, while keeping arbitrary missing
    paths fail-closed.
    """
    if not isinstance(owner, str):
        return True
    if (root / owner).is_file() and not (root / owner).is_symlink():
        return True
    planned = set(hint.get("planned_new_files", []) if isinstance(hint, Mapping) else [])
    allowed = set(hint.get("allowed_write_paths", []) if isinstance(hint, Mapping) else [])
    return (
        owner in _PACKAGE_A_PLANNED_PRODUCTION
        or owner in _PACKAGE_A_PLANNED_TEST_PATHS
        or (
            owner in planned
            and owner in allowed
            and not owner.startswith(("tests/", "scripts/sc/tests/", "PhaseA.Platform.Tests/"))
        )
    )


def _declare_supported_missing_fixture(contract: dict[str, Any]) -> None:
    hint = contract.get("slice_hint")
    if not isinstance(hint, dict):
        return
    snapshots = hint.get("execution_snapshot_paths")
    planned = hint.get("planned_new_files")
    if (isinstance(snapshots, list) and _CANDIDATE_FIXTURE in snapshots
            and isinstance(planned, list) and _CANDIDATE_FIXTURE not in planned):
        planned.append(_CANDIDATE_FIXTURE)


def _invalid_contract_ids(payload: Mapping[str, Any], contracts: Mapping[str, Any]) -> set[str]:
    """Return only cached IDs rejected by the same V3 semantic gates as publication."""
    projected = _project_current_output(
        {"obligation_contracts": contracts}, _obligation_refs(payload))
    findings = v3_domain._domain_findings("v3-schema-repair", payload, projected)
    known = set(_obligation_refs(payload))
    invalid = {
        oid for finding in findings
        for oid in re.findall(r"O-[0-9A-F]+", finding)
        if oid in known
    }
    # ADR-0041: a usable path is not proof of a schema-valid contract. Check
    # each projection to bind field-level failures to only its owning ID.
    for oid in known & set(contracts):
        single = _project_current_output(
            {"obligation_contracts": {oid: contracts[oid]}},
            {oid: _obligation_refs(payload)[oid]})
        if gate._worker_schema_findings("v3", single):
            invalid.add(oid)
    return invalid


def _cache_requires_refresh(projected, root, payload):
    """Apply current publication schema before accepting any persisted V3 cache."""
    return bool(gate._worker_schema_findings("v3", projected)) or sc._v3_cache_requires_contract_refresh(
        projected, root, payload)


def _text_tokens(value: Any) -> set[str]:
    if not isinstance(value, str):
        return set()
    return {token for token in value.lower().replace("_", " ").replace("-", " ").split()
            if len(token) > 2}


def _contract_semantic_projection(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Project only V3 meaning and execution context, excluding identity keys."""
    acceptance = contract.get("acceptance") if isinstance(contract.get("acceptance"), Mapping) else {}
    oracle = acceptance.get("oracle") if isinstance(acceptance.get("oracle"), Mapping) else {}
    failures = contract.get("failure_intents") if isinstance(contract.get("failure_intents"), list) else []
    hint = contract.get("slice_hint") if isinstance(contract.get("slice_hint"), Mapping) else {}
    return {
        "source_refs": sorted(str(x) for x in acceptance.get("source_refs", []) if isinstance(x, str)),
        "given": acceptance.get("given"), "when": acceptance.get("when"),
        "then": acceptance.get("then"), "assertion_ids": sorted(
            str(x) for x in acceptance.get("assertion_ids", []) if isinstance(x, str)),
        "oracle": {
            "observable": oracle.get("observable"), "expected": oracle.get("expected"),
            "forbidden": sorted(str(x) for x in oracle.get("forbidden", []) if isinstance(x, str)),
        },
        "failures": [{k: item.get(k) for k in ("failure_family", "selector_intent", "expected_outcome")}
                     for item in failures if isinstance(item, Mapping)],
        "hint": {k: hint.get(k) for k in (
            "production_owners", "verification_lane", "behavior_change", "affected_subjects",
            "state_transition", "rollback_scope", "allowed_write_paths", "execution_snapshot_paths",
            "planned_new_files", "terminal_predicate", "forbidden_paths", "validation_commands")},
    }


def _contract_matches_obligation(contract: Mapping[str, Any], obligation: Mapping[str, Any]) -> bool:
    """Fail-closed semantic match used only to recover an ID-renamed cache entry."""
    projection = _contract_semantic_projection(contract)
    refs = sorted(str(x) for x in obligation.get("source_refs", []) if isinstance(x, str))
    if not refs or projection["source_refs"] != refs:
        return False
    hint = projection["hint"]
    subject = str(obligation.get("subject", "")).strip()
    subjects = {str(x).strip() for x in hint.get("affected_subjects", []) if isinstance(x, str)}
    corpus = " ".join(str(projection.get(k, "")) for k in ("given", "when", "then"))
    corpus += " " + " ".join(str(x) for x in hint.get("affected_subjects", []) if isinstance(x, str))
    if not subject or (subject not in subjects and not _text_tokens(subject) <= _text_tokens(corpus)):
        return False
    # These fields are the stable semantic anchors emitted from the frozen obligation.
    expected = _text_tokens(obligation.get("expected_behavior"))
    observable = _text_tokens(obligation.get("observable_result"))
    acceptance_text = " ".join(str(projection.get(k, "")) for k in ("then",))
    oracle_text = " ".join(str(projection["oracle"].get(k, "")) for k in ("observable", "expected"))
    if expected and not (expected & _text_tokens(acceptance_text + " " + str(hint.get("behavior_change", "")))):
        return False
    if observable and not (observable & _text_tokens(oracle_text)):
        return False
    return True


def _rebind_contract(contract: Mapping[str, Any], oid: str, refs: list[str]) -> dict[str, Any]:
    """Bind a semantically matched historical contract to the current obligation ID."""
    rebound = json.loads(json.dumps(contract, ensure_ascii=False))
    acceptance = rebound.get("acceptance")
    if isinstance(acceptance, dict):
        acceptance["source_refs"] = list(refs)
    return {oid: rebound}


def _string_array(*, nonempty: bool = False, enum: list[str] | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"type": "string", "minLength": 1}
    if enum:
        item["enum"] = enum
    result: dict[str, Any] = {"type": "array", "items": item}
    if nonempty:
        result["minItems"] = 1
    return result


def _repair_obligations(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    original = payload.get("input")
    if not isinstance(original, Mapping):
        return []
    values = original.get("obligations")
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, Mapping) and item.get("status", "active") == "active"]


def group_cache_identity_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return the semantic cache identity, excluding discovery-only observations.

    ``repository_path_context`` helps the worker select existing files but has
    no normative authority. Including its current-worktree hashes made V3
    cache reuse depend on unrelated compiler/test edits. Schema-repair wrappers
    likewise carry diagnostics, not new frozen semantics, so their nested
    input shares the same identity as the original V3 request.
    """
    nested = payload.get("input")
    semantic = nested if isinstance(nested, Mapping) else payload
    return {
        **{"projection_contract": "vdd-v3-path-grounding-v2"},
        **{str(key): value for key, value in semantic.items()
           if key != "repository_path_context"},
    }


def _obligation_refs(payload: Mapping[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for item in _repair_obligations(payload):
        oid = item.get("obligation_id")
        refs = item.get("source_refs")
        if isinstance(oid, str) and oid and isinstance(refs, list):
            result[oid] = sorted({str(ref) for ref in refs if isinstance(ref, str) and ref})
    return result


def _narrow_repair_payload(payload: Mapping[str, Any], obligation_ids: list[str]) -> dict[str, Any]:
    """Keep a worker request bounded without changing its frozen source domain."""
    original = payload.get("input")
    if not isinstance(original, Mapping):
        raise ValueError("V3 group repair has no frozen input")
    source = dict(original)
    values = source.get("obligations")
    wanted = set(obligation_ids)
    if not isinstance(values, list) or not wanted:
        raise ValueError("V3 group repair has no active frozen obligations")
    narrowed = [
        dict(item)
        for item in values
        if isinstance(item, Mapping) and item.get("obligation_id") in wanted
    ]
    found = {
        str(item.get("obligation_id"))
        for item in narrowed
        if isinstance(item.get("obligation_id"), str)
    }
    if found != wanted:
        raise ValueError("V3 group repair chunk differs from frozen obligations")
    source["obligations"] = narrowed
    refs = {
        ref
        for item in narrowed
        for ref in item.get("source_refs", [])
        if isinstance(ref, str) and ref
    }
    contracts = source.get("source_contracts")
    if isinstance(contracts, list):
        source["source_contracts"] = [
            dict(item)
            for item in contracts
            if isinstance(item, Mapping) and item.get("source_ref") in refs
        ]
    contexts = source.get("execution_context_sources")
    if isinstance(contexts, list):
        paths = {item.get("repository_relative_source_path")
                 for item in source.get("source_contracts", []) if isinstance(item, Mapping)}
        source["execution_context_sources"] = [
            dict(item) for item in contexts
            if isinstance(item, Mapping) and item.get("repository_relative_source_path") in paths
        ]
    return {
        "original_stage": "v3",
        "input": source,
        "validator_findings": [
            "v3 chunked repair: return contracts only for the supplied frozen obligations"
        ],
    }


def _repair_chunks(payload: Mapping[str, Any]) -> list[list[str]]:
    ids = sorted(_obligation_refs(payload))
    if not ids:
        raise ValueError("V3 group repair has no active frozen obligations")
    return [ids[index:index + _MAX_CONTRACTS_PER_WORKER]
            for index in range(0, len(ids), _MAX_CONTRACTS_PER_WORKER)]


def _reusable_prior_contracts(
    *, root: Path, cache_dir: Path, payload: Mapping[str, Any], ids: list[str],
    prefer_recent: bool = False,
) -> dict[str, Any]:
    """Recover usable per-obligation contracts across changed group payloads.

    ADR-0041: chunk labels are positional presentation only.  A changed full V3 domain
    may move a still-valid obligation into a new group and therefore produce a
    different group-cache key.  Reuse the individual contract when its own
    current execution snapshot is usable; only missing/unusable obligations
    may cause a fresh worker request.
    """
    wanted = set(ids)
    obligations = {
        str(item.get("obligation_id")): item
        for item in _repair_obligations(payload)
        if isinstance(item.get("obligation_id"), str)
    }
    recovered: dict[str, Any] = {}
    # A prior request may have produced either a bounded child cache or a
    # complete parent cache.  Both contain independently reusable contracts;
    # restricting recovery to ``chunk-*`` would re-run an already completed
    # obligation when a later request changes the split shape.
    paths = list(cache_dir.glob(_GROUP_STAGE + "-*.json"))
    def repair_candidate_order(path):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            contracts = raw.get("obligation_contracts", {})
            size = len(contracts) if isinstance(contracts, Mapping) and contracts else sys.maxsize
        except (OSError, UnicodeError, ValueError, AttributeError):
            size = sys.maxsize
        return (size != 1, -path.stat().st_mtime_ns, path.name)
    # Replayed broad children may have newer filesystem times than completed
    # singleton repairs. Prefer the more specific candidate before recency.
    paths = sorted(paths, key=repair_candidate_order)
    exact_ids = set()
    for path in paths:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            values = value.get("obligation_contracts", {}) if isinstance(value, Mapping) else {}
            if isinstance(values, Mapping):
                exact_ids.update(values)
        except (OSError, UnicodeError, ValueError):
            continue
    for path in paths:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            contracts = raw.get("obligation_contracts") if isinstance(raw, Mapping) else None
            if not isinstance(contracts, Mapping):
                continue
            remaining = sorted(wanted - set(recovered))
            for oid in remaining:
                contract = contracts.get(oid)
                matched_oid = oid if isinstance(contract, Mapping) else None
                if matched_oid is None and (prefer_recent or oid in exact_ids):
                    # Parent collision recovery has stable frozen IDs. A
                    # loosely matching peer must not mask a later exact repair.
                    continue
                if matched_oid is None:
                    candidates = [
                        (old_oid, value) for old_oid, value in contracts.items()
                        if isinstance(value, Mapping)
                        and _contract_matches_obligation(value, obligations[oid])
                    ]
                    if len(candidates) == 1:
                        matched_oid, contract = candidates[0]
                    else:
                        continue
                if not isinstance(contract, Mapping):
                    continue
                single_payload = _narrow_repair_payload(payload, [oid])
                rebound = _rebind_contract(contract, oid, _obligation_refs(single_payload)[oid])
                single = {"obligation_contracts": rebound}
                projected = _project_execution_output(root, single_payload, single)
                if not _cache_requires_refresh(projected, root, single_payload):
                    recovered[oid] = rebound[oid]
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            continue
    return recovered


def _reusable_prior_complete_contracts(
    *, root: Path, cache_dir: Path, payload: Mapping[str, Any], ids: list[str],
) -> dict[str, Any] | None:
    """Reuse an exact complete V3 candidate before recomposing positional chunks.

    A transport timeout has no semantic meaning. If an earlier complete inline
    candidate still projects against every current frozen obligation and its
    execution snapshots remain usable, preserving it prevents an unrelated
    retry from changing deterministic Acceptance identities and invalidating
    all V4 source partitions.
    """
    wanted = set(ids)
    obligations = {
        str(item.get("obligation_id")): item
        for item in _repair_obligations(payload)
        if isinstance(item.get("obligation_id"), str)
    }
    candidates = sorted(
        (path for path in cache_dir.glob(_GROUP_STAGE + "-*.json") if "-chunk-" not in path.name),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            contracts = raw.get("obligation_contracts") if isinstance(raw, Mapping) else None
            if not isinstance(contracts, Mapping):
                continue
            rebound_contracts: dict[str, Any] = {}
            if set(contracts) == wanted:
                rebound_contracts = dict(contracts)
            else:
                for oid in sorted(wanted):
                    candidates = [
                        value for value in contracts.values()
                        if isinstance(value, Mapping)
                        and _contract_matches_obligation(value, obligations[oid])
                    ]
                    if len(candidates) != 1:
                        rebound_contracts = {}
                        break
                    rebound_contracts.update(_rebind_contract(candidates[0], oid, _obligation_refs(payload)[oid]))
            if set(rebound_contracts) != wanted:
                continue
            candidate = {"obligation_contracts": rebound_contracts}
            projected = _project_execution_output(root, payload, candidate)
            if (not _cache_requires_refresh(projected, root, payload)
                    and not _invalid_contract_ids(payload, rebound_contracts)):
                return candidate
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            continue
    return None


def _group_schema(payload: Mapping[str, Any]) -> dict[str, Any]:
    obligations = _repair_obligations(payload)
    known_ids = sorted({
        str(item["obligation_id"])
        for item in obligations
        if isinstance(item.get("obligation_id"), str) and item.get("obligation_id")
    })
    source_refs = sorted({
        str(ref)
        for item in obligations
        for ref in item.get("source_refs", [])
        if isinstance(ref, str) and ref
    })
    acceptance = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "source_refs": _string_array(nonempty=True, enum=source_refs or None),
            "given": {"type": "string", "minLength": 1},
            "when": {"type": "string", "minLength": 1},
            "then": {"type": "string", "minLength": 1},
            "oracle": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "observable": {"type": "string", "minLength": 1},
                    "expected": {"type": "string", "minLength": 1},
                    "forbidden": _string_array(),
                },
                "required": ["observable", "expected", "forbidden"],
            },
            "assertion_ids": _string_array(nonempty=True),
        },
        "required": ["source_refs", "given", "when", "then", "oracle", "assertion_ids"],
    }
    failure = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "failure_family": {"type": "string", "enum": sorted(sc.FAILURE_FAMILIES)},
            "selector_intent": {"type": "string", "minLength": 1},
            "expected_outcome": {"type": "string", "enum": ["fail"]},
            "failure_id": {"type": "string", "minLength": 1},
        },
        "required": ["failure_family", "selector_intent", "expected_outcome", "failure_id"],
    }
    slice_hint = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "production_owners": _string_array(nonempty=True),
            "verification_lane": {"type": "string", "enum": sorted(sc.LANES)},
            "behavior_change": {"type": "string", "minLength": 1},
            "affected_subjects": _string_array(nonempty=True),
            "state_transition": {"type": "string", "minLength": 1},
            "rollback_scope": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "production_paths": _string_array(nonempty=True),
                    "state_or_schema_compatibility": {"type": "string", "minLength": 1},
                },
                "required": ["production_paths", "state_or_schema_compatibility"],
            },
            "allowed_write_paths": _string_array(),
            "execution_snapshot_paths": _string_array(nonempty=True),
            "planned_new_files": _string_array(),
            "terminal_predicate": {"type": "string", "minLength": 1},
            "forbidden_paths": _string_array(),
            "validation_commands": {
                "type": "array", "minItems": 1,
                "items": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
            },
        },
        "required": [
            "production_owners", "verification_lane", "behavior_change", "affected_subjects",
            "state_transition", "rollback_scope", "allowed_write_paths", "execution_snapshot_paths",
            "planned_new_files", "terminal_predicate", "forbidden_paths", "validation_commands",
        ],
    }
    contract = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "acceptance": acceptance,
            "failure_intents": {"type": "array", "minItems": 1, "items": failure},
            "slice_hint": slice_hint,
        },
        "required": ["acceptance", "failure_intents", "slice_hint"],
    }
    contracts = {
        "type": "object", "additionalProperties": False,
        "properties": {oid: contract for oid in known_ids},
        "required": known_ids,
    }
    return {
        "type": "object", "additionalProperties": False,
        "properties": {
            "obligation_contracts": contracts,
        },
        "required": ["obligation_contracts"],
    }


def _group_body(raw: Mapping[str, Any], index: int) -> tuple[Mapping[str, Any], list[Any], Mapping[str, Any]]:
    acceptance = raw.get("acceptance")
    group_failures = raw.get("failure_intents")
    hint = raw.get("slice_hint")
    if not isinstance(acceptance, Mapping) or not isinstance(group_failures, list) or not group_failures or not isinstance(hint, Mapping):
        raise ValueError(f"V3 group repair group {index} is incomplete")
    return acceptance, group_failures, hint


def _append_atomic(
    *,
    oid: str,
    acceptance: Mapping[str, Any],
    group_failures: list[Any],
    hint: Mapping[str, Any],
    group_index: int,
    refs_by_oid: Mapping[str, list[str]] | None,
    acceptances: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    hints: list[dict[str, Any]],
) -> None:
    atomic_acceptance = dict(acceptance)
    if refs_by_oid is not None and oid in refs_by_oid:
        atomic_acceptance["source_refs"] = list(refs_by_oid[oid])
    acceptances.append({**atomic_acceptance, "obligation_ids": [oid]})
    hints.append({**dict(hint), "obligation_ids": [oid]})
    for failure in group_failures:
        if not isinstance(failure, Mapping):
            raise ValueError(f"V3 group repair failure in group {group_index} is not object")
        failures.append({**dict(failure), "obligation_ids": [oid]})


def _project_exact_assignments(
    value: Mapping[str, Any],
    groups: list[Any],
    *,
    refs_by_oid: Mapping[str, list[str]] | None,
) -> dict[str, Any]:
    raw_assignments = value.get("obligation_group_assignments")
    if not isinstance(raw_assignments, Mapping) or not raw_assignments:
        raise ValueError("V3 group repair assignments must be a non-empty object")
    if any(
        not isinstance(oid, str) or not oid.strip()
        or not isinstance(group_id, str) or not group_id.strip()
        for oid, group_id in raw_assignments.items()
    ):
        raise ValueError("V3 group repair assignments must map non-empty obligation IDs to non-empty group IDs")
    assignments = {
        str(oid).strip(): str(group_id).strip()
        for oid, group_id in raw_assignments.items()
    }
    if len(assignments) != len(raw_assignments):
        raise ValueError("V3 group repair assignments contain normalized duplicate obligation IDs")

    if refs_by_oid is not None:
        expected = set(refs_by_oid)
        actual = set(assignments)
        if actual != expected:
            details = []
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            if missing:
                details.append("missing=" + ",".join(missing))
            if extra:
                details.append("unknown=" + ",".join(extra))
            raise ValueError("V3 group repair assignments differ from frozen obligations: " + ";".join(details))

    contracts = value.get("obligation_contracts")
    if "obligation_contracts" in value and (
        not isinstance(contracts, Mapping) or set(contracts) != set(assignments)
    ):
        raise ValueError("V3 repair contracts must exactly cover assigned obligations")

    group_by_id: dict[str, tuple[int, Mapping[str, Any], list[Any], Mapping[str, Any]]] = {}
    for index, raw in enumerate(groups):
        if not isinstance(raw, Mapping):
            raise ValueError(f"V3 group repair group {index} is not object")
        group_id = raw.get("group_id")
        if not isinstance(group_id, str) or not group_id.strip():
            raise ValueError(f"V3 group repair group {index} has invalid group_id")
        normalized_group_id = group_id.strip()
        if normalized_group_id in group_by_id:
            raise ValueError(f"V3 group repair duplicate group_id: {normalized_group_id}")
        if contracts is None:
            acceptance, group_failures, hint = _group_body(raw, index)
        else:
            hint = raw.get("slice_hint")
            if not isinstance(hint, Mapping):
                raise ValueError(f"V3 repair group {index} has no implementation context")
            if "acceptance" in raw or "failure_intents" in raw:
                raise ValueError("V3 shared contexts cannot contain verification contracts")
            acceptance, group_failures = {}, []
        group_by_id[normalized_group_id] = (index, acceptance, group_failures, hint)

    unknown_groups = sorted(set(assignments.values()) - set(group_by_id))
    if unknown_groups:
        raise ValueError("V3 group repair assignments reference unknown groups: " + ",".join(unknown_groups))
    unused_groups = sorted(set(group_by_id) - set(assignments.values()))
    if unused_groups:
        raise ValueError("V3 group repair contains unused groups: " + ",".join(unused_groups))
    invalid_representatives = sorted(
        group_id
        for group_id in group_by_id
        if assignments.get(group_id) != group_id
    )
    if invalid_representatives:
        raise ValueError(
            "V3 group repair group IDs must represent obligations assigned to themselves: "
            + ",".join(invalid_representatives)
        )

    acceptances: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    hints: list[dict[str, Any]] = []
    for oid in sorted(assignments):
        group_index, acceptance, group_failures, hint = group_by_id[assignments[oid]]
        if contracts is not None:
            raw_contract = contracts[oid]
            if not isinstance(raw_contract, Mapping):
                raise ValueError(f"V3 repair contract {oid} is not object")
            acceptance, group_failures, _ = _group_body({**raw_contract, "slice_hint": hint}, group_index)
        elif list(assignments.values()).count(assignments[oid]) != 1:
            raise ValueError("V3 shared group requires per-obligation contracts; legacy oracle cloning is forbidden")
        _append_atomic(
            oid=oid,
            acceptance=acceptance,
            group_failures=group_failures,
            hint=hint,
            group_index=group_index,
            refs_by_oid=refs_by_oid,
            acceptances=acceptances,
            failures=failures,
            hints=hints,
        )
    return {"acceptances": acceptances, "failure_intents": failures, "slice_hints": hints}


def _project_legacy_groups(
    groups: list[Any],
    *,
    refs_by_oid: Mapping[str, list[str]] | None,
) -> dict[str, Any]:
    acceptances: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    hints: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(groups):
        if not isinstance(raw, Mapping):
            raise ValueError(f"V3 group repair group {index} is not object")
        ids = raw.get("obligation_ids")
        if not isinstance(ids, list) or not ids or any(not isinstance(x, str) or not x.strip() for x in ids):
            raise ValueError(f"V3 group repair group {index} has invalid obligation_ids")
        normalized_values = [str(x).strip() for x in ids]
        normalized_ids = sorted(set(normalized_values))
        if len(normalized_ids) != len(normalized_values):
            raise ValueError(f"V3 group repair group {index} has duplicate obligation_ids")
        duplicates = seen & set(normalized_ids)
        if duplicates:
            raise ValueError("V3 group repair obligation appears in multiple groups: " + ",".join(sorted(duplicates)))
        seen.update(normalized_ids)
        acceptance, group_failures, hint = _group_body(raw, index)
        if len(normalized_ids) != 1:
            raise ValueError("V3 shared group requires per-obligation contracts; legacy oracle cloning is forbidden")
        for oid in normalized_ids:
            _append_atomic(
                oid=oid,
                acceptance=acceptance,
                group_failures=group_failures,
                hint=hint,
                group_index=index,
                refs_by_oid=refs_by_oid,
                acceptances=acceptances,
                failures=failures,
                hints=hints,
            )
    return {"acceptances": acceptances, "failure_intents": failures, "slice_hints": hints}


def _project_inline_contracts(
    value: Mapping[str, Any], *, refs_by_oid: Mapping[str, list[str]] | None,
) -> dict[str, Any]:
    """Bind exact frozen keys without asking the worker to maintain group joins."""
    if set(value) != {"obligation_contracts"}:
        raise ValueError("V3 inline repair must contain only obligation_contracts")
    contracts = value.get("obligation_contracts")
    if not isinstance(contracts, Mapping) or not contracts:
        raise ValueError("V3 inline repair contracts must be a non-empty object")
    if any(not isinstance(oid, str) or not oid or oid != oid.strip() for oid in contracts):
        raise ValueError("V3 inline repair requires exact non-empty obligation IDs")
    if refs_by_oid is not None and set(contracts) != set(refs_by_oid):
        raise ValueError("V3 inline repair contracts differ from frozen obligations")
    acceptances: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    hints: list[dict[str, Any]] = []
    for index, oid in enumerate(sorted(contracts)):
        raw = contracts[oid]
        if not isinstance(raw, Mapping) or set(raw) != {"acceptance", "failure_intents", "slice_hint"}:
            raise ValueError(f"V3 inline repair contract {oid} requires proof and execution context")
        acceptance, group_failures, hint = _group_body(raw, index)
        _append_atomic(
            oid=oid, acceptance=acceptance, group_failures=group_failures, hint=hint,
            group_index=index, refs_by_oid=refs_by_oid,
            acceptances=acceptances, failures=failures, hints=hints,
        )
    return {"acceptances": acceptances, "failure_intents": failures, "slice_hints": hints}


def _project(value: Mapping[str, Any], *, refs_by_oid: Mapping[str, list[str]] | None = None) -> dict[str, Any]:
    if "obligation_contracts" in value and "groups" not in value:
        return _project_inline_contracts(value, refs_by_oid=refs_by_oid)
    groups = value.get("groups")
    if not isinstance(groups, list) or not groups:
        raise ValueError("V3 group repair must return non-empty groups")
    if "obligation_group_assignments" in value:
        return _project_exact_assignments(value, groups, refs_by_oid=refs_by_oid)
    return _project_legacy_groups(groups, refs_by_oid=refs_by_oid)


def _trace_summary(trace: str) -> str:
    text = trace.strip()
    return text if len(text) <= 2600 else text[:300] + "\n...<trace elided>...\n" + text[-2200:]


def _project_current_output(value: Mapping[str, Any], refs_by_oid: Mapping[str, list[str]]) -> dict[str, Any]:
    # A composed transport may call this guard after the inline wire has
    # already been projected into the compiler's normalized result shape.
    # Preserve that deterministic internal form; legacy group wire remains
    # rejected below and worker/cache boundaries still require inline keys.
    if set(value) == {"acceptances", "failure_intents", "slice_hints"}:
        return dict(value)
    if set(value) != {"obligation_contracts"}:
        raise ValueError("V3 current repair output requires inline obligation_contracts")
    # Keep the installed owner/write-set projection wrapper on the live path.
    return _project(value, refs_by_oid=refs_by_oid)


def _ground_group_result(root: Path, payload: Mapping[str, Any], value: Mapping[str, Any]) -> Mapping[str, Any]:
    """Apply finite stale-path projection after group aggregation."""
    source = payload.get("input")
    if not isinstance(source, Mapping):
        source = payload
    grounded, _changes = ground_v3_paths(Path(root), source, value)
    # Import at invocation time: the execution wrapper installs after this
    # projection module. Cache admission must inspect the same canonical hint
    # fields that the final execution-contract gate will receive.
    from semantic_worker_v3_execution_contract_patch import _normalize_production_write_sets
    return _normalize_production_write_sets(Path(root), grounded)


def _project_execution_output(root: Path, payload: Mapping[str, Any], value: Mapping[str, Any]) -> Mapping[str, Any]:
    """Project one exact wire domain and normalize it before cache admission."""
    return _ground_group_result(root, payload, _project_current_output(value, _obligation_refs(payload)))


class InvalidBoundV3Cache(ValueError):
    """A malformed exact request cache must not be bypassed by decomposition."""


def _conflicting_oracle_peers(value: Mapping[str, Any], oid: str) -> dict[str, Any]:
    """ADR-0041: bound repair context to the exact clone relation being repaired."""
    acceptances = value.get("acceptances", [])
    target = next((item for item in acceptances
                   if isinstance(item, Mapping) and item.get("obligation_ids") == [oid]), None)
    if target is None:
        return {}
    def oracle_key(item):
        return sc.sha256_value({"oracle": item.get("oracle"),
                                "assertions": sorted(item.get("assertion_ids", []))})
    target_key = oracle_key(target)
    return {
        item["obligation_ids"][0]: {
            "oracle": item.get("oracle"), "assertion_ids": item.get("assertion_ids"),
        }
        for item in acceptances
        if isinstance(item, Mapping) and isinstance(item.get("obligation_ids"), list)
        and len(item["obligation_ids"]) == 1 and item["obligation_ids"][0] != oid
        and oracle_key(item) == target_key
    }


def _live_group_repair(
    *, root: Path, out_dir: Path, payload: Mapping[str, Any], prompt: str,
    max_obligations: int | None = None,
) -> Mapping[str, Any]:
    obligations = _repair_obligations(payload)
    limit = max_obligations or _MAX_OBLIGATIONS_PER_CALL
    if len(obligations) > limit:
        combined = {"acceptances": [], "failure_intents": [], "slice_hints": []}
        original = payload.get("input")
        if not isinstance(original, Mapping):
            raise ValueError("V3 repair input is missing")
        chunks = []
        for offset in range(0, len(obligations), limit):
            chunk = obligations[offset:offset + limit]
            chunk_payload = dict(payload)
            chunk_payload["_repair_domain_ids"] = payload.get("_repair_domain_ids") or [item["obligation_id"] for item in obligations]
            chunk_payload["input"] = {**original, "obligations": chunk}
            chunks.append((chunk, chunk_payload))

        def compile_chunk(item):
            chunk, chunk_payload = item
            try:
                return _live_group_repair_one(
                    root=root, out_dir=out_dir, payload=chunk_payload, prompt=prompt,
                    max_attempts=_BEFORE_SPLIT_TRANSIENT_ATTEMPTS if len(chunk) > 1 else None,
                )
            except (TransientV3WorkerFailure, ValueError) as exc:
                if isinstance(exc, InvalidBoundV3Cache):
                    raise
                emit(out_dir, "V3-group-repair", "repair-rejected",
                     sc._worker_cache_key(_GROUP_STAGE, group_cache_identity_payload(chunk_payload)),
                     obligation_ids=[item["obligation_id"] for item in chunk],
                     error_type=type(exc).__name__, reason=str(exc))
                if len(chunk) == 1:
                    raise
                return _live_group_repair(
                    root=root, out_dir=out_dir, payload=chunk_payload, prompt=prompt,
                    max_obligations=max(1, len(chunk) // 2),
                )

        with ThreadPoolExecutor(max_workers=min(4, len(chunks))) as executor:
            projected_chunks = list(executor.map(compile_chunk, chunks))
        for projected in projected_chunks:
            for key in combined:
                values = projected.get(key)
                if not isinstance(values, list):
                    raise ValueError(f"V3 chunk output is missing {key}")
                combined[key].extend(values)
        combined = _ground_group_result(root, payload, combined)
        # ADR-0041: positional children can retain old peer collisions after
        # singleton repairs succeeded. Recompose those existing candidates
        # before requesting them again; recency selects candidates, while the
        # complete current schema, paths and semantic domain decide admission.
        if v3_domain._domain_findings("v3-schema-repair", payload, combined):
            ids = sorted(_obligation_refs(payload))
            recovered = _reusable_prior_contracts(
                root=root, cache_dir=out_dir / ".compiler-cache", payload=payload,
                ids=ids, prefer_recent=True)
            if set(recovered) == set(ids):
                candidate = _project_execution_output(root, payload, {"obligation_contracts": recovered})
                candidate_findings = v3_domain._domain_findings("v3-schema-repair", payload, candidate)
                prior_findings = v3_domain._domain_findings("v3-schema-repair", payload, combined)
                if (not _cache_requires_refresh(candidate, root, payload)
                        and (not _invalid_contract_ids(payload, recovered)
                             or len(candidate_findings) < len(prior_findings))):
                    combined = candidate
                else:
                    emit(out_dir, "V3-group-repair", "cache-recomposition-rejected", "parent",
                         invalid_ids=sorted(_invalid_contract_ids(payload, recovered)),
                         schema_findings=gate._worker_schema_findings("v3", candidate),
                         domain_findings=v3_domain._domain_findings("v3-schema-repair", payload, candidate))
        # The parent merge is the first point where contracts from different
        # worker chunks can be compared. Repair only cross-chunk cloned oracles
        # here; child caches and all valid contracts remain reusable.
        for repair_round in range(1, 4):
            findings = v3_domain._domain_findings("v3-schema-repair", payload, combined)
            invalid = {
                oid for finding in findings
                if "cloned-oracle-across-obligations:" in finding
                for oid in re.findall(r"O-[0-9A-F]+", finding)
            }
            if not invalid:
                break
            for oid in sorted(invalid):
                source = payload.get("input")
                if not isinstance(source, Mapping):
                    raise ValueError("V3 repair input is missing")
                single_source = dict(source)
                single_source["relational_repair_round"] = repair_round
                single_payload = {
                    **payload,
                    "_force_semantic_repair": True,
                    "input": {
                        **single_source,
                        "obligations": [
                            item for item in source.get("obligations", [])
                            if isinstance(item, Mapping) and item.get("obligation_id") == oid
                        ],
                    },
                }
                peer_summary = _conflicting_oracle_peers(combined, oid)
                repaired = _live_group_repair_one(
                    root=root, out_dir=out_dir, payload=single_payload,
                    prompt=(prompt + "\n\nORACLE UNIQUENESS CONSTRAINT: author an oracle and assertion set "
                            "specific to this obligation; do not copy any existing peer summary.\n"
                            + json.dumps(peer_summary, ensure_ascii=False, sort_keys=True)),
                )
                for key in ("acceptances", "failure_intents", "slice_hints"):
                    combined[key] = [
                        item for item in combined[key]
                        if not (isinstance(item, Mapping)
                                and item.get("obligation_ids") == [oid])
                    ]
                    combined[key].extend(
                        item for item in repaired.get(key, [])
                        if isinstance(item, Mapping)
                    )
        return combined

    if len(obligations) > 1:
        try:
            return _ground_group_result(
                root,
                payload,
                _live_group_repair_one(
                    root=root, out_dir=out_dir, payload=payload, prompt=prompt,
                    max_attempts=_BEFORE_SPLIT_TRANSIENT_ATTEMPTS,
                ),
            )
        except (TransientV3WorkerFailure, ValueError) as exc:
            if isinstance(exc, InvalidBoundV3Cache):
                raise
            emit(out_dir, "V3-group-repair", "repair-rejected",
                 sc._worker_cache_key(_GROUP_STAGE, group_cache_identity_payload(payload)),
                 obligation_ids=[item["obligation_id"] for item in obligations],
                 error_type=type(exc).__name__, reason=str(exc))
            return _live_group_repair(
                root=root, out_dir=out_dir, payload=payload, prompt=prompt,
                max_obligations=max(1, len(obligations) // 2),
            )
    return _live_group_repair_one(root=root, out_dir=out_dir, payload=payload, prompt=prompt)


def _cached_group_result(*, root: Path, out_dir: Path, payload: Mapping[str, Any]):
    """ADR-0041: reuse only an exact input after current contract validation."""
    path = out_dir / ".compiler-cache" / sc._worker_cache_key(
        _GROUP_STAGE, group_cache_identity_payload(payload))
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            return None
        projected = _ground_group_result(
            root, payload, _project_current_output(raw, _obligation_refs(payload)))
        contracts = raw.get("obligation_contracts")
        if (_cache_requires_refresh(projected, root, payload)
                or (isinstance(contracts, Mapping) and _invalid_contract_ids(payload, contracts))
                or v3_domain._domain_findings("v3-schema-repair", payload, projected)):
            return None
        return projected
    except (OSError, ValueError):
        return None


def _cached_split_result(*, root: Path, out_dir: Path, payload: Mapping[str, Any]):
    """Replay the existing deterministic split tree without retrying its parent.

    Cache files remain the only storage; no new receipt format or history scan.
    An incomplete split is not a completed judgment.
    """
    cached = _cached_group_result(root=root, out_dir=out_dir, payload=payload)
    if cached is not None:
        return cached
    obligations = _repair_obligations(payload)
    if len(obligations) <= 1:
        return None
    limit = max(1, len(obligations) // 2)
    combined = {"acceptances": [], "failure_intents": [], "slice_hints": []}
    for offset in range(0, len(obligations), limit):
        child = {**payload, "input": {**payload["input"],
                 "obligations": obligations[offset:offset + limit]}}
        result = _cached_split_result(root=root, out_dir=out_dir, payload=child)
        if result is None:
            return None
        for key in combined:
            combined[key].extend(result[key])
    combined = _ground_group_result(root, payload, combined)
    if v3_domain._domain_findings("v3-schema-repair", payload, combined):
        return None
    return combined


def _live_group_repair_one(
    *, root: Path, out_dir: Path, payload: Mapping[str, Any], prompt: str,
    max_attempts: int | None = None,
) -> Mapping[str, Any]:
    force_semantic_repair = bool(payload.get("_force_semantic_repair"))

    # Cache hits need current path/domain checks, but not model discovery context
    # or backend initialization. Successful child caches also survive a restart.
    cached = None if force_semantic_repair else _cached_split_result(
        root=root, out_dir=out_dir, payload=payload)
    if cached is not None:
        return cached
    payload = enrich_repository_context(root, payload)
    prompt += PATH_CONTEXT_PROMPT
    scripts = root / "scripts" / "sc"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    try:
        from _llm_backend import run_llm_exec, resolve_llm_backend
    except ImportError as exc:
        raise RuntimeError("shared LLM backend is unavailable") from exc

    cache_dir = out_dir / ".compiler-cache"
    cache_identity = group_cache_identity_payload(payload)
    call_suffix = sc._worker_cache_key(_GROUP_STAGE, cache_identity).rsplit("-", 1)[-1].removesuffix(".json")
    cache_path = cache_dir / sc._worker_cache_key(_GROUP_STAGE, cache_identity)
    refs_by_oid = _obligation_refs(payload)
    if cache_path.is_file() and not force_semantic_repair:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if not isinstance(cached, Mapping):
            raise ValueError("V3 group repair cache is malformed")
        projected = _project_execution_output(root, payload, cached)
        contracts = cached.get("obligation_contracts")
        if (isinstance(contracts, Mapping)
                and not _cache_requires_refresh(projected, root, payload)
                and not _invalid_contract_ids(payload, contracts)):
            return projected

    if not force_semantic_repair:
        # An exact request cache is a bound response, unlike unrelated history.
        # Validate its complete ID domain before prior-candidate recovery can
        # narrow it and silently hide a malformed foreign contract (ADR-0041).
        for index, ids in enumerate(_repair_chunks(payload), start=1):
            child_payload = _narrow_repair_payload(payload, ids)
            child_path = cache_dir / sc._worker_cache_key(
                f"{_GROUP_STAGE}-chunk-{index:02d}", child_payload)
            if child_path.is_file():
                raw = json.loads(child_path.read_text(encoding="utf-8"))
                try:
                    _project_current_output(raw, _obligation_refs(child_payload))
                except ValueError as exc:
                    raise InvalidBoundV3Cache(str(exc)) from exc

    complete = None if force_semantic_repair else _reusable_prior_complete_contracts(
        root=root, cache_dir=cache_dir, payload=payload, ids=sorted(refs_by_oid))
    if complete is not None:
        _write_refreshable_json(cache_path, complete)
        return _project_execution_output(root, payload, complete)

    # ADR-0041: recover child caches through the exact request keys below.
    # Directory-wide scans mix unrelated historical domains and can admit a
    # stale same-ID contract or reject an unrelated cache as a foreign response.
    if not force_semantic_repair:
        wanted = set(refs_by_oid)
        recomposed: dict[str, Any] = {}
        for child_path in sorted(cache_dir.glob(_GROUP_STAGE + "-chunk-*.json")):
            try:
                child = json.loads(child_path.read_text(encoding="utf-8"))
                contracts = child.get("obligation_contracts") if isinstance(child, Mapping) else None
                if not isinstance(contracts, Mapping) or not contracts or not set(contracts) <= wanted:
                    continue
                child_payload = _narrow_repair_payload(payload, sorted(contracts))
                child_stage = child_path.name.rsplit("-", 1)[0]
                if child_path.name != sc._worker_cache_key(child_stage, child_payload):
                    continue
                projected = _project_execution_output(root, child_payload, child)
                if (_cache_requires_refresh(projected, root, child_payload)
                        or _invalid_contract_ids(child_payload, contracts)
                        or v3_domain._domain_findings("v3-schema-repair", child_payload, projected)):
                    continue
                recomposed.update(contracts)
            except (OSError, UnicodeError, ValueError):
                continue
        if set(recomposed) == wanted:
            composed = {"obligation_contracts": recomposed}
            projected = _project_execution_output(root, payload, composed)
            if not v3_domain._domain_findings("v3-schema-repair", payload, projected):
                _write_refreshable_json(cache_path, composed)
                return projected

    grouped_prompt = (
        prompt
        + "\n\nV3 REPAIR OUTPUT CONTRACT: return only obligation_contracts{}. It must contain every "
        "supplied active obligation ID exactly once as a required key. Each value contains acceptance, "
        "failure_intents, and a complete slice_hint. Do not emit groups, group_id, or assignments. "
        "For compatible obligations, repeat the same real owner, lane, legal write boundary and selector "
        "context in their hints; do not invent different paths merely to distinguish atomic obligations. "
        "V6 owns grouping and dependency boundaries. Author the oracle, "
        "assertions and failure intents for THAT obligation, not the union of the group's behaviors. Do not copy "
        "one shared oracle across independent obligations. A boundary/structural constraint needs its own "
        "observable artifact and check, with the evaluation phase in when/oracle; a runtime result cannot prove "
        "a partition constraint. Do not assume the required result in given or claim future checks already ran. "
        "The compiler attaches frozen IDs and source refs; V4 independently judges semantic alignment. "
        "Verification contracts remain independent even when execution contexts match."

    )
    backend = resolve_llm_backend(None)
    def request_chunk(ids: list[str], label: str, rejected=None,
                      avoid_oracles: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Repair invalid cached contracts individually; retain valid peers."""
        chunk_payload = _narrow_repair_payload(payload, ids)
        chunk_stage = f"{_GROUP_STAGE}-chunk-{label}"
        chunk_cache = cache_dir / sc._worker_cache_key(chunk_stage, chunk_payload)
        if chunk_cache.is_file() and not force_semantic_repair:
            raw = json.loads(chunk_cache.read_text(encoding="utf-8"))
            projected = _project_execution_output(root, chunk_payload, raw)
            if not _cache_requires_refresh(projected, root, chunk_payload):
                return raw
            rejected = raw
        if len(ids) > 1 and isinstance(rejected, Mapping):
            contracts = rejected.get("obligation_contracts")
            if isinstance(contracts, Mapping):
                # ADR-0041: validate the complete frozen domain before narrowing;
                # never silently discard foreign or missing cached obligations.
                _project_execution_output(root, chunk_payload, rejected)
                repaired = {}
                for index, oid in enumerate(ids, start=1):
                    single = {"obligation_contracts": {oid: contracts[oid]}}
                    single_payload = _narrow_repair_payload(payload, [oid])
                    projected = _project_execution_output(root, single_payload, single)
                    if _cache_requires_refresh(projected, root, single_payload):
                        single = request_chunk([oid], f"{label}-{index}", rejected=single)
                    repaired.update(single["obligation_contracts"])
                raw = {"obligation_contracts": repaired}
                _project_execution_output(root, chunk_payload, raw)
                _write_refreshable_json(chunk_cache, raw)
                return raw
        # A prior grouped request may have timed out after each exact child was
        # successfully cached. Recompose that parent deterministically before
        # asking the worker again; child caches are validated against their own
        # frozen domains, so this is a cache replay, not a semantic shortcut.
        if len(ids) > 1:
            recovered: dict[str, Any] = {}
            for index, oid in enumerate(ids, start=1):
                child_payload = _narrow_repair_payload(payload, [oid])
                child_stage = f"{_GROUP_STAGE}-chunk-{label}-{index}"
                child_cache = cache_dir / sc._worker_cache_key(child_stage, child_payload)
                if not child_cache.is_file():
                    recovered = {}
                    break
                child = json.loads(child_cache.read_text(encoding="utf-8"))
                projected_child = _project_execution_output(root, child_payload, child)
                if _cache_requires_refresh(projected_child, root, child_payload):
                    recovered = {}
                    break
                recovered.update(child["obligation_contracts"])
            if len(recovered) == len(ids):
                raw = {"obligation_contracts": recovered}
                _project_execution_output(root, chunk_payload, raw)
                _write_refreshable_json(chunk_cache, raw)
                return raw
        output = out_dir / ".compiler-work" / f"{chunk_stage}-{call_suffix}-last-message.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        schema_path = transport._schema_path(out_dir, f"{chunk_stage}-{call_suffix}", _group_schema(chunk_payload))
        extra_args = ["--output-schema", str(schema_path)] if backend == "codex-cli" else []
        chunk_prompt = (grouped_prompt + "\n\nCHUNK BINDING: return contracts for these and only these frozen obligation IDs: "
                        + ",".join(ids))
        if isinstance(rejected, Mapping):
            rejected_projection = _project_execution_output(root, chunk_payload, rejected)
            schema_findings = gate._worker_schema_findings("v3", rejected_projection)
            if schema_findings:
                chunk_prompt += (
                    "\nREJECTED CONTRACT FIELDS: " + json.dumps(schema_findings)
                    + ". Supply source-supported values for the rejected fields; do not weaken the contract."
                )
            missing = sorted({
                path for hint in rejected_projection["slice_hints"]
                for path in hint.get("execution_snapshot_paths", [])
                if path not in hint.get("planned_new_files", []) and not (root / path).is_file()
            })
            if missing:
                chunk_prompt += (
                    "\nREJECTED SELECTOR TARGETS (absent and not planned): " + json.dumps(missing)
                    + ". Read the actual repository tests and select a semantically appropriate existing entry, "
                    "or declare an exact new test only when supported by the frozen source and write boundary. "
                    "Keep validation_commands and snapshot/planned/write fields consistent. Do not create placeholders, "
                    "weaken the oracle, or treat file presence as behavior evidence."
                )
        chunk_prompt += "\n\nINPUT:\n" + json.dumps(chunk_payload, ensure_ascii=False, sort_keys=True)
        if avoid_oracles:
            chunk_prompt += (
                "\n\nORACLE UNIQUENESS CONSTRAINT: the following existing obligation "
                "contracts are already in the merged repair. Author an obligation-specific "
                "oracle and assertion set for the requested ID; do not copy any listed oracle "
                "or assertion IDs.\nEXISTING CONTRACT SUMMARIES:\n"
                + json.dumps(avoid_oracles, ensure_ascii=False, sort_keys=True)
            )

        def run(extra: list[str]):
            return worker_call(run_llm_exec, progress_dir=out_dir, progress_stage=f"v3-schema-repair-chunk-{label}",
                backend=backend, root=root, prompt=chunk_prompt, output_last_message=output,
                timeout_sec=transport._REPAIR_TIMEOUT_SECONDS, codex_configs=['model_reasoning_effort="medium"'],
                codex_sandbox="read-only", codex_extra_args=[*transport.codex_worker_isolation_args(), *extra])

        attempts = min(max_attempts or transport._MAX_TRANSPORT_ATTEMPTS, 1 if len(ids) > 1 else transport._MAX_TRANSPORT_ATTEMPTS)
        traces: list[str] = []
        for attempt in range(1, attempts + 1):
            if output.exists():
                output.unlink()
            code, trace, _argv = run(extra_args)
            if code != 0 and extra_args and transport._unsupported_output_schema(trace):
                if output.exists():
                    output.unlink()
                code, trace, _argv = run([])
            if code == 0 and output.is_file():
                raw = sc._parse_json_output(output.read_text(encoding="utf-8"))
                contracts = raw.get("obligation_contracts") if isinstance(raw, Mapping) else None
                if isinstance(contracts, Mapping):
                    for contract in contracts.values():
                        if isinstance(contract, dict):
                            _declare_supported_missing_fixture(contract)
                _project_execution_output(root, chunk_payload, raw)
                _write_refreshable_json(chunk_cache, raw)
                return raw
            traces.append(f"attempt {attempt}: {_trace_summary(trace)}")
        if len(ids) > 1:
            # A timed-out grouped request has no semantic result. Re-request each
            # exact obligation independently, retaining all successful siblings.
            contracts: dict[str, Any] = {}
            for index, oid in enumerate(ids, start=1):
                child = request_chunk([oid], f"{label}-{index}")
                contracts.update(child["obligation_contracts"])
            return {"obligation_contracts": contracts}
        raise RuntimeError("semantic worker v3-schema-repair failed after " + str(attempts) + " attempts: " + "\n".join(traces))

    merged: dict[str, Any] = {}
    for chunk_index, ids in enumerate(_repair_chunks(payload), start=1):
        chunk_payload = _narrow_repair_payload(payload, ids)
        chunk_stage = f"{_GROUP_STAGE}-chunk-{chunk_index:02d}"
        chunk_cache = cache_dir / sc._worker_cache_key(chunk_stage, chunk_payload)
        if chunk_cache.is_file() and not force_semantic_repair:
            raw_chunk = json.loads(chunk_cache.read_text(encoding="utf-8"))
            projected_chunk = _project_execution_output(root, chunk_payload, raw_chunk)
            if _cache_requires_refresh(projected_chunk, root, chunk_payload):
                raw_chunk = request_chunk(ids, f"{chunk_index:02d}", rejected=raw_chunk)
        else:
            # The full group payload can change when a bounded V3 repair adds
            # unrelated obligations.  Reuse every individually executable
            # contract from prior groups before asking a worker for the actual
            # missing members.
            recovered = (
                {}
                if force_semantic_repair
                else _reusable_prior_contracts(root=root, cache_dir=cache_dir, payload=payload, ids=ids)
            )
            if recovered:
                for index, oid in enumerate(ids, start=1):
                    if oid not in recovered:
                        child = request_chunk([oid], f"{chunk_index:02d}-{index}")
                        recovered.update(child["obligation_contracts"])
                raw_chunk = {"obligation_contracts": recovered}
                _project_execution_output(root, chunk_payload, raw_chunk)
                _write_refreshable_json(chunk_cache, raw_chunk)
                contracts = raw_chunk["obligation_contracts"]
                overlap = set(merged) & set(contracts)
                if overlap:
                    raise ValueError("V3 group repair chunks duplicate frozen obligations: " + ",".join(sorted(overlap)))
                merged.update(contracts)
                continue
            output = out_dir / ".compiler-work" / f"{chunk_stage}-{call_suffix}-last-message.json"
            output.parent.mkdir(parents=True, exist_ok=True)
            if output.exists():
                output.unlink()
            schema_path = transport._schema_path(out_dir, f"{chunk_stage}-{call_suffix}", _group_schema(chunk_payload))
            extra_args = ["--output-schema", str(schema_path)] if backend == "codex-cli" else []
            chunk_prompt = (
                grouped_prompt
                + "\n\nCHUNK BINDING: return contracts for these and only these frozen obligation IDs: "
                + ",".join(ids)
                + "\n\nINPUT:\n" + json.dumps(chunk_payload, ensure_ascii=False, sort_keys=True)
            )
            def run(extra: list[str]):
                return worker_call(run_llm_exec, progress_dir=out_dir,
                    progress_stage=f"v3-schema-repair-chunk-{chunk_index:02d}",
                    backend=backend, root=root, prompt=chunk_prompt, output_last_message=output,
                    timeout_sec=transport._REPAIR_TIMEOUT_SECONDS,
                    codex_configs=['model_reasoning_effort="medium"'], codex_sandbox="read-only",
                    codex_extra_args=[*transport.codex_worker_isolation_args(), *extra],
                )

            raw_chunk = request_chunk(ids, f"{chunk_index:02d}")
        _project_execution_output(root, chunk_payload, raw_chunk)
        contracts = raw_chunk.get("obligation_contracts") if isinstance(raw_chunk, Mapping) else None
        if not isinstance(contracts, Mapping):
            raise ValueError("V3 group repair chunk has no obligation contracts")
        overlap = set(merged) & set(contracts)
        if overlap:
            raise ValueError("V3 group repair chunks duplicate frozen obligations: " + ",".join(sorted(overlap)))
        merged.update(contracts)
    # A usable selector snapshot is necessary but not sufficient. Historical
    # per-obligation contracts can still be semantically invalid only when
    # compared with their peers (for example a cloned oracle). Re-run only the
    # IDs named by the real V3 gate; all other cached contracts remain intact.
    remaining = _invalid_contract_ids(payload, merged)
    for repair_round in range(1, 4):
        if not remaining:
            break
        for batch_index, oid in enumerate(sorted(remaining), start=1):
            # A relational failure such as a cloned oracle is defined across
            # obligations. Re-request each named obligation independently and
            # show the current merged peers so the worker must author distinct
            # semantics. Cache labels are round-scoped to avoid replaying a
            # previously rejected clone.
            avoid: dict[str, Any] = {}
            for peer_oid, peer in merged.items():
                if peer_oid == oid or not isinstance(peer, Mapping):
                    continue
                acceptance = peer.get("acceptance")
                if isinstance(acceptance, Mapping):
                    avoid[peer_oid] = {
                        "oracle": acceptance.get("oracle"),
                        "assertion_ids": acceptance.get("assertion_ids"),
                    }
            repaired = request_chunk(
                [oid], f"semantic-v2-r{repair_round:02d}-{batch_index:02d}",
                avoid_oracles=avoid,
            )
            merged.update(repaired["obligation_contracts"])
        remaining = _invalid_contract_ids(payload, merged)
    if remaining:
        raise ValueError("V3 semantic cache repair remained invalid: " + ",".join(sorted(remaining)))
    raw = {"obligation_contracts": merged}
    _write_refreshable_json(cache_path, raw)
    projected = _project_execution_output(root, payload, raw)
    return _ground_group_result(root, payload, projected)


def group_repair_transport(*, root, out_dir, stage: str, payload: Mapping[str, Any], prompt: str, worker_cache: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    # Explicitly injected V3 fixtures are already frozen semantic inputs.  In
    # particular, the offline compiler replay tests intentionally provide a
    # complete large-domain V3 response whose snapshot paths belong to the
    # fixture and are not available in the temporary root.  Reuse that exact
    # response before entering the large-domain transport path; persisted
    # cache files still go through the normal refresh checks above.
    # A schema-repair retry is still a V3 transport boundary.  When a
    # caller supplies the complete frozen V3 response under the canonical
    # ``v3`` cache key, consume it for both the initial and schema-repair
    # stage.  Previously the retry-only stage skipped this branch and fell
    # through to the live worker even though the exact response was present.
    if stage in {"v3", "v3-schema-repair"} and isinstance(worker_cache, Mapping) and isinstance(worker_cache.get("v3"), Mapping):
        injected = worker_cache["v3"]
        if all(isinstance(injected.get(key), list) for key in ("acceptances", "failure_intents", "slice_hints")):
            projected = _project_current_output(injected, _obligation_refs(payload))
            findings = v3_domain._domain_findings(stage, payload, projected)
            if not findings:
                return projected
            if all("cloned-oracle-across-obligations:" in finding for finding in findings):
                injected = None
            else:
            # An explicitly supplied V3 fixture is authoritative for this
            # offline/repair run.  If it does not match the frozen payload,
            # fail closed instead of silently replacing it with a new model
            # request (which would defeat selective replay).
                raise ValueError("injected V3 cache failed frozen-domain validation: " + "; ".join(findings))
    # Do not repeatedly submit an all-obligation V3 payload after a bounded
    # source-gap repair. The initial V3 wire has the same per-obligation
    # contract as its schema-repair successor, so for a payload larger than a
    # safe worker chunk route directly through the exact-key chunk composer.
    # It retains each usable peer contract and requests only missing or proven
    # invalid obligations. Small V3 requests retain the normal direct path.
    is_large_initial_v3 = stage == "v3" and len([
        item for item in payload.get("obligations", [])
        if isinstance(item, Mapping) and item.get("status", "active") == "active"
    ]) > min(_MAX_CONTRACTS_PER_WORKER, _MAX_OBLIGATIONS_PER_CALL)
    if is_large_initial_v3:
        repair_payload = {
            "original_stage": "v3",
            "input": dict(payload),
            "validator_findings": [
                "v3 large-domain decomposition: retain usable obligation contracts and request only missing contracts"
            ],
        }
        value = _live_group_repair(root=Path(root), out_dir=Path(out_dir), payload=repair_payload, prompt=prompt)
        findings = v3_domain._domain_findings("v3", payload, value)
        if findings:
            raise ValueError("V3 frozen-domain validation failed: " + "; ".join(findings))
        return value
    if stage != "v3-schema-repair":
        return _BASE_DOMAIN_TRANSPORT(root=root, out_dir=out_dir, stage=stage, payload=payload, prompt=prompt, worker_cache=worker_cache)
    refs_by_oid = _obligation_refs(payload)
    if worker_cache and stage in worker_cache and isinstance(worker_cache[stage], Mapping):
        pre_findings = v3_domain._domain_findings(stage, payload, worker_cache[stage])
        if pre_findings:
            if all("cloned-oracle-across-obligations:" in finding for finding in pre_findings):
                value = _live_group_repair(root=Path(root), out_dir=Path(out_dir),
                                           payload=payload, prompt=prompt)
                findings = v3_domain._domain_findings(stage, payload, value)
                if findings:
                    raise ValueError("V3 frozen-domain validation failed: " + "; ".join(findings))
                return value
            raise ValueError("V3 frozen-domain validation failed: " + "; ".join(pre_findings))
        raw = worker_cache[stage]
        projected = _project(raw, refs_by_oid=refs_by_oid) if "groups" in raw or "obligation_contracts" in raw else dict(raw)
        domain_findings = v3_domain._domain_findings(stage, payload, projected)
        if domain_findings:
            raise ValueError("V3 frozen-domain validation failed: " + "; ".join(domain_findings))
        for contract in (raw.get("obligation_contracts", {}) if isinstance(raw.get("obligation_contracts"), Mapping) else {}).values():
            hint = contract.get("slice_hint") if isinstance(contract, Mapping) else None
            planned = set(hint.get("planned_new_files", []) if isinstance(hint, Mapping) else [])
            allowed = set(hint.get("allowed_write_paths", []) if isinstance(hint, Mapping) else [])
            for owner in (hint.get("production_owners", []) if isinstance(hint, Mapping) else []):
                if not _cached_owner_is_admissible(Path(root), owner, hint):
                    raise ValueError("no-real-production-entry:" + owner)
        value = projected
    elif worker_cache and stage in worker_cache:
        raise ValueError("injected V3 repair cache must be object")
    else:
        value = _live_group_repair(root=Path(root), out_dir=Path(out_dir), payload=payload, prompt=prompt)
    value = _ground_group_result(root, payload, value)
    findings = v3_domain._domain_findings(stage, payload, value)
    if findings:
        raise ValueError("V3 frozen-domain validation failed: " + "; ".join(findings))
    return value


def install() -> None:
    gate._ORIGINAL_INVOKE_WORKER = group_repair_transport


install()
