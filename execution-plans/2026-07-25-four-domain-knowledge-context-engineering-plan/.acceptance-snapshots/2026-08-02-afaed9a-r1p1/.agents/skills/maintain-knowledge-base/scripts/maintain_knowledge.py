#!/usr/bin/env python3
"""Deterministic, main-pinned derived knowledge maintenance."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


HARD_EXCLUDED_PREFIXES = ("docs/migration/",)
ALLOWED_OUTPUT_PREFIXES = (
    "knowledge/indexes/",
    "knowledge/projections/",
    "knowledge/snapshots/",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True, encoding="utf-8").strip()


def safe_relative(value: str) -> str:
    pure = PurePosixPath(value.replace("\\", "/"))
    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
        raise ValueError("invalid_source_path")
    normalized = pure.as_posix()
    if any(normalized == prefix.rstrip("/") or normalized.startswith(prefix) for prefix in HARD_EXCLUDED_PREFIXES):
        raise ValueError("source_path_excluded")
    return normalized


def catalog_source_snapshot(catalog: dict) -> dict | None:
    snapshot = catalog.get("source_snapshot")
    if snapshot is None:
        return None
    if not isinstance(snapshot, dict):
        raise ValueError("invalid_catalog_source_snapshot")
    if snapshot.get("ref") != "refs/heads/main" or not isinstance(snapshot.get("commit"), str) or len(snapshot["commit"]) != 40:
        raise ValueError("invalid_catalog_source_snapshot")
    sources = snapshot.get("sources")
    if not isinstance(sources, list):
        raise ValueError("invalid_catalog_source_snapshot")
    return snapshot


def repository_relative_path(repo: Path, path: Path) -> str:
    resolved = (path if path.is_absolute() else repo / path).resolve()
    try:
        return resolved.relative_to(repo).as_posix()
    except ValueError as exc:
        raise ValueError("invalid_output_path") from exc


def collision_relative(value: str) -> str:
    pure = PurePosixPath(value.replace("\\", "/"))
    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
        raise ValueError("invalid_output_path")
    return pure.as_posix()


def validate_output_path(repo: Path, output: Path, request_path: Path, catalog_path: Path, request: dict, catalog: dict) -> Path:
    output_relative = repository_relative_path(repo, output)
    if not any(output_relative.startswith(prefix) for prefix in ALLOWED_OUTPUT_PREFIXES):
        raise ValueError("invalid_output_path")

    protected = {
        repository_relative_path(repo, request_path),
        repository_relative_path(repo, catalog_path),
    }
    raw_entries = catalog.get("modules") if isinstance(catalog.get("modules"), list) else catalog.get("entries")
    if raw_entries is None and isinstance(catalog.get("files"), list):
        raw_entries = catalog["files"]
    for item in raw_entries or []:
        if not isinstance(item, dict):
            continue
        source = item.get("source_path", item.get("path"))
        if isinstance(source, str) and source:
            protected.add(collision_relative(source))
        for resource in item.get("resources", []):
            if isinstance(resource, dict) and isinstance(resource.get("path"), str):
                protected.add(collision_relative(resource["path"]))
    snapshot = catalog.get("source_snapshot")
    if isinstance(snapshot, dict):
        for item in snapshot.get("sources", []):
            if isinstance(item, dict) and isinstance(item.get("path"), str):
                protected.add(collision_relative(item["path"]))
    target = request.get("target")
    if isinstance(target, dict) and isinstance(target.get("repo_relative_path"), str) and target["repo_relative_path"]:
        protected.add(collision_relative(target["repo_relative_path"]))

    if output_relative in protected or output_relative.startswith("logs/knowledge-context/"):
        raise ValueError("invalid_output_path")
    return repo / output_relative


def render_preflight_failure(request: dict, failure_code: str) -> str:
    result = {
        "schema_version": "jimuyun.knowledge-maintenance-result.v1",
        "request_id": request.get("request_id", "invalid"),
        "mode": request.get("mode", "existing-only"),
        "main_commit": request.get("authority", {}).get("main_commit", ""),
        "status": "failed",
        "before_snapshot_id": request.get("knowledge_snapshot_id", "invalid"),
        "after_snapshot_id": request.get("knowledge_snapshot_id", "invalid"),
        "entries": [],
        "catalog_source_snapshot_status": "legacy",
        "suggested_catalog_source_snapshot": None,
        "lkg_disposition": "preserved",
        "source_mutation_count": 0,
        "log": {
            "append_only": True,
            "log_ref": "",
            "main_commit": request.get("authority", {}).get("main_commit", ""),
            "failure_code": failure_code,
        },
    }
    return json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    repo = args.repo_root.resolve()
    request = load_json(args.request)
    catalog = load_json(args.catalog)
    try:
        output_path = validate_output_path(repo, args.output, args.request, args.catalog, request, catalog)
    except ValueError:
        print(render_preflight_failure(request, "invalid_output_path"), end="")
        return 2
    failure = None
    entries_result: list[dict] = []
    suggested_sources: list[dict] = []
    snapshot_status = "legacy"
    try:
        if request.get("schema_version") != "jimuyun.knowledge-maintenance-request.v1" or request.get("skill_id") != "maintain-knowledge-base":
            raise ValueError("invalid_request")
        authority = request["authority"]
        if authority.get("authority_ref") != "refs/heads/main" or authority.get("implicit_fetch") or authority.get("dirty_worktree_authority") or request.get("source_write_policy") != "forbidden" or request.get("log_root") != "logs/knowledge-context" or not request.get("append_only_log"):
            raise ValueError("invalid_authority")
        main_commit = git(repo, "rev-parse", "refs/heads/main")
        if authority.get("main_commit") != main_commit:
            raise ValueError("main_commit_mismatch")
        mode = request["mode"]
        target = request["target"]
        if mode == "existing-only" and (target.get("kind") != "none" or request.get("discovery_policy") != "existing-entries-only"):
            raise ValueError("existing_only_discovery_forbidden")
        if mode == "targeted" and (target.get("kind") == "none" or request.get("discovery_policy") != "target-scoped"):
            raise ValueError("target_required")
        raw_entries = catalog.get("modules") if isinstance(catalog.get("modules"), list) else catalog.get("entries")
        if raw_entries is None and isinstance(catalog.get("files"), list):
            raw_entries = [
                {"entry_id": str(item.get("path", "")).replace("/", "."), "source_path": item.get("path"), "source_sha256": item.get("sha256")}
                for item in catalog["files"]
                if isinstance(item, dict)
            ]
        if not isinstance(raw_entries, list):
            raise ValueError("invalid_catalog")
        recorded_snapshot = catalog_source_snapshot(catalog)
        recorded_sources = {
            safe_relative(str(item.get("path", ""))): item.get("sha256")
            for item in (recorded_snapshot or {}).get("sources", [])
            if isinstance(item, dict)
        }
        if mode == "existing-only" and recorded_snapshot is not None:
            selected = [
                {
                    "entry_id": "source." + safe_relative(str(item.get("path", ""))).replace("/", "."),
                    "source_path": item.get("path"),
                    "source_sha256": item.get("sha256"),
                }
                for item in recorded_snapshot["sources"]
                if isinstance(item, dict)
            ]
        else:
            selected = list(raw_entries)
            for item in raw_entries:
                if not isinstance(item, dict):
                    continue
                for index, resource in enumerate(item.get("resources", [])):
                    if isinstance(resource, dict):
                        selected.append(
                            {
                                "entry_id": f"{item.get('entry_id', 'module')}.resource.{index}",
                                "source_path": resource.get("path"),
                                "source_sha256": resource.get("source_sha256"),
                            }
                        )
        if mode == "targeted":
            prefix = safe_relative(str(target.get("repo_relative_path") or "")).rstrip("/")
            selected = [item for item in selected if safe_relative(str(item.get("source_path", ""))).startswith(prefix + "/") or safe_relative(str(item.get("source_path", ""))) == prefix]
        for item in selected:
            source_path = safe_relative(str(item.get("source_path", "")))
            entry_id = str(item.get("entry_id", ""))
            if not entry_id:
                raise ValueError("invalid_catalog_entry")
            blob = subprocess.run(["git", "-C", str(repo), "show", f"{main_commit}:{source_path}"], capture_output=True)
            before = item.get("source_sha256")
            if blob.returncode:
                entries_result.append({"entry_id": entry_id, "source_path": source_path, "source_snapshot_kind": "main", "disposition": "missing", "authority_status": "main-backed", "before_sha256": before, "after_sha256": None, "changed_fields": ["missing"]})
                continue
            after = sha256(blob.stdout)
            disposition = "unchanged" if before == after else "updated"
            suggested_sources.append({"path": source_path, "sha256": after})
            entries_result.append({"entry_id": entry_id, "source_path": source_path, "source_snapshot_kind": "main", "disposition": disposition, "authority_status": "main-backed", "before_sha256": before, "after_sha256": after, "changed_fields": [] if disposition == "unchanged" else ["source_sha256"]})
        if mode == "targeted" and not selected:
            source_path = safe_relative(str(target.get("repo_relative_path")))
            blob = subprocess.run(["git", "-C", str(repo), "show", f"{main_commit}:{source_path}"], capture_output=True)
            if blob.returncode == 0:
                digest = sha256(blob.stdout)
                suggested_sources.append({"path": source_path, "sha256": digest})
                entries_result.append({"entry_id": f"candidate.{source_path.replace('/', '.')}", "source_path": source_path, "source_snapshot_kind": "main", "disposition": "candidate", "authority_status": "main-backed", "before_sha256": None, "after_sha256": digest, "changed_fields": ["candidate_source"]})
            elif target.get("snapshot_kind") == "worktree" and (repo / source_path).is_file():
                worktree = repo / source_path
                entries_result.append({"entry_id": f"candidate.{source_path.replace('/', '.')}", "source_path": source_path, "source_snapshot_kind": "worktree", "disposition": "candidate", "authority_status": "provisional", "before_sha256": None, "after_sha256": sha256(worktree.read_bytes()), "changed_fields": ["candidate_source"]})
        if recorded_snapshot is not None:
            actual_sources = {item["path"]: item["sha256"] for item in suggested_sources}
            catalog_bindings_current = True
            for item in raw_entries:
                if not isinstance(item, dict):
                    catalog_bindings_current = False
                    break
                source_path = safe_relative(str(item.get("source_path", "")))
                if recorded_sources.get(source_path) != item.get("source_sha256"):
                    catalog_bindings_current = False
                    break
                for resource in item.get("resources", []):
                    if not isinstance(resource, dict):
                        catalog_bindings_current = False
                        break
                    resource_path = safe_relative(str(resource.get("path", "")))
                    if recorded_sources.get(resource_path) != resource.get("source_sha256"):
                        catalog_bindings_current = False
                        break
            snapshot_status = "current" if recorded_sources == actual_sources and catalog_bindings_current else "stale"
        status = "updated" if any(item["disposition"] in {"updated", "missing", "candidate"} for item in entries_result) or snapshot_status == "stale" else "unchanged"
    except (KeyError, ValueError, subprocess.CalledProcessError) as exc:
        failure = str(exc)
        main_commit = authority.get("main_commit", "") if "authority" in locals() else ""
        mode = request.get("mode", "existing-only")
        status = "failed"
    advances_lkg = status == "updated" and not failure and any(item["authority_status"] == "main-backed" and item["disposition"] == "updated" for item in entries_result)
    result = {"schema_version": "jimuyun.knowledge-maintenance-result.v1", "request_id": request.get("request_id", "invalid"), "mode": mode, "main_commit": main_commit, "status": status, "before_snapshot_id": request.get("knowledge_snapshot_id", "invalid"), "after_snapshot_id": request.get("knowledge_snapshot_id", "invalid") if status != "updated" else sha256(json.dumps(entries_result, sort_keys=True).encode()), "entries": entries_result, "catalog_source_snapshot_status": snapshot_status, "suggested_catalog_source_snapshot": {"ref": "refs/heads/main", "commit": main_commit, "sources": sorted(suggested_sources, key=lambda item: item["path"])} if not failure else None, "lkg_disposition": "advanced" if advances_lkg else "preserved", "source_mutation_count": 0, "log": {"append_only": True, "log_ref": "", "main_commit": main_commit, "failure_code": failure}}
    timestamp = datetime.now(timezone.utc)
    log_date = timestamp.strftime("%Y-%m-%d")
    log_name = f"result-{timestamp.strftime('%H%M%S%f')}.v1.json"
    log_dir = repo / "logs" / "knowledge-context" / log_date / result["request_id"]
    result["log"]["log_ref"] = (Path("logs/knowledge-context") / log_date / result["request_id"] / log_name).as_posix()
    rendered = json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    if not args.dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8", newline="\n")
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / log_name).write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0 if not failure else 2


if __name__ == "__main__":
    raise SystemExit(main())
