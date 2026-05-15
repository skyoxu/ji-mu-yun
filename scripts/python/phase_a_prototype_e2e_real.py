from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import os
import sqlite3
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


ADMIN_TOKEN = "phase-a-real-e2e-admin-token"
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
EXPECTED_DEFAULT_SCENE = "res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a real Phase A prototype 7-step E2E check against an isolated temporary instance.")
    parser.add_argument("--repository-root", default=str(Path.cwd()))
    parser.add_argument("--timeout-seconds", type=int, default=1200)
    parser.add_argument("--stop-after-day", type=int, default=7, choices=[5, 6, 7])
    args = parser.parse_args()

    source_root = Path(args.repository_root).resolve()
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    run_dir = source_root / "logs" / "ci" / dt.date.today().isoformat() / "phase-a-prototype-e2e-real" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    work_root = run_dir / "repo-copy"
    copy_repo(source_root, work_root)

    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    workspace_root = run_dir / "workspaces"
    metadata_db = run_dir / "phase-a-platform.sqlite3"
    stdout_path = run_dir / "server.stdout.log"
    stderr_path = run_dir / "server.stderr.log"
    headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
    env = build_server_env(
        base_url=base_url,
        workspace_root=workspace_root,
        metadata_db=metadata_db,
        repository_root=work_root,
        admin_token=ADMIN_TOKEN,
        godot_bin=os.environ.get("GODOT_BIN", ""),
    )
    command = [
        "dotnet",
        "run",
        "--project",
        str(work_root / "PhaseA.Platform" / "PhaseA.Platform.csproj"),
        "--no-launch-profile",
    ]

    events: list[dict[str, Any]] = []
    process: subprocess.Popen[bytes] | None = None
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
                    "projectName": "phase-a-real-e2e",
                    "gameName": "Phase A Real E2E Prototype",
                    "gameTypeSource": "rpg",
                },
                timeout=60,
            )
            if not project.get("succeeded") or not project.get("projectId"):
                raise AssertionError(f"project creation failed: {project}")
            project_id = str(project["projectId"])
            events.append({"event": "project_created", "project_id": project_id})

            init_state = wait_for_project_ready(base_url, headers, project_id, timeout_seconds=args.timeout_seconds)
            events.append({"event": "project_initialized", "bootstrap_status": init_state.get("bootstrapStatus")})

            prototype = post_json(
                base_url,
                f"/api/projects/{project_id}/prototype-7day-playable",
                headers,
                prototype_payload(stop_after_day=args.stop_after_day),
                timeout=60,
            )
            if prototype.get("status") != "queued":
                raise AssertionError(f"prototype run was not queued: {prototype}")
            events.append({"event": "prototype_queued", "run_id": prototype.get("runId")})

            progress = wait_for_prototype_progress(base_url, headers, project_id, process=process, timeout_seconds=args.timeout_seconds)
            events.append({"event": "prototype_progress_finished", "status": progress.get("status"), "step": progress.get("step")})
            if progress.get("status") != "succeeded":
                raise AssertionError(f"prototype did not succeed: {progress}")
            if not progress.get("completionSummary"):
                raise AssertionError(f"missing completionSummary: {progress}")
            if not progress.get("defaultScene"):
                raise AssertionError(f"missing defaultScene: {progress}")
            if progress.get("defaultScene") != EXPECTED_DEFAULT_SCENE:
                raise AssertionError(f"unexpected defaultScene: {progress.get('defaultScene')}")
            if not progress.get("playtestFocusPoints"):
                raise AssertionError(f"missing playtestFocusPoints: {progress}")

            runs = get_json(base_url, f"/api/projects/{project_id}/runs", headers, timeout=60)
            events.append({"event": "runs_loaded", "run_count": len(runs.get('runs', []))})
            prototype_run = next((item for item in runs.get("runs", []) if item.get("runType") == "prototype-7day-playable"), None)
            if not prototype_run:
                raise AssertionError("prototype run not found in readback")

            run_details = get_json(base_url, f"/api/runs/{prototype_run['runId']}", headers, timeout=60)
            artifact_types = [str(item.get("artifactType")) for item in run_details.get("artifacts", [])]
            required_artifacts = {
                "prototype-record",
                "prototype-sidecar-json",
                "active-prototype-json",
                "prototype-packaging-summary",
                "prototype-completion-report",
            }
            missing_artifacts = sorted(required_artifacts.difference(artifact_types))
            if missing_artifacts:
                raise AssertionError(f"missing artifacts: {missing_artifacts}; got {artifact_types}")
            events.append({"event": "artifact_types_ok", "artifact_types": artifact_types})

            project_repo = resolve_project_repo(workspace_root, metadata_db, project_id)
            validation = validate_project_specific_outputs(project_repo)
            events.append({"event": "project_outputs_ok", **validation})

            status = "ok"
            return 0
    except Exception as exc:  # noqa: BLE001
        events.append({"event": "e2e_failed", "error": str(exc), "type": type(exc).__name__})
        print(f"PHASE_A_PROTOTYPE_E2E_REAL status=failed run_dir={run_dir} error={exc}", file=sys.stderr)
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
            "base_url": base_url,
            "work_root": str(work_root),
            "stdout": str(stdout_path),
            "stderr": str(stderr_path),
            "events": events,
        }
        (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
        if status == "ok":
            print(f"PHASE_A_PROTOTYPE_E2E_REAL status=ok run_dir={run_dir}")


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


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def to_windows_extended_path(path: Path) -> str:
    raw = str(path)
    if os.name != "nt":
        return raw
    if raw.startswith("\\\\?\\"):
        return raw
    if raw.startswith("\\\\"):
        return "\\\\?\\UNC\\" + raw[2:]
    return "\\\\?\\" + raw


def safe_exists(path: Path) -> bool:
    try:
        return os.path.exists(to_windows_extended_path(path.resolve()))
    except OSError:
        return False


def safe_read_text(path: Path) -> str:
    with open(to_windows_extended_path(path.resolve()), "r", encoding="utf-8") as handle:
        return handle.read()


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
        except Exception as ex:  # noqa: BLE001
            last_error = str(ex)
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


def wait_for_prototype_progress(
    base_url: str,
    headers: dict[str, str],
    project_id: str,
    *,
    process: subprocess.Popen[bytes],
    timeout_seconds: int,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_payload: dict[str, Any] = {}
    last_error = ""
    while time.monotonic() < deadline:
        try:
            payload = get_json(base_url, f"/api/projects/{project_id}/prototype-7day-playable/progress", headers, timeout=30)
            last_payload = payload
            if payload.get("status") in {"succeeded", "failed"}:
                return payload
        except urllib.error.URLError as exc:
            last_error = str(exc)
            if process.poll() is not None:
                raise RuntimeError(
                    f"server exited while polling prototype progress: exit_code={process.returncode}, last_error={last_error}, last_payload={last_payload}"
                ) from exc
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            if process.poll() is not None:
                raise RuntimeError(
                    f"server exited while polling prototype progress: exit_code={process.returncode}, last_error={last_error}, last_payload={last_payload}"
                ) from exc
        time.sleep(5)
    raise TimeoutError(f"prototype progress did not finish in time; last_payload={last_payload}; last_error={last_error}")


def prototype_payload(*, stop_after_day: int) -> dict[str, Any]:
    return {
        "slug": "dq-rpg",
        "hypothesis": "复古rpg加肉鸽成长",
        "corePlayerFantasy": "成长的不确定性和可选择性，是否能过boss",
        "minimumPlayableLoop": "地图移动，概率撞怪，打赢怪物，选择成长",
        "successCriteria": [
            "奖励3选1可以正确理解",
        ],
        "gameFeature": "地图场景用wsad自由连续移动；地图场景有宝箱，移动上去可以选择奖励3选1；地图场景概率撞怪进入战斗场景；战斗场景由玩家先手进行回合制的自动攻击，显示战斗日志；战斗胜利选择奖励3选1；选择后回到地图场景；打赢15场战斗赢得游戏胜利。",
        "coreGameplayLoop": "地图场景玩家可以自由移动；地图场景有宝箱，移动上去可以选择奖励3选1；地图场景概率撞怪进入战斗场景；战斗场景由玩家先手进行回合制的自动攻击；战斗胜利选择奖励3选1；选择后回到地图场景；打赢15场战斗赢得游戏胜利。",
        "winFailConditions": "打赢15场战斗赢得游戏胜利；任一战斗失败就游戏失败。",
        "confirm": True,
        "stopAfterDay": stop_after_day,
        "scoreEngine": "deterministic",
        "model": "gpt-5.4",
    }


def resolve_project_repo(workspace_root: Path, metadata_db: Path, project_id: str) -> Path:
    connection = sqlite3.connect(metadata_db)
    try:
        row = connection.execute("select account_id from projects where id = ?", (project_id,)).fetchone()
    finally:
        connection.close()
    if row is None or not row[0]:
        raise AssertionError(f"project account not found for project_id={project_id}")
    account_id = str(row[0])
    repo = workspace_root / account_id / project_id / "repo"
    if not safe_exists(repo):
        raise AssertionError(f"project repo missing: {repo}")
    return repo


def validate_project_specific_outputs(project_repo: Path) -> dict[str, Any]:
    required_paths = {
        "prototype_record": project_repo / "docs" / "prototypes" / "2026-05-15-dq-rpg.md",
        "prototype_spec": project_repo / "docs" / "prototypes" / "dq-rpg.prototype.json",
        "core_loop": project_repo / "Game.Core" / "Prototypes" / "DqRpgPrototypeLoop.cs",
        "runtime_script": project_repo / "Game.Godot" / "Prototypes" / "dq-rpg" / "Scripts" / "DqRpgPrototype.cs",
        "scene": project_repo / "Game.Godot" / "Prototypes" / "dq-rpg" / "DqRpgPrototype.tscn",
        "gdunit_test": project_repo / "Tests.Godot" / "tests" / "Prototype" / "DqRpgPrototype" / "test_dq_rpg_prototype_scene.gd",
        "completion_report": project_repo / "logs" / "ci" / "active-prototypes" / "dq-rpg.completion.md",
        "packaging_summary": project_repo / "logs" / "ci" / "active-prototypes" / "dq-rpg.packaging.json",
    }
    missing = [name for name, path in required_paths.items() if not safe_exists(path)]
    if missing:
        raise AssertionError(f"project-specific outputs missing: {missing}")

    record_text = safe_read_text(required_paths["prototype_record"])
    if "奖励3选1可以正确理解" not in record_text:
        raise AssertionError("prototype record missing reward acceptance criterion")

    spec = json.loads(safe_read_text(required_paths["prototype_spec"]))
    if str(spec.get("slug")) != "dq-rpg":
        raise AssertionError(f"unexpected prototype spec slug: {spec.get('slug')}")
    prototype_core = spec.get("prototype_core") if isinstance(spec.get("prototype_core"), dict) else {}
    game_feature = str(prototype_core.get("game_feature") or "")
    if "奖励3选1" not in game_feature or "15场战斗" not in game_feature:
        raise AssertionError("prototype spec game_feature is weaker than expected")

    core_loop_text = safe_read_text(required_paths["core_loop"])
    if "VictoryBattleCount = 15" not in core_loop_text or "RewardOptions" not in core_loop_text:
        raise AssertionError("core loop implementation does not match dq-rpg baseline expectations")

    runtime_script_text = safe_read_text(required_paths["runtime_script"])
    required_runtime_markers = ["WASD", "Attack", "Wins:", "Objective"]
    for marker in required_runtime_markers:
        if marker not in runtime_script_text:
            raise AssertionError(f"runtime script missing marker: {marker}")

    gdunit_text = safe_read_text(required_paths["gdunit_test"])
    if EXPECTED_DEFAULT_SCENE not in gdunit_text:
        raise AssertionError("project-specific gdunit test does not preload the dq-rpg scene")

    completion_report_text = safe_read_text(required_paths["completion_report"])
    if f"Default Scene: {EXPECTED_DEFAULT_SCENE}" not in completion_report_text:
        raise AssertionError("completion report did not publish the project-specific default scene")
    if "DefaultRpgTemplate/DefaultRpgPrototype.tscn" in completion_report_text:
        raise AssertionError("completion report still exposes template default scene")

    packaging = json.loads(safe_read_text(required_paths["packaging_summary"]))
    if packaging.get("default_scene") != EXPECTED_DEFAULT_SCENE:
        raise AssertionError(f"unexpected packaging default scene: {packaging.get('default_scene')}")

    return {
        "repo": str(project_repo),
        "default_scene": EXPECTED_DEFAULT_SCENE,
        "validated_files": sorted(required_paths.keys()),
    }


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


def request_json(method: str, url: str, *, headers: dict[str, str] | None = None, body: dict[str, Any] | None = None, timeout: int = 20) -> tuple[int, dict[str, Any]]:
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
    except urllib.error.HTTPError as ex:
        raw = ex.read().decode("utf-8")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return ex.code, payload


if __name__ == "__main__":
    raise SystemExit(main())
