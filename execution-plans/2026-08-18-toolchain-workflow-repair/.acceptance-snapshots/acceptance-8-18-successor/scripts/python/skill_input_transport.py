"""Deterministic bounded transport planning for Skill input snapshots."""

from __future__ import annotations

from typing import Any


def plan_transport(page_bytes: int, max_snapshot_bytes: int, *, content_hash: str) -> dict[str, Any]:
    if not isinstance(page_bytes, int) or page_bytes <= 0:
        raise ValueError("page_bytes must be positive")
    if not isinstance(max_snapshot_bytes, int) or max_snapshot_bytes <= 0:
        raise ValueError("max_snapshot_bytes must be positive")
    if not isinstance(content_hash, str) or not content_hash.startswith("sha256:"):
        raise ValueError("content_hash is invalid")
    pages = (max_snapshot_bytes + page_bytes - 1) // page_bytes
    return {"page_bytes": page_bytes, "max_snapshot_bytes": max_snapshot_bytes, "pages": pages, "content_hash": content_hash, "next_offset": 0}


def resume_transport(plan: dict[str, Any], *, content_hash: str) -> dict[str, Any]:
    if not isinstance(plan, dict) or plan.get("content_hash") != content_hash:
        raise ValueError("stale continuation")
    result = dict(plan)
    result["resumed"] = True
    return result
