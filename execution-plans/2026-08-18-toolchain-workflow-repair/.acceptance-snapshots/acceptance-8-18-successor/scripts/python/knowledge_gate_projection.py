"""Pure projection of execution, publication, and review knowledge gates."""

from __future__ import annotations

from typing import Any


def project_knowledge_gates(*, catalog_stale: bool, read_set_same: bool, source_bytes_same: bool) -> dict[str, Any]:
    if catalog_stale and read_set_same and source_bytes_same:
        return {"route": "degraded-continuation", "publication_allowed": False, "review_required": False}
    if read_set_same and not source_bytes_same:
        return {"route": "successor-refresh", "publication_allowed": False, "review_required": False}
    return {"route": "repair-required", "publication_allowed": False, "review_required": True}
