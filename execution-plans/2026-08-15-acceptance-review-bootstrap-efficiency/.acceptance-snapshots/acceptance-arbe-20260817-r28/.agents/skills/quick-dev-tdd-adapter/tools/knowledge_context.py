"""Verify that Quick Dev consumes, but never expands, VDD-frozen knowledge."""

from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


def _validator(repository_root: Path):
    module_path = repository_root / "scripts" / "python" / "knowledge_context_validation.py"
    for relative in ("scripts/python/knowledge_context_validation.py", "scripts/python/_knowledge_locator_core.py"):
        current = subprocess.run(
            ["git", "-C", str(repository_root), "show", f"refs/heads/main:{relative}"],
            capture_output=True,
            check=False,
        )
        if current.returncode or (repository_root / relative).read_bytes() != current.stdout:
            raise ImportError("context_validator_not_main_bound")
    spec = importlib.util.spec_from_file_location("quick_dev_knowledge_context_validation", module_path)
    if spec is None or spec.loader is None:
        raise ImportError("context_validator_unavailable")
    module = importlib.util.module_from_spec(spec)
    previous_path = list(sys.path)
    try:
        sys.path.insert(0, str(module_path.parent))
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = previous_path
    return module


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


def _accepted_worktree_projection(context: dict[str, Any]) -> dict[str, Any]:
    """Keep stale, unconsumed Locator candidates out of the execution gate."""
    accepted = {
        (decision["candidate"]["path"], decision["candidate"]["source_sha256"])
        for decision in context.get("decisions", [])
        if isinstance(decision, dict)
        and decision.get("decision") == "accepted"
        and isinstance(decision.get("candidate"), dict)
        and isinstance(decision["candidate"].get("path"), str)
        and isinstance(decision["candidate"].get("source_sha256"), str)
    }
    projected = dict(context)
    result = context.get("locator_result")
    if not isinstance(result, dict):
        return projected
    projected_result = dict(result)
    candidates = result.get("candidates")
    if isinstance(candidates, list):
        projected_result["candidates"] = [
            candidate for candidate in candidates
            if isinstance(candidate, dict)
            and (candidate.get("path"), candidate.get("source_sha256")) in accepted
        ]
    projected["locator_result"] = projected_result
    return projected


def verify_plan_context(repository_root: Path, plan_dir: Path) -> dict[str, Any]:
    """Fail closed when a declared VDD context no longer matches local sources."""
    context_path = plan_dir / "knowledge-context.v1.json"
    freeze_path = plan_dir / "knowledge-context.freeze.v1.json"
    if not context_path.is_file():
        return {"status": "not-declared"}
    if not freeze_path.is_file():
        return {"status": "vdd-repair", "failure_code": "KWI-QUICK-FROZEN-CONTEXT-STALE", "detail": "freeze_receipt_missing"}
    try:
        context_bytes = context_path.read_bytes()
        freeze_bytes = freeze_path.read_bytes()
        context = json.loads(context_bytes.decode("utf-8"))
        freeze = json.loads(freeze_bytes.decode("utf-8"))
        validator = _validator(repository_root.resolve())
        failure_code = validator.validate_context(
            context,
            repository_root=repository_root.resolve(),
            verify_catalog=True,
            verify_sources=False,
            expected_consumer="vdd",
            require_preflight=True,
        )
        if failure_code:
            return {"status": "vdd-repair", "failure_code": "KWI-QUICK-FROZEN-CONTEXT-STALE", "detail": failure_code}
        worktree_failure = validator.validate_worktree_sources(
            _accepted_worktree_projection(context), repository_root.resolve()
        )
        if worktree_failure:
            return {"status": "vdd-repair", "failure_code": "KWI-QUICK-FROZEN-CONTEXT-STALE", "detail": worktree_failure}
        accepted = [
            {
                "path": decision["candidate"]["path"],
                "source_sha256": decision["candidate"]["source_sha256"],
                "satisfies": sorted(decision["satisfies"]),
            }
            for decision in context["decisions"]
            if decision.get("decision") == "accepted"
        ]
        if (
            freeze.get("schema_version") != "jimuyun.vdd-knowledge-freeze.v1"
            or freeze.get("context_path") != context_path.name
            or freeze.get("context_sha256") != "sha256:" + hashlib.sha256(context_bytes).hexdigest()
            or freeze.get("canonical_context_sha256") != validator.canonical_hash(context)
            or freeze.get("request_sha256") != context.get("request_sha256")
            or freeze.get("result_sha256") != context.get("result_sha256")
            or freeze.get("snapshot") != context["locator_request"].get("snapshot")
            or freeze.get("source_snapshot_id") != context["locator_result"].get("source_snapshot_id")
            or freeze.get("policy_revision") != context["locator_request"].get("policy_revision")
            or freeze.get("accepted") != accepted
            or freeze.get("authorizes") != []
        ):
            return {"status": "vdd-repair", "failure_code": "KWI-QUICK-FROZEN-CONTEXT-STALE", "detail": "freeze_receipt_mismatch"}
    except (AttributeError, ImportError, KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return {"status": "vdd-repair", "failure_code": "KWI-QUICK-FROZEN-CONTEXT-STALE"}
    return {"status": "verified"}
