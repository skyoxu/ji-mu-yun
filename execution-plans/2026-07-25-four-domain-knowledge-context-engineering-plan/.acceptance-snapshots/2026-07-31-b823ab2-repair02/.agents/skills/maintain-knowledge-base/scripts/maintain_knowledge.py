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
    return pure.as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    request = load_json(args.request)
    catalog = load_json(args.catalog)
    repo = args.repo_root.resolve()
    failure = None
    entries_result: list[dict] = []
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
        raw_entries = catalog.get("entries")
        if raw_entries is None and isinstance(catalog.get("files"), list):
            raw_entries = [
                {"entry_id": str(item.get("path", "")).replace("/", "."), "source_path": item.get("path"), "source_sha256": item.get("sha256")}
                for item in catalog["files"]
                if isinstance(item, dict)
            ]
        if not isinstance(raw_entries, list):
            raise ValueError("invalid_catalog")
        selected = raw_entries
        if mode == "targeted":
            prefix = safe_relative(str(target.get("repo_relative_path") or "")).rstrip("/")
            selected = [item for item in raw_entries if safe_relative(str(item.get("source_path", ""))).startswith(prefix + "/") or safe_relative(str(item.get("source_path", ""))) == prefix]
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
            entries_result.append({"entry_id": entry_id, "source_path": source_path, "source_snapshot_kind": "main", "disposition": disposition, "authority_status": "main-backed", "before_sha256": before, "after_sha256": after, "changed_fields": [] if disposition == "unchanged" else ["source_sha256"]})
        if mode == "targeted" and not selected and target.get("snapshot_kind") == "worktree":
            source_path = safe_relative(str(target.get("repo_relative_path")))
            worktree = repo / source_path
            if worktree.is_file():
                entries_result.append({"entry_id": f"candidate.{source_path.replace('/', '.')}", "source_path": source_path, "source_snapshot_kind": "worktree", "disposition": "candidate", "authority_status": "provisional", "before_sha256": None, "after_sha256": sha256(worktree.read_bytes()), "changed_fields": ["candidate_source"]})
        status = "updated" if any(item["disposition"] in {"updated", "missing", "candidate"} for item in entries_result) else "unchanged"
    except (KeyError, ValueError, subprocess.CalledProcessError) as exc:
        failure = str(exc)
        main_commit = authority.get("main_commit", "") if "authority" in locals() else ""
        mode = request.get("mode", "existing-only")
        status = "failed"
    advances_lkg = status == "updated" and not failure and any(item["authority_status"] == "main-backed" and item["disposition"] == "updated" for item in entries_result)
    result = {"schema_version": "jimuyun.knowledge-maintenance-result.v1", "request_id": request.get("request_id", "invalid"), "mode": mode, "main_commit": main_commit, "status": status, "before_snapshot_id": request.get("knowledge_snapshot_id", "invalid"), "after_snapshot_id": request.get("knowledge_snapshot_id", "invalid") if status != "updated" else sha256(json.dumps(entries_result, sort_keys=True).encode()), "entries": entries_result, "lkg_disposition": "advanced" if advances_lkg else "preserved", "source_mutation_count": 0, "log": {"append_only": True, "log_ref": "", "main_commit": main_commit, "failure_code": failure}}
    timestamp = datetime.now(timezone.utc)
    log_date = timestamp.strftime("%Y-%m-%d")
    log_name = f"result-{timestamp.strftime('%H%M%S%f')}.v1.json"
    log_dir = repo / "logs" / "knowledge-context" / log_date / result["request_id"]
    result["log"]["log_ref"] = (Path("logs/knowledge-context") / log_date / result["request_id"] / log_name).as_posix()
    rendered = json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    if not args.dry_run:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / log_name).write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0 if not failure else 2


if __name__ == "__main__":
    raise SystemExit(main())
