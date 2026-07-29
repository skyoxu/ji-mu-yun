"""Deterministic, location-only repository knowledge retrieval primitives."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any


HARD_EXCLUDED_PREFIXES = ("docs/migration/",)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _tokens(query: str) -> list[str]:
    parts = re.findall(r"[a-z0-9]+(?:[._:-][a-z0-9]+)*|[\u3400-\u9fff]+", query.casefold())
    tokens: list[str] = []
    for part in parts:
        values = [part]
        if re.fullmatch(r"[\u3400-\u9fff]+", part) and len(part) > 2:
            values.extend(part[index : index + 2] for index in range(len(part) - 1))
        for value in values:
            if value and value not in tokens:
                tokens.append(value)
    return tokens


def _best_location(entry: dict[str, Any], tokens: list[str]) -> tuple[str, int, int]:
    content = entry.get("content", "")
    lines = content.splitlines()
    best_line = 1
    best_score = -1
    for index, line in enumerate(lines, 1):
        folded = line.casefold()
        score = sum(token in folded for token in tokens)
        if score > best_score:
            best_line, best_score = index, score
    anchor = entry.get("anchor", "document")
    for candidate in entry.get("anchors", []):
        if not isinstance(candidate, dict):
            continue
        start, end = candidate.get("line_start"), candidate.get("line_end")
        if isinstance(start, int) and isinstance(end, int) and start <= best_line <= end:
            anchor = candidate.get("anchor", anchor)
    return str(anchor), best_line, best_line


def _hard_excluded(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return any(normalized.startswith(prefix) for prefix in HARD_EXCLUDED_PREFIXES)


def _explicitly_names(query: str, entry: dict[str, Any]) -> bool:
    folded = query.casefold().strip()
    path = str(entry.get("source_path") or entry.get("path") or "").casefold()
    identifiers = {
        str(entry.get("module_id", "")).casefold(),
        str(entry.get("entry_id", "")).casefold(),
        str(entry.get("title", "")).casefold(),
        path,
        Path(path).name.casefold(),
        Path(path).parent.name.casefold(),
    }
    identifiers.discard("")
    return any(folded == value or (len(value) >= 8 and value in folded) for value in identifiers)


def _policy_allows(entry: dict[str, Any], query: str, policy: dict[str, Any] | None) -> bool:
    path = entry.get("source_path") or entry.get("path")
    if not isinstance(path, str) or _hard_excluded(path):
        return False
    if entry.get("semantic_eligible") is False or entry.get("status") == "excluded":
        return False
    if policy is None:
        return True
    consumer = policy.get("consumer")
    consumer_ids = entry.get("consumer_ids")
    if isinstance(consumer_ids, list) and consumer_ids and consumer not in consumer_ids:
        return False
    if entry.get("lifecycle", "repository-source") not in policy.get("lifecycles", ["repository-source"]):
        return False
    prefixes = policy.get("path_prefixes", [])
    exact_paths = policy.get("exact_paths", [])
    if path not in exact_paths and not any(path.startswith(prefix) for prefix in prefixes):
        return False
    status = entry.get("status", "active")
    if status not in policy.get("statuses", ["active"]):
        return False
    if status == "historical" and policy.get("historical_mode") == "exact-only" and not _explicitly_names(query, entry):
        return False
    visibility = entry.get("visibility")
    if isinstance(visibility, dict):
        allowed_visibility = set(policy.get("visibility", ["active", "dependency", "conditional"]))
        if not any(visibility.get(domain) in allowed_visibility for domain in policy.get("domains", [])):
            return False
    return True


def _score(query: str, tokens: list[str], entry: dict[str, Any]) -> tuple[int, str, int] | None:
    path = str(entry.get("source_path") or entry.get("path") or "")
    title = str(entry.get("title", ""))
    identifier = str(entry.get("module_id") or entry.get("entry_id") or "")
    searchable = " ".join(
        (
            path,
            str(entry.get("module_id", "")),
            str(entry.get("entry_id", "")),
            str(entry.get("title", "")),
            str(entry.get("content", "")),
            " ".join(str(item.get("path", "")) for item in entry.get("resources", []) if isinstance(item, dict)),
        )
    ).casefold()
    if not tokens:
        return None
    matches = sum(token in searchable for token in tokens)
    coverage = matches / len(tokens)
    folded_query = query.casefold().strip()
    exact = _explicitly_names(query, entry)
    phrase = folded_query in searchable
    if not exact and not phrase and coverage < 0.5:
        return None
    score = matches * 10
    score += sum(token in path.casefold() for token in tokens) * 8
    score += sum(token in title.casefold() for token in tokens) * 8
    score += sum(token in identifier.casefold() for token in tokens) * 8
    if phrase:
        score += 25
    if exact:
        score += 100
    if folded_query and folded_query in path.casefold():
        score += 20
    confidence = "high" if exact or (phrase and coverage == 1) else "medium"
    return score, confidence, matches


def _candidate(entry: dict[str, Any], tokens: list[str], score: int, confidence: str, matches: int, strategy: str) -> dict[str, Any]:
    path = entry.get("source_path") or entry.get("path")
    anchor, line_start, line_end = _best_location(entry, tokens)
    typed = isinstance(entry.get("module_id"), str)
    candidate: dict[str, Any] = {
        "path": path,
        "anchor": anchor,
        "line_start": line_start,
        "line_end": line_end,
        "source_sha256": entry["source_sha256"],
        "provenance": ["catalog-v2" if typed else "catalog-v1", "refs/heads/main"],
        "rank_evidence": {
            "token_matches": matches,
            "strategy": strategy,
            "score": score,
            "confidence": confidence,
        },
    }
    if typed:
        candidate.update(
            {
                "module_id": entry["module_id"],
                "kind": entry.get("kind"),
                "primary_domain": entry.get("primary_domain"),
                "visibility": entry.get("visibility"),
                "lifecycle": entry.get("lifecycle"),
                "enforcement_level": entry.get("enforcement_level"),
                "source_role": entry.get("source_role"),
                "status": entry.get("status"),
                "relations": entry.get("relations", []),
                "consumer_ids": entry.get("consumer_ids", []),
                "semantic_eligible": entry.get("semantic_eligible", True),
                "read_set": [
                    {"role": "primary", "path": path, "source_sha256": entry["source_sha256"]},
                    *[
                        {"role": item.get("role"), "path": item.get("path"), "source_sha256": item.get("source_sha256")}
                        for item in entry.get("resources", [])
                        if isinstance(item, dict)
                    ],
                ],
            }
        )
    return candidate


def locate(
    request: dict[str, Any],
    catalog: dict[str, Any],
    *,
    max_candidates: int = 12,
    policy: dict[str, Any] | None = None,
    eligible_module_ids: set[str] | None = None,
) -> dict[str, Any]:
    query = request.get("query")
    if not isinstance(query, str) or not query.strip() or max_candidates < 1:
        return {"status": "insufficient_match", "candidates": []}
    tokens = _tokens(query)
    raw_entries = catalog.get("modules") if isinstance(catalog.get("modules"), list) else catalog.get("entries", [])
    entries_by_id = {
        entry.get("module_id"): entry
        for entry in raw_entries
        if isinstance(entry, dict) and isinstance(entry.get("module_id"), str)
    }
    ranked: dict[str, tuple[int, str, dict[str, Any]]] = {}
    base_matches: list[tuple[int, dict[str, Any]]] = []
    for entry in raw_entries:
        if not isinstance(entry, dict):
            continue
        path = entry.get("path") or entry.get("source_path")
        content = entry.get("content", "")
        digest = entry.get("source_sha256")
        if not isinstance(path, str) or not isinstance(content, str) or not isinstance(digest, str):
            continue
        if eligible_module_ids is not None and entry.get("module_id") not in eligible_module_ids:
            continue
        if not _policy_allows(entry, query, policy):
            continue
        scored = _score(query, tokens, entry)
        if scored is None:
            continue
        score, confidence, matches = scored
        ranked[str(entry.get("module_id") or path)] = (
            score,
            path.casefold(),
            _candidate(entry, tokens, score, confidence, matches, "hybrid-token"),
        )
        base_matches.append((score, entry))
    for base_score, entry in base_matches:
        for relation in entry.get("relations", []):
            if not isinstance(relation, dict):
                continue
            related = entries_by_id.get(relation.get("target"))
            if related is None or related.get("module_id") in ranked:
                continue
            if eligible_module_ids is not None and related.get("module_id") not in eligible_module_ids:
                continue
            if not _policy_allows(related, query, policy):
                continue
            relation_score = max(1, min(9, base_score // 20))
            path = str(related.get("source_path"))
            ranked[related["module_id"]] = (
                relation_score,
                path.casefold(),
                _candidate(related, tokens, relation_score, "medium", 0, "relation-expansion"),
            )
    ordered = sorted(ranked.values(), key=lambda item: (-item[0], item[1]))
    selected = [item[2] for item in ordered[:max_candidates]]
    result: dict[str, Any] = {"status": "matched" if selected else "insufficient_match", "candidates": selected}
    snapshot = catalog.get("source_snapshot")
    if isinstance(snapshot, dict) and isinstance(snapshot.get("snapshot_id"), str):
        result["source_snapshot_id"] = snapshot["snapshot_id"]
    if policy is not None:
        result["policy_revision"] = request.get("policy_revision")
    return result


def bind_result_to_request(request: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Project a location-only core result into the stable CLI envelope."""
    request_id = request.get("request_id")
    snapshot = request.get("snapshot")
    if not isinstance(request_id, str) or not request_id or not isinstance(snapshot, dict):
        raise ValueError("invalid_locator_request")
    status = result.get("status")
    candidates = result.get("candidates")
    if status not in {"matched", "insufficient_match", "blocked"} or not isinstance(candidates, list):
        raise ValueError("invalid_locator_result")
    return {
        "schema_version": "jimuyun.knowledge-locator-result.v1",
        "request_id": request_id,
        "status": status,
        "snapshot": snapshot,
        "candidates": candidates,
        **({"source_snapshot_id": result["source_snapshot_id"]} if isinstance(result.get("source_snapshot_id"), str) else {}),
        **({"policy_revision": result["policy_revision"]} if isinstance(result.get("policy_revision"), str) else {}),
    }


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", delete=False, dir=path.parent, suffix=".tmp") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def publish_index_generation(root: Path, catalog: dict[str, Any], snapshot_id: str, policy_revision: str) -> dict[str, Any]:
    canonical = json.dumps(catalog, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    generation_id = _sha(f"{snapshot_id}\0{policy_revision}\0".encode("utf-8") + canonical)
    generation = {"schema_version": "jimuyun.knowledge-index-generation.v1", "generation_id": generation_id, "snapshot_id": snapshot_id, "policy_revision": policy_revision, "catalog_sha256": _sha(canonical), "catalog": catalog}
    generation_path = root / "generations" / f"{generation_id}.json"
    if not generation_path.is_file():
        _atomic_json(generation_path, generation)
    pointer = {"schema_version": "jimuyun.knowledge-index-pointer.v1", "generation_id": generation_id}
    _atomic_json(root / "current.json", pointer)
    _atomic_json(root / "last-known-good.json", pointer)
    return generation


def last_known_good(root: Path) -> dict[str, Any]:
    pointer = json.loads((root / "last-known-good.json").read_text(encoding="utf-8"))
    return json.loads((root / "generations" / f"{pointer['generation_id']}.json").read_text(encoding="utf-8"))


def catalog_source_snapshot(catalog: dict[str, Any]) -> dict[str, Any] | None:
    snapshot = catalog.get("source_snapshot")
    if not isinstance(snapshot, dict) or snapshot.get("ref") != "refs/heads/main":
        return None
    commit = snapshot.get("commit")
    sources = snapshot.get("sources")
    if not isinstance(commit, str) or len(commit) != 40 or not isinstance(sources, list):
        return None
    return snapshot


def require_fresh_catalog(catalog: dict[str, Any], current_sources: dict[str, str] | str) -> dict[str, str]:
    """Check source content freshness without binding a cache to its own commit."""
    if catalog.get("authority_ref") != "refs/heads/main":
        return {"status": "knowledge_refresh_required"}
    if isinstance(current_sources, str):
        # Compatibility path for historical callers while they migrate to the
        # source-snapshot contract.
        return {"status": "current"} if catalog.get("main_commit") == current_sources else {"status": "knowledge_refresh_required"}
    snapshot = catalog_source_snapshot(catalog)
    if snapshot is None:
        return {"status": "knowledge_refresh_required"}
    expected: dict[str, str] = {}
    for item in snapshot["sources"]:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("sha256"), str):
            return {"status": "knowledge_refresh_required"}
        expected[item["path"]] = item["sha256"]
    if not expected or any(current_sources.get(path) != digest for path, digest in expected.items()):
        return {"status": "knowledge_refresh_required"}
    if any(_hard_excluded(path) for path in expected):
        return {"status": "knowledge_refresh_required"}
    entries = catalog.get("modules") if isinstance(catalog.get("modules"), list) else catalog.get("entries", [])
    for entry in entries:
        if not isinstance(entry, dict):
            return {"status": "knowledge_refresh_required"}
        path = entry.get("source_path") or entry.get("path")
        if not isinstance(path, str) or _hard_excluded(path) or expected.get(path) != entry.get("source_sha256"):
            return {"status": "knowledge_refresh_required"}
        for resource in entry.get("resources", []):
            if not isinstance(resource, dict):
                return {"status": "knowledge_refresh_required"}
            resource_path = resource.get("path")
            if not isinstance(resource_path, str) or _hard_excluded(resource_path) or expected.get(resource_path) != resource.get("source_sha256"):
                return {"status": "knowledge_refresh_required"}
    return {"status": "current"}
