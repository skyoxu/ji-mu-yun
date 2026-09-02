"""Partition V3 Acceptance hints by semantic compatibility, not exact path-set identity.

The canonical compiler already permits multiple Acceptances in one slice, but
its original bucket key required exact equality of allowed/snapshot/planned path
sets.  Model-authored per-Acceptance hints therefore fragmented one cohesive
behavior into many slices even when they shared the same production owner,
verification lane, state transition, failure mechanism and test root.

This patch keeps the true split boundaries and unions compatible path evidence.
It never merges across owner, lane, state-transition, failure-family or test-root
boundaries, and it refuses a merge when one hint forbids a path another hint
must write.  Terminal and rollback predicates are conjunctively preserved.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import semantic_compiler as sc
import semantic_compiler_gate as gate


def _paths(hint: Mapping[str, Any], key: str, *, nonempty: bool = False) -> list[str]:
    return sc._validate_paths(hint.get(key, []), key, nonempty=nonempty)


def _snapshot_roots(paths: Sequence[str]) -> tuple[str, ...]:
    roots = {
        path.rsplit("/", 1)[0] if "/" in path else "."
        for path in paths
    }
    return tuple(sorted(roots))


def _strings(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value if isinstance(item, str) and item}


def _base_key(
    acceptance: Mapping[str, Any],
    hint: Mapping[str, Any],
    failure_by_acceptance: Mapping[str, Sequence[Mapping[str, Any]]],
) -> str:
    aid = str(acceptance["acceptance_id"])
    owners = _paths(hint, "production_owners", nonempty=True)
    snapshots = _paths(hint, "execution_snapshot_paths", nonempty=True)
    lane = hint.get("verification_lane")
    if lane not in sc.LANES:
        raise ValueError("slice hint verification_lane invalid")
    transition = hint.get("state_transition")
    if not isinstance(transition, str) or not transition:
        raise ValueError("slice hint state_transition missing")
    families = sorted({str(item["failure_family"]) for item in failure_by_acceptance.get(aid, [])})
    return sc.sha256_value({
        "owners": sorted(owners),
        "lane": lane,
        "transition": transition,
        "families": families,
        "snapshot_roots": _snapshot_roots(snapshots),
    })


def _compatible(cluster: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]], candidate: Mapping[str, Any]) -> bool:
    candidate_allowed = set(_paths(candidate, "allowed_write_paths"))
    candidate_planned = set(_paths(candidate, "planned_new_files"))
    candidate_owners = set(_paths(candidate, "production_owners", nonempty=True))
    candidate_forbidden = _strings(candidate.get("forbidden_paths"))

    cluster_allowed: set[str] = set()
    cluster_planned: set[str] = set()
    cluster_owners: set[str] = set()
    cluster_forbidden: set[str] = set()
    for _acceptance, hint in cluster:
        cluster_allowed.update(_paths(hint, "allowed_write_paths"))
        cluster_planned.update(_paths(hint, "planned_new_files"))
        cluster_owners.update(_paths(hint, "production_owners", nonempty=True))
        cluster_forbidden.update(_strings(hint.get("forbidden_paths")))

    candidate_writes = candidate_allowed | candidate_planned | candidate_owners
    cluster_writes = cluster_allowed | cluster_planned | cluster_owners
    return not (candidate_forbidden & cluster_writes or cluster_forbidden & candidate_writes)


def _conjunction(values: Sequence[str], fallback: str) -> str:
    unique = sorted({value.strip() for value in values if isinstance(value, str) and value.strip()})
    if not unique:
        return fallback
    if len(unique) == 1:
        return unique[0]
    return " AND ".join(f"({value})" for value in unique)


def cohesive_partition_slices(
    obligations: Sequence[Mapping[str, Any]],
    acceptances: Sequence[Mapping[str, Any]],
    failures: Sequence[Mapping[str, Any]],
    hints: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Mapping[str, Any]]]:
    failure_by_acceptance: dict[str, list[Mapping[str, Any]]] = {
        str(item["acceptance_id"]): [] for item in acceptances
    }
    for failure in failures:
        for aid in failure.get("acceptance_ids", []):
            failure_by_acceptance.setdefault(str(aid), []).append(failure)

    hint_by_acceptance: dict[str, Mapping[str, Any]] = {}
    broad: dict[str, list[list[tuple[Mapping[str, Any], Mapping[str, Any]]]]] = {}
    for acceptance in acceptances:
        hint = sc._hint_for_acceptance(hints, acceptance)
        aid = str(acceptance["acceptance_id"])
        hint_by_acceptance[aid] = hint
        key = _base_key(acceptance, hint, failure_by_acceptance)
        clusters = broad.setdefault(key, [])
        for cluster in clusters:
            if _compatible(cluster, hint):
                cluster.append((acceptance, hint))
                break
        else:
            clusters.append([(acceptance, hint)])

    buckets = [
        cluster
        for key in sorted(broad)
        for cluster in broad[key]
    ]
    slices: list[dict[str, Any]] = []
    for number, pairs in enumerate(buckets, start=1):
        acceptance_ids = sorted(str(a["acceptance_id"]) for a, _ in pairs)
        obligation_ids = sorted({str(oid) for a, _ in pairs for oid in a["obligation_ids"]})
        related_failures = [f for f in failures if set(f.get("acceptance_ids", [])) & set(acceptance_ids)]
        first_hint = pairs[0][1]

        production_owners = sorted({p for _, h in pairs for p in _paths(h, "production_owners", nonempty=True)})
        allowed_write_paths = sorted({p for _, h in pairs for p in _paths(h, "allowed_write_paths")})
        execution_snapshot_paths = sorted({p for _, h in pairs for p in _paths(h, "execution_snapshot_paths", nonempty=True)})
        planned_new_files = sorted({p for _, h in pairs for p in _paths(h, "planned_new_files")})
        affected = sorted({x for _, h in pairs for x in h.get("affected_subjects", []) if isinstance(x, str) and x})
        selectors = sorted({str(f["selector_intent"]) for f in related_failures})
        assertions = sorted({str(x) for a, _ in pairs for x in a["assertion_ids"]})
        rollback_paths = sorted({
            p
            for _, h in pairs
            for p in sc._validate_paths((h.get("rollback_scope") or {}).get("production_paths", []), "rollback.production_paths")
        })
        behaviors = sorted({str(h.get("behavior_change") or "").strip() for _, h in pairs if str(h.get("behavior_change") or "").strip()})
        terminals = [str(h.get("terminal_predicate") or "") for _, h in pairs]
        rollback_compat = [str((h.get("rollback_scope") or {}).get("state_or_schema_compatibility") or "") for _, h in pairs]

        lane = first_hint["verification_lane"]
        transition = first_hint["state_transition"]
        bucket_material = {
            "acceptance_ids": acceptance_ids,
            "obligation_ids": obligation_ids,
            "owners": production_owners,
            "lane": lane,
            "transition": transition,
            "failure_families": sorted({str(f["failure_family"]) for f in related_failures}),
            "snapshot_roots": _snapshot_roots(execution_snapshot_paths),
        }
        slice_id = f"S{number}"
        slices.append({
            "slice_id": slice_id,
            "slice_input_hash": sc.sha256_value(bucket_material),
            "obligation_ids": obligation_ids,
            "acceptance_ids": acceptance_ids,
            "failure_intent_ids": sorted(str(f["failure_intent_id"]) for f in related_failures),
            "production_owners": production_owners,
            "verification_lane": lane,
            "behavior_change": " | ".join(behaviors) or "Implement the bound Acceptance behaviors",
            "affected_subjects": affected or production_owners,
            "state_transition": transition,
            "proof": {
                "acceptance_ids": acceptance_ids,
                "selector_intents": selectors,
                "assertion_ids": assertions,
            },
            "rollback_scope": {
                "production_paths": rollback_paths or production_owners,
                "state_or_schema_compatibility": _conjunction(rollback_compat, "preserve declared compatibility"),
            },
            "allowed_write_paths": allowed_write_paths,
            "execution_snapshot_paths": execution_snapshot_paths,
            "planned_new_files": planned_new_files,
            "terminal_predicate": _conjunction(terminals, "all bound Acceptance predicates pass"),
        })
    return slices, hint_by_acceptance


def install() -> None:
    # semantic_compiler_gate.partition_slices_with_preflight delegates through
    # this mutable base reference, so preflight enrichment remains unchanged.
    gate._ORIGINAL_PARTITION_SLICES = cohesive_partition_slices


install()
