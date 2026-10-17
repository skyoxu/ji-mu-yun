"""Apply one bounded Acceptance-only repair after independent V4 misalignment.

V4 remains the semantic judge. A repair is permitted for an isolated
Acceptance semantic gap: either no coverage finding exists, or every missing
and uncovered active obligation is bound only to the reported misaligned
Acceptances. Invented or unknown IDs, and every other coverage failure, remain
non-repairable. The repair worker may change only Given/When/Then/oracle/assertion
semantics for the named Acceptance IDs; obligation/source binding, RED
selector/family, hints, owners and write sets remain frozen. Deterministic IDs
are recomputed and a second independent V4 worker must accept the repaired
candidates.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import json
from pathlib import Path

import semantic_compiler_gate as gate
import semantic_worker_v3_domain_patch  # noqa: F401  # preserve frozen V3 domain first

sc = gate.sc
_BASE_SEMANTIC_ALIGN = sc.semantic_align
_MAX_V4_ALIGNMENT_INPUT_CHARS = 900_000
_REPAIRS_PER_APPROVED_CYCLE = 3
_approved_repair_cycles = 0


def configure_approved_v4_repair_cycles(cycles: int) -> None:
    """Allow explicitly approved follow-up batches without weakening V4 gates."""
    if not isinstance(cycles, int) or cycles < 0:
        raise ValueError("approved V4 repair cycles must be a non-negative integer")
    global _approved_repair_cycles
    _approved_repair_cycles = cycles


def _maximum_closed_v4_repair_passes() -> int:
    return _REPAIRS_PER_APPROVED_CYCLE * (1 + _approved_repair_cycles)


def _v4_source_chunk_result_matches_scope(
    raw: Mapping[str, Any], obligation_ids: set[str], acceptance_ids: set[str],
    acceptance_obligations: Mapping[str, set[str]],
) -> bool:
    """Accept a cached V4 partition only when its IDs and bindings are local."""
    for field in ("covered_obligation_ids", "missing_obligation_ids"):
        values = raw.get(field)
        if not isinstance(values, list) or any(
            not isinstance(value, str) or value not in obligation_ids for value in values
        ):
            return False
    values = raw.get("misaligned_acceptance_ids")
    if not isinstance(values, list) or not all(
        isinstance(value, str) and value in acceptance_ids for value in values
    ):
        return False
    # A non-empty misalignment is an actionable semantic finding, not a
    # reusable successful partition. Force the bounded Acceptance repair path
    # to receive a fresh independent worker result for this source chunk.
    if values:
        return False
    # A source partition receives exactly its own active obligations.  An ID
    # from that partition is therefore never "invented"; if its Acceptance or
    # RED binding is absent, V4 must report it as missing.  Reject the worker
    # result so the bounded retry can correct the classification instead of
    # allowing a valid current obligation to poison the aggregate as invented.
    invented = raw.get("invented_obligation_ids")
    if not isinstance(invented, list) or any(
        not isinstance(value, str) or value in obligation_ids for value in invented
    ):
        return False
    missing = {value for value in raw["missing_obligation_ids"] if isinstance(value, str)}
    if not missing:
        return True
    # V3 emits one Acceptance contract per active obligation. A cached V4
    # conclusion that says an obligation is missing yet omits its actual bound
    # Acceptance cannot guide an Acceptance-only repair, even if it names some
    # other current Acceptance from the same source partition.
    bound = {
        aid for aid, bound_obligations in acceptance_obligations.items()
        if missing.intersection(bound_obligations)
    }
    return bound <= set(values)


def _preserve_stale_v4_chunk_cache(*, out_dir, stage: str, payload: Mapping[str, Any]) -> None:
    """Move one invalid cache entry aside so only its source partition is replayed."""
    cache_path = Path(out_dir) / ".compiler-cache" / sc._worker_cache_key(stage, payload)
    if not cache_path.is_file():
        return
    sidecar = cache_path.with_name(cache_path.name + ".stale-v4-source-scope")
    suffix = 1
    while sidecar.exists():
        sidecar = cache_path.with_name(cache_path.name + f".stale-v4-source-scope-{suffix}")
        suffix += 1
    cache_path.replace(sidecar)


def _invoke_v4_source_chunk(
    *, root, out_dir, stage: str, payload: Mapping[str, Any], prompt: str,
    worker_cache, obligation_ids: set[str], acceptance_ids: set[str],
    acceptance_obligations: Mapping[str, set[str]],
) -> Mapping[str, Any]:
    raw = sc.invoke_worker(
        root=root, out_dir=out_dir, stage=stage, payload=payload,
        worker_cache=worker_cache, prompt=prompt,
    )
    if _v4_source_chunk_result_matches_scope(raw, obligation_ids, acceptance_ids, acceptance_obligations):
        return raw
    _preserve_stale_v4_chunk_cache(out_dir=out_dir, stage=stage, payload=payload)
    # An injected fixture may be just as stale as the disk cache. Do not feed it
    # back into the retry; the stale value has already been retained as a sidecar.
    return sc.invoke_worker(
        root=root, out_dir=out_dir, stage=stage, payload=payload,
        worker_cache=None, prompt=prompt,
    )


def _chunked_alignment(
    *, root, out_dir, source_index, obligations, acceptances, failures, worker_cache,
) -> dict[str, Any]:
    """ADR-0041: split only an input that cannot fit the worker transport."""
    entries = [item for item in source_index.get("entries", []) if isinstance(item, Mapping)]
    by_acceptance = {str(item.get("acceptance_id")): item for item in acceptances if isinstance(item, Mapping)}
    merged = {key: [] for key in ("covered_obligation_ids", "missing_obligation_ids", "invented_obligation_ids", "misaligned_acceptance_ids", "repairs")}
    for index, entry in enumerate(entries, start=1):
        ref = entry.get("source_ref")
        if not isinstance(ref, str):
            continue
        scoped_obligations = [item for item in obligations if ref in item.get("source_refs", [])]
        ids = {str(item.get("obligation_id")) for item in scoped_obligations}
        scoped_acceptances = [item for item in acceptances if ids.intersection(str(x) for x in item.get("obligation_ids", []))]
        aids = {str(item.get("acceptance_id")) for item in scoped_acceptances}
        acceptance_obligations = {
            str(item.get("acceptance_id")): {
                str(oid) for oid in item.get("obligation_ids", []) if isinstance(oid, str)
            }
            for item in scoped_acceptances
        }
        scoped_failures = [item for item in failures if aids.intersection(str(x) for x in item.get("acceptance_ids", []))]
        payload = sc.alignment_payload({"entries": [entry]}, scoped_obligations, scoped_acceptances, scoped_failures)
        raw = _invoke_v4_source_chunk(
            root=root, out_dir=out_dir, stage=f"v4-source-chunk-{index:02d}", payload=payload,
            worker_cache=worker_cache, obligation_ids=ids, acceptance_ids=aids,
            acceptance_obligations=acceptance_obligations, prompt=(
                "Independently align this frozen source partition to its supplied obligations, Acceptance and RED intents. "
                "Return covered_obligation_ids[], missing_obligation_ids[], invented_obligation_ids[], "
                "misaligned_acceptance_ids[], oracle_alignment object, repairs[]. A boolean valid is not authoritative."
                + sc.ALIGNMENT_SCOPE_PROMPT
                + " For this source partition, every supplied active obligation ID is a real current obligation, never an invented one. If its Acceptance or RED binding is absent or semantically unusable, place that ID in missing_obligation_ids. Keep invented_obligation_ids empty; do not use it for a supplied ID."
            ),
        )
        for key in merged:
            value = raw.get(key)
            if not isinstance(value, list):
                raise ValueError(f"V4 source chunk {index} missing {key}")
            merged[key].extend(value)
    for key in merged:
        if key != "repairs":
            merged[key] = sorted(set(str(value) for value in merged[key] if isinstance(value, str)))
    return {**merged, "oracle_alignment": {"mode": "source-partitioned"}}


def _alignment_worker_result(*, root, out_dir, source_index, obligations, acceptances, failures, worker_cache, stage: str, prompt: str) -> Mapping[str, Any]:
    payload = sc.alignment_payload(source_index, obligations, acceptances, failures)
    serialized_size = len(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    # Recheck carries repaired Acceptance prose and is materially larger than
    # the first V4 alignment. Keep its transport bounded even when it remains
    # below the historical global threshold; this is a transport decision, not
    # a semantic scope reduction.
    threshold = 300_000 if stage == "v4-recheck" else _MAX_V4_ALIGNMENT_INPUT_CHARS
    if serialized_size > threshold:
        return _chunked_alignment(root=root, out_dir=out_dir, source_index=source_index,
                                  obligations=obligations, acceptances=acceptances,
                                  failures=failures, worker_cache=worker_cache)
    return sc.invoke_worker(root=root, out_dir=out_dir, stage=stage, payload=payload,
                            worker_cache=worker_cache, prompt=prompt)


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


def _repair_targets(
    raw: Mapping[str, Any], acceptances: Sequence[Mapping[str, Any]], *, findings: Sequence[str] = (),
) -> set[str]:
    """Use compiler-owned bindings when a worker reports an incomplete association.

    V4 may identify a real wording issue but associate its reported Acceptance
    ID with the wrong missing obligation.  IDs and obligation bindings are
    compiler-owned, so only current reported IDs are retained and the actual
    bound Acceptance for each reported missing obligation is added. The caller
    still requires the resulting set to be closed over the active missing set.
    """
    current_ids = {
        str(item.get("acceptance_id"))
        for item in acceptances
        if isinstance(item, Mapping) and isinstance(item.get("acceptance_id"), str)
    }
    # Worker IDs are diagnostic claims, not authority. A repaired candidate
    # has deterministic new IDs, so an ID absent from the supplied current
    # candidates cannot be a legal repair target.
    missing = {
        str(item)
        for item in raw.get("missing_obligation_ids", [])
        if isinstance(item, str) and item
    }
    # V4's worker lists explicit missing IDs separately from its coverage
    # projection.  Treat a compiler-confirmed active-not-covered ID as the
    # same bounded repair input when the worker omitted it from that list;
    # otherwise a local Acceptance repair is incorrectly rejected solely due
    # to two inconsistent diagnostic projections.
    for finding in findings:
        prefix = "v4:active-not-covered:"
        if isinstance(finding, str) and finding.startswith(prefix):
            missing.update(item for item in finding[len(prefix):].split(",") if item)
    # A missing obligation is a compiler-owned binding problem.  Do not let a
    # worker's potentially stale association pull a peer Acceptance into this
    # bounded repair. The next independent recheck can surface an unrelated
    # semantic mismatch as its own (second and final) closed repair.
    targets: set[str] = set()
    for acceptance in acceptances:
        if not isinstance(acceptance, Mapping):
            continue
        aid = acceptance.get("acceptance_id")
        bound = acceptance.get("obligation_ids")
        if isinstance(aid, str) and isinstance(bound, list) and missing.intersection(
            str(oid) for oid in bound if isinstance(oid, str)
        ):
            targets.add(aid)
    if missing:
        return targets
    targets.update(
        str(item)
        for item in raw.get("misaligned_acceptance_ids", [])
        if isinstance(item, str) and item in current_ids
    )
    return targets


def _isolated_acceptance_semantic_gap(
    raw: Mapping[str, Any],
    obligations: Sequence[Mapping[str, Any]],
    acceptances: Sequence[Mapping[str, Any]],
    *,
    findings: Sequence[str] = (),
) -> bool:
    """Permit repair only when V4 localizes all coverage loss to its own targets."""
    targets = _repair_targets(raw, acceptances, findings=findings)
    if not targets:
        return False
    by_acceptance = {
        str(item.get("acceptance_id")): item
        for item in acceptances
        if isinstance(item, Mapping) and isinstance(item.get("acceptance_id"), str)
    }
    if not targets <= set(by_acceptance):
        return False
    active = {
        str(item.get("obligation_id"))
        for item in obligations
        if isinstance(item, Mapping) and item.get("status") == "active" and isinstance(item.get("obligation_id"), str)
    }
    target_obligations = {
        str(oid)
        for aid in targets
        for oid in by_acceptance[aid].get("obligation_ids", [])
        if isinstance(oid, str)
    }
    covered = {str(item) for item in raw.get("covered_obligation_ids", []) if isinstance(item, str)}
    missing = {str(item) for item in raw.get("missing_obligation_ids", []) if isinstance(item, str)}
    invented = {str(item) for item in raw.get("invented_obligation_ids", []) if isinstance(item, str)}
    if invented or not missing <= active or not covered <= active:
        return False
    # Partitioned V4 reports coverage and explicit missing IDs independently.
    # Require the full compiler-derived uncovered set to remain inside the
    # actual repair closure, rather than requiring the two worker projections
    # to be byte-for-byte equivalent.
    return (active - covered) <= target_obligations and missing <= target_obligations


def _requires_frozen_execution_binding_change(raw: Mapping[str, Any]) -> bool:
    """Reject V4 repair advice that would alter a frozen RED/assertion binding.

    The V4 repair worker may revise Acceptance wording only.  A request to add
    or replace a RED intent or assertion binding belongs to the upstream
    contract producer; allowing the wording worker to attempt it wastes its
    bounded repair budget and cannot establish a real executable assertion.
    """
    repairs = raw.get("repairs")
    if not isinstance(repairs, list):
        return False
    for repair in repairs:
        if not isinstance(repair, Mapping):
            continue
        text = " ".join(
            str(value) for key, value in repair.items()
            if key in {"action", "repair", "reason"} and isinstance(value, str)
        ).lower()
        if "red intent" in text or "assertion binding" in text or "assertion ids" in text:
            return True
    return False


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
    raw = _alignment_worker_result(
        root=root, out_dir=out_dir, source_index=source_index, obligations=obligations,
        acceptances=acceptances, failures=failures, worker_cache=worker_cache, stage="v4-recheck", prompt=(
            "Independently re-evaluate the frozen source against the repaired Acceptance candidates. "
            "Do not trust the repair worker or any prior V4 conclusion. Return covered_obligation_ids[], "
            "missing_obligation_ids[], invented_obligation_ids[], misaligned_acceptance_ids[], "
            "oracle_alignment object, repairs[]. A boolean valid is not authoritative."
            + sc.ALIGNMENT_SCOPE_PROMPT
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
    payload = sc.alignment_payload(source_index, obligations, acceptances, failures)
    if len(json.dumps(payload, ensure_ascii=False, sort_keys=True)) > _MAX_V4_ALIGNMENT_INPUT_CHARS:
        raw = _alignment_worker_result(root=root, out_dir=out_dir, source_index=source_index,
                                       obligations=obligations, acceptances=acceptances,
                                       failures=failures, worker_cache=worker_cache, stage="v4",
                                       prompt="source-partitioned alignment")
        findings = _alignment_findings(raw, obligations, acceptances)
        first = {"valid": not findings, "findings": findings, "worker": raw}
    else:
        first = _BASE_SEMANTIC_ALIGN(root=root, out_dir=out_dir, source_index=source_index,
                                     obligations=obligations, acceptances=acceptances,
                                     failures=failures, worker_cache=worker_cache)
    if first.get("valid"):
        return first
    findings = [str(item) for item in first.get("findings", [])]
    if not findings or any(
        not item.startswith(("v4:misaligned-acceptance:", "v4:active-not-covered:", "v4:missing:"))
        for item in findings
    ):
        return first
    if not isinstance(acceptances, list) or not isinstance(failures, list):
        return first

    # A recheck may expose a semantic wording error that was masked by an
    # earlier candidate. Each maintainer-approved cycle permits exactly three
    # closed repairs; coverage, identity, or invented-ID findings stop
    # immediately. A new cycle never lowers those gates or reuses a finding as
    # approval.
    candidate = first
    transcript: list[dict[str, Any]] = []
    maximum_passes = _maximum_closed_v4_repair_passes()
    for repair_pass in range(1, maximum_passes + 1):
        candidate_findings = [str(item) for item in candidate.get("findings", [])]
        if not candidate_findings or any(
            not item.startswith(("v4:misaligned-acceptance:", "v4:active-not-covered:", "v4:missing:"))
            for item in candidate_findings
        ):
            return candidate
        raw_candidate = candidate.get("worker")
        if not isinstance(raw_candidate, Mapping):
            return candidate
        if _requires_frozen_execution_binding_change(raw_candidate):
            return candidate
        if not _isolated_acceptance_semantic_gap(
            raw_candidate, obligations, acceptances, findings=candidate_findings,
        ):
            return candidate
        targets = _repair_targets(raw_candidate, acceptances, findings=candidate_findings)
        current_ids = {str(item.get("acceptance_id")) for item in acceptances if isinstance(item, Mapping)}
        if not targets or not targets <= current_ids:
            return candidate

        repair_payload = {
            "obligations": list(obligations),
            "acceptances": list(acceptances),
            "failure_intents": list(failures),
            "misaligned_acceptance_ids": sorted(targets),
            "v4_repairs": list(raw_candidate.get("repairs", [])) if isinstance(raw_candidate.get("repairs"), list) else [],
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
            [dict(item) for item in acceptances], [dict(item) for item in failures], repair_map,
        )
        preflight = sc.semantic_preflight(obligations, repaired_acceptances, repaired_failures)
        if not preflight.get("valid"):
            return {
                "valid": False,
                "findings": ["v4:acceptance-repair-preflight:" + ",".join(str(x) for x in preflight.get("findings", []))],
                "worker": {"transcript": transcript, "initial": dict(raw_candidate), "repair": dict(repair_raw)},
                "repair_attempted": True,
                "repair_passes": repair_pass,
                "repair_scope": "acceptance-semantics-only",
            }

        acceptances[:] = repaired_acceptances
        failures[:] = repaired_failures
        recheck = _independent_recheck(
            root=root, out_dir=out_dir, source_index=source_index, obligations=obligations,
            acceptances=acceptances, failures=failures, worker_cache=worker_cache,
        )
        transcript.append({"input": dict(raw_candidate), "repair": dict(repair_raw), "recheck": dict(recheck.get("worker", {}))})
        candidate = recheck
        if candidate.get("valid"):
            return {
                **candidate,
                "worker": {"transcript": transcript},
                "repair_attempted": True,
                "repair_passes": repair_pass,
                "repair_scope": "acceptance-semantics-only",
            }

    return {
        **candidate,
        "worker": {"transcript": transcript, "final_recheck": dict(candidate.get("worker", {}))},
        "repair_attempted": True,
        "repair_passes": maximum_passes,
        "approved_repair_cycles": _approved_repair_cycles,
        "repair_scope": "acceptance-semantics-only",
    }


def install() -> None:
    sc.semantic_align = semantic_align_with_bounded_repair


install()
