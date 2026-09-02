"""Complete only genuinely missing V3 Acceptance coverage inside the one repair lane.

The stable V3 schema-repair transport can return a structurally valid grouped
candidate that still omits active frozen obligations.  The execution-contract
must continue to reject that state, but a live compile gets one bounded,
missing-only semantic completion before the rejection becomes terminal.

This layer never marks an obligation covered locally.  A read-only worker must
author Acceptance/RED/slice semantics for the exact missing obligation domain.
The completion is then revalidated against frozen obligation IDs, subject
boundaries, source refs, owner/write-set rules and explicit frozen path facts.
If any active obligation remains missing, the downstream execution-contract
fails closed exactly as before.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import semantic_worker_v3_domain_patch as v3_domain
import semantic_worker_v3_execution_contract_patch as execution_contract
import semantic_worker_v3_explicit_path_contract_patch as path_contract
import semantic_worker_v3_group_repair_patch as grouped
import semantic_worker_v3_group_safety_patch as safety

_BASE_TRANSPORT = execution_contract._BASE_TRANSPORT
_COMPLETION_CACHE_KEY = "v3-coverage-completion"


def _input_payload(stage: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    if stage.startswith("v3-schema-repair"):
        nested = payload.get("input")
        return nested if isinstance(nested, Mapping) else {}
    return payload


def _active_ids(stage: str, payload: Mapping[str, Any]) -> set[str]:
    values = _input_payload(stage, payload).get("obligations")
    if not isinstance(values, list):
        return set()
    return {
        str(item["obligation_id"])
        for item in values
        if isinstance(item, Mapping)
        and item.get("status") == "active"
        and isinstance(item.get("obligation_id"), str)
        and item.get("obligation_id")
    }


def _covered_ids(value: Mapping[str, Any]) -> set[str]:
    values = value.get("acceptances")
    if not isinstance(values, list):
        return set()
    return {
        str(oid)
        for raw in values
        if isinstance(raw, Mapping)
        for oid in raw.get("obligation_ids", [])
        if isinstance(oid, str) and oid
    }


def _narrow_payload(stage: str, payload: Mapping[str, Any], missing: set[str]) -> dict[str, Any]:
    source = dict(_input_payload(stage, payload))
    obligations = source.get("obligations")
    if not isinstance(obligations, list):
        raise ValueError("V3 coverage completion has no frozen obligations")
    source["obligations"] = [
        dict(item)
        for item in obligations
        if isinstance(item, Mapping) and item.get("obligation_id") in missing
    ]
    if len(source["obligations"]) != len(missing):
        raise ValueError("V3 coverage completion cannot bind every missing frozen obligation")

    refs = {
        ref
        for item in source["obligations"]
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
    return {
        "original_stage": "v3",
        "input": source,
        "validator_findings": ["v3-contract:hard-uncovered:" + ",".join(sorted(missing))],
    }


def _completion_from_fixture(worker_cache: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if not worker_cache or _COMPLETION_CACHE_KEY not in worker_cache:
        return None
    raw = worker_cache[_COMPLETION_CACHE_KEY]
    if not isinstance(raw, Mapping):
        raise ValueError("injected V3 coverage completion must be object")
    return grouped._project(raw) if "groups" in raw else dict(raw)


def _complete_missing(
    *,
    root: Path,
    out_dir: Path,
    stage: str,
    payload: Mapping[str, Any],
    missing: set[str],
    worker_cache: Mapping[str, Any] | None,
) -> Mapping[str, Any]:
    narrowed = _narrow_payload(stage, payload, missing)
    fixture = _completion_from_fixture(worker_cache)
    if fixture is not None:
        completion = fixture
    elif worker_cache:
        # Unit/injected runs must never escape into a live model call merely
        # because a fixture intentionally exercises a hard-uncovered failure.
        raise ValueError("V3 injected repair remains hard-uncovered")
    else:
        completion = grouped._live_group_repair(
            root=root,
            out_dir=out_dir,
            payload=narrowed,
            prompt=(
                "COVERAGE COMPLETION: author semantics only for the supplied missing active obligations. "
                "Every supplied obligation must appear in at least one Acceptance group. Do not rewrite, merge with, "
                "or weaken any previously accepted group. Preserve subject boundaries and frozen source semantics."
            ),
        )

    findings = v3_domain._domain_findings("v3-schema-repair", narrowed, completion)
    if findings:
        raise ValueError("V3 coverage completion domain validation failed: " + "; ".join(findings))
    safety._validate_subject_domains(narrowed, completion)
    return safety._normalize_repaired_value(Path(root), completion)


def _merge(base: Mapping[str, Any], completion: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key in ("acceptances", "failure_intents", "slice_hints"):
        left = base.get(key)
        right = completion.get(key)
        if not isinstance(left, list) or not isinstance(right, list):
            raise ValueError(f"V3 coverage completion {key} is malformed")
        result[key] = [*left, *right]
    return result


def total_coverage_transport(
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
    if not stage.startswith("v3-schema-repair"):
        return value

    active = _active_ids(stage, payload)
    missing = active - _covered_ids(value)
    if not missing:
        return value

    completion = _complete_missing(
        root=Path(root),
        out_dir=Path(out_dir),
        stage=stage,
        payload=payload,
        missing=missing,
        worker_cache=worker_cache,
    )
    combined = _merge(value, completion)

    # Reapply the explicit frozen path projection because the completion was
    # authored after the normal path-contract transport already ran.
    combined = dict(path_contract.normalize_explicit_path_contracts(Path(root), stage, payload, combined))

    remaining = active - _covered_ids(combined)
    if remaining:
        raise ValueError("V3 coverage completion remains hard-uncovered: " + ",".join(sorted(remaining)))
    return combined


def install() -> None:
    # Keep the public transport composition stable: v4 still wraps the V3
    # execution-contract function.  Only that function's base candidate source
    # gains bounded total-coverage completion before its deterministic findings.
    execution_contract._BASE_TRANSPORT = total_coverage_transport


install()
