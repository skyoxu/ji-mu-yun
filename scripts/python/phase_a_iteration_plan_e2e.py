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
DEFAULT_DOTNET = shutil.which("dotnet") or str(Path(r"C:\Program Files\dotnet\dotnet.exe"))
EXCLUDED_COPY_DIRS = {
    ".git",
    ".vs",
    ".godot",
    ".dotnet",
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
    parser.add_argument("--dotnet", default=DEFAULT_DOTNET)
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
    fake_codex = create_fake_codex(run_dir)
    env = build_server_env(
        base_url=base_url,
        workspace_root=workspace_root,
        metadata_db=metadata_db,
        repository_root=work_root,
        admin_token=args.admin_token,
        godot_bin=os.environ.get("GODOT_BIN", ""),
        fake_codex_command=fake_codex,
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
            seed_phase2_gdd_sources(project)
            events.append({"event": "phase2_gdd_sources_seeded"})

            requirement_map = post_json(
                base_url,
                f"/api/projects/{project_id}/gdd/requirements-map",
                headers,
                {"refresh": True},
                timeout=60,
            )
            events.append(
                {
                    "event": "requirement_map_created",
                    "status": requirement_map.get("status"),
                    "source_requirement_map_hash": requirement_map.get("sourceRequirementMapHash"),
                    "requirement_count": len(requirement_map.get("requirements", [])),
                }
            )
            if requirement_map.get("status") != "ready":
                raise AssertionError(f"requirement map was not ready: {requirement_map}")

            contract = post_json(
                base_url,
                f"/api/projects/{project_id}/prototype-contract/freeze",
                headers,
                {},
                timeout=60,
            )
            events.append(
                {
                    "event": "prototype_contract_frozen",
                    "status": contract.get("status"),
                    "contract_hash": contract.get("contractHash"),
                    "source_requirement_map_hash": contract.get("sourceRequirementMapHash"),
                }
            )
            if contract.get("status") != "fresh":
                raise AssertionError(f"prototype contract was not fresh: {contract}")
            seed_phase2_prototype_skeleton(project, contract)
            events.append({"event": "prototype_skeleton_seeded"})

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
                    "plan_hash": plan.get("planHash"),
                    "confirmation_status": (plan.get("confirmation") or {}).get("status"),
                }
            )
            if plan.get("status") != "ready" or not plan.get("planHash"):
                raise AssertionError(f"iteration plan was not traceability-ready: {plan}")
            if (plan.get("confirmation") or {}).get("status") != "unconfirmed":
                raise AssertionError(f"new plan did not start unconfirmed: {plan}")

            confirmation = post_json(
                base_url,
                f"/api/projects/{project_id}/iteration-plan/confirm",
                headers,
                {
                    "sessionId": plan.get("sessionId"),
                    "planHash": plan.get("planHash"),
                },
                timeout=60,
            )
            events.append(
                {
                    "event": "plan_confirmed",
                    "status": confirmation.get("status"),
                    "operation_status": confirmation.get("operationStatus"),
                    "session_id": (confirmation.get("confirmation") or {}).get("sessionId"),
                    "plan_hash": (confirmation.get("confirmation") or {}).get("planHash"),
                }
            )
            if confirmation.get("status") != "confirmed":
                raise AssertionError(f"iteration plan confirmation failed: {confirmation}")

            latest = get_json(base_url, f"/api/projects/{project_id}/iteration-plan/latest", headers, timeout=60)
            latest_goals = latest.get("goals", [])
            events.append(
                {
                    "event": "plan_loaded",
                    "session_status": latest.get("session", {}).get("status"),
                    "current_goal_index": latest.get("session", {}).get("currentGoalIndex"),
                    "goal_statuses": [goal.get("status") for goal in latest_goals],
                    "confirmation_status": (latest.get("confirmation") or {}).get("status"),
                }
            )
            if latest.get("session", {}).get("status") != "ready":
                raise AssertionError(f"iteration plan was not ready: {latest}")
            if len(latest_goals) < 3:
                raise AssertionError(f"expected at least 3 goals: {latest}")
            if (latest.get("confirmation") or {}).get("status") != "confirmed":
                raise AssertionError(f"latest plan did not preserve confirmation: {latest}")

            execute_status, execute_payload = request_json(
                "POST",
                f"{base_url}/api/projects/{project_id}/iteration-plan/execute-next",
                headers=headers,
                body={},
                timeout=args.timeout_seconds,
            )
            events.append(
                {
                    "event": "execute_next_phase_gate_checked",
                    "http_status": execute_status,
                    "operation_status": execute_payload.get("operationStatus"),
                    "code": execute_payload.get("code"),
                    "domain_code": (execute_payload.get("details") or {}).get("domainCode"),
                }
            )
            if (
                execute_status != 409
                or execute_payload.get("code") != "route_action_rejected"
                or (execute_payload.get("details") or {}).get("domainCode") != "phase_gate_blocked"
            ):
                raise AssertionError(f"execute-next was not phase-gated in Phase 2: {execute_payload}")

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


def build_server_env(
    *,
    base_url: str,
    workspace_root: Path,
    metadata_db: Path,
    repository_root: Path,
    admin_token: str,
    godot_bin: str,
    fake_codex_command: Path,
) -> dict[str, str]:
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
            "PHASEA_CODEX_COMMAND": str(fake_codex_command),
            "PHASEA_FAKE_CODEX_COUNTER": str(fake_codex_command.with_suffix(".counter")),
            "DELIVERY_PROFILE": "fast-ship",
        }
    )
    if godot_bin:
        env["GODOT_BIN"] = godot_bin
    return env


def create_fake_codex(run_dir: Path) -> Path:
    fake_py = run_dir / "fake_codex.py"
    fake_cmd = run_dir / "fake_codex.cmd"
    fake_py.write_text(
        """
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    output_path = None
    output_schema = None
    args = sys.argv[1:]
    for index, value in enumerate(args):
        if value == "-o" and index + 1 < len(args):
            output_path = Path(args[index + 1])
        if value == "--output-schema" and index + 1 < len(args):
            output_schema = Path(args[index + 1])
    if output_path is None:
        print("missing -o output path", file=sys.stderr)
        return 2

    prompt = sys.stdin.buffer.read().decode("utf-8", errors="replace")

    schema_name = output_schema.name if output_schema is not None else ""
    if schema_name == "prototype-iteration-planning-analysis.schema.json":
        content = json.dumps({
            "analysisSummary": "The isolated E2E project is ready for a small ordered iteration plan.",
            "fieldCoverage": [],
        })
    elif schema_name == "prototype-iteration-goal-plan.schema.json":
        marker = "Goal scaffold that must be preserved:"
        scaffold = json.loads(prompt.split(marker, 1)[1].strip())
        content = json.dumps({
            "goals": [
                {
                    "title": goal["Title"],
                    "description": goal["Description"],
                    "acceptanceHint": goal["AcceptanceHint"],
                }
                for goal in scaffold
            ]
        })
    elif schema_name == "prototype-iteration-evaluation.schema.json":
        content = json.dumps({
            "decision": "ready_to_execute",
            "summary": "The isolated plan is ready.",
            "reason": "Goals are ordered and independently verifiable.",
            "suggestedAction": "execute_next_goal",
            "suggestedPromptForRegeneration": None,
        })
    elif "Phase A GDD requirement map" in prompt:
        content = json.dumps({
            "requirements": [
                {
                    "requirement_id": "REQ-001",
                    "normalized_requirement": "Player must move on the field map and trigger one visible encounter.",
                    "priority": "P0",
                    "kind": "scene",
                    "mapped_scene_ids": ["field_map"],
                    "mapped_required_module_ids": ["field_map"],
                    "status": "mapped",
                    "capability_domain_ids": [],
                    "acceptance_markers": ["Field movement and one visible encounter are observable."],
                },
                {
                    "requirement_id": "REQ-002",
                    "normalized_requirement": "HUD feedback must show HP, reward, and return-to-map state.",
                    "priority": "P1",
                    "kind": "ui",
                    "mapped_scene_ids": ["field_map"],
                    "mapped_required_module_ids": ["combat_hud"],
                    "status": "mapped",
                    "capability_domain_ids": ["ui_component_system", "ui_overlays_feedback"],
                    "acceptance_markers": ["HUD shows HP, reward, and return-to-map feedback."],
                },
            ]
        })
    else:
        counter_path = Path(os.environ.get("PHASEA_FAKE_CODEX_COUNTER", str(output_path) + ".counter"))
        try:
            current = int(counter_path.read_text(encoding="utf-8").strip() or "0")
        except FileNotFoundError:
            current = 0
        next_value = current + 1
        counter_path.write_text(str(next_value), encoding="utf-8", newline="\\n")
        if next_value == 1:
            content = (
                "STATUS: needs_fix\\n"
                "SUMMARY: The current goal needs a focused route repair before continuing.\\n"
                "CHANGED: No durable project change was made in this fake execution.\\n"
                "VERIFY: Platform E2E confirms the goal is marked needs_fix.\\n"
                "REMAINING: Run needs-fix route for this step.\\n"
            )
        else:
            content = (
                "STATUS: completed\\n"
                "SUMMARY: The current step was repaired through the needs-fix route.\\n"
                "CHANGED: The fake execution completed the isolated step.\\n"
                "VERIFY: Platform E2E confirms route state and goal status.\\n"
                "REMAINING: none\\n"
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8", newline="\\n")
    print("fake codex ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
""".lstrip(),
        encoding="utf-8",
        newline="\n",
    )
    fake_cmd.write_text(
        f'@echo off\r\n"{sys.executable}" "{fake_py}" %*\r\n',
        encoding="utf-8",
        newline="",
    )
    return fake_cmd


def seed_phase2_gdd_sources(project: dict[str, Any]) -> None:
    workspace_root = Path(str(project["workspaceRootPath"]))
    repo_root = workspace_root / "repo"
    gdd_text = (
        "# Phase A Iteration E2E\n\n"
        "- Player must move on the field map and trigger one visible encounter.\n"
        "- HUD feedback must show HP, reward, and return-to-map state.\n"
    )
    gdd_path = repo_root / "docs" / "gdd" / "GDD.md"
    gdd_path.parent.mkdir(parents=True, exist_ok=True)
    gdd_path.write_text(gdd_text, encoding="utf-8", newline="\n")
    gdd_hash = hashlib.sha256(gdd_text.strip().encode("utf-8")).hexdigest()
    scene_route_hash = "phase2-e2e-scene-route-hash-v1"
    write_project_route_state(
        workspace_root,
        "scene-route/latest.json",
        {
            "schema_version": "scene-route.v1",
            "route": "scene-route-confirmation",
            "status": "confirmed",
            "source_gdd_form_hash": "phase2-e2e-gdd-form-hash-v1",
            "source_generated_gdd_hash": gdd_hash,
            "source_contract_snapshot_hash": "phase2-e2e-contract-snapshot-hash-v1",
            "confirmed_scene_route_hash": scene_route_hash,
            "scenes": [{"scene_id": "field_map"}],
        },
    )
    write_project_route_state(
        workspace_root,
        "gdd-document/latest.json",
        {
            "schema_version": "gdd-document-generation.v1",
            "route": "gdd-document-generation",
            "status": "ready",
            "generated_gdd_hash": gdd_hash,
            "source_scene_route_hash": scene_route_hash,
        },
    )
    write_project_route_state(
        workspace_root,
        "prototype/latest.json",
        {
            "route": "prototype-7day-playable",
            "run_id": "phase2-e2e-seeded-prototype",
            "status": "succeeded",
            "exit_code": 0,
            "slug": "phase-a-iteration-e2e",
            "prototype_completion": {"status": "ok"},
            "godot_smoke": {"status": "skipped"},
            "updated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        },
    )


def seed_phase2_prototype_skeleton(project: dict[str, Any], contract: dict[str, Any]) -> None:
    workspace_root = Path(str(project["workspaceRootPath"]))
    write_project_route_state(
        workspace_root,
        "prototype-skeleton/latest.json",
        {
            "schema_version": "prototype-skeleton-readback.v1",
            "route": "prototype-skeleton",
            "status": "succeeded",
            "source_boundary_enforced": True,
            "recovery_source_order_ref": "hosted-route-recovery-order.v1",
            "source_boundary": {
                "recovery_source_order_ref": "hosted-route-recovery-order.v1",
                "authority_sources": [
                    "game-type-route-profile",
                    "meta/project-execution-guide.md",
                    "routes/prototype-contract/latest.json",
                    "meta/routes/gdd-requirements/latest.json",
                    "meta/routes/prototype/latest.json",
                ],
                "source_hashes": {
                    "source_gdd_hash": contract.get("sourceGddHash"),
                    "source_scene_route_hash": contract.get("sourceSceneRouteHash"),
                    "source_requirement_map_hash": contract.get("sourceRequirementMapHash"),
                    "source_contract_hash": contract.get("contractHash"),
                    "source_contract_snapshot_hash": contract.get("sourceContractSnapshotHash"),
                    "source_godot_ui_contract_hash": contract.get("sourceGodotUiContractHash"),
                    "source_ui_style_contract_hash": contract.get("sourceUiStyleContractHash"),
                    "ui_style_snapshot_hash": contract.get("uiStyleSnapshotHash"),
                },
            },
            "freshness": "fresh",
            "source_gdd_hash": contract.get("sourceGddHash"),
            "source_scene_route_hash": contract.get("sourceSceneRouteHash"),
            "source_requirement_map_hash": contract.get("sourceRequirementMapHash"),
            "source_contract_hash": contract.get("contractHash"),
            "source_contract_snapshot_hash": contract.get("sourceContractSnapshotHash"),
            "source_godot_ui_contract_hash": contract.get("sourceGodotUiContractHash"),
            "source_ui_style_contract_hash": contract.get("sourceUiStyleContractHash"),
            "ui_style_snapshot_hash": contract.get("uiStyleSnapshotHash"),
            "evidence_refs": ["meta/routes/prototype/latest.json"],
            "updated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        },
    )


def write_project_route_state(workspace_root: Path, relative_path: str, payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, indent=2)
    for root in (workspace_root / "meta" / "routes", workspace_root / "repo" / "meta" / "routes"):
        path = root / Path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(serialized, encoding="utf-8", newline="\n")


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
    last_projects: Any = None
    while time.monotonic() < deadline:
        projects = get_json(base_url, "/api/projects", headers, timeout=30)
        last_projects = projects
        project = next((item for item in projects if str(item.get("projectId")) == project_id), None)
        if project and project.get("bootstrapStatus") == "succeeded":
            return project
        if project and project.get("bootstrapStatus") == "failed":
            raise AssertionError(f"project bootstrap failed: {project}")
        if project is None:
            failure_status, failure_payload = request_json(
                "GET",
                f"{base_url}/api/project-creation-failures/latest",
                headers=headers,
                timeout=30,
            )
            if failure_status == 200 and str(failure_payload.get("projectId")) == project_id:
                raise AssertionError(f"project bootstrap failed and project was deleted: {failure_payload}")
        time.sleep(5)
    raise TimeoutError(f"project bootstrap did not finish in time; last_projects={last_projects}")


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
