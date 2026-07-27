"""Verify that Quick Dev consumes, but never expands, VDD-frozen knowledge."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


def _validate_context(repository_root: Path, context: dict[str, Any]) -> str | None:
    module_path = repository_root / "scripts" / "python" / "knowledge_context_validation.py"
    spec = importlib.util.spec_from_file_location("quick_dev_knowledge_context_validation", module_path)
    if spec is None or spec.loader is None:
        return "context_validator_unavailable"
    module = importlib.util.module_from_spec(spec)
    previous_path = list(sys.path)
    try:
        sys.path.insert(0, str(module_path.parent))
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = previous_path
    return module.validate_context(
        context,
        repository_root=repository_root,
        verify_catalog=True,
        verify_sources=True,
    )


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


def verify_plan_context(repository_root: Path, plan_dir: Path) -> dict[str, Any]:
    """Fail closed when a declared VDD context no longer matches local sources."""
    context_path = plan_dir / "knowledge-context.v1.json"
    if not context_path.is_file():
        return {"status": "not-declared"}
    try:
        context = json.loads(context_path.read_text(encoding="utf-8"))
        failure_code = _validate_context(repository_root.resolve(), context)
        if failure_code:
            return {"status": "vdd-repair", "failure_code": "KWI-QUICK-FROZEN-CONTEXT-STALE", "detail": failure_code}
    except (AttributeError, ImportError, KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return {"status": "vdd-repair", "failure_code": "KWI-QUICK-FROZEN-CONTEXT-STALE"}
    return {"status": "verified"}
