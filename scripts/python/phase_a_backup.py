from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sqlite3
import zipfile
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a Phase A SQLite/workspace backup bundle.")
    parser.add_argument("--metadata-db", default=os.environ.get("PHASEA_METADATA_DB_PATH", ""))
    parser.add_argument("--workspace-root", default=os.environ.get("HOSTED_WORKSPACE_ROOT", ""))
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--include-logs", action="store_true")
    parser.add_argument("--logs-root", default="logs")
    args = parser.parse_args()

    metadata_db = require_file("--metadata-db", args.metadata_db)
    workspace_root = require_directory("--workspace-root", args.workspace_root)
    out_dir = Path(args.out_dir) if args.out_dir else Path("logs") / "ci" / dt.date.today().isoformat() / "phase-a-backup"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_db = out_dir / f"phase-a-metadata-{stamp}.sqlite3"
    backup_zip = out_dir / f"phase-a-workspaces-{stamp}.zip"
    manifest_path = out_dir / f"phase-a-backup-{stamp}.json"

    sqlite_backup(metadata_db, backup_db)
    zip_directory(workspace_root, backup_zip)
    log_zip = None
    if args.include_logs:
        logs_root = Path(args.logs_root)
        if logs_root.exists():
            log_zip = out_dir / f"phase-a-logs-{stamp}.zip"
            zip_directory(logs_root, log_zip)

    manifest: dict[str, Any] = {
        "status": "ok",
        "created_utc": stamp,
        "metadata_source": str(metadata_db),
        "workspace_source": str(workspace_root),
        "metadata_backup": str(backup_db),
        "workspace_backup": str(backup_zip),
        "logs_backup": str(log_zip) if log_zip else "",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8", newline="\n")
    print(f"PHASE_A_BACKUP status=ok manifest={manifest_path}")
    return 0


def require_file(label: str, value: str) -> Path:
    if not value:
        raise SystemExit(f"{label} is required")
    path = Path(value)
    if not path.is_file():
        raise SystemExit(f"{label} does not exist: {path}")
    return path


def require_directory(label: str, value: str) -> Path:
    if not value:
        raise SystemExit(f"{label} is required")
    path = Path(value)
    if not path.is_dir():
        raise SystemExit(f"{label} does not exist: {path}")
    return path


def sqlite_backup(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
        src.backup(dst)


def zip_directory(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in source.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(source).as_posix())


if __name__ == "__main__":
    raise SystemExit(main())
