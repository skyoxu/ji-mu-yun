"""Constrain V3 semantic-worker references to the frozen obligation domain.

V3 may only compile Acceptance/RED/slice candidates from the obligations supplied
by the deterministic compiler.  Unknown obligation IDs or mismatched source refs
are transport-contract failures: the existing one-shot schema-repair lane may
correct them once, but the compiler never silently drops or rewrites references.
"""
from __future__ import annotations

import json
from typing import Any, Mapping

import semantic_compiler_gate as gate
import semantic_worker_transport_patch  # noqa: F401  # install structured transport first

_BASE_TRANSPORT = gate._ORIGINAL_INVOKE_WORKER


def _cloned_oracle_findings(known: Mapping[str, Any], value: Mapping[str, Any]) -> list[str]:
    """ADR-0041: an identical multi-behavior oracle cannot prove distinct atomic semantics.

    This detects exact clones, not natural-language equivalence. Independent V4
    remains responsible for judging each oracle against the frozen source.
    """
    seen: dict[str, tuple[str, str]] = {}
    findings: list[str] = []
    acceptances = value.get("acceptances")
    if not isinstance(acceptances, list):
        return findings
    for item in acceptances:
        if not isinstance(item, Mapping):
            continue
        ids = item.get("obligation_ids")
        if (not isinstance(ids, list) or len(ids) != 1
                or not isinstance(ids[0], str) or ids[0] not in known):
            continue
        obligation = known[ids[0]]
        if not obligation.get("expected_behavior") or not isinstance(item.get("oracle"), Mapping):
            continue
        assertions = item.get("assertion_ids")
        if not isinstance(assertions, list) or any(not isinstance(aid, str) for aid in assertions):
            continue
        oracle_key = json.dumps({
            "oracle": item["oracle"],
            "assertions": sorted(assertions),
        }, sort_keys=True, ensure_ascii=False)
        semantics = json.dumps({name: obligation.get(name) for name in (
            "subject", "trigger", "state_before", "state_after", "expected_behavior", "observable_result"
        )}, sort_keys=True, ensure_ascii=False)
        prior = seen.get(oracle_key)
        if prior is not None and prior[1] != semantics:
            findings.append("v3-domain:cloned-oracle-across-obligations:" + prior[0] + "," + ids[0])
        else:
            seen[oracle_key] = (ids[0], semantics)
    return findings


def _obligations_from_payload(stage: str, payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    candidate: Any = payload
    if stage.startswith("v3-schema-repair"):
        candidate = payload.get("input")
    if not isinstance(candidate, Mapping):
        return []
    values = candidate.get("obligations")
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, Mapping)]


def _domain_findings(stage: str, payload: Mapping[str, Any], value: Mapping[str, Any]) -> list[str]:
    if stage != "v3" and not stage.startswith("v3-schema-repair"):
        return []
    obligations = _obligations_from_payload(stage, payload)
    known = {
        str(item.get("obligation_id")): item
        for item in obligations
        if isinstance(item.get("obligation_id"), str) and str(item.get("obligation_id"))
    }
    if not known:
        return ["v3-domain:frozen-obligations-unavailable"]

    findings: list[str] = []
    for label in ("acceptances", "failure_intents", "slice_hints"):
        values = value.get(label)
        if not isinstance(values, list):
            continue
        for index, raw in enumerate(values):
            if not isinstance(raw, Mapping):
                continue
            ids = raw.get("obligation_ids")
            if not isinstance(ids, list) or not ids or any(not isinstance(oid, str) or not oid for oid in ids):
                continue
            if len(ids) != len(set(ids)):
                findings.append(f"v3-domain:{label}[{index}]:duplicate-obligation-id")
            unknown = sorted({str(oid) for oid in ids if str(oid) not in known})
            if unknown:
                findings.append(f"v3-domain:{label}[{index}]:unknown-obligation:" + ",".join(unknown))
                continue
            if label == "acceptances":
                if len(ids) != 1:
                    findings.append(f"v3-domain:acceptances[{index}]:per-obligation-contract-required")
                if any(known[oid].get("status", "active") != "active" for oid in ids):
                    findings.append(f"v3-domain:acceptances[{index}]:inactive-obligation")
                expected_refs = sorted({
                    str(ref)
                    for oid in ids
                    for ref in known[str(oid)].get("source_refs", [])
                    if isinstance(ref, str) and ref
                })
                raw_refs = raw.get("source_refs")
                if not isinstance(raw_refs, list) or sorted(set(str(ref) for ref in raw_refs if isinstance(ref, str))) != expected_refs:
                    findings.append(f"v3-domain:{label}[{index}]:source-ref-binding-mismatch")
    findings.extend(_cloned_oracle_findings(known, value))
    return findings


def domain_transport_invoke_worker(
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
    findings = _domain_findings(stage, payload, value)
    if findings:
        raise ValueError("V3 frozen-domain validation failed: " + "; ".join(findings))
    return value


def install() -> None:
    gate._ORIGINAL_INVOKE_WORKER = domain_transport_invoke_worker


install()
