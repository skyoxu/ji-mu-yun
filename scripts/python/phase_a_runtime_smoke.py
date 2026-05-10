from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any


DEFAULT_ADMIN_TOKEN = "phase-a-smoke-admin-token"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase A platform runtime smoke checks.")
    parser.add_argument("--repository-root", default=str(Path.cwd()))
    parser.add_argument("--dotnet", default=None)
    parser.add_argument("--admin-token", default=DEFAULT_ADMIN_TOKEN)
    parser.add_argument("--timeout-seconds", type=int, default=45)
    args = parser.parse_args()

    repository_root = Path(args.repository_root).resolve()
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    run_dir = repository_root / "logs" / "ci" / dt.date.today().isoformat() / "phase-a-runtime-smoke" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    dotnet = find_dotnet(args.dotnet)
    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    workspace_root = run_dir / "workspaces"
    metadata_db = run_dir / "phase-a-platform.sqlite3"
    stdout_path = run_dir / "server.stdout.log"
    stderr_path = run_dir / "server.stderr.log"

    env = os.environ.copy()
    env.update(
        {
            "APP_BIND_URL": base_url,
            "HTTPS_TERMINATION": "caddy",
            "PUBLIC_BASE_URL": "https://localhost",
            "LLM_GATEWAY_BASE_URL": "https://localhost/v1",
            "HOSTED_PROJECT_LIMIT": "2",
            "HOSTED_WORKSPACE_ROOT": str(workspace_root),
            "PHASEA_METADATA_DB_PATH": str(metadata_db),
            "PHASEA_REPOSITORY_ROOT": str(repository_root),
            "PHASEA_ADMIN_TOKEN_HASH": args.admin_token,
            "PHASEA_ADMIN_USERNAME": "admin",
            "DELIVERY_PROFILE": "fast-ship",
        }
    )

    command = [
        dotnet,
        "run",
        "--project",
        str(repository_root / "PhaseA.Platform" / "PhaseA.Platform.csproj"),
        "--no-launch-profile",
    ]

    events: list[dict[str, Any]] = []
    process: subprocess.Popen[bytes] | None = None
    exit_code = 1
    try:
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.Popen(
                command,
                cwd=str(repository_root),
                env=env,
                stdout=stdout,
                stderr=stderr,
            )
            events.append({"event": "server_started", "pid": process.pid, "base_url": base_url})

            wait_for_health(base_url, process, args.timeout_seconds)
            events.append({"event": "health_ok"})

            checks = run_checks(base_url, args.admin_token)
            events.extend(checks)

            exit_code = 0
            return exit_code
    except Exception as ex:
        events.append({"event": "smoke_failed", "error": str(ex), "type": type(ex).__name__})
        print(f"PHASE_A_RUNTIME_SMOKE status=failed run_dir={run_dir} error={ex}", file=sys.stderr)
        return 1
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)

        summary = {
            "status": "ok" if exit_code == 0 else "failed",
            "run_id": run_id,
            "base_url": base_url,
            "workspace_root": str(workspace_root),
            "metadata_db": str(metadata_db),
            "stdout": str(stdout_path),
            "stderr": str(stderr_path),
            "events": events,
        }
        summary_path = run_dir / "summary.json"
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8", newline="\n")
        if exit_code == 0:
            print(f"PHASE_A_RUNTIME_SMOKE status=ok run_dir={run_dir}")


def find_dotnet(explicit: str | None) -> str:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    candidates.append(Path("dotnet"))
    candidates.append(Path(r"C:\Program Files\dotnet\dotnet.exe"))

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


def wait_for_health(base_url: str, process: subprocess.Popen[bytes], timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = ""
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"server exited before health check, exit_code={process.returncode}")
        try:
            status, payload = request_json("GET", f"{base_url}/healthz")
            if status == 200 and payload.get("status") == "ok":
                return
        except Exception as ex:
            last_error = str(ex)
        time.sleep(0.5)

    raise TimeoutError(f"health check did not pass within {timeout_seconds}s; last_error={last_error}")


def run_checks(base_url: str, admin_token: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    status, payload = request_json("GET", f"{base_url}/api/projects")
    assert_status(status, 401, payload, "unauthorized project list")
    events.append({"event": "unauthorized_rejected", "status": status})

    headers = {"Authorization": f"Bearer {admin_token}"}
    status, payload = request_json("GET", f"{base_url}/api/projects", headers=headers)
    assert_status(status, 200, payload, "authorized project list")
    if payload != []:
        raise AssertionError(f"expected empty project list, got {payload}")
    events.append({"event": "authorized_project_list_ok", "status": status})

    status, payload = request_json(
        "POST",
        f"{base_url}/api/projects",
        headers=headers,
        body={
            "gameName": "Forbidden Git Game",
            "gameTypeSource": "manual",
            "gitUrl": "https://example.invalid/repo.git",
        },
    )
    assert_status(status, 400, payload, "forbidden git URL")
    assert_error_or_failure(payload, "git_url_not_allowed")
    events.append({"event": "git_url_rejected", "status": status})

    first = create_project(base_url, headers, "Smoke Game One")
    second = create_project(base_url, headers, "Smoke Game Two")
    events.append({"event": "project_created", "project_id": first.get("projectId")})
    events.append({"event": "project_created", "project_id": second.get("projectId")})

    status, payload = request_json(
        "POST",
        f"{base_url}/api/projects",
        headers=headers,
        body={"gameName": "Smoke Game Three", "gameTypeSource": "manual"},
    )
    assert_status(status, 400, payload, "project quota")
    assert_error_or_failure(payload, "project_quota_exceeded")
    events.append({"event": "quota_enforced", "status": status})

    status, payload = request_json("GET", f"{base_url}/api/projects", headers=headers)
    assert_status(status, 200, payload, "project list after creation")
    if len(payload) != 2:
        raise AssertionError(f"expected exactly two projects, got {len(payload)}")
    events.append({"event": "project_list_count_ok", "count": len(payload)})

    return events


def create_project(base_url: str, headers: dict[str, str], game_name: str) -> dict[str, Any]:
    status, payload = request_json(
        "POST",
        f"{base_url}/api/projects",
        headers=headers,
        body={"gameName": game_name, "gameTypeSource": "manual"},
    )
    assert_status(status, 200, payload, f"create project {game_name}")
    if not payload.get("succeeded"):
        raise AssertionError(f"project creation did not succeed: {payload}")
    if payload.get("templateRuleId") != "godot-prototype-default":
        raise AssertionError(f"unexpected templateRuleId: {payload}")
    return payload


def request_json(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
) -> tuple[int, Any]:
    data = None
    request_headers = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as ex:
        raw = ex.read().decode("utf-8")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return ex.code, payload


def assert_status(status: int, expected: int, payload: Any, label: str) -> None:
    if status != expected:
        raise AssertionError(f"{label}: expected HTTP {expected}, got {status}, payload={payload}")


def assert_error_or_failure(payload: Any, expected: str) -> None:
    if not isinstance(payload, dict):
        raise AssertionError(f"expected object payload, got {payload}")
    actual = payload.get("error") or payload.get("failureCode")
    if actual != expected:
        raise AssertionError(f"expected error/failureCode {expected}, got {payload}")


if __name__ == "__main__":
    raise SystemExit(main())
