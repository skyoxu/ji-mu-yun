from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from pathlib import Path
from typing import Any


ADMIN_TOKEN = "phase-a-restore-drill-admin-token"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a Phase A backup/restore drill.")
    parser.add_argument("--repository-root", default=str(Path.cwd()))
    parser.add_argument("--dotnet", default=None)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    args = parser.parse_args()

    repository_root = Path(args.repository_root).resolve()
    dotnet = find_dotnet(args.dotnet)
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    run_dir = repository_root / "logs" / "ci" / dt.date.today().isoformat() / "phase-a-restore-drill" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    events: list[dict[str, Any]] = []
    exit_code = 1
    try:
        source_workspace = run_dir / "source-workspaces"
        source_db = run_dir / "source.sqlite3"
        seed_fixture(source_workspace, source_db)
        events.append({"event": "fixture_seeded", "workspace": str(source_workspace), "metadata_db": str(source_db)})

        backup_dir = run_dir / "backup"
        run_backup(repository_root, source_db, source_workspace, backup_dir)
        manifest = latest_manifest(backup_dir)
        events.append({"event": "backup_created", "manifest": str(manifest)})

        restored_workspace = run_dir / "restored-workspaces"
        restored_db = run_dir / "restored.sqlite3"
        restore_from_manifest(manifest, restored_db, restored_workspace)
        assert_restored_fixture(restored_workspace, restored_db)
        events.append({"event": "restore_files_verified", "workspace": str(restored_workspace), "metadata_db": str(restored_db)})

        service = PhaseAService(
            repository_root=repository_root,
            dotnet=dotnet,
            workspace_root=restored_workspace,
            metadata_db=restored_db,
            admin_token=ADMIN_TOKEN,
            run_dir=run_dir / "service",
        )
        with service:
            service.wait_for_health(args.timeout_seconds)
            projects = service.get_json("/api/projects", token=ADMIN_TOKEN)
            if not any(item.get("gameName") == "Restore Drill Game" for item in projects):
                raise AssertionError(f"restored project was not visible through API: {projects}")
            events.append({"event": "restored_service_readback_ok", "project_count": len(projects)})

        exit_code = 0
        return 0
    except Exception as ex:
        events.append({"event": "restore_drill_failed", "error": str(ex), "type": type(ex).__name__})
        print(f"PHASE_A_RESTORE_DRILL status=failed run_dir={run_dir} error={ex}")
        return 1
    finally:
        summary = {"status": "ok" if exit_code == 0 else "failed", "run_id": run_id, "events": events}
        (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8", newline="\n")
        if exit_code == 0:
            print(f"PHASE_A_RESTORE_DRILL status=ok run_dir={run_dir}")


def seed_fixture(workspace_root: Path, metadata_db: Path) -> None:
    account_id = "restore-account"
    project_id = "restore-project"
    workspace_id = "restore-workspace"
    repo_path = workspace_root / account_id / project_id / "repo"
    runtime_path = workspace_root / account_id / project_id / "runtime"
    meta_path = workspace_root / account_id / project_id / "meta"
    for path in [repo_path, runtime_path, meta_path]:
        path.mkdir(parents=True, exist_ok=True)
    (repo_path / "restore-marker.txt").write_text("restore drill marker", encoding="utf-8")
    metadata_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(metadata_db) as con:
        con.executescript(
            """
            CREATE TABLE accounts (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NULL,
                token_hash TEXT NULL,
                is_admin INTEGER NOT NULL,
                created_utc TEXT NOT NULL
            );
            CREATE TABLE projects (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                name TEXT NOT NULL,
                game_name TEXT NOT NULL,
                game_type_source TEXT NOT NULL,
                template_rule_id TEXT NOT NULL,
                workspace_root_path TEXT NOT NULL,
                llm_binding_required INTEGER NOT NULL DEFAULT 0,
                allowed_workflows_json TEXT NOT NULL DEFAULT '[]',
                created_utc TEXT NOT NULL
            );
            CREATE TABLE workspaces (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                root_path TEXT NOT NULL,
                repo_path TEXT NOT NULL,
                runtime_path TEXT NOT NULL,
                meta_path TEXT NOT NULL,
                created_utc TEXT NOT NULL
            );
            CREATE TABLE runs (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                workspace_id TEXT NULL,
                run_type TEXT NOT NULL,
                status TEXT NOT NULL,
                exit_code INTEGER NULL,
                stdout_text TEXT NULL,
                stderr_text TEXT NULL,
                evidence_json TEXT NULL,
                llm_gateway TEXT NULL,
                llm_request_id TEXT NULL,
                llm_model TEXT NULL,
                llm_cost_json TEXT NULL,
                created_utc TEXT NOT NULL,
                started_utc TEXT NULL,
                completed_utc TEXT NULL
            );
            CREATE TABLE artifacts (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                artifact_type TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                summary TEXT NOT NULL,
                created_utc TEXT NOT NULL
            );
            CREATE TABLE runner_locks (
                project_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                acquired_utc TEXT NOT NULL
            );
            CREATE TABLE project_limits (
                account_id TEXT PRIMARY KEY,
                project_limit INTEGER NOT NULL
            );
            CREATE TABLE account_llm_bindings (
                account_id TEXT PRIMARY KEY,
                gateway_provider TEXT NOT NULL,
                gateway_base_url TEXT NOT NULL,
                external_account_ref TEXT NOT NULL,
                token_ref TEXT NOT NULL,
                created_utc TEXT NOT NULL,
                updated_utc TEXT NOT NULL
            );
            """
        )
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        con.execute("INSERT INTO accounts VALUES (?, ?, NULL, ?, 1, ?)", (account_id, "admin", ADMIN_TOKEN, now))
        con.execute(
            "INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)",
            (
                project_id,
                account_id,
                "restore-project",
                "Restore Drill Game",
                "restore-drill",
                "godot-prototype-default",
                str(workspace_root),
                json.dumps(["chapter2-bootstrap", "prototype-7day-playable", "prototype-tdd", "prototype-scene"]),
                now,
            ),
        )
        con.execute(
            "INSERT INTO workspaces VALUES (?, ?, ?, ?, ?, ?, ?)",
            (workspace_id, project_id, str(workspace_root), str(repo_path), str(runtime_path), str(meta_path), now),
        )


def run_backup(repository_root: Path, metadata_db: Path, workspace_root: Path, backup_dir: Path) -> None:
    command = [
        "py",
        "-3",
        "scripts/python/dev_cli.py",
        "phase-a-backup",
        "--metadata-db",
        str(metadata_db),
        "--workspace-root",
        str(workspace_root),
        "--out-dir",
        str(backup_dir),
    ]
    result = subprocess.run(command, cwd=str(repository_root), text=True, capture_output=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"backup failed rc={result.returncode} stdout={result.stdout} stderr={result.stderr}")


def latest_manifest(backup_dir: Path) -> Path:
    manifests = sorted(backup_dir.glob("phase-a-backup-*.json"))
    if not manifests:
        raise FileNotFoundError("backup manifest was not created")
    return manifests[-1]


def restore_from_manifest(manifest_path: Path, restored_db: Path, restored_workspace: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    shutil.copyfile(manifest["metadata_backup"], restored_db)
    restored_workspace.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(manifest["workspace_backup"]) as zf:
        zf.extractall(restored_workspace)


def assert_restored_fixture(workspace_root: Path, metadata_db: Path) -> None:
    marker = workspace_root / "restore-account" / "restore-project" / "repo" / "restore-marker.txt"
    if marker.read_text(encoding="utf-8") != "restore drill marker":
        raise AssertionError("workspace marker was not restored")
    with sqlite3.connect(metadata_db) as con:
        row = con.execute("SELECT game_name FROM projects WHERE id = 'restore-project'").fetchone()
    if row is None or row[0] != "Restore Drill Game":
        raise AssertionError("metadata project row was not restored")


class PhaseAService:
    def __init__(self, *, repository_root: Path, dotnet: str, workspace_root: Path, metadata_db: Path, admin_token: str, run_dir: Path):
        self.repository_root = repository_root
        self.dotnet = dotnet
        self.workspace_root = workspace_root
        self.metadata_db = metadata_db
        self.admin_token = admin_token
        self.run_dir = run_dir
        self.base_url = f"http://127.0.0.1:{find_free_port()}"
        self.process: subprocess.Popen[bytes] | None = None

    def __enter__(self) -> "PhaseAService":
        self.run_dir.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.update(
            {
                "APP_BIND_URL": self.base_url,
                "HTTPS_TERMINATION": "caddy",
                "PUBLIC_BASE_URL": "https://localhost",
                "LLM_GATEWAY_BASE_URL": "https://localhost/v1",
                "HOSTED_PROJECT_LIMIT": "2",
                "HOSTED_WORKSPACE_ROOT": str(self.workspace_root),
                "PHASEA_METADATA_DB_PATH": str(self.metadata_db),
                "PHASEA_REPOSITORY_ROOT": str(self.repository_root),
                "PHASEA_ADMIN_TOKEN_HASH": self.admin_token,
                "PHASEA_ADMIN_USERNAME": "admin",
                "DELIVERY_PROFILE": "fast-ship",
            }
        )
        stdout = (self.run_dir / "server.stdout.log").open("wb")
        stderr = (self.run_dir / "server.stderr.log").open("wb")
        self.process = subprocess.Popen(
            [self.dotnet, "run", "--project", str(self.repository_root / "PhaseA.Platform" / "PhaseA.Platform.csproj"), "--no-launch-profile"],
            cwd=str(self.repository_root),
            env=env,
            stdout=stdout,
            stderr=stderr,
        )
        return self

    def __exit__(self, *_args: object) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)

    def wait_for_health(self, timeout_seconds: int) -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if self.process is not None and self.process.poll() is not None:
                raise RuntimeError(f"service exited early: {self.process.returncode}")
            try:
                payload = self.get_json("/healthz")
                if payload.get("status") == "ok":
                    return
            except Exception:
                time.sleep(0.5)
        raise TimeoutError("service did not become healthy")

    def get_json(self, path: str, token: str | None = None) -> Any:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        status, payload = request_json("GET", f"{self.base_url}{path}", headers=headers)
        if status < 200 or status >= 300:
            raise AssertionError(f"GET {path} failed HTTP {status}: {payload}")
        return payload


def find_dotnet(explicit: str | None) -> str:
    candidates = [Path(explicit)] if explicit else []
    candidates += [Path("dotnet"), Path(r"C:\Program Files\dotnet\dotnet.exe")]
    for candidate in candidates:
        if candidate.name == "dotnet":
            return str(candidate)
        if candidate.exists():
            return str(candidate)
    raise FileNotFoundError("dotnet executable was not found")


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def request_json(method: str, url: str, *, headers: dict[str, str] | None = None) -> tuple[int, Any]:
    request = urllib.request.Request(url, headers=dict(headers or {}), method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as ex:
        raw = ex.read().decode("utf-8")
        try:
            return ex.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return ex.code, {"raw": raw}


if __name__ == "__main__":
    raise SystemExit(main())
