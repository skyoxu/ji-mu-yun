"""Partition atomic Acceptances by real implementation boundaries.

Model-authored failure, state-transition, and execution-evidence text is not a
stable split key. Cohesion is therefore decided by production owner,
verification lane, explicit dependency boundaries, and write/forbidden
conflicts. Compatible atomic Acceptances are merged into one slice while their
transitions, predicates, and rollback constraints are retained conjunctively.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import semantic_compiler as sc
import semantic_compiler_gate as gate


def _paths(hint: Mapping[str, Any], key: str, *, nonempty: bool = False) -> list[str]:
    return sc._validate_paths(hint.get(key, []), key, nonempty=nonempty)


def _snapshot_roots(paths: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted({path.rsplit("/", 1)[0] if "/" in path else "." for path in paths}))


def _strings(value: Any) -> set[str]:
    return {str(item) for item in value if isinstance(item, str) and item} if isinstance(value, list) else set()


def _base_key(hint: Mapping[str, Any]) -> str:
    owners = _paths(hint, "production_owners", nonempty=True)
    lane = hint.get("verification_lane")
    if lane not in sc.LANES:
        raise ValueError("slice hint verification_lane invalid")
    return sc.sha256_value({"owners": sorted(owners), "lane": lane})


def _dependency_boundary(cluster: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]], candidate: Mapping[str, Any], obligations_by_id: Mapping[str, Mapping[str, Any]]) -> bool:
    candidate_ids = _strings(candidate.get("obligation_ids"))
    cluster_ids = {oid for acceptance, _hint in cluster for oid in _strings(acceptance.get("obligation_ids"))}
    for oid in candidate_ids:
        deps = _strings(obligations_by_id.get(oid, {}).get("depends_on"))
        if deps & cluster_ids:
            return True
    for oid in cluster_ids:
        deps = _strings(obligations_by_id.get(oid, {}).get("depends_on"))
        if deps & candidate_ids:
            return True
    return False


def _compatible(cluster: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]], acceptance: Mapping[str, Any], candidate: Mapping[str, Any], obligations_by_id: Mapping[str, Mapping[str, Any]]) -> bool:
    if _dependency_boundary(cluster, acceptance, obligations_by_id):
        return False
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
    return unique[0] if len(unique) == 1 else " AND ".join(f"({value})" for value in unique)


def cohesive_partition_slices(obligations: Sequence[Mapping[str, Any]], acceptances: Sequence[Mapping[str, Any]], failures: Sequence[Mapping[str, Any]], hints: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Mapping[str, Any]]]:
    obligations_by_id = {
        str(item.get("obligation_id")): item
        for item in obligations
        if isinstance(item, Mapping) and isinstance(item.get("obligation_id"), str)
    }
    hint_by_acceptance: dict[str, Mapping[str, Any]] = {}
    broad: dict[str, list[list[tuple[Mapping[str, Any], Mapping[str, Any]]]]] = {}
    for acceptance in acceptances:
        hint = sc._hint_for_acceptance(hints, acceptance)
        aid = str(acceptance["acceptance_id"])
        hint_by_acceptance[aid] = hint
        key = _base_key(hint)
        clusters = broad.setdefault(key, [])
        for cluster in clusters:
            if _compatible(cluster, acceptance, hint, obligations_by_id):
                cluster.append((acceptance, hint))
                break
        else:
            clusters.append([(acceptance, hint)])

    buckets = [cluster for key in sorted(broad) for cluster in broad[key]]
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
        rollback_paths = sorted({p for _, h in pairs for p in sc._validate_paths((h.get("rollback_scope") or {}).get("production_paths", []), "rollback.production_paths")})
        behaviors = [str(h.get("behavior_change") or "") for _, h in pairs]
        transitions = [str(h.get("state_transition") or "") for _, h in pairs]
        terminals = [str(h.get("terminal_predicate") or "") for _, h in pairs]
        rollback_compat = [str((h.get("rollback_scope") or {}).get("state_or_schema_compatibility") or "") for _, h in pairs]
        lane = first_hint["verification_lane"]
        bucket_material = {
            "acceptance_ids": acceptance_ids,
            "obligation_ids": obligation_ids,
            "owners": production_owners,
            "lane": lane,
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
            "behavior_change": _conjunction(behaviors, "Implement the bound Acceptance behaviors"),
            "affected_subjects": affected or production_owners,
            "state_transition": _conjunction(transitions, "all bound state transitions hold"),
            "proof": {"acceptance_ids": acceptance_ids, "selector_intents": selectors, "assertion_ids": assertions},
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
    gate._ORIGINAL_PARTITION_SLICES = cohesive_partition_slices


install()
