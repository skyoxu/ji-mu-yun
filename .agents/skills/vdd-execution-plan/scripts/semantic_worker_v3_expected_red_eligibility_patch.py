"""Validate which V3 failure intents may become Q3 expected-RED markers.

The independent Q3 judge compares the observed runtime marker set with the VDD
failure intents classified as ``expected-red``. That family is therefore an
execution role, not a generic label for every constraint mentioned near a RED
requirement.

This patch composes with the existing frozen-domain validator. A failure intent
may use ``expected-red`` only when every bound frozen obligation describes an
executable behavior/quality and is not governance. Constraint/governance
obligations remain in the semantic plan, but must use the non-expected family
that describes their actual guard (for example artifact integrity, target
binding, harness failure, or semantic contract gap).

Invalid initial V3 output enters the existing one-attempt schema-repair lane.
Invalid repaired or missing-only completion output remains fail-closed. No
failure intent is silently dropped or reclassified, and failure IDs are never
used as semantic heuristics.
"""
from __future__ import annotations

from typing import Any, Mapping

import semantic_worker_v3_domain_patch as domain


_BASE_DOMAIN_FINDINGS = domain._domain_findings
_RUNTIME_EXPECTED_RED_KINDS = frozenset({"behavior", "quality"})


def _expected_red_eligibility_findings(
    stage: str,
    payload: Mapping[str, Any],
    value: Mapping[str, Any],
) -> list[str]:
    if stage != "v3" and not stage.startswith("v3-schema-repair"):
        return []

    obligations = domain._obligations_from_payload(stage, payload)
    known = {
        str(item.get("obligation_id")): item
        for item in obligations
        if isinstance(item.get("obligation_id"), str) and item.get("obligation_id")
    }
    failures = value.get("failure_intents")
    if not isinstance(failures, list):
        return []

    findings: list[str] = []
    for index, raw in enumerate(failures):
        if not isinstance(raw, Mapping) or raw.get("failure_family") != "expected-red":
            continue
        ids = raw.get("obligation_ids")
        if not isinstance(ids, list) or not ids:
            continue

        ineligible: list[str] = []
        for raw_oid in ids:
            if not isinstance(raw_oid, str):
                continue
            obligation = known.get(raw_oid)
            if not isinstance(obligation, Mapping):
                continue
            kind = obligation.get("obligation_kind")
            requirement_type = obligation.get("requirement_type")
            if (
                kind not in _RUNTIME_EXPECTED_RED_KINDS
                or requirement_type == "Governance"
            ):
                ineligible.append(
                    f"{raw_oid}={kind or 'missing-kind'}/{requirement_type or 'missing-type'}"
                )

        if ineligible:
            findings.append(
                f"v3-expected-red:failure_intents[{index}]:"
                "runtime-marker-ineligible:"
                + ",".join(sorted(ineligible))
            )
    return findings


def _domain_findings(
    stage: str,
    payload: Mapping[str, Any],
    value: Mapping[str, Any],
) -> list[str]:
    return [
        *_BASE_DOMAIN_FINDINGS(stage, payload, value),
        *_expected_red_eligibility_findings(stage, payload, value),
    ]


def install() -> None:
    domain._domain_findings = _domain_findings


install()
