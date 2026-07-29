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

from _knowledge_locator_core import require_fresh_catalog, verify_current_publication


CATALOG_RELATIVE = Path("knowledge/catalogs/repository-knowledge-catalog.v2.json")
POLICY_RELATIVE = Path("knowledge/policies/consumer-policies.v2.json")
PROJECTION_RELATIVE = Path("knowledge/projections/consumer-projections.v1.json")
REQUEST_SCHEMA = "jimuyun.knowledge-locator-request.v1"
RESULT_SCHEMA = "jimuyun.knowledge-locator-result.v1"
CONTEXT_SCHEMAS = {
    "jimuyun.vdd-knowledge-context.v1",
    "jimuyun.knowledge-consumer-context.v1",
}
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
    snapshot = catalog.get("source_snapshot")
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("sources"), list):
        raise ValueError("catalog_source_snapshot_invalid")
    current = subprocess.run(
        ["git", "-C", str(repository_root), "rev-parse", "refs/heads/main"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if current.returncode:
        raise ValueError("catalog_main_commit_unavailable")
    current_commit = current.stdout.strip()
    snapshot_commit = snapshot.get("commit")
    ancestry = subprocess.run(
        ["git", "-C", str(repository_root), "merge-base", "--is-ancestor", snapshot_commit, current_commit],
        capture_output=True,
        check=False,
    )
    if ancestry.returncode:
        raise ValueError("catalog_source_snapshot_not_main_ancestor")
    paths = [item.get("path") for item in snapshot["sources"] if isinstance(item, dict) and isinstance(item.get("path"), str)]
    request_bytes = "".join(f"{current_commit}:{path}\n" for path in paths).encode("utf-8")
    completed = subprocess.run(
        ["git", "-C", str(repository_root), "cat-file", "--batch"],
        input=request_bytes,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise ValueError("catalog_main_source_unavailable")
    values: dict[str, str] = {}
    offset = 0
    for path in paths:
        newline = completed.stdout.find(b"\n", offset)
        if newline < 0:
            raise ValueError("catalog_main_source_unavailable")
        header = completed.stdout[offset:newline].decode("ascii", errors="replace")
        offset = newline + 1
        parts = header.rsplit(" ", 2)
        if len(parts) != 3 or parts[1] != "blob" or not parts[2].isdigit():
            raise ValueError("catalog_main_source_unavailable")
        size = int(parts[2])
        blob = completed.stdout[offset : offset + size]
        offset += size
        if completed.stdout[offset : offset + 1] != b"\n":
            raise ValueError("catalog_main_source_unavailable")
        offset += 1
        values[path] = hashlib.sha256(blob).hexdigest()
    return values


def validate_catalog_freshness(repository_root: Path) -> str | None:
    catalog_path = repository_root / CATALOG_RELATIVE
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        policy_path = repository_root / POLICY_RELATIVE
        projection_path = repository_root / PROJECTION_RELATIVE
        if not verify_current_publication(
            repository_root,
            catalog_path=catalog_path,
            policy_path=policy_path,
            projections_path=projection_path,
        ):
            return "catalog_publication_invalid"
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


def _snapshot_blob(repository_root: Path, commit: str, raw_path: object) -> bytes:
    _contained_source(repository_root, raw_path)
    assert isinstance(raw_path, str)
    normalized = raw_path.replace("\\", "/")
    if normalized.startswith("docs/migration/"):
        raise ValueError("candidate_path_excluded")
    result = subprocess.run(
        ["git", "-C", str(repository_root), "show", f"{commit}:{normalized}"],
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise ValueError("candidate_snapshot_source_unavailable")
    return result.stdout


def _catalog_candidates(catalog: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    raw_entries = catalog.get("modules") if isinstance(catalog.get("modules"), list) else catalog.get("entries", [])
    values: dict[tuple[str, str], dict[str, Any]] = {}
    for entry in raw_entries:
        if not isinstance(entry, dict):
            continue
        path, digest = entry.get("source_path") or entry.get("path"), entry.get("source_sha256")
        if isinstance(path, str) and isinstance(digest, str):
            values[(path, digest)] = entry
    return values


def _candidate_read_set(candidate: dict[str, Any]) -> list[tuple[str, str]]:
    read_set = candidate.get("read_set")
    if read_set is None:
        return [(candidate["path"], candidate["source_sha256"])]
    if not isinstance(read_set, list) or not read_set:
        raise ValueError("locator_candidate_read_set_invalid")
    values: list[tuple[str, str]] = []
    for item in read_set:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("source_sha256"), str):
            raise ValueError("locator_candidate_read_set_invalid")
        values.append((item["path"], item["source_sha256"]))
    if values[0] != (candidate["path"], candidate["source_sha256"]):
        raise ValueError("locator_candidate_read_set_invalid")
    return values


def validate_worktree_sources(payload: dict[str, Any], repository_root: Path) -> str | None:
    result = payload.get("locator_result") if isinstance(payload, dict) else None
    candidates = result.get("candidates") if isinstance(result, dict) else None
    if not isinstance(candidates, list):
        return "locator_candidates_invalid"
    for candidate in candidates:
        if not isinstance(candidate, dict):
            return "locator_candidates_invalid"
        try:
            for raw_path, digest in _candidate_read_set(candidate):
                source = _contained_source(repository_root, raw_path)
                if raw_path.replace("\\", "/").startswith("docs/migration/"):
                    return "candidate_path_excluded"
                if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
                    return "candidate_worktree_source_hash_mismatch"
        except (OSError, ValueError) as error:
            return str(error) if isinstance(error, ValueError) else "candidate_worktree_source_unavailable"
    return None


def validate_context(
    payload: dict[str, Any],
    *,
    repository_root: Path | None = None,
    verify_catalog: bool = False,
    verify_sources: bool = False,
    expected_consumer: str | None = None,
    require_selection: bool = False,
    require_preflight: bool = False,
) -> str | None:
    """Return a stable failure code, or ``None`` for a complete bound context."""
    if not isinstance(payload, dict) or payload.get("schema_version") not in CONTEXT_SCHEMAS:
        return "context_schema_invalid"
    request, result = payload.get("locator_request"), payload.get("locator_result")
    required_modules, decisions = payload.get("required_modules"), payload.get("decisions")
    if not isinstance(request, dict) or not isinstance(result, dict) or not isinstance(required_modules, list) or not isinstance(decisions, list):
        return "context_shape_invalid"
    if request.get("schema_version") != REQUEST_SCHEMA or result.get("schema_version") != RESULT_SCHEMA:
        return "locator_schema_invalid"
    generic_context = payload.get("schema_version") == "jimuyun.knowledge-consumer-context.v1"
    consumer = payload.get("consumer") if generic_context else "vdd"
    if consumer not in {"vdd", "bootstrap", "refactor-acceptance"}:
        return "knowledge_consumer_mismatch"
    if (generic_context or expected_consumer is not None or request.get("consumer") is not None) and request.get("consumer") != consumer:
        return "knowledge_consumer_mismatch"
    if expected_consumer is not None and consumer != expected_consumer:
        return "knowledge_consumer_mismatch"
    if request.get("request_id") != result.get("request_id"):
        return "locator_request_id_mismatch"
    if request.get("snapshot") != result.get("snapshot"):
        return "locator_snapshot_mismatch"
    if payload.get("request_sha256") != canonical_hash(request) or payload.get("result_sha256") != canonical_hash(result):
        return "locator_hash_mismatch"
    preflight = payload.get("preflight")
    if preflight is None:
        if require_preflight:
            return "preflight_invalid"
    elif not isinstance(preflight, dict):
        return "preflight_invalid"
    else:
        context_without_preflight = {key: value for key, value in payload.items() if key != "preflight"}
        if preflight.get("context_sha256") != canonical_hash(context_without_preflight):
            return "preflight_context_hash_mismatch"
        if preflight.get("status") != "ready" or preflight.get("failure_code") is not None:
            return "preflight_status_invalid"
    snapshot = request.get("snapshot")
    if not isinstance(snapshot, dict) or snapshot.get("ref") != "refs/heads/main" or not isinstance(snapshot.get("commit"), str):
        return "locator_snapshot_invalid"
    if result.get("status") != "matched":
        return "locator_result_not_matched"
    if any(not isinstance(module, str) or not module for module in required_modules) or len(set(required_modules)) != len(required_modules):
        return "required_modules_invalid"
    if require_selection and not required_modules:
        return "required_modules_empty"
    candidates = result.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return "locator_candidates_invalid"
    available: set[tuple[str, str]] = set()
    candidate_documents: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict) or not isinstance(candidate.get("path"), str) or not isinstance(candidate.get("source_sha256"), str):
            return "locator_candidates_invalid"
        if candidate["path"].replace("\\", "/").startswith("docs/migration/"):
            return "candidate_path_excluded"
        try:
            _candidate_read_set(candidate)
        except ValueError as exc:
            return str(exc)
        key = (candidate["path"], candidate["source_sha256"])
        if key in available:
            return "locator_candidates_duplicate"
        available.add(key)
        candidate_documents.append(candidate)
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
        if not set(satisfies).issubset(set(required_modules)):
            return "consumption_modules_outside_required"
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
    if require_selection and not accepted:
        return "accepted_decisions_empty"
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
        if catalog.get("schema_version") == "jimuyun.repository-knowledge-catalog.v2":
            if result.get("source_snapshot_id") != source_snapshot.get("snapshot_id"):
                return "catalog_source_snapshot_id_mismatch"
            if result.get("policy_revision") != request.get("policy_revision"):
                return "catalog_policy_revision_mismatch"
            try:
                policies = json.loads((repository_root / POLICY_RELATIVE).read_text(encoding="utf-8"))
                projections = json.loads((repository_root / PROJECTION_RELATIVE).read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                return "consumer_projection_invalid"
            if (
                request.get("policy_revision") != policies.get("policy_revision")
                or projections.get("policy_revision") != policies.get("policy_revision")
                or projections.get("policy_sha256") != canonical_hash(policies)
                or projections.get("catalog_sha256") != canonical_hash(catalog)
                or projections.get("source_snapshot_id") != source_snapshot.get("snapshot_id")
            ):
                return "consumer_projection_stale"
            consumer_projection = next(
                (
                    item
                    for item in projections.get("projections", [])
                    if isinstance(item, dict) and item.get("consumer") == request.get("consumer")
                ),
                None,
            )
            if consumer_projection is None or not isinstance(consumer_projection.get("eligible_module_ids"), list):
                return "consumer_projection_invalid"
            eligible_module_ids = set(consumer_projection["eligible_module_ids"])
        else:
            eligible_module_ids = None
        registered = _catalog_candidates(catalog)
        for candidate in candidate_documents:
            entry = registered.get((candidate["path"], candidate["source_sha256"]))
            if entry is None:
                return "locator_candidate_catalog_mismatch"
            if candidate.get("module_id") is not None and candidate.get("module_id") != entry.get("module_id"):
                return "locator_candidate_catalog_mismatch"
            if eligible_module_ids is not None and candidate.get("module_id") not in eligible_module_ids:
                return "locator_candidate_outside_consumer_projection"
            if candidate.get("read_set") is not None:
                expected = [(entry["source_path"], entry["source_sha256"])] + [
                    (item.get("path"), item.get("source_sha256"))
                    for item in entry.get("resources", [])
                    if isinstance(item, dict)
                ]
                try:
                    actual = _candidate_read_set(candidate)
                except ValueError as exc:
                    return str(exc)
                if actual != expected:
                    return "locator_candidate_read_set_mismatch"
    if verify_sources:
        commit = snapshot["commit"]
        for candidate in candidate_documents:
            try:
                read_set = _candidate_read_set(candidate)
                for path, digest in read_set:
                    blob = _snapshot_blob(repository_root, commit, path)
                    if hashlib.sha256(blob).hexdigest() != digest:
                        return "candidate_source_hash_mismatch"
            except ValueError as exc:
                return str(exc)
    return None
