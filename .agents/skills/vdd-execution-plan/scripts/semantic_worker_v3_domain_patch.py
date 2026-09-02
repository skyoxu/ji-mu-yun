"""Constrain V3 semantic-worker references to the frozen obligation domain.

V3 may only compile Acceptance/RED/slice candidates from the obligations supplied
by the deterministic compiler.  Unknown obligation IDs or mismatched source refs
are transport-contract failures: the existing one-shot schema-repair lane may
correct them once, but the compiler never silently drops or rewrites references.
"""
from __future__ import annotations

from typing import Any, Mapping

import semantic_compiler_gate as gate
import semantic_worker_transport_patch  # noqa: F401  # install structured transport first

_BASE_TRANSPORT = gate._ORIGINAL_INVOKE_WORKER


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
                expected_refs = sorted({
                    str(ref)
                    for oid in ids
                    for ref in known[str(oid)].get("source_refs", [])
                    if isinstance(ref, str) and ref
                })
                raw_refs = raw.get("source_refs")
                if not isinstance(raw_refs, list) or sorted(set(str(ref) for ref in raw_refs if isinstance(ref, str))) != expected_refs:
                    findings.append(f"v3-domain:{label}[{index}]:source-ref-binding-mismatch")
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
