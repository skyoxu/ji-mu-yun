from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any


OLD_TOKEN = "phase-a-old-admin-token"
NEW_TOKEN = "phase-a-new-admin-token"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a Phase A admin token rotation drill.")
    parser.add_argument("--repository-root", default=str(Path.cwd()))
    parser.add_argument("--dotnet", default=None)
    parser.add_argument("--timeout-seconds", type=int, default=45)
    args = parser.parse_args()

    repository_root = Path(args.repository_root).resolve()
    dotnet = find_dotnet(args.dotnet)
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    run_dir = repository_root / "logs" / "ci" / dt.date.today().isoformat() / "phase-a-token-rotation-drill" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    metadata_db = run_dir / "phase-a-platform.sqlite3"
    workspace_root = run_dir / "workspaces"

    events: list[dict[str, Any]] = []
    exit_code = 1
    try:
        with PhaseAService(repository_root, dotnet, workspace_root, metadata_db, OLD_TOKEN, run_dir / "old-service") as service:
            service.wait_for_health(args.timeout_seconds)
            service.expect_projects_status(OLD_TOKEN, 200)
            events.append({"event": "old_token_accepted"})

        with PhaseAService(repository_root, dotnet, workspace_root, metadata_db, NEW_TOKEN, run_dir / "new-service") as service:
            service.wait_for_health(args.timeout_seconds)
            service.expect_projects_status(OLD_TOKEN, 401)
            service.expect_projects_status(NEW_TOKEN, 200)
            events.append({"event": "old_token_rejected_after_restart"})
            events.append({"event": "new_token_accepted_after_restart"})

        exit_code = 0
        return 0
    except Exception as ex:
        events.append({"event": "token_rotation_drill_failed", "error": str(ex), "type": type(ex).__name__})
        print(f"PHASE_A_TOKEN_ROTATION_DRILL status=failed run_dir={run_dir} error={ex}")
        return 1
    finally:
        summary = {"status": "ok" if exit_code == 0 else "failed", "run_id": run_id, "events": events}
        (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8", newline="\n")
        if exit_code == 0:
            print(f"PHASE_A_TOKEN_ROTATION_DRILL status=ok run_dir={run_dir}")


class PhaseAService:
    def __init__(self, repository_root: Path, dotnet: str, workspace_root: Path, metadata_db: Path, admin_token: str, run_dir: Path):
        self.repository_root = repository_root
        self.dotnet = dotnet
        self.workspace_root = workspace_root
        self.metadata_db = metadata_db
        self.admin_token = admin_token
        self.run_dir = run_dir
        self.base_url = f"http://127.0.0.1:{find_free_port()}"
        self.process: subprocess.Popen[bytes] | None = None
        self.stdout = None
        self.stderr = None

    def __enter__(self) -> "PhaseAService":
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.stdout = (self.run_dir / "server.stdout.log").open("wb")
        self.stderr = (self.run_dir / "server.stderr.log").open("wb")
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
        self.process = subprocess.Popen(
            [self.dotnet, "run", "--project", str(self.repository_root / "PhaseA.Platform" / "PhaseA.Platform.csproj"), "--no-launch-profile"],
            cwd=str(self.repository_root),
            env=env,
            stdout=self.stdout,
            stderr=self.stderr,
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
        if self.stdout:
            self.stdout.close()
        if self.stderr:
            self.stderr.close()

    def wait_for_health(self, timeout_seconds: int) -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if self.process is not None and self.process.poll() is not None:
                raise RuntimeError(f"service exited early: {self.process.returncode}")
            status, payload = request_json("GET", f"{self.base_url}/healthz")
            if status == 200 and payload.get("status") == "ok":
                return
            time.sleep(0.5)
        raise TimeoutError("service did not become healthy")

    def expect_projects_status(self, token: str, expected_status: int) -> None:
        status, payload = request_json("GET", f"{self.base_url}/api/projects", headers={"Authorization": f"Bearer {token}"})
        if status != expected_status:
            raise AssertionError(f"expected /api/projects HTTP {expected_status}, got {status}, payload={payload}")


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
    except urllib.error.URLError:
        return 0, {}


if __name__ == "__main__":
    raise SystemExit(main())
