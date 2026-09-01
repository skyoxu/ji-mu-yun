"""Deterministic pre-execution stop-loss for repeated Quick Dev failures.

The guard runs before the public stable runner executes a selector.  Two
consecutive identical deterministic failure fingerprints for the same candidate
and selector block the third identical attempt.  A candidate or selector change
clears the stop-loss without rewriting prior evidence.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from runtime_evidence import HASH_RE, selector_identity_from_descriptor, validate_descriptor


THRESHOLD = 2


def repeat_guard(
    *,
    descriptor: Mapping[str, Any],
    history: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    validate_descriptor(descriptor)
    candidate_hash = descriptor["candidate_hash"]
    selector_identity = selector_identity_from_descriptor(descriptor)

    comparable: list[tuple[str, str, str]] = []
    for index, item in enumerate(history):
        if not isinstance(item, Mapping):
            raise ValueError(f"failure history[{index}] must be object")
        fingerprint = item.get("failure_fingerprint")
        prior_candidate = item.get("candidate_hash")
        prior_selector = item.get("selector_identity")
        if fingerprint is None:
            continue
        if not isinstance(fingerprint, str) or not HASH_RE.fullmatch(fingerprint):
            raise ValueError(f"failure history[{index}] fingerprint invalid")
        if not isinstance(prior_candidate, str) or not HASH_RE.fullmatch(prior_candidate):
            raise ValueError(f"failure history[{index}] candidate invalid")
        if not isinstance(prior_selector, str) or not HASH_RE.fullmatch(prior_selector):
            raise ValueError(f"failure history[{index}] selector invalid")
        comparable.append((fingerprint, prior_candidate, prior_selector))

    relevant = [row for row in comparable if row[1] == candidate_hash and row[2] == selector_identity]
    repeated = False
    fingerprint: str | None = None
    if len(relevant) >= THRESHOLD:
        tail = relevant[-THRESHOLD:]
        repeated = len({row[0] for row in tail}) == 1
        fingerprint = tail[-1][0] if repeated else None

    if repeated:
        return {
            "schema": "quick-dev.repeat-guard.v1",
            "status": "blocked",
            "failure_family": "repeated-deterministic-failure",
            "failure_fingerprint": fingerprint,
            "candidate_hash": candidate_hash,
            "selector_identity": selector_identity,
            "threshold": THRESHOLD,
            "matching_prior_failures": THRESHOLD,
            "recommended_action": "repair-vdd",
            "tests_executed": False,
            "process_attempts": 0,
            "authorizes": [],
        }
    return {
        "schema": "quick-dev.repeat-guard.v1",
        "status": "continue",
        "candidate_hash": candidate_hash,
        "selector_identity": selector_identity,
        "threshold": THRESHOLD,
        "matching_prior_failures": len(relevant),
        "tests_executed": False,
        "process_attempts": 0,
        "authorizes": [],
    }
