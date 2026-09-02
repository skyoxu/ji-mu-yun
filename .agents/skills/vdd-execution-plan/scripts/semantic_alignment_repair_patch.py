"""Apply one bounded Acceptance-only repair after independent V4 misalignment.

V4 remains the semantic judge.  A repair is permitted only when V4 reports
misaligned Acceptance semantics and no missing/invented/coverage failure.  The
repair worker may change only Given/When/Then/oracle/assertion semantics for the
named Acceptance IDs; obligation/source binding, RED selector/family, hints,
owners and write sets remain frozen.  Deterministic IDs are recomputed and a
second independent V4 worker must accept the repaired candidates.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import semantic_compiler_gate as gate
import semantic_worker_v3_domain_patch  # noqa: F401  # preserve frozen V3 domain first

sc = gate.sc
_BASE_SEMANTIC_ALIGN = sc.semantic_align


def _string_list(value: Any, *, nonempty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (bool(value) or not nonempty)
        and all(isinstance(item, str) and bool(item.strip()) for item in value)
    )


def _alignment_findings(
    raw: Mapping[str, Any],
    obligations: Sequence[Mapping[str, Any]],
    acceptances: Sequence[Mapping[str, Any]],
) -> list[str]:
    required = (
        "covered_obligation_ids",
        "missing_obligation_ids",
        "invented_obligation_ids",
        "misaligned_acceptance_ids",
        "repairs",
    )
    findings: list[str] = []
    for key in required:
        if not isinstance(raw.get(key), list):
            findings.append(f"v4-recheck:{key}:missing")
    if findings:
        return findings

    known = {str(item["obligation_id"]) for item in obligations if item.get("status") == "active"}
    acceptance_ids = {str(item["acceptance_id"]) for item in acceptances}
    covered = {str(item) for item in raw["covered_obligation_ids"] if isinstance(item, str)}
    missing = {str(item) for item in raw["missing_obligation_ids"] if isinstance(item, str)}
    invented = {str(item) for item in raw["invented_obligation_ids"] if isinstance(item, str)}
    misaligned = {str(item) for item in raw["misaligned_acceptance_ids"] if isinstance(item, str)}

    unknown_covered = covered - known
    unknown_missing = missing - known
    unknown_misaligned = misaligned - acceptance_ids
    if unknown_covered:
        findings.append("v4:unknown-covered:" + ",".join(sorted(unknown_covered)))
    if unknown_missing:
        findings.append("v4:unknown-missing:" + ",".join(sorted(unknown_missing)))
    if unknown_misaligned:
        findings.append("v4:unknown-misaligned-acceptance:" + ",".join(sorted(unknown_misaligned)))
    if known - covered:
        findings.append("v4:active-not-covered:" + ",".join(sorted(known - covered)))
    if missing:
        findings.append("v4:missing:" + ",".join(sorted(missing)))
    if invented:
        findings.append("v4:invented:" + ",".join(sorted(invented)))
    if misaligned:
        findings.append("v4:misaligned-acceptance:" + ",".join(sorted(misaligned)))
    return findings


def _repair_map(raw: Mapping[str, Any], targets: set[str]) -> dict[str, Mapping[str, Any]]:
    values = raw.get("acceptance_repairs")
    if not isinstance(values, list):
        raise ValueError("V4 acceptance repair missing acceptance_repairs")
    result: dict[str, Mapping[str, Any]] = {}
    for index, item in enumerate(values):
        if not isinstance(item, Mapping):
            raise ValueError(f"V4 acceptance repair item {index} is not object")
        aid = item.get("acceptance_id")
        if not isinstance(aid, str) or aid not in targets or aid in result:
            raise ValueError("V4 acceptance repair target is invalid")
        for field in ("given", "when", "then"):
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"V4 acceptance repair {field} is invalid")
        oracle = item.get("oracle")
        if not isinstance(oracle, Mapping):
            raise ValueError("V4 acceptance repair oracle is invalid")
        if not isinstance(oracle.get("observable"), str) or not oracle["observable"].strip():
            raise ValueError("V4 acceptance repair oracle observable is invalid")
        if not isinstance(oracle.get("expected"), str) or not oracle["expected"].strip():
            raise ValueError("V4 acceptance repair oracle expected is invalid")
        if not _string_list(oracle.get("forbidden")):
            raise ValueError("V4 acceptance repair oracle forbidden is invalid")
        if not _string_list(item.get("assertion_ids"), nonempty=True):
            raise ValueError("V4 acceptance repair assertion ids are invalid")
        result[aid] = item
    if set(result) != targets:
        raise ValueError("V4 acceptance repair does not exactly cover misaligned Acceptance IDs")
    return result


def _apply_repairs(
    acceptances: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    repairs: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    aid_map: dict[str, str] = {}
    repaired_acceptances: list[dict[str, Any]] = []
    for raw in acceptances:
        item = dict(raw)
        old_aid = str(item["acceptance_id"])
        patch = repairs.get(old_aid)
        if patch is not None:
            item["given"] = str(patch["given"]).strip()
            item["when"] = str(patch["when"]).strip()
            item["then"] = str(patch["then"]).strip()
            oracle = patch["oracle"]
            item["oracle"] = {
                "observable": str(oracle["observable"]).strip(),
                "expected": str(oracle["expected"]).strip(),
                "forbidden": list(oracle["forbidden"]),
            }
            item["assertion_ids"] = sorted(set(str(value) for value in patch["assertion_ids"]))
            # Frozen binding fields are intentionally untouched.
            item["obligation_ids"] = list(raw["obligation_ids"])
            item["source_refs"] = list(raw["source_refs"])
            new_aid = sc._stable_acceptance_id(item)
            item["acceptance_id"] = new_aid
            aid_map[old_aid] = new_aid
        else:
            aid_map[old_aid] = old_aid
        item["red_intent_ids"] = []
        repaired_acceptances.append(item)

    if len({item["acceptance_id"] for item in repaired_acceptances}) != len(repaired_acceptances):
        raise ValueError("V4 acceptance repair causes Acceptance ID collision")

    repaired_failures: list[dict[str, Any]] = []
    for raw in failures:
        item = dict(raw)
        item["acceptance_ids"] = [aid_map.get(str(aid), str(aid)) for aid in raw.get("acceptance_ids", [])]
        item["failure_intent_id"] = sc._stable_failure_intent_id(item)
        repaired_failures.append(item)

    if len({item["failure_intent_id"] for item in repaired_failures}) != len(repaired_failures):
        raise ValueError("V4 acceptance repair causes failure-intent ID collision")

    by_aid = {item["acceptance_id"]: item for item in repaired_acceptances}
    for failure in repaired_failures:
        for aid in failure.get("acceptance_ids", []):
            if aid not in by_aid:
                raise ValueError("V4 acceptance repair orphaned failure intent")
            by_aid[aid]["red_intent_ids"].append(failure["failure_intent_id"])
    for acceptance in repaired_acceptances:
        acceptance["red_intent_ids"] = sorted(set(acceptance["red_intent_ids"]))
    return repaired_acceptances, repaired_failures


def _independent_recheck(
    *,
    root,
    out_dir,
    source_index: Mapping[str, Any],
    obligations: Sequence[Mapping[str, Any]],
    acceptances: Sequence[Mapping[str, Any]],
    failures: Sequence[Mapping[str, Any]],
    worker_cache: Mapping[str, Any] | None,
) -> dict[str, Any]:
    payload = {
        "source_index": source_index,
        "obligations": list(obligations),
        "acceptances": list(acceptances),
        "failure_intents": list(failures),
    }
    raw = sc.invoke_worker(
        root=root,
        out_dir=out_dir,
        stage="v4-recheck",
        payload=payload,
        worker_cache=worker_cache,
        prompt=(
            "Independently re-evaluate the frozen source against the repaired Acceptance candidates. "
            "Do not trust the repair worker or any prior V4 conclusion. Return covered_obligation_ids[], "
            "missing_obligation_ids[], invented_obligation_ids[], misaligned_acceptance_ids[], "
            "oracle_alignment object, repairs[]. A boolean valid is not authoritative."
        ),
    )
    findings = _alignment_findings(raw, obligations, acceptances)
    return {"valid": not findings, "findings": findings, "worker": dict(raw)}


def semantic_align_with_bounded_repair(
    *,
    root,
    out_dir,
    source_index: Mapping[str, Any],
    obligations: Sequence[Mapping[str, Any]],
    acceptances: Sequence[Mapping[str, Any]],
    failures: Sequence[Mapping[str, Any]],
    worker_cache: Mapping[str, Any] | None,
) -> dict[str, Any]:
    first = _BASE_SEMANTIC_ALIGN(
        root=root,
        out_dir=out_dir,
        source_index=source_index,
        obligations=obligations,
        acceptances=acceptances,
        failures=failures,
        worker_cache=worker_cache,
    )
    if first.get("valid"):
        return first
    findings = [str(item) for item in first.get("findings", [])]
    if not findings or any(not item.startswith("v4:misaligned-acceptance:") for item in findings):
        return first
    if not isinstance(acceptances, list) or not isinstance(failures, list):
        return first

    raw_first = first.get("worker")
    if not isinstance(raw_first, Mapping):
        return first
    targets = {
        str(aid)
        for aid in raw_first.get("misaligned_acceptance_ids", [])
        if isinstance(aid, str) and aid
    }
    current_ids = {str(item.get("acceptance_id")) for item in acceptances if isinstance(item, Mapping)}
    if not targets or not targets <= current_ids:
        return first

    repair_payload = {
        "obligations": list(obligations),
        "acceptances": list(acceptances),
        "failure_intents": list(failures),
        "misaligned_acceptance_ids": sorted(targets),
        "v4_repairs": list(raw_first.get("repairs", [])) if isinstance(raw_first.get("repairs"), list) else [],
    }
    repair_raw = sc.invoke_worker(
        root=root,
        out_dir=out_dir,
        stage="v4-acceptance-repair",
        payload=repair_payload,
        worker_cache=worker_cache,
        prompt=(
            "Repair only the semantic wording of the named misaligned Acceptance candidates. Return "
            "{\"acceptance_repairs\":[{acceptance_id,given,when,then,oracle{observable,expected,forbidden[]},assertion_ids[]}]} "
            "with exactly one item per misaligned Acceptance ID. Preserve every Acceptance obligation_ids/source_refs "
            "binding and preserve all RED selector/family semantics, slice hints, owners and write sets. Use the frozen "
            "obligations and V4 repair advice only to make Given/When/Then/oracle/assertions faithfully discriminate the "
            "already-bound behavior; do not merge, split, add or remove obligations."
        ),
    )
    repair_map = _repair_map(repair_raw, targets)
    repaired_acceptances, repaired_failures = _apply_repairs(
        [dict(item) for item in acceptances],
        [dict(item) for item in failures],
        repair_map,
    )
    preflight = sc.semantic_preflight(obligations, repaired_acceptances, repaired_failures)
    if not preflight.get("valid"):
        return {
            "valid": False,
            "findings": ["v4:acceptance-repair-preflight:" + ",".join(str(x) for x in preflight.get("findings", []))],
            "worker": {"initial": dict(raw_first), "repair": dict(repair_raw)},
        }

    acceptances[:] = repaired_acceptances
    failures[:] = repaired_failures
    recheck = _independent_recheck(
        root=root,
        out_dir=out_dir,
        source_index=source_index,
        obligations=obligations,
        acceptances=acceptances,
        failures=failures,
        worker_cache=worker_cache,
    )
    return {
        **recheck,
        "worker": {
            "initial": dict(raw_first),
            "repair": dict(repair_raw),
            "recheck": dict(recheck.get("worker", {})),
        },
        "repair_attempted": True,
        "repair_scope": "acceptance-semantics-only",
    }


def install() -> None:
    sc.semantic_align = semantic_align_with_bounded_repair


install()
