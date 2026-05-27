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


PREWARM_TIMEOUT_SEC = 120


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

    if expected_scene.find("/dq-rpg/") >= 0:
        var start_button = _find_node_by_name(current, "StartButton")
        if start_button == null:
            push_error("rpg_start_button_missing")
            quit(10)
            return

        start_button.emit_signal("pressed")
        await process_frame
        await process_frame
        await process_frame

        var map_scene = _find_node_by_name(current, "MapScene")
        if map_scene == null:
            push_error("rpg_map_scene_missing_after_start")
            quit(11)
            return
        if not map_scene.visible:
            push_error("rpg_map_scene_not_visible_after_start")
            quit(12)
            return
        if map_scene is Control:
            var control := map_scene as Control
            if control.size.x <= 0.0 or control.size.y <= 0.0:
                push_error("rpg_map_scene_has_no_visible_size_after_start")
                quit(13)
                return

        var map_title = _find_node_by_name(map_scene, "Title")
        var map_grid = _find_node_by_name(map_scene, "Grid")
        var map_status = _find_node_by_name(map_scene, "StatusLabel")
        if map_title == null or map_grid == null or map_status == null:
            push_error("rpg_map_visible_markers_missing_after_start")
            quit(14)
            return

        print("RPG_START_ADVENTURE_MAP_VISIBLE PASS")

    print("MAIN_MENU_PROTOTYPE_NAV PASS scene=%s" % actual_scene)
    quit(0)

func _find_node_by_name(root: Node, wanted_name: String) -> Node:
    if root.name == wanted_name:
        return root
    for child in root.get_children():
        if child is Node:
            var found = _find_node_by_name(child, wanted_name)
            if found != null:
                return found
    return null
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


def _candidate_dotnet_paths(root: Path) -> list[Path]:
    exe_name = "dotnet.exe" if os.name == "nt" else "dotnet"
    candidates: list[Path] = []

    which_dotnet = shutil.which("dotnet")
    if which_dotnet:
        candidates.append(Path(which_dotnet))

    for env_key in ("DOTNET_ROOT", "DOTNET_HOME"):
        env_val = os.environ.get(env_key)
        if env_val:
            candidates.append(Path(env_val) / exe_name)

    candidates.append(root / ".dotnet" / exe_name)
    candidates.append(Path.home() / ".dotnet" / exe_name)

    if os.name == "nt":
        candidates.append(Path(r"C:\Program Files\dotnet\dotnet.exe"))
        candidates.append(Path(r"C:\Program Files (x86)\dotnet\dotnet.exe"))

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = os.path.normcase(os.path.normpath(str(candidate)))
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def _resolve_dotnet(root: Path) -> str:
    for candidate in _candidate_dotnet_paths(root):
        if candidate.is_file():
            return str(candidate)
    return "dotnet"


def _build_process_env(dotnet_bin: str) -> dict[str, str]:
    env = os.environ.copy()
    if os.path.isfile(dotnet_bin):
        dotnet_root = os.path.dirname(dotnet_bin)
        env["DOTNET_ROOT"] = dotnet_root
        env["DOTNET_HOME"] = dotnet_root
        current_path = env.get("PATH", "")
        path_parts = current_path.split(os.pathsep) if current_path else []
        if dotnet_root not in path_parts:
            env["PATH"] = dotnet_root + (os.pathsep + current_path if current_path else "")
    return env


def _ensure_runtime_logs_godot_ignored(project_root: Path) -> None:
    logs_root = project_root / "logs"
    _ensure_dir(logs_root)
    gdignore = logs_root / ".gdignore"
    if not gdignore.exists():
        _write_text(gdignore, "")


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


def _run_captured_process(cmd: list[str], cwd: Path, timeout_sec: int, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    process = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
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


def _run(godot_bin: str, project_path: str, expected_scene: str, timeout_sec: int) -> int:
    bin_path = Path(godot_bin)
    project_root = Path(project_path)
    dotnet_bin = _resolve_dotnet(project_root)
    process_env = _build_process_env(dotnet_bin)
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
    _ensure_runtime_logs_godot_ignored(project_root)

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
        prewarm_returncode, prewarm_stdout, prewarm_stderr = _run_captured_process(
            prewarm_cmd,
            project_root,
            PREWARM_TIMEOUT_SEC,
            env=process_env,
        )
        prewarm_mode = "godot-build-solutions"
        if prewarm_returncode == 124:
            _cleanup_godot_processes(str(bin_path))
            prewarm_stderr += "\n[prototype_main_menu_navigation] godot build-solutions prewarm timed out."
        if prewarm_returncode != 0:
            fallback_returncode, fallback_stdout, fallback_stderr = _run_captured_process(
                [dotnet_bin, "build", "GodotGame.csproj", "-c", "Debug", "-v", "minimal"],
                project_root,
                PREWARM_TIMEOUT_SEC,
                env=process_env,
            )
            prewarm_mode = "dotnet-build"
            prewarm_stdout += ("\n" if prewarm_stdout else "") + fallback_stdout
            prewarm_stderr += ("\n" if prewarm_stderr else "") + fallback_stderr
            if fallback_returncode == 124:
                prewarm_stderr += "\n[prototype_main_menu_navigation] dotnet prewarm fallback timed out."
            if fallback_returncode != 0:
                summary = {
                    "run_id": f"prototype-main-menu-navigation-{ts}",
                    "expected_scene": expected_scene,
                    "passed": False,
                    "exit_code": fallback_returncode,
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
                return fallback_returncode or 1

        cmd = [
            str(bin_path),
            "--headless",
            "--path",
            str(project_root),
            "-s",
            str(temp_script),
        ]
        env = dict(**os.environ)
        env.update(process_env)
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

        godot_error_markers = (
            "ERROR:",
            "SCRIPT ERROR:",
            "Parse Error:",
            "Failed to instantiate",
            "Cannot instantiate",
        )
        has_godot_errors = any(marker in combined for marker in godot_error_markers)
        rpg_start_required = "/dq-rpg/" in expected_scene
        rpg_start_passed = (not rpg_start_required) or "RPG_START_ADVENTURE_MAP_VISIBLE PASS" in combined
        passed = (
            proc.returncode == 0
            and "MAIN_MENU_PROTOTYPE_NAV PASS" in combined
            and rpg_start_passed
            and not has_godot_errors
        )
        summary = {
            "run_id": f"prototype-main-menu-navigation-{ts}",
            "expected_scene": expected_scene,
            "passed": passed,
            "exit_code": proc.returncode,
            "prewarm_mode": prewarm_mode,
            "godot_errors_detected": has_godot_errors,
            "rpg_start_adventure_required": rpg_start_required,
            "rpg_start_adventure_passed": rpg_start_passed,
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
