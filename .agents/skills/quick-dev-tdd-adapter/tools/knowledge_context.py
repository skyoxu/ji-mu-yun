"""Verify that Quick Dev consumes, but never expands, VDD-frozen knowledge."""

from __future__ import annotations

from typing import Any


def _canonical(value: dict[str, Any]) -> tuple[str, str, tuple[str, ...]]:
    path, digest, satisfies = value.get("path"), value.get("source_sha256"), value.get("satisfies")
    if not isinstance(path, str) or not isinstance(digest, str) or not isinstance(satisfies, list) or any(not isinstance(item, str) for item in satisfies):
        raise ValueError("invalid frozen knowledge decision")
    return path, digest, tuple(sorted(satisfies))


def verify_frozen_context(frozen: dict[str, Any], proposed: dict[str, Any]) -> dict[str, Any]:
    try:
        frozen_entries = {_canonical(value) for value in frozen.get("accepted", [])}
        proposed_entries = {_canonical(value) for value in proposed.get("accepted", [])}
    except (AttributeError, TypeError, ValueError):
        return {"status": "vdd-repair", "failure_code": "KWI-QUICK-SCOPE-EXPANSION"}
    if frozen_entries != proposed_entries:
        return {"status": "vdd-repair", "failure_code": "KWI-QUICK-SCOPE-EXPANSION"}
    return {"status": "verified", "accepted": len(frozen_entries)}
