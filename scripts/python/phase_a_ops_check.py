from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import sys
import urllib.parse
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Phase A deployment operations prerequisites.")
    parser.add_argument("--repository-root", default=os.environ.get("PHASEA_REPOSITORY_ROOT", str(Path.cwd())))
    parser.add_argument("--workspace-root", default=os.environ.get("HOSTED_WORKSPACE_ROOT", ""))
    parser.add_argument("--metadata-db", default=os.environ.get("PHASEA_METADATA_DB_PATH", ""))
    parser.add_argument("--app-bind-url", default=os.environ.get("APP_BIND_URL", "http://127.0.0.1:8080"))
    parser.add_argument("--public-base-url", default=os.environ.get("PUBLIC_BASE_URL", ""))
    parser.add_argument("--https-termination", default=os.environ.get("HTTPS_TERMINATION", "caddy"))
    parser.add_argument("--godot-bin", default=os.environ.get("GODOT_BIN", ""))
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    checks: list[dict[str, Any]] = []
    checks.append(check_directory("repository_root", args.repository_root, must_exist=True))
    checks.append(check_directory("workspace_root", args.workspace_root, must_exist=False))
    checks.append(check_parent_directory("metadata_db", args.metadata_db))
    checks.append(check_command("python_launcher", "py"))
    checks.append(check_command("dotnet", "dotnet"))
    if args.godot_bin:
        checks.append(check_file("godot_bin", args.godot_bin))
    else:
        checks.append({"name": "godot_bin", "status": "warn", "message": "GODOT_BIN is not set; Day 5/GdUnit checks must remain disabled."})
    checks.append(check_app_bind(args.app_bind_url, args.https_termination))
    checks.append(check_public_base_url(args.public_base_url))

    status = "ok"
    if any(item["status"] == "fail" for item in checks):
        status = "fail"
    elif any(item["status"] == "warn" for item in checks):
        status = "warn"

    payload = {"status": status, "checks": checks}
    out_path = Path(args.out) if args.out else default_out_path()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8", newline="\n")
    print(f"PHASE_A_OPS_CHECK status={status} out={out_path}")
    return 0 if status in {"ok", "warn"} else 1


def default_out_path() -> Path:
    import datetime as dt

    return Path("logs") / "ci" / dt.date.today().isoformat() / "phase-a-ops-check" / "summary.json"


def check_directory(name: str, value: str, *, must_exist: bool) -> dict[str, str]:
    if not value:
        return {"name": name, "status": "fail", "message": "path is required"}
    path = Path(value)
    if not path.is_absolute():
        return {"name": name, "status": "fail", "message": "path must be absolute"}
    if must_exist and not path.is_dir():
        return {"name": name, "status": "fail", "message": "directory does not exist"}
    if not must_exist:
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as ex:
            return {"name": name, "status": "fail", "message": f"directory cannot be created: {ex}"}
    return {"name": name, "status": "ok", "message": str(path)}


def check_parent_directory(name: str, value: str) -> dict[str, str]:
    if not value:
        return {"name": name, "status": "fail", "message": "path is required"}
    path = Path(value)
    if not path.is_absolute():
        return {"name": name, "status": "fail", "message": "path must be absolute"}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as ex:
        return {"name": name, "status": "fail", "message": f"parent directory cannot be created: {ex}"}
    return {"name": name, "status": "ok", "message": str(path)}


def check_file(name: str, value: str) -> dict[str, str]:
    path = Path(value)
    if not path.is_file():
        return {"name": name, "status": "fail", "message": "file does not exist"}
    return {"name": name, "status": "ok", "message": str(path)}


def check_command(name: str, command: str) -> dict[str, str]:
    resolved = shutil.which(command)
    if not resolved:
        return {"name": name, "status": "fail", "message": f"{command} is not on PATH"}
    return {"name": name, "status": "ok", "message": resolved}


def check_app_bind(value: str, https_termination: str) -> dict[str, str]:
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return {"name": "app_bind_url", "status": "fail", "message": "APP_BIND_URL must be absolute HTTP/HTTPS"}
    if https_termination.lower() == "caddy":
        if parsed.scheme != "http":
            return {"name": "app_bind_url", "status": "fail", "message": "APP_BIND_URL must use HTTP behind Caddy"}
        if parsed.hostname.lower() not in {"127.0.0.1", "localhost"}:
            return {"name": "app_bind_url", "status": "fail", "message": "APP_BIND_URL must bind localhost behind Caddy"}
    port = parsed.port or (80 if parsed.scheme == "http" else 443)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        result = sock.connect_ex((parsed.hostname, port))
    if result == 0:
        return {"name": "app_bind_url", "status": "warn", "message": "port is already listening; this is ok only if PhaseA is running"}
    return {"name": "app_bind_url", "status": "ok", "message": value}


def check_public_base_url(value: str) -> dict[str, str]:
    if not value:
        return {"name": "public_base_url", "status": "warn", "message": "PUBLIC_BASE_URL is not set; public smoke must wait"}
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        return {"name": "public_base_url", "status": "fail", "message": "PUBLIC_BASE_URL must be absolute HTTPS"}
    return {"name": "public_base_url", "status": "ok", "message": value}


if __name__ == "__main__":
    raise SystemExit(main())
