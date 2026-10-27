"""Validate and freeze Refactor Acceptance knowledge before run input publication."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from acceptance_core import InputError, canonical_hash


def _repository_root(target_root: Path) -> Path:
    roots = [candidate for candidate in (target_root, *target_root.parents)
             if (candidate / ".git").exists() and (candidate / "knowledge").is_dir()]
    if len(roots) > 1:
        raise InputError("knowledge validation repository root is ambiguous")
    if roots:
        return roots[0]
    raise InputError("repository root for knowledge validation is unavailable")


def _validator(repository_root: Path):
    # ADR-0053/0058: execute actual main bytes, never candidate validator code.
    from trusted_knowledge_validator import TrustedMainValidator
    try:
        return TrustedMainValidator(repository_root, error_type=InputError)
    except (ValueError, OSError) as exc:
        raise InputError(str(exc)) from exc


def freeze_knowledge_context(target_root: Path, raw_path: str) -> dict[str, Any]:
    relative = Path(raw_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise InputError("knowledge context path must stay inside the target root")
    unresolved = target_root / relative
    current = target_root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise InputError("knowledge context path must not use symlinks")
    path = unresolved.resolve()
    try:
        path.relative_to(target_root)
    except ValueError as exc:
        raise InputError("knowledge context path escapes the target root") from exc
    try:
        context_bytes = path.read_bytes()
        document = json.loads(context_bytes.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InputError("knowledge context is unreadable") from exc
    repository_root = _repository_root(target_root)
    validation = _validator(repository_root)
    failure_code = validation.validate_context(
        document,
        repository_root=repository_root,
        verify_catalog=True,
        verify_sources=True,
        expected_consumer="refactor-acceptance",
        require_selection=True,
        require_preflight=True,
    )
    if failure_code:
        raise InputError(f"knowledge context is invalid: {failure_code}")
    worktree_failure = validation.validate_worktree_sources(document, repository_root)
    if worktree_failure:
        raise InputError(f"knowledge context is invalid: {worktree_failure}")
    if document.get("consumer") != "refactor-acceptance":
        raise InputError("knowledge context consumer must be refactor-acceptance")
    preflight = document.get("preflight")
    if not isinstance(preflight, dict) or preflight.get("status") != "ready":
        raise InputError("knowledge context preflight is not ready")
    catalog_failure = validation.validate_catalog_freshness(repository_root)
    if catalog_failure not in {None, "catalog_stale"}:
        raise InputError(f"knowledge context catalog is invalid: {catalog_failure}")
    expected_freshness = "degraded" if catalog_failure == "catalog_stale" else "current"
    if preflight.get("knowledge_freshness") != expected_freshness:
        raise InputError("knowledge context freshness declaration is invalid")
    expected_catalog_failure = "catalog_stale" if expected_freshness == "degraded" else None
    if preflight.get("catalog_failure_code") != expected_catalog_failure:
        raise InputError("knowledge context catalog freshness evidence is invalid")
    accepted = [
        decision
        for decision in document.get("decisions", [])
        if isinstance(decision, dict) and decision.get("decision") == "accepted"
    ]
    return {
        "path": relative.as_posix(),
        "sha256": "sha256:" + hashlib.sha256(context_bytes).hexdigest(),
        "contextHash": canonical_hash(document),
        "requestHash": document["request_sha256"],
        "resultHash": document["result_sha256"],
        "sourceSnapshotId": document["locator_result"].get("source_snapshot_id"),
        "acceptedDecisions": accepted,
        "authorizes": [],
    }


def refresh_context_read_set(context: dict[str, Any], repository_root: Path) -> dict[str, Any]:
    """Refresh bytes with the shared validated selected-read-set primitive."""
    validation = _validator(repository_root.resolve())
    refreshed = validation.refresh_context_read_set(context, repository_root.resolve())
    if not isinstance(refreshed, dict):
        raise InputError("knowledge read-set refresh is invalid")
    return refreshed
