#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT_TEXT = r'''extends SceneTree

const MAIN_SCENE := "res://Game.Godot/Scenes/Main.tscn"

func _initialize() -> void:
    var expected_scene := String(OS.get_environment("PHASEA_EXPECTED_PROTOTYPE_SCENE")).strip_edges()
    if expected_scene == "":
        push_error("PHASEA_EXPECTED_PROTOTYPE_SCENE missing")
        quit(2)
        return

    var packed = load(MAIN_SCENE)
    if packed == null:
        push_error("main_scene_missing")
        quit(3)
        return

    var main = packed.instantiate()
    get_root().add_child(main)
    await process_frame
    await process_frame

    var menu = main.get_node_or_null("MainMenu")
    if menu == null:
        push_error("main_menu_missing")
        quit(4)
        return

    var nav = main.get_node_or_null("ScreenNavigator")
    if nav == null:
        push_error("screen_navigator_missing")
        quit(5)
        return
    if "UseFadeTransition" in nav:
        nav.UseFadeTransition = false

    var button = menu.get_node_or_null("VBox/BtnPrototype")
    if button == null:
        push_error("prototype_button_missing")
        quit(6)
        return

    button.emit_signal("pressed")
    await process_frame
    await process_frame
    await process_frame

    var root = main.get_node_or_null("ScreenRoot")
    if root == null:
        push_error("screen_root_missing")
        quit(7)
        return

    if root.get_child_count() == 0:
        push_error("prototype_scene_not_loaded")
        quit(8)
        return

    var current = root.get_child(root.get_child_count() - 1)
    var actual_scene = ""
    if current != null:
        actual_scene = String(current.scene_file_path)

    if actual_scene != expected_scene:
        push_error("prototype_scene_mismatch expected=%s actual=%s" % [expected_scene, actual_scene])
        quit(9)
        return

    print("MAIN_MENU_PROTOTYPE_NAV PASS scene=%s" % actual_scene)
    quit(0)
'''


def _to_windows_extended_path(path: Path) -> str:
    raw = str(path)
    if os.name != "nt":
        return raw
    if raw.startswith("\\\\?\\"):
        return raw
    if raw.startswith("\\\\"):
        return "\\\\?\\UNC\\" + raw[2:]
    return "\\\\?\\" + raw


def _ensure_dir(path: Path) -> None:
    os.makedirs(_to_windows_extended_path(path.resolve()), exist_ok=True)


def _write_text(path: Path, content: str) -> None:
    _ensure_dir(path.parent)
    with open(_to_windows_extended_path(path.resolve()), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def _read_text(path: Path) -> str:
    with open(_to_windows_extended_path(path.resolve()), "r", encoding="utf-8", errors="ignore") as handle:
        return handle.read()


def _open_writer(path: Path):
    _ensure_dir(path.parent)
    return open(_to_windows_extended_path(path.resolve()), "w", encoding="utf-8", errors="ignore")


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


def _run(godot_bin: str, project_path: str, expected_scene: str, timeout_sec: int) -> int:
    bin_path = Path(godot_bin)
    project_root = Path(project_path)
    if not bin_path.is_file():
        print(f"[prototype_main_menu_navigation] GODOT_BIN not found: {godot_bin}", file=sys.stderr)
        return 1
    if not project_root.is_dir():
        print(f"[prototype_main_menu_navigation] --project-path not found: {project_path}", file=sys.stderr)
        return 2
    if not expected_scene.startswith("res://") or not expected_scene.endswith(".tscn"):
        print(f"[prototype_main_menu_navigation] invalid expected scene: {expected_scene}", file=sys.stderr)
        return 2
    if timeout_sec <= 0:
        print("[prototype_main_menu_navigation] --timeout-sec must be greater than 0", file=sys.stderr)
        return 2

    day = _dt.date.today().strftime("%Y-%m-%d")
    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = project_root / "logs" / "ci" / day / "prototype-main-menu-navigation" / ts
    _ensure_dir(dest)

    temp_script_dir = Path(tempfile.mkdtemp(prefix="phasea-nav-smoke-"))
    try:
        _cleanup_godot_processes(str(bin_path))
        temp_script = temp_script_dir / "main_menu_navigation_smoke.gd"
        out_path = dest / "out.log"
        err_path = dest / "err.log"
        log_path = dest / "combined.log"
        summary_path = dest / "summary.json"
        _write_text(temp_script, SCRIPT_TEXT)

        prewarm_cmd = [str(bin_path), "--headless", "--path", str(project_root), "--build-solutions", "--quit"]
        prewarm = subprocess.run(
            prewarm_cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=600,
        )
        prewarm_mode = "godot-build-solutions"
        prewarm_stdout = prewarm.stdout or ""
        prewarm_stderr = prewarm.stderr or ""
        if prewarm.returncode != 0:
            fallback = subprocess.run(
                ["dotnet", "build", "GodotGame.csproj", "-c", "Debug", "-v", "minimal"],
                cwd=project_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=600,
            )
            prewarm_mode = "dotnet-build"
            prewarm_stdout += ("\n" if prewarm_stdout else "") + (fallback.stdout or "")
            prewarm_stderr += ("\n" if prewarm_stderr else "") + (fallback.stderr or "")
            if fallback.returncode != 0:
                summary = {
                    "run_id": f"prototype-main-menu-navigation-{ts}",
                    "expected_scene": expected_scene,
                    "passed": False,
                    "exit_code": fallback.returncode,
                    "prewarm_mode": prewarm_mode,
                    "prewarm_failed": True,
                    "artifacts": {
                        "script": str(temp_script),
                    },
                }
                _write_text(summary_path, json.dumps(summary, ensure_ascii=False, indent=2))
                print("MAIN_MENU_PROTOTYPE_NAV FAIL", file=sys.stderr)
                if prewarm_stdout.strip():
                    print(prewarm_stdout, file=sys.stderr)
                if prewarm_stderr.strip():
                    print(prewarm_stderr, file=sys.stderr)
                return fallback.returncode or 1

        cmd = [
            str(bin_path),
            "--headless",
            "--path",
            str(project_root),
            "-s",
            str(temp_script),
        ]
        env = dict(**os.environ)
        env["PHASEA_EXPECTED_PROTOTYPE_SCENE"] = expected_scene

        with _open_writer(out_path) as f_out, _open_writer(err_path) as f_err:
            proc = subprocess.Popen(cmd, stdout=f_out, stderr=f_err, text=True, env=env, cwd=project_root)
            try:
                proc.wait(timeout=timeout_sec)
            except subprocess.TimeoutExpired:
                proc.kill()
                print("[prototype_main_menu_navigation] timeout", file=sys.stderr)
                return 124
            finally:
                _cleanup_godot_processes(str(bin_path))

        stdout = _read_text(out_path) if out_path.exists() else ""
        stderr = _read_text(err_path) if err_path.exists() else ""
        combined = stdout + ("\n" + stderr if stderr else "")
        _write_text(log_path, combined)

        passed = proc.returncode == 0 and "MAIN_MENU_PROTOTYPE_NAV PASS" in combined
        summary = {
            "run_id": f"prototype-main-menu-navigation-{ts}",
            "expected_scene": expected_scene,
            "passed": passed,
            "exit_code": proc.returncode,
            "prewarm_mode": prewarm_mode,
            "artifacts": {
                "stdout": str(out_path),
                "stderr": str(err_path),
                "combined": str(log_path),
                "script": str(temp_script),
            },
        }
        _write_text(summary_path, json.dumps(summary, ensure_ascii=False, indent=2))

        if passed:
            print(f"MAIN_MENU_PROTOTYPE_NAV PASS scene={expected_scene}")
            return 0

        print("MAIN_MENU_PROTOTYPE_NAV FAIL", file=sys.stderr)
        if combined.strip():
            print(combined, file=sys.stderr)
        return proc.returncode if proc.returncode != 0 else 1
    finally:
        _cleanup_godot_processes(str(bin_path))
        shutil.rmtree(_to_windows_extended_path(temp_script_dir.resolve()), ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Main.tscn prototype button navigates to the expected prototype scene.")
    parser.add_argument("--godot-bin", required=True)
    parser.add_argument("--project-path", required=True)
    parser.add_argument("--expected-scene", required=True)
    parser.add_argument("--timeout-sec", type=int, default=15)
    args = parser.parse_args()
    return _run(args.godot_bin, args.project_path, args.expected_scene, args.timeout_sec)


if __name__ == "__main__":
    sys.exit(main())
