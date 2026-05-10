from __future__ import annotations

import argparse
import datetime as dt
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


DEFAULT_ADMIN_TOKEN = "phase-a-prototype-e2e-admin-token"
EXCLUDED_COPY_DIRS = {
    ".git",
    ".vs",
    ".godot",
    "bin",
    "obj",
    "logs",
    ".pytest_cache",
    "__pycache__",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase A hosted prototype lane end-to-end checks.")
    parser.add_argument("--repository-root", default=str(Path.cwd()))
    parser.add_argument("--dotnet", default=None)
    parser.add_argument("--admin-token", default=DEFAULT_ADMIN_TOKEN)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--stop-after-day", type=int, default=4, choices=[2, 3, 4, 5])
    parser.add_argument("--use-current-repo", action="store_true")
    parser.add_argument("--skip-chapter2", action="store_true")
    args = parser.parse_args()

    source_root = Path(args.repository_root).resolve()
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    run_dir = source_root / "logs" / "ci" / dt.date.today().isoformat() / "phase-a-prototype-e2e" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    work_root = source_root if args.use_current_repo else run_dir / "repo-copy"
    if not args.use_current_repo:
        copy_repo(source_root, work_root)

    events: list[dict[str, Any]] = []
    exit_code = 1
    process: subprocess.Popen[bytes] | None = None
    stdout_path = run_dir / "server.stdout.log"
    stderr_path = run_dir / "server.stderr.log"

    try:
        dotnet = find_dotnet(args.dotnet)
        port = find_free_port()
        base_url = f"http://127.0.0.1:{port}"
        workspace_root = run_dir / "workspaces"
        metadata_db = run_dir / "phase-a-platform.sqlite3"
        env = build_server_env(
            base_url=base_url,
            workspace_root=workspace_root,
            metadata_db=metadata_db,
            repository_root=work_root,
            admin_token=args.admin_token,
            dotnet=dotnet,
        )

        command = [
            dotnet,
            "run",
            "--project",
            str(work_root / "PhaseA.Platform" / "PhaseA.Platform.csproj"),
            "--no-launch-profile",
        ]

        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.Popen(command, cwd=str(work_root), env=env, stdout=stdout, stderr=stderr)
            events.append({"event": "server_started", "pid": process.pid, "base_url": base_url, "work_root": str(work_root)})
            wait_for_health(base_url, process, args.timeout_seconds)
            events.append({"event": "health_ok"})

            headers = {"Authorization": f"Bearer {args.admin_token}"}
            project = create_project(base_url, headers)
            project_id = str(project["projectId"])
            events.append({"event": "project_created", "project_id": project_id})

            if not args.skip_chapter2:
                chapter2 = post_json(base_url, f"/api/projects/{project_id}/chapter2-bootstrap", headers, {})
                events.append(assert_run_result(chapter2, "chapter2-bootstrap"))

            prototype = post_json(
                base_url,
                f"/api/projects/{project_id}/prototype-7day-playable",
                headers,
                prototype_payload(stop_after_day=args.stop_after_day),
            )
            events.append(assert_run_result(prototype, "prototype-7day-playable"))

            scene = post_json(
                base_url,
                f"/api/projects/{project_id}/prototype-scene",
                headers,
                {"slug": "phase-a-e2e-loop", "sceneRoot": "Node2D"},
            )
            events.append(assert_run_result(scene, "prototype-scene"))

            tdd = post_json(
                base_url,
                f"/api/projects/{project_id}/prototype-tdd",
                headers,
                {
                    "slug": "phase-a-e2e-loop",
                    "stage": "refactor",
                    "expect": "pass",
                    "timeoutSec": 300,
                    "dotnetTarget": ["Game.Core.Tests/Game.Core.Tests.csproj"],
                },
            )
            events.append(assert_run_result(tdd, "prototype-tdd-refactor"))

            runs = get_json(base_url, f"/api/projects/{project_id}/runs", headers)
            run_types = [str(item.get("runType")) for item in runs.get("runs", [])]
            required = {"prototype-7day-playable", "prototype-scene", "prototype-tdd-refactor"}
            if not args.skip_chapter2:
                required.add("chapter2-bootstrap")
            missing = sorted(required.difference(run_types))
            if missing:
                raise AssertionError(f"missing run types: {missing}; got {run_types}")
            events.append({"event": "run_readback_ok", "run_types": run_types})

            artifact_count = sum(len(get_json(base_url, f"/api/runs/{item['runId']}", headers).get("artifacts", [])) for item in runs.get("runs", []))
            if artifact_count < 1:
                raise AssertionError("expected at least one indexed artifact")
            events.append({"event": "artifact_readback_ok", "artifact_count": artifact_count})

            exit_code = 0
            return 0
    except Exception as ex:
        events.append({"event": "prototype_e2e_failed", "error": str(ex), "type": type(ex).__name__})
        print(f"PHASE_A_PROTOTYPE_E2E status=failed run_dir={run_dir} error={ex}", file=sys.stderr)
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
            "source_root": str(source_root),
            "work_root": str(work_root),
            "stdout": str(stdout_path),
            "stderr": str(stderr_path),
            "events": events,
        }
        (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8", newline="\n")
        if exit_code == 0:
            print(f"PHASE_A_PROTOTYPE_E2E status=ok run_dir={run_dir}")


def copy_repo(source_root: Path, target_root: Path) -> None:
    def ignore(directory: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        for name in names:
            path = Path(directory) / name
            if name in EXCLUDED_COPY_DIRS:
                ignored.add(name)
            elif path.is_file() and name.lower().endswith((".exe", ".zip", ".7z")):
                ignored.add(name)
        return ignored

    shutil.copytree(source_root, target_root, ignore=ignore)


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


def build_server_env(*, base_url: str, workspace_root: Path, metadata_db: Path, repository_root: Path, admin_token: str, dotnet: str) -> dict[str, str]:
    env = os.environ.copy()
    dotnet_parent = str(Path(dotnet).resolve().parent) if Path(dotnet).exists() else ""
    if dotnet_parent:
        env["PATH"] = dotnet_parent + os.pathsep + env.get("PATH", "")
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
            "PHASEA_ADMIN_TOKEN_HASH": admin_token,
            "PHASEA_ADMIN_USERNAME": "admin",
            "DELIVERY_PROFILE": "fast-ship",
        }
    )
    return env


def wait_for_health(base_url: str, process: subprocess.Popen[bytes], timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = ""
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"server exited before health check, exit_code={process.returncode}")
        try:
            payload = get_json(base_url, "/healthz", {})
            if payload.get("status") == "ok":
                return
        except Exception as ex:
            last_error = str(ex)
        time.sleep(0.5)
    raise TimeoutError(f"health check did not pass within {timeout_seconds}s; last_error={last_error}")


def create_project(base_url: str, headers: dict[str, str]) -> dict[str, Any]:
    payload = post_json(
        base_url,
        "/api/projects",
        headers,
        {"projectName": "phase-a-e2e", "gameName": "Phase A E2E Prototype", "gameTypeSource": "prototype-e2e"},
    )
    if not payload.get("succeeded") or not payload.get("projectId"):
        raise AssertionError(f"project creation failed: {payload}")
    return payload


def prototype_payload(*, stop_after_day: int) -> dict[str, Any]:
    return {
        "slug": "phase-a-e2e-loop",
        "hypothesis": "A hosted browser-triggered prototype lane can create and verify a small playable loop.",
        "corePlayerFantasy": "The player immediately understands a tiny risk/reward room loop.",
        "minimumPlayableLoop": "Enter a room, trigger one encounter, resolve feedback, and return to the map.",
        "successCriteria": [
            "The hosted route creates a prototype record and sidecar.",
            "The hosted route indexes prototype artifacts.",
            "The TDD refactor command can be triggered and read back through artifacts.",
        ],
        "gameFeature": "A compact room loop where one encounter proves the hosted prototype workflow.",
        "coreGameplayLoop": "Choose action, receive feedback, update state, and decide whether to continue.",
        "winFailConditions": "Win by completing one loop with readable feedback; fail if no action feedback is visible.",
        "confirm": True,
        "stopAfterDay": stop_after_day,
        "scoreEngine": "deterministic",
    }


def assert_run_result(payload: dict[str, Any], label: str) -> dict[str, Any]:
    if payload.get("status") != "succeeded":
        raise AssertionError(f"{label} did not succeed: {payload}")
    if not payload.get("runId"):
        raise AssertionError(f"{label} did not return runId: {payload}")
    return {
        "event": "run_succeeded",
        "label": label,
        "run_id": payload.get("runId"),
        "artifact_count": len(payload.get("artifacts", [])),
    }


def get_json(base_url: str, path: str, headers: dict[str, str]) -> dict[str, Any]:
    status, payload = request_json("GET", f"{base_url}{path}", headers=headers)
    if status < 200 or status >= 300:
        raise AssertionError(f"GET {path} failed: HTTP {status}, payload={payload}")
    return payload


def post_json(base_url: str, path: str, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
    status, payload = request_json("POST", f"{base_url}{path}", headers=headers, body=body)
    if status < 200 or status >= 300:
        raise AssertionError(f"POST {path} failed: HTTP {status}, payload={payload}")
    return payload


def request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    data = None
    request_headers = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as ex:
        raw = ex.read().decode("utf-8")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return ex.code, payload


if __name__ == "__main__":
    raise SystemExit(main())
