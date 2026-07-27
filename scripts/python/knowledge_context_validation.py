"""Validate a VDD-owned, Locator-bound knowledge context.

This module deliberately binds a single maintainer's local repository state to
the pinned ``main`` knowledge projection.  It provides no multi-writer,
signature, or remote-coordination mechanism.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from _knowledge_locator_core import require_fresh_catalog


CATALOG_RELATIVE = Path("knowledge/catalogs/repository-knowledge-catalog.v1.json")
REQUEST_SCHEMA = "jimuyun.knowledge-locator-request.v1"
RESULT_SCHEMA = "jimuyun.knowledge-locator-result.v1"
CONTEXT_SCHEMA = "jimuyun.vdd-knowledge-context.v1"
DECISION_OWNER = "adapter"
REJECTION_REASONS = {
    "wrong_domain",
    "insufficient_specificity",
    "authority_conflict",
    "duplicate",
}


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _main_source_hashes(repository_root: Path, catalog: dict[str, Any]) -> dict[str, str]:
    paths = {
        entry.get("source_path")
        for entry in catalog.get("entries", [])
        if isinstance(entry, dict) and isinstance(entry.get("source_path"), str)
    }
    values: dict[str, str] = {}
    for path in paths:
        result = subprocess.run(
            ["git", "-C", str(repository_root), "show", f"refs/heads/main:{path}"],
            capture_output=True,
            check=False,
        )
        if result.returncode:
            raise ValueError("catalog_main_source_unavailable")
        values[path] = hashlib.sha256(result.stdout).hexdigest()
    return values


def validate_catalog_freshness(repository_root: Path) -> str | None:
    catalog_path = repository_root / CATALOG_RELATIVE
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        freshness = require_fresh_catalog(catalog, _main_source_hashes(repository_root, catalog))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        return "catalog_invalid"
    if freshness.get("status") != "current":
        return "catalog_stale"
    return None


def _contained_source(repository_root: Path, raw_path: object) -> Path:
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError("candidate_path_invalid")
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise ValueError("candidate_path_outside_repository")
    resolved_root = repository_root.resolve()
    resolved = (resolved_root / candidate).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("candidate_path_outside_repository") from exc
    return resolved


def validate_context(
    payload: dict[str, Any],
    *,
    repository_root: Path | None = None,
    verify_catalog: bool = False,
    verify_sources: bool = False,
) -> str | None:
    """Return a stable failure code, or ``None`` for a complete bound context."""
    if not isinstance(payload, dict) or payload.get("schema_version") != CONTEXT_SCHEMA:
        return "context_schema_invalid"
    request, result = payload.get("locator_request"), payload.get("locator_result")
    required_modules, decisions = payload.get("required_modules"), payload.get("decisions")
    if not isinstance(request, dict) or not isinstance(result, dict) or not isinstance(required_modules, list) or not isinstance(decisions, list):
        return "context_shape_invalid"
    if request.get("schema_version") != REQUEST_SCHEMA or result.get("schema_version") != RESULT_SCHEMA:
        return "locator_schema_invalid"
    if request.get("request_id") != result.get("request_id"):
        return "locator_request_id_mismatch"
    if request.get("snapshot") != result.get("snapshot"):
        return "locator_snapshot_mismatch"
    if payload.get("request_sha256") != canonical_hash(request) or payload.get("result_sha256") != canonical_hash(result):
        return "locator_hash_mismatch"
    snapshot = request.get("snapshot")
    if not isinstance(snapshot, dict) or snapshot.get("ref") != "refs/heads/main" or not isinstance(snapshot.get("commit"), str):
        return "locator_snapshot_invalid"
    if result.get("status") != "matched":
        return "locator_result_not_matched"
    if any(not isinstance(module, str) or not module for module in required_modules):
        return "required_modules_invalid"
    candidates = result.get("candidates")
    if not isinstance(candidates, list):
        return "locator_candidates_invalid"
    available: set[tuple[str, str]] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict) or not isinstance(candidate.get("path"), str) or not isinstance(candidate.get("source_sha256"), str):
            return "locator_candidates_invalid"
        key = (candidate["path"], candidate["source_sha256"])
        if key in available:
            return "locator_candidates_duplicate"
        available.add(key)
    seen: set[tuple[str, str]] = set()
    accepted: list[tuple[str, str]] = []
    satisfied_modules: set[str] = set()
    for decision in decisions:
        if not isinstance(decision, dict) or not isinstance(decision.get("candidate"), dict):
            return "consumption_decision_invalid"
        if decision.get("owner") != DECISION_OWNER:
            return "consumption_decision_owner_invalid"
        candidate = decision["candidate"]
        key = (candidate.get("path"), candidate.get("source_sha256"))
        if key not in available:
            return "accepted_candidate_not_locator_bound"
        if key in seen:
            return "consumption_decision_duplicate"
        seen.add(key)
        satisfies = decision.get("satisfies")
        if not isinstance(satisfies, list) or any(not isinstance(value, str) or not value for value in satisfies):
            return "consumption_modules_invalid"
        if decision.get("decision") == "accepted":
            if not satisfies:
                return "accepted_candidate_missing_coverage"
            accepted.append(key)
            satisfied_modules.update(satisfies)
        elif decision.get("decision") == "rejected":
            if satisfies or decision.get("rejection_reason") not in REJECTION_REASONS:
                return "rejected_candidate_invalid"
        else:
            return "consumption_decision_invalid"
    if seen != available:
        return "locator_candidate_decision_missing"
    if not set(required_modules).issubset(satisfied_modules):
        return "required_modules_unsatisfied"
    if repository_root is None:
        return None
    repository_root = repository_root.resolve()
    if verify_catalog:
        catalog_error = validate_catalog_freshness(repository_root)
        if catalog_error:
            return catalog_error
        catalog = json.loads((repository_root / CATALOG_RELATIVE).read_text(encoding="utf-8"))
        source_snapshot = catalog.get("source_snapshot", {})
        if request.get("snapshot") != {"ref": source_snapshot.get("ref"), "commit": source_snapshot.get("commit")}:
            return "catalog_snapshot_mismatch"
    if verify_sources:
        for path, digest in accepted:
            try:
                source = _contained_source(repository_root, path)
            except ValueError as exc:
                return str(exc)
            if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != digest:
                return "candidate_source_hash_mismatch"
    return None
