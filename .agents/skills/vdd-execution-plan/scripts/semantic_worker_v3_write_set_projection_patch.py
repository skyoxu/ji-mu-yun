"""Normalize repaired V3 owner/write-set identity without inventing paths.

This wrapper is intentionally transparent to future grouped projection keyword
arguments (for example refs_by_oid). It only unions already-declared owners into
allowed_write_paths and removes the exact owner overlap from forbidden_paths.
"""
from __future__ import annotations

from typing import Any, Mapping

import semantic_worker_v3_group_repair_patch as grouped

_BASE_PROJECT = grouped._project


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str) and item]


def project_with_owner_write_set(value: Mapping[str, Any], **kwargs: Any) -> dict[str, Any]:
    result = _BASE_PROJECT(value, **kwargs)
    hints = result.get("slice_hints")
    if not isinstance(hints, list):
        return result
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(hints):
        if not isinstance(raw, Mapping):
            raise ValueError(f"V3 repaired slice hint {index} is not object")
        hint = dict(raw)
        owners = set(_strings(hint.get("production_owners")))
        allowed = set(_strings(hint.get("allowed_write_paths")))
        forbidden = set(_strings(hint.get("forbidden_paths")))
        hint["allowed_write_paths"] = sorted(allowed | owners)
        hint["forbidden_paths"] = sorted(forbidden - owners)
        normalized.append(hint)
    result["slice_hints"] = normalized
    return result


def install() -> None:
    grouped._project = project_with_owner_write_set


install()
