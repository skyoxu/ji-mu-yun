"""Validate and freeze Refactor Acceptance knowledge before run input publication."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from acceptance_core import InputError, canonical_hash


def _repository_root(target_root: Path) -> Path:
    for candidate in (target_root, *target_root.parents):
        if (candidate / ".git").exists() and (candidate / "knowledge").is_dir():
            return candidate
    raise InputError("repository root for knowledge validation is unavailable")


def _validator(repository_root: Path):
    module_path = repository_root / "scripts" / "python" / "knowledge_context_validation.py"
    spec = importlib.util.spec_from_file_location("refactor_acceptance_knowledge_context_validation", module_path)
    if spec is None or spec.loader is None:
        raise InputError("knowledge context validator is unavailable")
    module = importlib.util.module_from_spec(spec)
    previous_path = list(sys.path)
    try:
        sys.path.insert(0, str(module_path.parent))
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = previous_path
    return module


def freeze_knowledge_context(target_root: Path, raw_path: str) -> dict[str, Any]:
    relative = Path(raw_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise InputError("knowledge context path must stay inside the target root")
    path = (target_root / relative).resolve()
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
    )
    if failure_code:
        raise InputError(f"knowledge context is invalid: {failure_code}")
    if document.get("consumer") != "refactor-acceptance":
        raise InputError("knowledge context consumer must be refactor-acceptance")
    preflight = document.get("preflight")
    if not isinstance(preflight, dict) or preflight.get("status") != "ready":
        raise InputError("knowledge context preflight is not ready")
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
