"""Constrain grouped V3 repair to canonical subject and production-owner domains.

The one-shot grouped repair remains model-authored. This layer enforces two
canonical invariants after the worker has returned its normal structured shape:

* one Acceptance group may reference obligation IDs from exactly one frozen
  subject domain, matching canonical V3A overbroad-subject semantics;
* when a repaired hint names no real production owner but its own rollback scope
  already names real production paths, those declared production paths become
  the repaired production owners and are included in the write set.

Subject compatibility is deliberately validated after structured output
instead of encoded with JSON-Schema composition keywords. Codex structured
output accepts only a supported JSON-Schema subset, while the deterministic
validator remains authoritative and fail-closed.

When rollback recovery promotes an already-declared production path to owner,
the same path is removed from forbidden_paths because canonical V7 requires a
production owner to be writable. Only that exact owner overlap is normalized;
all unrelated forbidden paths remain unchanged.

No repository-wide owner guessing, sibling-group borrowing, semantic retry, or
truth-gate relaxation is performed. If neither the declared owners nor the
hint's own rollback production paths resolve to real files, the downstream V3
execution-contract continues to fail closed.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import semantic_compiler_gate as gate
import semantic_worker_v3_group_repair_patch as grouped

_BASE_GROUP_TRANSPORT = gate._ORIGINAL_INVOKE_WORKER


def _obligation_subjects(payload: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in grouped._repair_obligations(payload):
        oid = item.get("obligation_id")
        subject = item.get("subject")
        if isinstance(oid, str) and oid and isinstance(subject, str) and subject.strip():
            result[oid] = subject.strip()
    if not result:
        raise ValueError("V3 grouped repair has no frozen subject domain")
    return result


def _validate_subject_domains(payload: Mapping[str, Any], value: Mapping[str, Any]) -> None:
    subjects_by_id = _obligation_subjects(payload)
    acceptances = value.get("acceptances")
    if not isinstance(acceptances, list) or not acceptances:
        return
    findings: list[str] = []
    for index, raw in enumerate(acceptances):
        if not isinstance(raw, Mapping):
            continue
        ids = raw.get("obligation_ids")
        if not isinstance(ids, list) or not ids:
            continue
        unknown = sorted({str(oid) for oid in ids if isinstance(oid, str)} - set(subjects_by_id))
        if unknown:
            findings.append(
                f"acceptances[{index}]:unknown-obligation-id:" + ",".join(unknown)
            )
            continue
        subjects = sorted({subjects_by_id[str(oid)] for oid in ids if isinstance(oid, str)})
        if len(subjects) > 1:
            findings.append(
                f"acceptances[{index}]:overbroad-subject:" + ",".join(subjects)
            )
    if findings:
        raise ValueError("V3 grouped repair subject validation failed: " + "; ".join(findings))


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

    owners = set(_strings(hint.get("production_owners")))
    allowed = set(_strings(hint.get("allowed_write_paths")))
    forbidden = set(_strings(hint.get("forbidden_paths")))
    hint["allowed_write_paths"] = sorted(allowed | owners)
    hint["forbidden_paths"] = sorted(forbidden - owners)
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
    _validate_subject_domains(payload, value)
    return _normalize_repaired_value(Path(root), value)


def install() -> None:
    # Compose over the grouped transport so injected and live repair results share
    # the same deterministic subject and owner checks before execution-contract.
    gate._ORIGINAL_INVOKE_WORKER = group_safety_transport


install()
