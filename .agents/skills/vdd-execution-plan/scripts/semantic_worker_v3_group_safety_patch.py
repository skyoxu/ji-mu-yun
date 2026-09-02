"""Constrain grouped V3 repair to canonical subject and production-owner domains.

The one-shot grouped repair remains model-authored.  This layer only makes two
canonical invariants structural before the existing V3 validators run:

* one Acceptance group may reference obligation IDs from exactly one frozen
  subject domain, matching canonical V3A overbroad-subject semantics;
* when a repaired hint names no real production owner but its own rollback scope
  already names real production paths, those declared production paths become
  the repaired production owners and are included in the write set.

No repository-wide owner guessing, sibling-group borrowing, semantic retry, or
truth-gate relaxation is performed.  If neither the declared owners nor the
hint's own rollback production paths resolve to real files, the downstream V3
execution-contract continues to fail closed.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import semantic_compiler_gate as gate
import semantic_worker_v3_group_repair_patch as grouped

_BASE_GROUP_SCHEMA = grouped._group_schema
_BASE_GROUP_TRANSPORT = gate._ORIGINAL_INVOKE_WORKER


def _subject_domains(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    by_subject: dict[str, list[str]] = {}
    for item in grouped._repair_obligations(payload):
        oid = item.get("obligation_id")
        subject = item.get("subject")
        if not isinstance(oid, str) or not oid or not isinstance(subject, str) or not subject.strip():
            continue
        by_subject.setdefault(subject.strip(), []).append(oid)
    domains: list[dict[str, Any]] = []
    for subject in sorted(by_subject):
        ids = sorted(set(by_subject[subject]))
        if not ids:
            continue
        domains.append(
            {
                "type": "array",
                "minItems": 1,
                "uniqueItems": True,
                "items": {"type": "string", "enum": ids},
            }
        )
    if not domains:
        raise ValueError("V3 grouped repair has no frozen subject domains")
    return domains


def _group_schema(payload: Mapping[str, Any]) -> dict[str, Any]:
    schema = deepcopy(_BASE_GROUP_SCHEMA(payload))
    try:
        group = schema["properties"]["groups"]["items"]
        group["properties"]["obligation_ids"] = {"oneOf": _subject_domains(payload)}
    except (KeyError, TypeError) as exc:
        raise ValueError("V3 grouped repair schema shape is unavailable") from exc
    return schema


def _real_file(root: Path, raw: str) -> bool:
    try:
        path = (root / raw).resolve()
        path.relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return path.is_file() and not path.is_symlink()


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if isinstance(item, str) and item.strip()]


def _normalize_hint(root: Path, raw: Mapping[str, Any]) -> dict[str, Any]:
    hint = dict(raw)
    owners = _strings(hint.get("production_owners"))
    real_owners = [owner for owner in owners if _real_file(root, owner)]

    if not real_owners:
        rollback = hint.get("rollback_scope")
        production_paths = _strings(rollback.get("production_paths")) if isinstance(rollback, Mapping) else []
        rollback_real = [path for path in production_paths if _real_file(root, path)]
        if rollback_real:
            owners = sorted(set(rollback_real))
            hint["production_owners"] = owners

    owners = _strings(hint.get("production_owners"))
    forbidden = set(_strings(hint.get("forbidden_paths")))
    conflict = sorted(set(owners) & forbidden)
    if conflict:
        raise ValueError("V3 grouped repair production owner is forbidden: " + ",".join(conflict))

    allowed = set(_strings(hint.get("allowed_write_paths")))
    allowed.update(owners)
    hint["allowed_write_paths"] = sorted(allowed)
    return hint


def _normalize_repaired_value(root: Path, value: Mapping[str, Any]) -> Mapping[str, Any]:
    hints = value.get("slice_hints")
    if not isinstance(hints, list):
        return value
    normalized = dict(value)
    normalized["slice_hints"] = [
        _normalize_hint(root, item) if isinstance(item, Mapping) else item
        for item in hints
    ]
    return normalized


def group_safety_transport(
    *,
    root,
    out_dir,
    stage: str,
    payload: Mapping[str, Any],
    prompt: str,
    worker_cache: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    value = _BASE_GROUP_TRANSPORT(
        root=root,
        out_dir=out_dir,
        stage=stage,
        payload=payload,
        prompt=prompt,
        worker_cache=worker_cache,
    )
    if stage != "v3-schema-repair":
        return value
    return _normalize_repaired_value(Path(root), value)


def install() -> None:
    # Live grouped repair resolves this schema global at call time.
    grouped._group_schema = _group_schema
    # Compose over the grouped transport so injected and live repair results share
    # the same deterministic owner normalization before execution-contract checks.
    gate._ORIGINAL_INVOKE_WORKER = group_safety_transport


install()
