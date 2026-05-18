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


def _prewarm_csharp(godot_bin: str, project_root: Path) -> tuple[bool, str, str, str]:
    prewarm_cmd = [godot_bin, "--headless", "--path", str(project_root), "--build-solutions", "--quit"]
    prewarm = subprocess.run(
        prewarm_cmd,
        cwd=project_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        timeout=600,
    )
    if prewarm.returncode == 0:
        return True, "godot-build-solutions", prewarm.stdout or "", prewarm.stderr or ""

    fallback = subprocess.run(
        ["dotnet", "build", "GodotGame.csproj", "-c", "Debug", "-v", "minimal"],
        cwd=project_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        timeout=600,
    )
    stdout = (prewarm.stdout or "") + (("\n" + fallback.stdout) if fallback.stdout else "")
    stderr = (prewarm.stderr or "") + (("\n" + fallback.stderr) if fallback.stderr else "")
    return fallback.returncode == 0, "dotnet-build", stdout, stderr


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

    out_path = dest / "headless.out.log"
    err_path = dest / "headless.err.log"
    log_path = dest / "headless.log"
    summary_path = dest / "summary.json"
    prewarm_out_path = dest / "prewarm.out.log"
    prewarm_err_path = dest / "prewarm.err.log"

    cmd = [str(bin_path), "--headless", "--path", project_path, "--scene", scene]
    cmd_text = " ".join(cmd)
    print(f"[smoke_headless] starting Godot: {' '.join(cmd)} (timeout={timeout_sec}s)")
    _cleanup_godot_processes(str(bin_path))
    prewarm_ok, prewarm_mode, prewarm_stdout, prewarm_stderr = _prewarm_csharp(str(bin_path), project_root)
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

    if has_marker:
        print("SMOKE PASS (marker)")
    elif has_db_open:
        print("SMOKE PASS (db opened)")
    elif has_any:
        print("SMOKE PASS (any output)")
    else:
        print("SMOKE INCONCLUSIVE (no output). Check logs.")

    exit_code = 0
    if strict:
        # Strict mode: require at least the marker or a DB opened line.
        exit_code = 0 if (has_marker or has_db_open) else 1

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
