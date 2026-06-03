#!/usr/bin/env python3
"""Headless smoke test runner for Godot (Windows, Godot+C# template).

This is a Python equivalent of `scripts/ci/smoke_headless.ps1` with two behaviors:

- default (permissive): never fails the build; prints PASS hints only.
- strict (`--strict`): returns non-zero unless core markers are detected.

Heuristics (kept aligned with the PowerShell version):
- Prefer "[TEMPLATE_SMOKE_READY]".
- Fallback to "[DB] opened".
- In loose mode, any output counts as PASS.

Example (PowerShell):
  py -3 scripts/python/smoke_headless.py `
    --godot-bin "C:\\Godot\\Godot_v4.5.1-stable_mono_win64_console.exe" `
    --project-path "." --scene "res://Game.Godot/Scenes/Main.tscn" `
    --timeout-sec 5 --strict
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import subprocess
import sys
from pathlib import Path


PREWARM_TIMEOUT_SEC = 120


def _is_known_good_scene(scene: str) -> bool:
    return bool(scene) and scene.startswith("res://") and scene.lower().endswith(".tscn")


def _cleanup_godot_processes(godot_bin: str) -> None:
    exe_name = os.path.basename(godot_bin).strip()
    if not exe_name:
        return
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", exe_name, "/T"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=20,
        )
    except Exception:
        pass


def _ensure_runtime_logs_godot_ignored(project_root: Path) -> None:
    logs_root = project_root / "logs"
    logs_root.mkdir(parents=True, exist_ok=True)
    gdignore = logs_root / ".gdignore"
    if not gdignore.exists():
        gdignore.write_text("", encoding="utf-8")


def _ensure_non_runtime_dirs_godot_ignored(project_root: Path) -> list[str]:
    ignored_dirs = [
        ".agents",
        "backup",
        "docs",
        "logs",
        "PhaseA.Platform/wwwroot",
        "_bmad",
    ]
    written: list[str] = []
    for relative in ignored_dirs:
        directory = project_root / relative
        if not directory.is_dir():
            continue
        gdignore = directory / ".gdignore"
        if not gdignore.exists():
            gdignore.write_text("", encoding="utf-8")
            written.append(gdignore.relative_to(project_root).as_posix())
    return written


def _strip_utf8_bom_from_godot_text_resources(project_root: Path) -> list[str]:
    resource_roots = [
        project_root / "Game.Godot",
        project_root / "Tests.Godot",
    ]
    suffixes = {".gd", ".tscn", ".tres"}
    fixed: list[str] = []
    for root in resource_roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in suffixes:
                continue
            data = path.read_bytes()
            if data.startswith(b"\xef\xbb\xbf"):
                path.write_bytes(data[3:])
                fixed.append(path.relative_to(project_root).as_posix())
    return fixed


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        subprocess.run(
            ["taskkill", "/F", "/PID", str(process.pid), "/T"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=20,
        )
    except Exception:
        try:
            process.kill()
        except Exception:
            pass


def _run_captured_process(cmd: list[str], cwd: Path, timeout_sec: int) -> tuple[int, str, str]:
    process = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_sec)
        return process.returncode, stdout or "", stderr or ""
    except subprocess.TimeoutExpired as exc:
        _terminate_process_tree(process)
        stdout, stderr = process.communicate()
        prefix_stdout = exc.stdout.decode("utf-8", errors="ignore") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        prefix_stderr = exc.stderr.decode("utf-8", errors="ignore") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return 124, prefix_stdout + (stdout or ""), prefix_stderr + (stderr or "")


def _msbuild_isolation_args(scope: str) -> list[str]:
    build_root = os.environ.get("PHASEA_VALIDATION_BUILD_ROOT", "").strip()
    if not build_root:
        return []
    safe_scope = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in scope).strip("_") or "validation"
    obj_root = Path(build_root) / safe_scope / "obj" / "$(MSBuildProjectName)"
    bin_root = Path(build_root) / safe_scope / "bin" / "$(MSBuildProjectName)"
    return [
        f"-p:BaseIntermediateOutputPath={obj_root}{os.sep}",
        f"-p:BaseOutputPath={bin_root}{os.sep}",
        "-p:UseSharedCompilation=false",
        "-p:NodeReuse=false",
        "-m:1",
        "-p:BuildInParallel=false",
    ]


def _build_output_has_success(stdout: str, stderr: str) -> bool:
    combined = f"{stdout}\n{stderr}".lower()
    return (
        "[ done ]" in combined
        and "dotnet_build_project" in combined
        and not _build_output_has_failure(stdout, stderr)
    )


def _build_output_has_failure(stdout: str, stderr: str) -> bool:
    combined = f"{stdout}\n{stderr}".lower()
    failure_markers = (
        "error:",
        "parse error:",
        "is not compiling",
        "build callback failed",
        "aborting",
        "cannot instantiate c# script",
        "failed to create an autoload",
        "failed to instantiate an autoload",
    )
    return any(marker in combined for marker in failure_markers)


def _is_prototype_scene(scene: str) -> bool:
    return scene.lower().startswith("res://game.godot/prototypes/")


def _has_runtime_failure(output: str) -> bool:
    lowered = output.lower()
    failure_markers = (
        "script error",
        "fatal:",
        "unhandled exception",
        "exception:",
        "error:",
        "failed loading resource",
        "can't load",
        "cannot load",
        "nodes with non-equal opposite anchors",
        "c# backtrace",
    )
    return any(marker in lowered for marker in failure_markers)


def _stop_dotnet_build_server(project_root: Path) -> None:
    try:
        subprocess.run(
            ["dotnet", "build-server", "shutdown"],
            cwd=project_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=30,
        )
    except Exception:
        pass


def _prewarm_csharp(godot_bin: str, project_root: Path, timeout_sec: int = PREWARM_TIMEOUT_SEC) -> tuple[bool, str, str, str]:
    prewarm_timeout = max(1, PREWARM_TIMEOUT_SEC)
    dotnet_returncode, dotnet_stdout, dotnet_stderr = _run_captured_process(
        ["dotnet", "build", "GodotGame.csproj", "-c", "Debug", "-v", "minimal", *_msbuild_isolation_args("smoke-headless")],
        project_root,
        prewarm_timeout,
    )
    if dotnet_returncode == 0 and not _build_output_has_failure(dotnet_stdout, dotnet_stderr):
        _stop_dotnet_build_server(project_root)
        return True, "dotnet-build", dotnet_stdout, dotnet_stderr
    if dotnet_returncode == 124:
        dotnet_stderr += "\n[smoke_headless] dotnet prewarm timed out; falling back to godot build-solutions."

    godot_cmd = [godot_bin, "--headless", "--path", str(project_root), "--build-solutions", "--quit"]
    godot_returncode, godot_stdout, godot_stderr = _run_captured_process(
        godot_cmd,
        project_root,
        prewarm_timeout,
    )
    if godot_returncode == 124:
        _cleanup_godot_processes(godot_bin)
        godot_stderr += "\n[smoke_headless] godot build-solutions prewarm timed out."
    stdout = dotnet_stdout + (("\n" + godot_stdout) if godot_stdout else "")
    stderr = dotnet_stderr + (("\n" + godot_stderr) if godot_stderr else "")
    if (
        (godot_returncode == 0 or _build_output_has_success(godot_stdout, godot_stderr))
        and not _build_output_has_failure(godot_stdout, godot_stderr)
    ):
        _stop_dotnet_build_server(project_root)
        return True, "godot-build-solutions", stdout, stderr

    _stop_dotnet_build_server(project_root)
    return False, "dotnet-build", stdout, stderr


def _run_smoke(
    godot_bin: str,
    project_path: str,
    scene: str,
    timeout_sec: int,
    strict: bool,
    task_id: int | None = None,
) -> int:
    bin_path = Path(godot_bin)
    if not bin_path.is_file():
        print(f"[smoke_headless] GODOT_BIN not found: {godot_bin}", file=sys.stderr)
        return 1
    if timeout_sec <= 0:
        print("[smoke_headless] --timeout-sec must be greater than 0", file=sys.stderr)
        return 2

    project_root = Path(project_path)
    if not project_root.exists() or not project_root.is_dir():
        print(f"[smoke_headless] --project-path not found or not a directory: {project_path}", file=sys.stderr)
        return 2

    if not _is_known_good_scene(scene):
        print(f"[smoke_headless] --scene must be a known-good res://*.tscn path: {scene}", file=sys.stderr)
        return 2

    day = _dt.date.today().strftime("%Y-%m-%d")
    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = Path("logs") / "ci" / day / "smoke" / ts
    dest.mkdir(parents=True, exist_ok=True)
    _ensure_runtime_logs_godot_ignored(project_root)
    gdignore_written = _ensure_non_runtime_dirs_godot_ignored(project_root)
    bom_fixed = _strip_utf8_bom_from_godot_text_resources(project_root)

    out_path = dest / "headless.out.log"
    err_path = dest / "headless.err.log"
    log_path = dest / "headless.log"
    summary_path = dest / "summary.json"
    prewarm_out_path = dest / "prewarm.out.log"
    prewarm_err_path = dest / "prewarm.err.log"

    cmd = [str(bin_path), "--headless", "--path", project_path, "--scene", scene]
    cmd_text = " ".join(cmd)
    print(f"[smoke_headless] starting Godot: {' '.join(cmd)} (timeout={timeout_sec}s)")
    if bom_fixed:
        print(f"[smoke_headless] stripped UTF-8 BOM from {len(bom_fixed)} Godot text resources")
    if gdignore_written:
        print(f"[smoke_headless] wrote {len(gdignore_written)} non-runtime .gdignore files")
    _cleanup_godot_processes(str(bin_path))
    prewarm_ok, prewarm_mode, prewarm_stdout, prewarm_stderr = _prewarm_csharp(str(bin_path), project_root, timeout_sec)
    prewarm_out_path.write_text(prewarm_stdout, encoding="utf-8", errors="ignore")
    prewarm_err_path.write_text(prewarm_stderr, encoding="utf-8", errors="ignore")
    if not prewarm_ok:
        print("[smoke_headless] failed to prewarm C# build", file=sys.stderr)
        summary = {
            "runId": f"smoke-{ts}",
            "date": day,
            "timestamp": ts,
            "godot_bin": str(bin_path),
            "project_path": project_path,
            "scene": scene,
            "known_good_scene": _is_known_good_scene(scene),
            "timeout_sec": timeout_sec,
            "strict": strict,
            "command": cmd_text,
            "prewarm_mode": prewarm_mode,
            "artifacts": {
                "prewarm_out_log": str(prewarm_out_path),
                "prewarm_err_log": str(prewarm_err_path),
                "summary_json": str(summary_path),
            },
            "exit_code": 1,
        }
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
            errors="ignore",
        )
        return 1

    with out_path.open("w", encoding="utf-8", errors="ignore") as f_out, \
            err_path.open("w", encoding="utf-8", errors="ignore") as f_err:
        try:
            proc = subprocess.Popen(cmd, stdout=f_out, stderr=f_err, text=True)
        except Exception as exc:  # pragma: no cover - environment-specific failure
            print(f"[smoke_headless] failed to start Godot: {exc}", file=sys.stderr)
            return 1

        try:
            proc.wait(timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            print("[smoke_headless] timeout reached; terminating Godot (expected for smoke)")
            try:
                proc.kill()
            except Exception:
                pass
        finally:
            _cleanup_godot_processes(str(bin_path))

    content_parts: list[str] = []
    if out_path.is_file():
        content_parts.append(out_path.read_text(encoding="utf-8", errors="ignore"))
    if err_path.is_file():
        content_parts.append("\n" + err_path.read_text(encoding="utf-8", errors="ignore"))

    combined = "".join(content_parts)
    log_path.write_text(combined, encoding="utf-8", errors="ignore")
    print(f"[smoke_headless] log saved at {log_path} (out={out_path}, err={err_path})")

    text = combined or ""
    has_marker = "[TEMPLATE_SMOKE_READY]" in text
    has_db_open = "[DB] opened" in text
    has_any = bool(text.strip())
    has_runtime_failure = _has_runtime_failure(text)
    has_prototype_alive = _is_prototype_scene(scene) and has_any and not has_runtime_failure

    if has_marker:
        print("SMOKE PASS (marker)")
    elif has_db_open:
        print("SMOKE PASS (db opened)")
    elif has_prototype_alive:
        print("SMOKE PASS (prototype scene alive)")
    elif has_any:
        print("SMOKE PASS (any output)")
    else:
        print("SMOKE INCONCLUSIVE (no output). Check logs.")

    exit_code = 0
    if strict:
        # Strict mode keeps Main.tscn marker semantics, but prototype scenes
        # validate as a running scene when they emit output without runtime failures.
        exit_code = 0 if (has_marker or has_db_open or has_prototype_alive) else 1

    summary = {
        "runId": f"smoke-{ts}",
        "date": day,
        "timestamp": ts,
        "godot_bin": str(bin_path),
        "project_path": project_path,
        "scene": scene,
        "known_good_scene": _is_known_good_scene(scene),
        "timeout_sec": timeout_sec,
        "strict": strict,
        "command": cmd_text,
        "markers": {
            "template_smoke_ready": has_marker,
            "db_opened": has_db_open,
            "any_output": has_any,
            "prototype_scene_alive": has_prototype_alive,
            "runtime_failure": has_runtime_failure,
        },
        "prewarm_mode": prewarm_mode,
        "artifacts": {
            "prewarm_out_log": str(prewarm_out_path),
            "prewarm_err_log": str(prewarm_err_path),
            "out_log": str(out_path),
            "err_log": str(err_path),
            "combined_log": str(log_path),
            "summary_json": str(summary_path),
        },
        "exit_code": exit_code,
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
        errors="ignore",
    )

    if task_id is not None:
        task_summary = Path("logs") / "ci" / day / f"task-{int(task_id):04d}.json"
        task_payload = {
            "task_id": int(task_id),
            "date": day,
            "timestamp": ts,
            "platform": "windows",
            "runner": "scripts/python/smoke_headless.py",
            "command": f"py -3 scripts/python/smoke_headless.py --godot-bin \"{godot_bin}\" --project-path \"{project_path}\" --scene \"{scene}\" --timeout-sec {timeout_sec}" + (" --strict" if strict else ""),
            "exit_code": exit_code,
            "strict": strict,
            "known_good_scene": scene,
            "artifacts": {
                "headless_out_log": str(out_path),
                "headless_err_log": str(err_path),
                "summary_json": str(summary_path),
            },
            "verification": {
                "headless_out_log_exists": out_path.exists(),
                "headless_err_log_exists": err_path.exists(),
                "summary_json_exists": summary_path.exists(),
            },
        }
        task_summary.write_text(
            json.dumps(task_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
            errors="ignore",
        )

    # Permissive mode never gates; logs are the artifact.
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Godot headless smoke test (Python variant)")
    parser.add_argument("--godot-bin", required=True, help="Path to Godot executable (mono console)")
    parser.add_argument("--project-path", default=".", help="Godot project path (default '.')")
    parser.add_argument("--scene", default="res://Game.Godot/Scenes/Main.tscn", help="Scene to load")
    parser.add_argument("--timeout-sec", type=int, default=5, help="Timeout seconds before kill")
    parser.add_argument("--strict", action="store_true", help="Enable strict gate mode")
    parser.add_argument("--task-id", type=int, default=None, help="Optional task id to emit logs/ci/<date>/task-<id>.json")

    args = parser.parse_args()
    return _run_smoke(args.godot_bin, args.project_path, args.scene, args.timeout_sec, args.strict, args.task_id)


if __name__ == "__main__":
    sys.exit(main())
