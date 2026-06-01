#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import sqlite3
import stat
import time
import uuid
from pathlib import Path


PROTECTED_PHASEA_DATA = {
    "phase-a-platform.sqlite3",
    "aicodemirror-codex-homes",
}
DATE_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
HEX32_RE = re.compile(r"^[0-9a-fA-F]{32}$")
MIN_CLEANUP_REPORT_DAYS = 7


class CleanupConfigError(RuntimeError):
    pass


def validate_repo_root(repo_root: Path) -> None:
    required = [
        repo_root / "AGENTS.md",
        repo_root / "PhaseA.Platform",
        repo_root / "logs" / "phase-a-innernet",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise CleanupConfigError(f"Not a Phase A repo root or runtime root is missing: {missing}")


def is_reparse_or_symlink(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attrs = path.stat().st_file_attributes
    except (AttributeError, OSError):
        return False
    return bool(attrs & getattr(os.stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400))


def find_reparse_or_symlink_descendant(path: Path) -> Path | None:
    if is_reparse_or_symlink(path):
        return path
    if not path.exists() or not path.is_dir():
        return None
    try:
        for item in path.rglob("*"):
            if is_reparse_or_symlink(item):
                return item
    except OSError:
        return path
    return None


def file_size(path: Path) -> tuple[int, int]:
    total = 0
    files = 0
    if not path.exists():
        return total, files
    if is_reparse_or_symlink(path):
        return total, files
    iterator = path.rglob("*") if path.is_dir() else [path]
    for item in iterator:
        if is_reparse_or_symlink(item) or not item.is_file():
            continue
        try:
            total += item.stat().st_size
            files += 1
        except OSError:
            pass
    return total, files


def read_live_workspace_roots(repo_root: Path) -> set[str]:
    db_path = repo_root / "logs" / "phase-a-innernet" / "data" / "phase-a-platform.sqlite3"
    if not db_path.exists():
        raise CleanupConfigError(f"Metadata database not found: {db_path}")
    try:
        connection = sqlite3.connect(db_path)
        try:
            rows = connection.execute("SELECT root_path FROM workspaces WHERE root_path IS NOT NULL").fetchall()
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise CleanupConfigError(f"Failed to read workspace metadata: {exc}") from exc
    roots: set[str] = set()
    for row in rows:
        if not row or not row[0]:
            continue
        root_path = Path(row[0])
        if not root_path.is_absolute():
            root_path = repo_root / root_path
        roots.add(str(root_path.resolve()).casefold())
    return roots


def read_project_metadata(repo_root: Path) -> dict[str, dict]:
    db_path = repo_root / "logs" / "phase-a-innernet" / "data" / "phase-a-platform.sqlite3"
    if not db_path.exists():
        raise CleanupConfigError(f"Metadata database not found: {db_path}")
    try:
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(
                """
                SELECT
                    w.project_id,
                    w.root_path,
                    w.created_utc AS workspace_created_utc,
                    p.account_id,
                    p.name,
                    p.game_name,
                    p.game_type_source,
                    p.bootstrap_status,
                    p.bootstrap_error,
                    p.created_utc AS project_created_utc
                FROM workspaces w
                LEFT JOIN projects p ON p.id = w.project_id
                WHERE w.root_path IS NOT NULL
                """
            ).fetchall()
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise CleanupConfigError(f"Failed to read workspace project metadata: {exc}") from exc

    metadata: dict[str, dict] = {}
    for row in rows:
        root_path = Path(row["root_path"])
        if not root_path.is_absolute():
            root_path = repo_root / root_path
        metadata[str(root_path.resolve()).casefold()] = {
            "project_id": row["project_id"],
            "account_id": row["account_id"],
            "name": row["name"],
            "game_name": row["game_name"],
            "game_type_source": row["game_type_source"],
            "bootstrap_status": row["bootstrap_status"],
            "bootstrap_error": row["bootstrap_error"],
            "workspace_created_utc": row["workspace_created_utc"],
            "project_created_utc": row["project_created_utc"],
        }
    return metadata


def older_than(path: Path, days: int, now: dt.datetime) -> bool:
    try:
        modified = dt.datetime.fromtimestamp(path.stat().st_mtime)
    except OSError:
        return False
    return modified < now - dt.timedelta(days=days)


def add_candidate(
    candidates: list[dict],
    path: Path,
    reason: str,
    protected: bool = False,
    measure_size: bool = True,
    **metadata: object,
) -> None:
    size, files = file_size(path) if measure_size else (0, 0)
    item = {
        "path": str(path),
        "reason": reason,
        "protected": protected,
        "size_bytes": size,
        "size_mb": round(size / 1024 / 1024, 2),
        "files": files,
        "size_measured": measure_size,
    }
    item.update(metadata)
    candidates.append(item)


def add_deletable_candidate(candidates: list[dict], path: Path, reason: str) -> None:
    reparse_path = find_reparse_or_symlink_descendant(path)
    if reparse_path is not None:
        add_candidate(
            candidates,
            path,
            f"{reason}-tree-reparse-protected",
            protected=True,
            reparse_path=str(reparse_path),
        )
        return
    add_candidate(candidates, path, reason)


def collect_candidates(
    repo_root: Path,
    keep_log_days: int,
    keep_tmp_days: int,
    keep_orphan_days: int,
    keep_test_result_days: int,
    include_test_results: bool,
    max_tmp_candidates: int,
    measure_protected: bool,
    keep_cleanup_report_days: int,
    include_cleanup_reports: bool,
) -> list[dict]:
    now = dt.datetime.now()
    candidates: list[dict] = []
    live_roots = read_live_workspace_roots(repo_root)

    workspaces_root = repo_root / "logs" / "phase-a-innernet" / "workspaces"
    if workspaces_root.exists():
        for account_dir in workspaces_root.iterdir():
            if not account_dir.is_dir():
                continue
            if not HEX32_RE.match(account_dir.name):
                add_candidate(
                    candidates,
                    account_dir,
                    "nonstandard-workspace-account-protected",
                    protected=True,
                    measure_size=measure_protected,
                )
                continue
            for project_dir in account_dir.iterdir():
                if not project_dir.is_dir():
                    continue
                if not HEX32_RE.match(project_dir.name):
                    add_candidate(
                        candidates,
                        project_dir,
                        "nonstandard-workspace-project-protected",
                        protected=True,
                        measure_size=measure_protected,
                    )
                    continue
                if is_reparse_or_symlink(project_dir):
                    add_candidate(
                        candidates,
                        project_dir,
                        "workspace-reparse-protected",
                        protected=True,
                        measure_size=measure_protected,
                    )
                    continue
                resolved = str(project_dir.resolve()).casefold()
                if resolved in live_roots:
                    add_candidate(
                        candidates,
                        project_dir,
                        "live-workspace-protected",
                        protected=True,
                        measure_size=measure_protected,
                    )
                    continue
                reparse_path = find_reparse_or_symlink_descendant(project_dir)
                if reparse_path is not None:
                    add_candidate(
                        candidates,
                        project_dir,
                        "workspace-descendant-reparse-protected",
                        protected=True,
                        measure_size=measure_protected,
                        reparse_path=str(reparse_path),
                    )
                    continue
                add_candidate(
                    candidates,
                    project_dir,
                    f"orphan-workspace-older-than-{keep_orphan_days}d"
                    if older_than(project_dir, keep_orphan_days, now)
                    else f"recent-orphan-workspace-protected-{keep_orphan_days}d",
                    protected=not older_than(project_dir, keep_orphan_days, now),
                )

    tmp_root = repo_root / "logs" / "phase-a-innernet" / "tmp"
    if tmp_root.exists():
        tmp_candidates: list[dict] = []
        for child in tmp_root.iterdir():
            if is_reparse_or_symlink(child):
                add_candidate(candidates, child, "tmp-reparse-protected", protected=True, measure_size=measure_protected)
                continue
            if older_than(child, keep_tmp_days, now):
                add_deletable_candidate(tmp_candidates, child, f"tmp-older-than-{keep_tmp_days}d")
        tmp_candidates.sort(key=lambda item: item["size_bytes"], reverse=True)
        if max_tmp_candidates > 0:
            candidates.extend(tmp_candidates[:max_tmp_candidates])
            omitted = tmp_candidates[max_tmp_candidates:]
            if omitted:
                candidates.append(
                    {
                        "path": str(tmp_root),
                        "reason": f"tmp-omitted-after-top-{max_tmp_candidates}",
                        "protected": True,
                        "size_bytes": sum(item["size_bytes"] for item in omitted),
                        "size_mb": round(sum(item["size_bytes"] for item in omitted) / 1024 / 1024, 2),
                        "files": sum(item["files"] for item in omitted),
                        "omitted_count": len(omitted),
                    }
                )
        else:
            candidates.extend(tmp_candidates)

    for relative in ("logs/ci", "logs/e2e", "logs/unit"):
        root = repo_root / relative
        if not root.exists():
            continue
        for child in root.iterdir():
            if is_reparse_or_symlink(child):
                add_candidate(
                    candidates,
                    child,
                    f"{relative}-reparse-protected",
                    protected=True,
                    measure_size=measure_protected,
                )
                continue
            if child.is_dir() and DATE_DIR_RE.match(child.name) and older_than(child, keep_log_days, now):
                add_deletable_candidate(candidates, child, f"{relative}-older-than-{keep_log_days}d")

    for relative in (
        "Game.Core.Tests/TestResults",
        "PhaseA.Platform.Tests/TestResults",
        "Tests.Godot/reports",
    ):
        path = repo_root / relative
        if path.exists():
            if include_test_results and older_than(path, keep_test_result_days, now):
                add_deletable_candidate(candidates, path, f"test-results-older-than-{keep_test_result_days}d")
            else:
                reason = (
                    f"recent-test-results-protected-{keep_test_result_days}d"
                    if include_test_results
                    else "test-results-protected-use-include-test-results"
                )
                add_candidate(candidates, path, reason, protected=True)

    data_root = repo_root / "logs" / "phase-a-innernet" / "data"
    if data_root.exists():
        for child in data_root.iterdir():
            if child.name in PROTECTED_PHASEA_DATA:
                add_candidate(candidates, child, "phasea-data-protected", protected=True, measure_size=measure_protected)

    cleanup_root = repo_root / "logs" / "cleanup"
    if cleanup_root.exists():
        for child in cleanup_root.iterdir():
            if is_reparse_or_symlink(child):
                add_candidate(
                    candidates,
                    child,
                    "cleanup-report-reparse-protected",
                    protected=True,
                    measure_size=measure_protected,
                )
                continue
            if not child.is_file() or not child.name.startswith("phasea-daily-cleanup-"):
                continue
            if not (child.suffix in {".json", ".md"}):
                continue
            if include_cleanup_reports and older_than(child, keep_cleanup_report_days, now):
                add_deletable_candidate(candidates, child, f"cleanup-report-older-than-{keep_cleanup_report_days}d")
            else:
                reason = (
                    f"recent-cleanup-report-protected-{keep_cleanup_report_days}d"
                    if include_cleanup_reports
                    else "cleanup-report-protected-use-include-cleanup-reports"
                )
                add_candidate(candidates, child, reason, protected=True, measure_size=measure_protected)

    return candidates


def collect_workspace_audit(repo_root: Path) -> list[dict]:
    workspaces_root = repo_root / "logs" / "phase-a-innernet" / "workspaces"
    project_metadata = read_project_metadata(repo_root)
    workspaces: list[dict] = []
    if not workspaces_root.exists():
        return workspaces

    for account_dir in workspaces_root.iterdir():
        if not account_dir.is_dir():
            continue
        if not HEX32_RE.match(account_dir.name):
            size, files = file_size(account_dir)
            workspaces.append(
                {
                    "path": str(account_dir),
                    "account_dir": account_dir.name,
                    "project_dir": None,
                    "status": "nonstandard-account",
                    "size_bytes": size,
                    "size_mb": round(size / 1024 / 1024, 2),
                    "files": files,
                    "in_metadata": False,
                    "reparse_path": str(find_reparse_or_symlink_descendant(account_dir) or ""),
                }
            )
            continue
        for project_dir in account_dir.iterdir():
            if not project_dir.is_dir():
                continue
            size, files = file_size(project_dir)
            resolved = str(project_dir.resolve()).casefold()
            metadata = project_metadata.get(resolved, {})
            reparse_path = find_reparse_or_symlink_descendant(project_dir)
            if not HEX32_RE.match(project_dir.name):
                status = "nonstandard-project"
            elif metadata:
                status = "live"
            elif reparse_path is not None:
                status = "orphan-reparse-protected"
            else:
                status = "orphan"
            item = {
                "path": str(project_dir),
                "account_dir": account_dir.name,
                "project_dir": project_dir.name,
                "status": status,
                "size_bytes": size,
                "size_mb": round(size / 1024 / 1024, 2),
                "files": files,
                "in_metadata": bool(metadata),
                "reparse_path": str(reparse_path or ""),
                "project_id": metadata.get("project_id"),
                "project_name": metadata.get("name"),
                "game_name": metadata.get("game_name"),
                "game_type_source": metadata.get("game_type_source"),
                "bootstrap_status": metadata.get("bootstrap_status"),
                "bootstrap_error": metadata.get("bootstrap_error"),
                "project_created_utc": metadata.get("project_created_utc"),
                "workspace_created_utc": metadata.get("workspace_created_utc"),
            }
            workspaces.append(item)
    return sorted(workspaces, key=lambda item: item["size_bytes"], reverse=True)


def collect_workspace_lookup(repo_root: Path) -> list[dict]:
    workspaces_root = repo_root / "logs" / "phase-a-innernet" / "workspaces"
    project_metadata = read_project_metadata(repo_root)
    workspaces: list[dict] = []
    if not workspaces_root.exists():
        return workspaces

    for account_dir in workspaces_root.iterdir():
        if not account_dir.is_dir():
            continue
        if not HEX32_RE.match(account_dir.name):
            workspaces.append(
                {
                    "path": str(account_dir),
                    "account_dir": account_dir.name,
                    "project_dir": None,
                    "status": "nonstandard-account",
                    "size_bytes": 0,
                    "size_mb": 0,
                    "files": 0,
                    "in_metadata": False,
                }
            )
            continue
        for project_dir in account_dir.iterdir():
            if not project_dir.is_dir():
                continue
            resolved = str(project_dir.resolve()).casefold()
            metadata = project_metadata.get(resolved, {})
            if not HEX32_RE.match(project_dir.name):
                status = "nonstandard-project"
            elif metadata:
                status = "live"
            else:
                status = "orphan"
            item = {
                "path": str(project_dir),
                "account_dir": account_dir.name,
                "project_dir": project_dir.name,
                "status": status,
                "size_bytes": 0,
                "size_mb": 0,
                "files": 0,
                "in_metadata": bool(metadata),
                "reparse_path": "",
                "project_id": metadata.get("project_id"),
                "project_name": metadata.get("name"),
                "game_name": metadata.get("game_name"),
                "game_type_source": metadata.get("game_type_source"),
                "bootstrap_status": metadata.get("bootstrap_status"),
                "bootstrap_error": metadata.get("bootstrap_error"),
                "project_created_utc": metadata.get("project_created_utc"),
                "workspace_created_utc": metadata.get("workspace_created_utc"),
            }
            workspaces.append(item)
    return workspaces


def find_workspace_by_project_dir(workspaces: list[dict], project_dir_name: str) -> dict | None:
    matches = [item for item in workspaces if item.get("project_dir") == project_dir_name]
    if len(matches) != 1:
        return None
    return matches[0]


def windows_long_path(path: Path | str) -> str:
    text = os.path.abspath(os.fspath(path))
    if os.name != "nt" or text.startswith("\\\\?\\"):
        return text
    if text.startswith("\\\\"):
        return "\\\\?\\UNC\\" + text.lstrip("\\")
    return "\\\\?\\" + text


def path_is_reparse_or_symlink(path: str) -> bool:
    try:
        if os.path.islink(path):
            return True
        attrs = os.lstat(path).st_file_attributes
    except (AttributeError, OSError):
        return False
    return bool(attrs & getattr(os.stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400))


def remove_tree_no_follow(path: str) -> None:
    try:
        path_stat = os.lstat(path)
    except FileNotFoundError:
        return
    is_dir = stat.S_ISDIR(path_stat.st_mode)
    if path_is_reparse_or_symlink(path) or not is_dir:
        make_writable_for_workspace_delete(path)
        if is_dir:
            os.rmdir(path)
        else:
            os.unlink(path)
        return

    try:
        entries = list(os.scandir(path))
    except FileNotFoundError:
        return
    for entry in entries:
        remove_tree_no_follow(entry.path)

    make_writable_for_workspace_delete(path)
    for _ in range(3):
        try:
            os.rmdir(path)
            return
        except FileNotFoundError:
            return
        except OSError as exc:
            if getattr(exc, "winerror", None) != 145:
                raise
            try:
                for entry in list(os.scandir(path)):
                    remove_tree_no_follow(entry.path)
            except FileNotFoundError:
                return
            time.sleep(0.05)
    os.rmdir(path)


def safe_remove_tree_contents(path: Path) -> tuple[bool, str]:
    try:
        if not path.exists():
            return True, ""
        remove_tree_no_follow(windows_long_path(path))
        return True, ""
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def workspace_rmtree_onexc(function, path: str, exc) -> None:
    if isinstance(exc, FileNotFoundError):
        return
    candidate = Path(path)
    make_writable_for_workspace_delete(candidate)
    try:
        function(path)
    except FileNotFoundError:
        return


def make_writable_for_workspace_delete(path: Path | str) -> None:
    try:
        os.chmod(os.fspath(path), stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
    except OSError:
        pass


def safe_remove_workspace_tree(repo_root: Path, path: Path) -> tuple[bool, str]:
    try:
        resolved_root = repo_root.resolve()
        workspaces_root = (repo_root / "logs" / "phase-a-innernet" / "workspaces").resolve()
        resolved_path = path.resolve()
        if resolved_path == resolved_root or resolved_root not in resolved_path.parents:
            return False, f"refusing to delete outside repo root: {resolved_path}"
        if workspaces_root not in resolved_path.parents:
            return False, f"refusing to delete outside workspaces root: {resolved_path}"
        relative = resolved_path.relative_to(workspaces_root)
        if len(relative.parts) != 2:
            return False, f"refusing to delete non-project workspace path: {resolved_path}"
        if not HEX32_RE.match(relative.parts[0]) or not HEX32_RE.match(relative.parts[1]):
            return False, f"refusing to delete nonstandard workspace path: {resolved_path}"
        return safe_remove_tree_contents(path)
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def preflight_remove_tree(path: Path) -> dict:
    result = {
        "path": str(path),
        "exists": path.exists(),
        "files": 0,
        "dirs": 0,
        "reparse_entries": 0,
        "readonly_entries": 0,
        "errors": 0,
        "first_error": "",
    }
    if not path.exists():
        return result

    def walk(current: Path) -> None:
        if result["first_error"]:
            return
        try:
            if is_reparse_or_symlink(current):
                result["reparse_entries"] += 1
                return
            try:
                if current.stat().st_file_attributes & getattr(os.stat, "FILE_ATTRIBUTE_READONLY", 0x0001):
                    result["readonly_entries"] += 1
            except (AttributeError, OSError):
                pass
            if current.is_file():
                result["files"] += 1
                return
            if current.is_dir():
                result["dirs"] += 1
                for child in current.iterdir():
                    walk(child)
        except Exception as exc:
            result["errors"] += 1
            result["first_error"] = f"{type(exc).__name__}: {exc}"

    walk(path)
    return result


def validate_external_workspace_root(path: Path) -> None:
    resolved = path.resolve()
    allowed = Path("C:/workspaces").resolve()
    if resolved != allowed:
        raise CleanupConfigError(f"External workspace root is not allowed: {resolved}")
    if not resolved.exists() or not resolved.is_dir():
        raise CleanupConfigError(f"External workspace root not found: {resolved}")


def collect_external_workspace_audit(root: Path) -> list[dict]:
    validate_external_workspace_root(root)
    items: list[dict] = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        size, files = file_size(child)
        reparse_path = find_reparse_or_symlink_descendant(child)
        try:
            modified = dt.datetime.fromtimestamp(child.stat().st_mtime).isoformat()
        except OSError:
            modified = ""
        items.append(
            {
                "path": str(child),
                "workspace_id": child.name,
                "status": "external-workspace" if HEX32_RE.match(child.name) else "external-nonstandard",
                "size_bytes": size,
                "size_mb": round(size / 1024 / 1024, 2),
                "files": files,
                "last_write": modified,
                "reparse_path": str(reparse_path or ""),
            }
        )
    return sorted(items, key=lambda item: item["size_bytes"], reverse=True)


def collect_external_workspace_lookup(root: Path) -> list[dict]:
    validate_external_workspace_root(root)
    items: list[dict] = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        try:
            modified = dt.datetime.fromtimestamp(child.stat().st_mtime).isoformat()
        except OSError:
            modified = ""
        items.append(
            {
                "path": str(child),
                "workspace_id": child.name,
                "status": "external-workspace" if HEX32_RE.match(child.name) else "external-nonstandard",
                "size_bytes": 0,
                "size_mb": 0,
                "files": 0,
                "last_write": modified,
                "reparse_path": "",
            }
        )
    return items


def run_external_workspace_delete(
    root: Path,
    workspace_ids: list[str],
    apply: bool,
    confirm_external_workspaces: str,
) -> tuple[dict, int]:
    validate_external_workspace_root(root)
    if not workspace_ids:
        raise CleanupConfigError("--external-workspace-delete requires at least one workspace id.")
    if any(not HEX32_RE.match(workspace_id) for workspace_id in workspace_ids):
        raise CleanupConfigError("--external-workspace-delete values must be 32-character hex ids.")
    if apply and confirm_external_workspaces != "EXTERNAL-WORKSPACES":
        raise CleanupConfigError("Apply requires --confirm-external-workspaces EXTERNAL-WORKSPACES.")

    audit = collect_external_workspace_lookup(root)
    by_id = {item["workspace_id"]: item for item in audit}
    selected: list[dict] = []
    failures: list[dict] = []
    deleted: list[dict] = []
    for workspace_id in workspace_ids:
        item = by_id.get(workspace_id)
        if item is None:
            failures.append({"workspace_id": workspace_id, "error": "external_workspace_not_found"})
            continue
        if item["status"] != "external-workspace":
            failures.append({"workspace_id": workspace_id, "path": item["path"], "error": "refusing_nonstandard_external_workspace"})
            continue
        item = dict(item)
        size, files = file_size(Path(item["path"]))
        item["size_bytes"] = size
        item["size_mb"] = round(size / 1024 / 1024, 2)
        item["files"] = files
        reparse_path = find_reparse_or_symlink_descendant(Path(item["path"]))
        item["reparse_path"] = str(reparse_path or "")
        item["delete_preflight"] = preflight_remove_tree(Path(item["path"]))
        selected.append(item)

    failures.extend(
        {
            "workspace_id": item["workspace_id"],
            "path": item["path"],
            "error": f"preflight_failed: {item['delete_preflight']['first_error']}",
        }
        for item in selected
        if item.get("delete_preflight", {}).get("errors")
    )
    blocked_by_failures = bool(failures)
    if apply and not blocked_by_failures:
        for item in selected:
            ok, error = safe_remove_tree_contents(Path(item["path"]))
            if ok:
                deleted.append(item)
            else:
                failed = dict(item)
                failed["error"] = error
                failures.append(failed)

    payload = {
        "mode": "external-workspace-delete" if apply else "external-workspace-delete-dry-run",
        "repo_root": "",
        "external_workspace_root": str(root.resolve()),
        "reclaimable_mb": round(sum(item["size_bytes"] for item in selected) / 1024 / 1024, 2),
        "deleted_mb": round(sum(item["size_bytes"] for item in deleted) / 1024 / 1024, 2),
        "will_apply": bool(apply and not blocked_by_failures),
        "blocked_by_failures": blocked_by_failures,
        "candidates": [],
        "deleted": deleted,
        "failures": failures,
        "selected": selected,
    }
    return payload, 1 if failures else 0


def run_workspace_delete(
    repo_root: Path,
    project_dir_names: list[str],
    apply: bool,
    confirm_orphan_workspaces: str,
) -> tuple[dict, int]:
    if not project_dir_names:
        raise CleanupConfigError("--workspace-delete requires at least one project_dir id.")
    if any(not HEX32_RE.match(project_dir_name) for project_dir_name in project_dir_names):
        raise CleanupConfigError("--workspace-delete values must be 32-character hex project_dir ids.")
    if apply and confirm_orphan_workspaces != "ORPHAN-WORKSPACES":
        raise CleanupConfigError("Apply requires --confirm-orphan-workspaces ORPHAN-WORKSPACES.")

    workspaces = collect_workspace_lookup(repo_root)
    selected: list[dict] = []
    failures: list[dict] = []
    deleted: list[dict] = []
    for project_dir_name in project_dir_names:
        item = find_workspace_by_project_dir(workspaces, project_dir_name)
        if item is None:
            failures.append({"project_dir": project_dir_name, "error": "workspace_not_found_or_not_unique"})
            continue
        if item["status"] == "live":
            failures.append({"project_dir": project_dir_name, "path": item["path"], "error": "refusing_live_workspace"})
            continue
        if item["status"] in {"nonstandard-account", "nonstandard-project"}:
            failures.append({"project_dir": project_dir_name, "path": item["path"], "error": "refusing_nonstandard_workspace"})
            continue
        item = dict(item)
        if item["status"] == "orphan":
            reparse_path = find_reparse_or_symlink_descendant(Path(item["path"]))
            if reparse_path is not None:
                item["status"] = "orphan-reparse-protected"
                item["reparse_path"] = str(reparse_path)
            size, files = file_size(Path(item["path"]))
            item["size_bytes"] = size
            item["size_mb"] = round(size / 1024 / 1024, 2)
            item["files"] = files
        item["delete_preflight"] = preflight_remove_tree(Path(item["path"]))
        selected.append(item)

    preflight_failures = [
        {
            "project_dir": item["project_dir"],
            "path": item["path"],
            "error": f"preflight_failed: {item['delete_preflight']['first_error']}",
        }
        for item in selected
        if item.get("delete_preflight", {}).get("errors")
    ]
    failures.extend(preflight_failures)
    blocked_by_failures = bool(failures)
    if apply and not blocked_by_failures:
        for item in selected:
            ok, error = safe_remove_workspace_tree(repo_root, Path(item["path"]))
            if ok:
                deleted.append(item)
            else:
                failed = dict(item)
                failed["error"] = error
                failures.append(failed)

    payload = {
        "mode": "workspace-delete" if apply else "workspace-delete-dry-run",
        "repo_root": str(repo_root),
        "reclaimable_mb": round(sum(item["size_bytes"] for item in selected) / 1024 / 1024, 2),
        "deleted_mb": round(sum(item["size_bytes"] for item in deleted) / 1024 / 1024, 2),
        "will_apply": bool(apply and not blocked_by_failures),
        "blocked_by_failures": blocked_by_failures,
        "candidates": [],
        "deleted": deleted,
        "failures": failures,
        "selected": selected,
    }
    return payload, 1 if failures else 0


def remove_path(repo_root: Path, path: Path) -> tuple[bool, str]:
    try:
        resolved_root = repo_root.resolve()
        resolved_path = path.resolve()
        if resolved_path == resolved_root or resolved_root not in resolved_path.parents:
            return False, f"refusing to delete outside repo root: {resolved_path}"
        if is_reparse_or_symlink(path):
            return False, f"refusing to delete reparse point or symlink: {path}"
        reparse_path = find_reparse_or_symlink_descendant(path)
        if reparse_path is not None:
            return False, f"refusing to delete tree containing reparse point or symlink: {reparse_path}"
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
        return True, ""
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def write_reports(repo_root: Path, payload: dict) -> tuple[Path, Path]:
    report_root = repo_root / "logs" / "cleanup"
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    suffix = uuid.uuid4().hex[:8]
    json_path = report_root / f"phasea-daily-cleanup-{stamp}-{suffix}.json"
    md_path = report_root / f"phasea-daily-cleanup-{stamp}-{suffix}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Phase A Daily Cleanup",
        "",
        f"- mode: `{payload['mode']}`",
        f"- reclaimable_mb: `{payload['reclaimable_mb']}`",
        f"- deleted_mb: `{payload['deleted_mb']}`",
        f"- candidates: `{len(payload['candidates'])}`",
        f"- deleted: `{len(payload['deleted'])}`",
        f"- failures: `{len(payload['failures'])}`",
        "",
        "## Largest Reclaimable",
        "",
    ]
    reclaimable = [item for item in payload["candidates"] if not item["protected"]]
    for item in sorted(reclaimable, key=lambda x: x["size_bytes"], reverse=True)[:20]:
        lines.append(f"- `{item['size_mb']} MB` `{item['reason']}` {item['path']}")
    if payload["failures"]:
        lines.extend(["", "## Failures", ""])
        for item in payload["failures"]:
            lines.append(f"- `{item['error']}` {item['path']}")
    if payload["mode"] == "workspace-audit":
        lines.extend(
            [
                "",
                "## Workspace Summary",
                "",
                f"- workspace_mb: `{payload.get('workspace_mb')}`",
                f"- workspace_orphan_mb: `{payload.get('workspace_orphan_mb')}`",
                f"- workspace_orphan_reparse_mb: `{payload.get('workspace_orphan_reparse_mb')}`",
                "",
                "## Largest Workspaces",
                "",
            ]
        )
        for item in payload.get("workspaces", [])[:30]:
            label = item.get("project_name") or item.get("project_dir") or item.get("account_dir")
            lines.append(
                f"- `{item['size_mb']} MB` `{item['status']}` "
                f"`{item.get('bootstrap_status')}` {label} {item['path']}"
            )
    if payload["mode"] in {"workspace-delete-dry-run", "workspace-delete"}:
        lines.extend(
            [
                "",
                "## Workspace Delete State",
                "",
                f"- will_apply: `{payload.get('will_apply')}`",
                f"- blocked_by_failures: `{payload.get('blocked_by_failures')}`",
                "",
                "## Selected Workspaces",
                "",
            ]
        )
        for item in payload.get("selected", []):
            preflight = item.get("delete_preflight", {})
            lines.append(
                f"- `{item['size_mb']} MB` `{item['status']}` "
                f"`{item.get('project_dir')}` "
                f"files=`{preflight.get('files')}` dirs=`{preflight.get('dirs')}` "
                f"reparse=`{preflight.get('reparse_entries')}` errors=`{preflight.get('errors')}` "
                f"readonly=`{preflight.get('readonly_entries')}` "
                f"{item['path']}"
            )
    if payload["mode"] == "external-workspace-audit":
        lines.extend(
            [
                "",
                "## External Workspace Summary",
                "",
                f"- external_workspace_root: `{payload.get('external_workspace_root')}`",
                f"- external_workspace_mb: `{payload.get('external_workspace_mb')}`",
                f"- external_workspace_count: `{payload.get('external_workspace_count')}`",
                "",
                "## Largest External Workspaces",
                "",
            ]
        )
        for item in payload.get("external_workspaces", [])[:50]:
            lines.append(f"- `{item['size_mb']} MB` `{item['status']}` `{item['workspace_id']}` {item['path']}")
    if payload["mode"] in {"external-workspace-delete-dry-run", "external-workspace-delete"}:
        lines.extend(
            [
                "",
                "## External Workspace Delete State",
                "",
                f"- external_workspace_root: `{payload.get('external_workspace_root')}`",
                f"- will_apply: `{payload.get('will_apply')}`",
                f"- blocked_by_failures: `{payload.get('blocked_by_failures')}`",
                "",
                "## Selected External Workspaces",
                "",
            ]
        )
        for item in payload.get("selected", []):
            preflight = item.get("delete_preflight", {})
            lines.append(
                f"- `{item['size_mb']} MB` `{item['status']}` "
                f"`{item.get('workspace_id')}` "
                f"files=`{preflight.get('files')}` dirs=`{preflight.get('dirs')}` "
                f"reparse=`{preflight.get('reparse_entries')}` errors=`{preflight.get('errors')}` "
                f"readonly=`{preflight.get('readonly_entries')}` "
                f"{item['path']}"
            )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit and clean Phase A local runtime clutter.")
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--apply", action="store_true", help="Delete reclaimable candidates.")
    parser.add_argument("--confirm-delete", default="", help="Required with --apply. Must be DELETE.")
    parser.add_argument("--keep-log-days", type=int, default=3)
    parser.add_argument("--keep-tmp-days", type=int, default=1)
    parser.add_argument("--keep-orphan-days", type=int, default=1)
    parser.add_argument("--keep-test-result-days", type=int, default=1)
    parser.add_argument("--include-test-results", action="store_true", help="Allow deletion of old test result folders.")
    parser.add_argument("--max-delete-mb", type=float, default=2048.0, help="Maximum reclaimable MB allowed for one apply run. Use 0 to disable.")
    parser.add_argument("--max-tmp-candidates", type=int, default=200, help="Maximum old tmp children to include per run. Use 0 for unlimited.")
    parser.add_argument("--measure-protected", action="store_true", help="Measure protected directory sizes. Slower but useful for audits.")
    parser.add_argument("--keep-cleanup-report-days", type=int, default=14)
    parser.add_argument("--include-cleanup-reports", action="store_true", help="Allow deletion of old phasea-daily-cleanup reports.")
    parser.add_argument("--confirm-cleanup-reports", default="", help="Required with --apply --include-cleanup-reports. Must be CLEANUP-REPORTS.")
    parser.add_argument("--confirm-unbounded-delete", default="", help="Required with --apply --max-delete-mb 0. Must be UNBOUNDED.")
    parser.add_argument("--workspace-audit", action="store_true", help="Write a read-only workspace disk usage audit report.")
    parser.add_argument("--workspace-delete", action="append", default=[], help="Dry-run or delete one orphan workspace by 32-character project_dir id. Repeatable.")
    parser.add_argument("--confirm-orphan-workspaces", default="", help="Required with --apply --workspace-delete. Must be ORPHAN-WORKSPACES.")
    parser.add_argument("--external-workspace-root", default="C:\\workspaces", help="Allowed external workspace root. Only C:\\workspaces is accepted.")
    parser.add_argument("--external-workspace-audit", action="store_true", help="Write a read-only C:\\workspaces audit report.")
    parser.add_argument("--external-workspace-delete", action="append", default=[], help="Dry-run or delete one C:\\workspaces child by 32-character id. Repeatable.")
    parser.add_argument("--confirm-external-workspaces", default="", help="Required with --apply --external-workspace-delete. Must be EXTERNAL-WORKSPACES.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    if (
        args.keep_log_days < 0
        or args.keep_tmp_days < 0
        or args.keep_orphan_days < 0
        or args.keep_test_result_days < 0
        or args.keep_cleanup_report_days < 0
    ):
        print("PHASEA_DAILY_CLEANUP error=retention_days_must_be_non_negative")
        return 2
    if args.max_delete_mb < 0 or args.max_tmp_candidates < 0:
        print("PHASEA_DAILY_CLEANUP error=limits_must_be_non_negative")
        return 2
    if args.apply and args.confirm_delete != "DELETE":
        print("PHASEA_DAILY_CLEANUP error=confirm_delete_required hint=use --confirm-delete DELETE")
        return 2
    if args.apply and args.workspace_audit:
        print("PHASEA_DAILY_CLEANUP error=workspace_audit_is_read_only")
        return 2
    if args.workspace_audit and args.workspace_delete:
        print("PHASEA_DAILY_CLEANUP error=workspace_audit_cannot_combine_with_workspace_delete")
        return 2
    if args.external_workspace_audit and args.external_workspace_delete:
        print("PHASEA_DAILY_CLEANUP error=external_workspace_audit_cannot_combine_with_external_workspace_delete")
        return 2
    if args.apply and args.external_workspace_audit:
        print("PHASEA_DAILY_CLEANUP error=external_workspace_audit_is_read_only")
        return 2
    if args.apply and args.max_delete_mb == 0 and args.confirm_unbounded_delete != "UNBOUNDED":
        print(
            "PHASEA_DAILY_CLEANUP error=confirm_unbounded_delete_required "
            "hint=use --confirm-unbounded-delete UNBOUNDED"
        )
        return 2
    if args.include_cleanup_reports and args.keep_cleanup_report_days < MIN_CLEANUP_REPORT_DAYS:
        print(
            "PHASEA_DAILY_CLEANUP error=cleanup_report_retention_too_low "
            f"min_days={MIN_CLEANUP_REPORT_DAYS}"
        )
        return 2
    if args.apply and args.include_cleanup_reports and args.confirm_cleanup_reports != "CLEANUP-REPORTS":
        print(
            "PHASEA_DAILY_CLEANUP error=confirm_cleanup_reports_required "
            "hint=use --confirm-cleanup-reports CLEANUP-REPORTS"
        )
        return 2

    try:
        validate_repo_root(repo_root)
        external_root = Path(args.external_workspace_root).resolve()
        if args.external_workspace_delete:
            payload, status = run_external_workspace_delete(
                external_root,
                args.external_workspace_delete,
                args.apply,
                args.confirm_external_workspaces,
            )
            json_path, md_path = write_reports(repo_root, payload)
            print(
                "PHASEA_DAILY_CLEANUP "
                f"mode={payload['mode']} reclaimable_mb={payload['reclaimable_mb']} "
                f"deleted_mb={payload['deleted_mb']} failures={len(payload['failures'])} report={json_path}"
            )
            print(f"PHASEA_DAILY_CLEANUP_MARKDOWN report={md_path}")
            return status
        if args.external_workspace_audit:
            external_workspaces = collect_external_workspace_audit(external_root)
            total_bytes = sum(item["size_bytes"] for item in external_workspaces)
            payload = {
                "mode": "external-workspace-audit",
                "repo_root": str(repo_root),
                "external_workspace_root": str(external_root),
                "reclaimable_mb": 0,
                "deleted_mb": 0,
                "candidates": [],
                "deleted": [],
                "failures": [],
                "external_workspace_count": len(external_workspaces),
                "external_workspace_bytes": total_bytes,
                "external_workspace_mb": round(total_bytes / 1024 / 1024, 2),
                "external_workspaces": external_workspaces,
            }
            json_path, md_path = write_reports(repo_root, payload)
            print(
                "PHASEA_DAILY_CLEANUP "
                f"mode=external-workspace-audit external_workspace_mb={payload['external_workspace_mb']} "
                f"external_workspace_count={payload['external_workspace_count']} report={json_path}"
            )
            print(f"PHASEA_DAILY_CLEANUP_MARKDOWN report={md_path}")
            return 0
        if args.workspace_delete:
            payload, status = run_workspace_delete(
                repo_root,
                args.workspace_delete,
                args.apply,
                args.confirm_orphan_workspaces,
            )
            json_path, md_path = write_reports(repo_root, payload)
            print(
                "PHASEA_DAILY_CLEANUP "
                f"mode={payload['mode']} reclaimable_mb={payload['reclaimable_mb']} "
                f"deleted_mb={payload['deleted_mb']} failures={len(payload['failures'])} report={json_path}"
            )
            print(f"PHASEA_DAILY_CLEANUP_MARKDOWN report={md_path}")
            return status
        if args.workspace_audit:
            workspaces = collect_workspace_audit(repo_root)
            total_bytes = sum(item["size_bytes"] for item in workspaces)
            orphan_bytes = sum(item["size_bytes"] for item in workspaces if item["status"] == "orphan")
            orphan_reparse_bytes = sum(
                item["size_bytes"] for item in workspaces if item["status"] == "orphan-reparse-protected"
            )
            payload = {
                "mode": "workspace-audit",
                "repo_root": str(repo_root),
                "reclaimable_mb": 0,
                "deleted_mb": 0,
                "candidates": [],
                "deleted": [],
                "failures": [],
                "workspace_count": len(workspaces),
                "workspace_bytes": total_bytes,
                "workspace_mb": round(total_bytes / 1024 / 1024, 2),
                "workspace_orphan_mb": round(orphan_bytes / 1024 / 1024, 2),
                "workspace_orphan_reparse_mb": round(orphan_reparse_bytes / 1024 / 1024, 2),
                "workspaces": workspaces,
            }
            json_path, md_path = write_reports(repo_root, payload)
            print(
                "PHASEA_DAILY_CLEANUP "
                f"mode=workspace-audit workspace_mb={payload['workspace_mb']} "
                f"workspace_count={payload['workspace_count']} report={json_path}"
            )
            print(f"PHASEA_DAILY_CLEANUP_MARKDOWN report={md_path}")
            return 0
        candidates = collect_candidates(
            repo_root,
            args.keep_log_days,
            args.keep_tmp_days,
            args.keep_orphan_days,
            args.keep_test_result_days,
            args.include_test_results,
            args.max_tmp_candidates,
            args.measure_protected,
            args.keep_cleanup_report_days,
            args.include_cleanup_reports,
        )
    except CleanupConfigError as exc:
        print(f"PHASEA_DAILY_CLEANUP error=config {exc}")
        return 2
    reclaimable = [item for item in candidates if not item["protected"]]
    deleted: list[dict] = []
    failures: list[dict] = []
    reclaimable_mb = round(sum(item["size_bytes"] for item in reclaimable) / 1024 / 1024, 2)

    if args.apply and args.max_delete_mb > 0 and reclaimable_mb > args.max_delete_mb:
        payload = {
            "mode": "blocked",
            "repo_root": str(repo_root),
            "keep_log_days": args.keep_log_days,
            "keep_tmp_days": args.keep_tmp_days,
            "keep_orphan_days": args.keep_orphan_days,
            "keep_test_result_days": args.keep_test_result_days,
            "include_test_results": args.include_test_results,
            "max_delete_mb": args.max_delete_mb,
            "max_tmp_candidates": args.max_tmp_candidates,
            "measure_protected": args.measure_protected,
            "keep_cleanup_report_days": args.keep_cleanup_report_days,
            "include_cleanup_reports": args.include_cleanup_reports,
            "confirm_cleanup_reports": bool(args.confirm_cleanup_reports),
            "confirm_unbounded_delete": bool(args.confirm_unbounded_delete),
            "reclaimable_bytes": sum(item["size_bytes"] for item in reclaimable),
            "reclaimable_mb": reclaimable_mb,
            "deleted_bytes": 0,
            "deleted_mb": 0,
            "candidates": candidates,
            "deleted": deleted,
            "failures": [
                {
                    "path": str(repo_root),
                    "error": f"reclaimable_mb {reclaimable_mb} exceeds max_delete_mb {args.max_delete_mb}",
                }
            ],
        }
        json_path, md_path = write_reports(repo_root, payload)
        print(
            "PHASEA_DAILY_CLEANUP "
            f"error=max_delete_mb_exceeded reclaimable_mb={reclaimable_mb} "
            f"max_delete_mb={args.max_delete_mb} report={json_path}"
        )
        print(f"PHASEA_DAILY_CLEANUP_MARKDOWN report={md_path}")
        return 2

    if args.apply:
        for item in reclaimable:
            ok, error = remove_path(repo_root, Path(item["path"]))
            if ok:
                deleted.append(item)
            else:
                failed = dict(item)
                failed["error"] = error
                failures.append(failed)

    payload = {
        "mode": "apply" if args.apply else "dry-run",
        "repo_root": str(repo_root),
        "keep_log_days": args.keep_log_days,
        "keep_tmp_days": args.keep_tmp_days,
        "keep_orphan_days": args.keep_orphan_days,
        "keep_test_result_days": args.keep_test_result_days,
        "include_test_results": args.include_test_results,
        "max_delete_mb": args.max_delete_mb,
        "max_tmp_candidates": args.max_tmp_candidates,
        "measure_protected": args.measure_protected,
        "keep_cleanup_report_days": args.keep_cleanup_report_days,
        "include_cleanup_reports": args.include_cleanup_reports,
        "confirm_cleanup_reports": bool(args.confirm_cleanup_reports),
        "confirm_unbounded_delete": bool(args.confirm_unbounded_delete),
        "reclaimable_bytes": sum(item["size_bytes"] for item in reclaimable),
        "reclaimable_mb": reclaimable_mb,
        "deleted_bytes": sum(item["size_bytes"] for item in deleted),
        "deleted_mb": round(sum(item["size_bytes"] for item in deleted) / 1024 / 1024, 2),
        "candidates": candidates,
        "deleted": deleted,
        "failures": failures,
    }
    json_path, md_path = write_reports(repo_root, payload)
    print(f"PHASEA_DAILY_CLEANUP mode={payload['mode']} reclaimable_mb={payload['reclaimable_mb']} deleted_mb={payload['deleted_mb']} report={json_path}")
    print(f"PHASEA_DAILY_CLEANUP_MARKDOWN report={md_path}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
