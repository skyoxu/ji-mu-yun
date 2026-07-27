"""Deterministic, location-only repository knowledge retrieval primitives."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _tokens(query: str) -> list[str]:
    return [part.casefold() for part in query.replace("/", " ").replace("_", " ").split() if part]


def _line_for(content: str, tokens: list[str]) -> int:
    for index, line in enumerate(content.splitlines(), 1):
        if all(token in line.casefold() for token in tokens):
            return index
    return 1


def locate(request: dict[str, Any], catalog: dict[str, Any], *, max_candidates: int = 12) -> dict[str, Any]:
    query = request.get("query")
    if not isinstance(query, str) or not query.strip() or max_candidates < 1:
        return {"status": "insufficient_match", "candidates": []}
    tokens = _tokens(query)
    candidates: list[tuple[int, str, dict[str, Any]]] = []
    for entry in catalog.get("entries", []):
        if not isinstance(entry, dict):
            continue
        path = entry.get("path") or entry.get("source_path")
        content = entry.get("content", "")
        digest = entry.get("source_sha256")
        if not isinstance(path, str) or not isinstance(content, str) or not isinstance(digest, str):
            continue
        haystack = f"{path} {content}".casefold()
        score = sum(token in haystack for token in tokens)
        if score == 0:
            continue
        line = _line_for(content, tokens)
        candidates.append((score, path, {"path": path, "anchor": entry.get("anchor", "document"), "line_start": line, "line_end": line, "source_sha256": digest, "provenance": ["catalog"], "rank_evidence": {"token_matches": score, "strategy": "token"}}))
    candidates.sort(key=lambda item: (-item[0], item[1].casefold()))
    selected = [item[2] for item in candidates[:max_candidates]]
    return {"status": "matched" if selected else "insufficient_match", "candidates": selected}


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
    for entry in catalog.get("entries", []):
        if not isinstance(entry, dict):
            return {"status": "knowledge_refresh_required"}
        path = entry.get("source_path") or entry.get("path")
        if not isinstance(path, str) or expected.get(path) != entry.get("source_sha256"):
            return {"status": "knowledge_refresh_required"}
    return {"status": "current"}
