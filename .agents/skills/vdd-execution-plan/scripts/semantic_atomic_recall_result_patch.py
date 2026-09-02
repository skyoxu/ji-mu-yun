"""Correct V4 atomic-recall diagnostics without weakening the gate.

The canonical V4 implementation correctly blocks unknown obligation ids, but its
partition diagnostic also fires when the only difference is an extra unknown id
and then renders an empty missing-id suffix.  Keep unknown-id findings blocking;
only remove the empty partition finding because no known obligation is missing.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import semantic_compiler_gate as gate

_BASE_ATOMIC_RECALL_ALIGNMENT = gate.atomic_recall_alignment
_EMPTY_PARTITION_FINDING = "atomic-recall:obligation-partition-incomplete:"


def _normalize_result(result: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(result)
    findings = [str(item) for item in result.get("findings", [])]
    cleaned = [item for item in findings if item != _EMPTY_PARTITION_FINDING]
    normalized["findings"] = cleaned
    normalized["valid"] = not cleaned

    worker = result.get("worker")
    unknown_supported = [item for item in cleaned if item.startswith("atomic-recall:unknown-supported:")]
    unknown_invented = [item for item in cleaned if item.startswith("atomic-recall:unknown-invented:")]
    normalized["protocol_metrics"] = {
        "unknown_supported_finding_count": len(unknown_supported),
        "unknown_invented_finding_count": len(unknown_invented),
        "worker_result_present": isinstance(worker, Mapping),
    }
    return normalized


def atomic_recall_alignment(
    *,
    root,
    out_dir,
    source_index: Mapping[str, Any],
    obligations: Sequence[Mapping[str, Any]],
    worker_cache: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return _normalize_result(
        _BASE_ATOMIC_RECALL_ALIGNMENT(
            root=root,
            out_dir=out_dir,
            source_index=source_index,
            obligations=obligations,
            worker_cache=worker_cache,
        )
    )


def install() -> None:
    gate.atomic_recall_alignment = atomic_recall_alignment


install()
