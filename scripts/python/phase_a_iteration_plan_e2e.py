from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any


DEFAULT_ADMIN_TOKEN = "phase-a-iteration-plan-e2e-admin-token"
EXCLUDED_COPY_DIRS = {
    ".git",
    ".vs",
    ".godot",
    "logs",
    ".pytest_cache",
    "__pycache__",
}
DOTNET_BUILD_OUTPUT_PARENTS = {
    "PhaseA.Platform",
    "PhaseA.Platform.Tests",
    "Game.Core",
    "Game.Core.Tests",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase A iteration-plan flow E2E checks against an isolated temporary instance.")
    parser.add_argument("--repository-root", default=str(Path.cwd()))
    parser.add_argument("--dotnet", default=str(Path(r"C:\Program Files\dotnet\dotnet.exe")))
    parser.add_argument("--admin-token", default=DEFAULT_ADMIN_TOKEN)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    args = parser.parse_args()

    source_root = Path(args.repository_root).resolve()
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    run_dir = source_root / "logs" / "ci" / dt.date.today().isoformat() / "phase-a-iteration-plan-e2e" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    work_root = run_dir / "repo-copy"
    copy_repo(source_root, work_root)

    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    workspace_root = run_dir / "workspaces"
    metadata_db = run_dir / "phase-a-platform.sqlite3"
    stdout_path = run_dir / "server.stdout.log"
    stderr_path = run_dir / "server.stderr.log"
    headers = {"Authorization": f"Bearer {args.admin_token}"}
    env = build_server_env(
        base_url=base_url,
        workspace_root=workspace_root,
        metadata_db=metadata_db,
        repository_root=work_root,
        admin_token=args.admin_token,
        godot_bin=os.environ.get("GODOT_BIN", ""),
    )
    command = [
        args.dotnet,
        "run",
        "--project",
        str(work_root / "PhaseA.Platform" / "PhaseA.Platform.csproj"),
        "--no-launch-profile",
    ]

    process: subprocess.Popen[bytes] | None = None
    events: list[dict[str, Any]] = []
    status = "failed"
    try:
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.Popen(command, cwd=str(work_root), env=env, stdout=stdout, stderr=stderr)
            events.append({"event": "server_started", "pid": process.pid, "base_url": base_url})
            wait_for_health(base_url, process, args.timeout_seconds)
            events.append({"event": "health_ok"})

            project = post_json(
                base_url,
                "/api/projects",
                headers,
                {
                    "projectName": "phase-a-iteration-e2e",
                    "gameName": "Phase A Iteration E2E",
                    "gameTypeSource": "rpg",
                },
                timeout=60,
            )
            project_id = str(project["projectId"])
            events.append({"event": "project_created", "project_id": project_id})
            project_state = wait_for_project_ready(base_url, headers, project_id, timeout_seconds=args.timeout_seconds)
            events.append({"event": "project_ready", "bootstrap_status": project_state.get("bootstrapStatus")})

            plan = post_json(
                base_url,
                f"/api/projects/{project_id}/iteration-plan",
                headers,
                {
                    "message": "Clarify the prototype entry point in the current project page. Add a clearer current objective hint. Make the first-time flow easier to understand.",
                    "sourceKind": "manual_feedback",
                },
                timeout=60,
            )
            events.append(
                {
                    "event": "plan_created",
                    "session_id": plan.get("sessionId"),
                    "status": plan.get("status"),
                    "goal_count": len(plan.get("goals", [])),
                    "goal_titles": [goal.get("title") for goal in plan.get("goals", [])],
                }
            )

            latest = get_json(base_url, f"/api/projects/{project_id}/iteration-plan/latest", headers, timeout=60)
            latest_goals = latest.get("goals", [])
            events.append(
                {
                    "event": "plan_loaded",
                    "session_status": latest.get("session", {}).get("status"),
                    "current_goal_index": latest.get("session", {}).get("currentGoalIndex"),
                    "goal_statuses": [goal.get("status") for goal in latest_goals],
                }
            )
            if latest.get("session", {}).get("status") != "ready":
                raise AssertionError(f"iteration plan was not ready: {latest}")
            if len(latest_goals) < 3:
                raise AssertionError(f"expected at least 3 goals: {latest}")

            execute_status, execute_payload = request_json(
                "POST",
                f"{base_url}/api/projects/{project_id}/iteration-plan/execute-next",
                headers=headers,
                body={},
                timeout=args.timeout_seconds,
            )
            events.append(
                {
                    "event": "execute_next_finished",
                    "http_status": execute_status,
                    "result_status": execute_payload.get("status"),
                    "session_status": execute_payload.get("sessionStatus"),
                    "goal_index": execute_payload.get("goalIndex"),
                    "has_more_goals": execute_payload.get("hasMoreGoals"),
                    "summary": execute_payload.get("summary"),
                }
            )

            latest_after = get_json(base_url, f"/api/projects/{project_id}/iteration-plan/latest", headers, timeout=60)
            events.append(
                {
                    "event": "plan_reloaded_after_execute",
                    "session_status": latest_after.get("session", {}).get("status"),
                    "current_goal_index": latest_after.get("session", {}).get("currentGoalIndex"),
                    "goal_statuses": [goal.get("status") for goal in latest_after.get("goals", [])],
                    "goal_run_count": len(latest_after.get("goalRuns", [])),
                }
            )

            status = "ok"
            return 0
    except Exception as exc:  # noqa: BLE001
        events.append({"event": "e2e_failed", "error": str(exc), "type": type(exc).__name__})
        print(f"PHASE_A_ITERATION_PLAN_E2E status=failed run_dir={run_dir} error={exc}", file=sys.stderr)
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
            "status": status,
            "run_id": run_id,
            "source_root": str(source_root),
            "work_root": str(work_root),
            "stdout": str(stdout_path),
            "stderr": str(stderr_path),
            "events": events,
        }
        (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8", newline="\n")
        if status == "ok":
            print(f"PHASE_A_ITERATION_PLAN_E2E status=ok run_dir={run_dir}")


def copy_repo(source_root: Path, target_root: Path) -> None:
    def ignore(directory: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        directory_path = Path(directory)
        for name in names:
            path = Path(directory) / name
            if name in EXCLUDED_COPY_DIRS:
                ignored.add(name)
            elif name in {"bin", "obj"} and directory_path.name in DOTNET_BUILD_OUTPUT_PARENTS:
                ignored.add(name)
            elif path.is_file() and name.lower().endswith((".exe", ".zip", ".7z")):
                ignored.add(name)
        return ignored

    shutil.copytree(source_root, target_root, ignore=ignore)


def build_server_env(*, base_url: str, workspace_root: Path, metadata_db: Path, repository_root: Path, admin_token: str, godot_bin: str) -> dict[str, str]:
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
            "PHASEA_ADMIN_TOKEN_HASH": token_hash(admin_token),
            "PHASEA_ADMIN_USERNAME": "admin",
            "DELIVERY_PROFILE": "fast-ship",
        }
    )
    if godot_bin:
        env["GODOT_BIN"] = godot_bin
    return env


def token_hash(token: str) -> str:
    digest = hashlib.sha256(token.strip().encode("utf-8")).digest()
    return base64.b64encode(digest).decode("ascii").rstrip("=").replace("+", "-").replace("/", "_")


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
            payload = get_json(base_url, "/healthz", {}, timeout=5)
            if payload.get("status") == "ok":
                return
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
        time.sleep(0.5)
    raise TimeoutError(f"health check did not pass within {timeout_seconds}s; last_error={last_error}")


def wait_for_project_ready(base_url: str, headers: dict[str, str], project_id: str, *, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        projects = get_json(base_url, "/api/projects", headers, timeout=30)
        project = next((item for item in projects if str(item.get("projectId")) == project_id), None)
        if project and project.get("bootstrapStatus") == "succeeded":
            return project
        if project and project.get("bootstrapStatus") == "failed":
            raise AssertionError(f"project bootstrap failed: {project}")
        time.sleep(5)
    raise TimeoutError("project bootstrap did not finish in time")


def get_json(base_url: str, path: str, headers: dict[str, str], *, timeout: int) -> dict[str, Any]:
    status, payload = request_json("GET", f"{base_url}{path}", headers=headers, timeout=timeout)
    if status < 200 or status >= 300:
        raise AssertionError(f"GET {path} failed: HTTP {status}, payload={payload}")
    return payload


def post_json(base_url: str, path: str, headers: dict[str, str], body: dict[str, Any], *, timeout: int) -> dict[str, Any]:
    status, payload = request_json("POST", f"{base_url}{path}", headers=headers, body=body, timeout=timeout)
    if status < 200 or status >= 300:
        raise AssertionError(f"POST {path} failed: HTTP {status}, payload={payload}")
    return payload


def request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    timeout: int = 20,
) -> tuple[int, dict[str, Any]]:
    data = None
    request_headers = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return exc.code, payload


if __name__ == "__main__":
    raise SystemExit(main())
