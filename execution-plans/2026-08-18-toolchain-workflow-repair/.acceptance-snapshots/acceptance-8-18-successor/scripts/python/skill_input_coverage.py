"""Adapter-owned coverage proof for paged Skill input."""

from __future__ import annotations

from typing import Any, Iterable


def evaluate_coverage(
    *,
    required_pages: Iterable[str],
    observed_pages: Iterable[str],
    source_hash: str | None = None,
    observed_source_hash: str | None = None,
) -> dict[str, Any]:
    required_pages = list(required_pages)
    if any(not isinstance(item, str) or not item for item in required_pages):
        raise ValueError("required page identity is invalid")
    observed_pages = list(observed_pages)
    if any(not isinstance(item, str) or not item for item in observed_pages):
        raise ValueError("observed page identity is invalid")
    required = sorted({item for item in required_pages if isinstance(item, str) and item})
    observed_values = [item for item in observed_pages if isinstance(item, str) and item]
    observed = set(observed_values)
    duplicates = sorted({item for item in observed_values if observed_values.count(item) > 1})
    unexpected = sorted(observed - set(required))
    missing = [item for item in required if item not in observed]
    if source_hash is not None or observed_source_hash is not None:
        if not isinstance(source_hash, str) or not isinstance(observed_source_hash, str):
            raise ValueError("source hash is invalid")
        if source_hash != observed_source_hash:
            return {"status": "stale-source", "missing": missing, "duplicates": duplicates, "unexpected": unexpected, "required": required}
    return {"status": "complete" if not missing and not duplicates and not unexpected else "insufficient", "missing": missing, "duplicates": duplicates, "unexpected": unexpected, "required": required}
