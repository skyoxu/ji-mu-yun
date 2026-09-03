"""Validate relational V3 semantic-worker contracts at the model boundary.

The worker may use a multi-obligation set to express one genuinely shared
implementation context. The V3 execution-contract deterministically projects
such an unambiguous set to atomic canonical Acceptance records before stable
IDs. Relational validation still requires exact set identity across Acceptance,
RED intent and slice hint and rejects overlaps/duplicates through downstream
canonical checks.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

import semantic_compiler_gate as gate
import semantic_worker_contract_patch  # noqa: F401

_BASE_SCHEMA_FINDINGS = gate._worker_schema_findings
_BASE_NORMATIVE_INVOKE = gate.normative_invoke_worker


def _obligation_key(value: Any) -> tuple[str, ...] | None:
    if not isinstance(value, list) or not value:
        return None
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            return None
        normalized.append(item.strip())
    return tuple(sorted(set(normalized)))


def _key_text(key: tuple[str, ...]) -> str:
    return ",".join(key)


def _worker_schema_findings(stage: str, value: Mapping[str, Any]) -> list[str]:
    findings = list(_BASE_SCHEMA_FINDINGS(stage, value))
    if stage != "v3":
        return findings

    acceptances = value.get("acceptances")
    failures = value.get("failure_intents")
    hints = value.get("slice_hints")
    if not isinstance(acceptances, list) or not isinstance(failures, list) or not isinstance(hints, list):
        return findings

    acceptance_keys = [key for raw in acceptances if isinstance(raw, Mapping) for key in [_obligation_key(raw.get("obligation_ids"))] if key is not None]
    failure_keys = [key for raw in failures if isinstance(raw, Mapping) for key in [_obligation_key(raw.get("obligation_ids"))] if key is not None]
    hint_keys = [key for raw in hints if isinstance(raw, Mapping) for key in [_obligation_key(raw.get("obligation_ids"))] if key is not None]

    acceptance_counts = Counter(acceptance_keys)
    failure_counts = Counter(failure_keys)
    hint_counts = Counter(hint_keys)

    for key, count in sorted(acceptance_counts.items()):
        if count != 1:
            findings.append("worker-output:v3-relational:acceptance-obligation-set=" + _key_text(key) + f":count={count}:must-equal-1")

    for key in sorted(acceptance_counts):
        hint_count = hint_counts.get(key, 0)
        if hint_count != 1:
            findings.append("worker-output:v3-relational:acceptance-obligation-set=" + _key_text(key) + f":slice-hint-count={hint_count}:must-equal-1")
        failure_count = failure_counts.get(key, 0)
        if failure_count < 1:
            findings.append("worker-output:v3-relational:acceptance-obligation-set=" + _key_text(key) + ":failure-intent-count=0:must-be-at-least-1")

    for key, count in sorted(hint_counts.items()):
        acceptance_count = acceptance_counts.get(key, 0)
        if acceptance_count != 1:
            findings.append("worker-output:v3-relational:slice-hint-obligation-set=" + _key_text(key) + f":matching-acceptance-count={acceptance_count}:must-equal-1")
        if count > 1:
            findings.append("worker-output:v3-relational:slice-hint-obligation-set=" + _key_text(key) + f":duplicate-count={count}:must-equal-1")

    for key in sorted(failure_counts):
        acceptance_count = acceptance_counts.get(key, 0)
        if acceptance_count != 1:
            findings.append("worker-output:v3-relational:failure-intent-obligation-set=" + _key_text(key) + f":matching-acceptance-count={acceptance_count}:must-equal-1")

    return findings


def _augment_prompt(stage: str, prompt: str) -> str:
    if stage != "v3":
        return prompt
    return prompt + (
        "\n\nSTRICT V3 RELATIONAL CONTRACT: treat each Acceptance obligation_ids array as one normalized set. "
        "Do not emit two Acceptances with the same obligation set. Emit EXACTLY ONE slice_hint for each Acceptance, "
        "and that slice_hint obligation_ids set MUST exactly equal the Acceptance obligation_ids set. Every failure_intent "
        "obligation_ids set MUST exactly equal one and only one Acceptance obligation_ids set. Every Acceptance MUST have "
        "at least one matching failure_intent. When multiple obligations truly share the SAME production owner(s), "
        "verification lane, RED selector/fixture/runtime lifecycle, legal write boundary, and have no predecessor boundary, "
        "prefer ONE shared obligation_ids set so the implementation context is authored once. Do not create different owner "
        "or selector guesses merely because the obligations are semantically atomic. The deterministic V3 boundary will "
        "project an unambiguous shared set to one-obligation canonical Acceptances before stable evidence IDs are generated."
    )


def normative_invoke_worker(
    *,
    root,
    out_dir,
    stage: str,
    payload: Mapping[str, Any],
    prompt: str,
    worker_cache: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    return _BASE_NORMATIVE_INVOKE(
        root=root,
        out_dir=out_dir,
        stage=stage,
        payload=payload,
        prompt=_augment_prompt(stage, prompt),
        worker_cache=worker_cache,
    )


def install() -> None:
    gate._worker_schema_findings = _worker_schema_findings
    gate.normative_invoke_worker = normative_invoke_worker
    gate.sc.invoke_worker = normative_invoke_worker


install()
