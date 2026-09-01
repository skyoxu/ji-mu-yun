"""Exact semantic-chain audit for VDD Chapter 4/5/6 plan-ready bundles.

This is a deterministic authority check, not a semantic worker.  It proves that
all active obligations survive source -> Acceptance -> RED intent -> V5 -> V6 ->
V6A without source drift, terminal swallowing, lane mixing, or proof projection
loss.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

STAGES = ("red", "green", "refactor", "terminal")


def _maps(value: Any) -> list[Mapping[str, Any]]:
    return list(value) if isinstance(value, list) and all(isinstance(x, Mapping) for x in value) else []


def _ids(values: Any) -> set[str]:
    if not isinstance(values, list):
        return set()
    return {str(value) for value in values if isinstance(value, str) and value}


def audit_bundle(bundle: Mapping[str, Any]) -> dict[str, Any]:
    findings: list[str] = []
    obligations = _maps(bundle.get("obligations"))
    acceptances = _maps(bundle.get("acceptances"))
    failures = _maps(bundle.get("failure_intents"))
    pre_edges = _maps(bundle.get("pre_slice_coverage"))
    slices = _maps(bundle.get("slices"))
    final_edges = _maps(bundle.get("final_plan_coverage"))

    obligation_by_id = {str(x.get("obligation_id")): x for x in obligations if isinstance(x.get("obligation_id"), str)}
    acceptance_by_id = {str(x.get("acceptance_id")): x for x in acceptances if isinstance(x.get("acceptance_id"), str)}
    failure_by_id = {str(x.get("failure_intent_id")): x for x in failures if isinstance(x.get("failure_intent_id"), str)}
    slice_by_id = {str(x.get("slice_id")): x for x in slices if isinstance(x.get("slice_id"), str)}
    active = {oid for oid, item in obligation_by_id.items() if item.get("status") == "active"}

    acceptance_for_obligation: dict[str, set[str]] = {oid: set() for oid in active}
    failures_for_acceptance: dict[str, set[str]] = {aid: set() for aid in acceptance_by_id}
    for fid, failure in failure_by_id.items():
        aids = _ids(failure.get("acceptance_ids"))
        if len(aids) != 1:
            findings.append(f"chain:failure:{fid}:must-bind-exactly-one-acceptance")
        for aid in aids:
            if aid in failures_for_acceptance:
                failures_for_acceptance[aid].add(fid)
            else:
                findings.append(f"chain:failure:{fid}:unknown-acceptance:{aid}")

    for aid, acceptance in acceptance_by_id.items():
        obligation_ids = _ids(acceptance.get("obligation_ids"))
        known = {oid for oid in obligation_ids if oid in obligation_by_id}
        for oid in known & active:
            acceptance_for_obligation[oid].add(aid)
        expected_sources = {ref for oid in known for ref in _ids(obligation_by_id[oid].get("source_refs"))}
        actual_sources = _ids(acceptance.get("source_refs"))
        if actual_sources != expected_sources:
            findings.append(f"chain:acceptance:{aid}:source-ref-drift")
        declared_red = _ids(acceptance.get("red_intent_ids"))
        actual_red = failures_for_acceptance.get(aid, set())
        if not declared_red or declared_red != actual_red:
            findings.append(f"chain:acceptance:{aid}:red-intent-exact-cover")
        assertion_ids = _ids(acceptance.get("assertion_ids"))
        if not assertion_ids:
            findings.append(f"chain:acceptance:{aid}:assertion-empty")

        semantic_shapes = {
            (
                str(obligation_by_id[oid].get("subject")),
                str(obligation_by_id[oid].get("state_before")),
                str(obligation_by_id[oid].get("state_after")),
            )
            for oid in known
        }
        if len(semantic_shapes) > 1:
            findings.append(f"chain:acceptance:{aid}:overbroad-independent-behavior")

    for oid in active:
        if not acceptance_for_obligation.get(oid):
            findings.append(f"chain:obligation:{oid}:no-acceptance")

    expected_v5: set[tuple[str, str, str, str, str]] = set()
    for aid, acceptance in acceptance_by_id.items():
        for oid in _ids(acceptance.get("obligation_ids")) & active:
            obligation = obligation_by_id[oid]
            shared_sources = _ids(obligation.get("source_refs")) & _ids(acceptance.get("source_refs"))
            for source_ref in shared_sources:
                for fid in _ids(acceptance.get("red_intent_ids")):
                    expected_v5.add((str(obligation.get("requirement_id")), oid, aid, source_ref, fid))
    actual_v5 = {
        tuple(str(edge.get(key)) for key in ("requirement_id", "obligation_id", "acceptance_id", "source_ref", "failure_intent_id"))
        for edge in pre_edges
    }
    if actual_v5 != expected_v5 or len(actual_v5) != len(pre_edges):
        findings.append("chain:v5:semantic-edge-exact-cover")

    slice_for_acceptance: dict[str, str] = {}
    for sid, selected in slice_by_id.items():
        aids = _ids(selected.get("acceptance_ids"))
        for aid in aids:
            if aid in slice_for_acceptance:
                findings.append(f"chain:acceptance:{aid}:multiple-slices")
            slice_for_acceptance[aid] = sid
        expected_obligations = {oid for aid in aids if aid in acceptance_by_id for oid in _ids(acceptance_by_id[aid].get("obligation_ids"))}
        if _ids(selected.get("obligation_ids")) != expected_obligations:
            findings.append(f"chain:slice:{sid}:obligation-projection")
        expected_failures = {fid for aid in aids if aid in acceptance_by_id for fid in _ids(acceptance_by_id[aid].get("red_intent_ids"))}
        if _ids(selected.get("failure_intent_ids")) != expected_failures:
            findings.append(f"chain:slice:{sid}:failure-projection")
        lanes = {acceptance_by_id[aid].get("verification_lane") for aid in aids if aid in acceptance_by_id and acceptance_by_id[aid].get("verification_lane") is not None}
        if lanes and (len(lanes) != 1 or selected.get("verification_lane") not in lanes):
            findings.append(f"chain:slice:{sid}:incompatible-verification-lanes")
        proof = selected.get("proof")
        if not isinstance(proof, Mapping):
            findings.append(f"chain:slice:{sid}:proof-missing")
        else:
            if _ids(proof.get("acceptance_ids")) != aids:
                findings.append(f"chain:slice:{sid}:proof-acceptance-projection")
            expected_assertions = {assertion for aid in aids if aid in acceptance_by_id for assertion in _ids(acceptance_by_id[aid].get("assertion_ids"))}
            if _ids(proof.get("assertion_ids")) != expected_assertions:
                findings.append(f"chain:slice:{sid}:proof-assertion-projection")
            expected_selectors = {str(failure_by_id[fid].get("selector_intent")) for fid in expected_failures if fid in failure_by_id}
            if _ids(proof.get("selector_intents")) != expected_selectors:
                findings.append(f"chain:slice:{sid}:proof-selector-projection")

    if set(slice_for_acceptance) != set(acceptance_by_id):
        findings.append("chain:v6:acceptance-single-slice-cover")

    expected_v6a: set[tuple[str, str, str, str, str, str, str, str, tuple[str, ...]]] = set()
    for edge in pre_edges:
        aid = str(edge.get("acceptance_id"))
        sid = slice_for_acceptance.get(aid)
        selected = slice_by_id.get(sid or "")
        if selected is None:
            continue
        expected_v6a.add((
            str(edge.get("requirement_id")),
            str(edge.get("obligation_id")),
            aid,
            str(edge.get("source_ref")),
            str(edge.get("failure_intent_id")),
            sid or "",
            str(selected.get("verification_lane")),
            str(selected.get("terminal_predicate")),
            STAGES,
        ))
    actual_v6a = {
        (
            str(edge.get("requirement_id")), str(edge.get("obligation_id")), str(edge.get("acceptance_id")),
            str(edge.get("source_ref")), str(edge.get("failure_intent_id")), str(edge.get("slice_id")),
            str(edge.get("verification_lane")), str(edge.get("terminal_predicate")), tuple(edge.get("stage_scope", [])) if isinstance(edge.get("stage_scope"), list) else tuple(),
        )
        for edge in final_edges
    }
    if actual_v6a != expected_v6a or len(actual_v6a) != len(final_edges):
        findings.append("chain:v6a:semantic-edge-exact-cover")

    chained_obligations = {
        oid for oid in active
        if acceptance_for_obligation.get(oid)
        and any(edge[1] == oid for edge in actual_v5)
        and any(edge[1] == oid for edge in actual_v6a)
    }
    metrics = {
        "active_obligation_count": len(active),
        "fully_chained_obligation_count": len(chained_obligations),
        "obligation_chain_coverage": (len(chained_obligations) / len(active)) if active else 1.0,
        "acceptance_count": len(acceptance_by_id),
        "single_slice_acceptance_count": sum(1 for aid in acceptance_by_id if aid in slice_for_acceptance),
        "v5_expected_edge_count": len(expected_v5),
        "v5_actual_edge_count": len(actual_v5),
        "v6a_expected_edge_count": len(expected_v6a),
        "v6a_actual_edge_count": len(actual_v6a),
    }
    return {
        "schema": "vdd.semantic-chain-audit.v1",
        "valid": not findings and metrics["obligation_chain_coverage"] == 1.0,
        "findings": findings,
        "metrics": metrics,
        "authorizes": [],
    }
