#!/usr/bin/env python3
"""Safely retire old Phase-A game workspaces without following reparse points.

This tool is deliberately physical-only. It never edits the Phase metadata DB.
Use the service/admin lifecycle to remove project rows separately.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sqlite3
from pathlib import Path


HEX32 = set("0123456789abcdef")


def is_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        return bool(path.stat(follow_symlinks=False).st_file_attributes & 0x400)
    except (AttributeError, OSError):
        return False


def allowed_workspace(path: Path, root: Path) -> bool:
    try:
        rel = path.resolve(strict=False).relative_to(root.resolve())
    except ValueError:
        return False
    return len(rel.parts) == 2 and all(len(x) == 32 and set(x.casefold()) <= HEX32 for x in rel.parts)


def walk_no_follow(path: Path) -> tuple[int, int, int, list[str]]:
    files = dirs = reparses = 0
    errors: list[str] = []
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            if current != path and is_reparse(current):
                reparses += 1
                continue
            if current.is_file():
                files += 1
                continue
            if not current.is_dir():
                continue
            dirs += 1
            with os.scandir(current) as entries:
                for entry in entries:
                    child = Path(entry.path)
                    try:
                        if entry.is_symlink() or bool(entry.stat(follow_symlinks=False).st_file_attributes & 0x400):
                            reparses += 1
                        elif entry.is_dir(follow_symlinks=False):
                            stack.append(child)
                        else:
                            files += 1
                    except OSError as exc:
                        errors.append(f"{child}: {type(exc).__name__}: {exc}")
        except OSError as exc:
            errors.append(f"{current}: {type(exc).__name__}: {exc}")
    return files, dirs, reparses, errors


def remove_no_follow(path: Path, root: Path) -> tuple[bool, str]:
    if not allowed_workspace(path, root) or path.resolve() == root.resolve():
        return False, "target is not an approved two-level workspace path"
    if not path.exists():
        return True, "already absent"
    stack = [path]
    try:
        while stack:
            current = stack[-1]
            if is_reparse(current) and current != path:
                current.unlink(missing_ok=True)
                stack.pop()
                continue
            if current.is_file():
                try:
                    current.chmod(current.stat().st_mode | 0o200)
                except OSError:
                    pass
                current.unlink()
                stack.pop()
                continue
            children = list(current.iterdir())
            if children:
                stack.extend(reversed(children))
                continue
            current.rmdir()
            stack.pop()
        return True, ""
    except OSError as exc:
        return False, f"{type(exc).__name__}: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    repo = Path(args.repo_root).resolve()
    root = (repo / "logs" / "phase-a-innernet" / "workspaces").resolve()
    db = repo / "logs" / "phase-a-innernet" / "data" / "phase-a-platform.sqlite3"
    if not (repo / "AGENTS.md").exists() or not db.exists() or not root.is_dir():
        raise SystemExit("refusing: repository/runtime root validation failed")
    con = sqlite3.connect(db)
    rows = con.execute("SELECT p.id,p.name,w.root_path FROM projects p JOIN workspaces w ON w.project_id=p.id ORDER BY p.id").fetchall()
    con.close()
    selected = []
    for project_id, name, raw in rows:
        path = Path(raw).resolve(strict=False)
        if not allowed_workspace(path, root):
            continue
        files, dirs, reparses, errors = walk_no_follow(path) if path.exists() else (0, 0, 0, [])
        selected.append({"project_id": project_id, "name": name, "path": str(path), "files": files, "dirs": dirs, "reparse_entries": reparses, "errors": errors})
    report = {"schema": "retire-old-game-workspaces.v1", "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "mode": "apply" if args.apply else "dry-run", "selected": selected, "removed": [], "failures": []}
    if args.apply:
        if args.confirm != "RETIRE-OLD-GAME-WORKSPACES":
            raise SystemExit("apply requires --confirm RETIRE-OLD-GAME-WORKSPACES")
        for item in selected:
            ok, error = remove_no_follow(Path(item["path"]), root)
            (report["removed"] if ok else report["failures"]).append({"project_id": item["project_id"], "path": item["path"], **({} if ok else {"error": error})})
    out = repo / "logs" / "cleanup" / f"retire-old-game-workspaces-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(out), "selected": len(selected), "removed": len(report["removed"]), "failures": len(report["failures"])}, ensure_ascii=False))
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
