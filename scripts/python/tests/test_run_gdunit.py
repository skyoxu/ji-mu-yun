#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON_DIR = REPO_ROOT / "scripts" / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))


def _load_module(name: str, relative_path: str):
    path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"failed to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


run_gdunit = _load_module("run_gdunit_test_module", "scripts/python/run_gdunit.py")
prototype_main_menu_navigation_smoke = _load_module(
    "prototype_main_menu_navigation_smoke_test_module",
    "scripts/python/prototype_main_menu_navigation_smoke.py",
)


class RunGdUnitTests(unittest.TestCase):
    def test_godot_example_scene_files_should_not_start_with_utf8_bom(self) -> None:
        scene_files = sorted((REPO_ROOT / "Game.Godot" / "Examples").rglob("*.tscn"))

        self.assertTrue(scene_files)
        offenders = [
            str(path.relative_to(REPO_ROOT)).replace("\\", "/")
            for path in scene_files
            if path.read_bytes().startswith(b"\xef\xbb\xbf")
        ]
        self.assertEqual([], offenders)

    def test_godot_smoke_runners_should_strip_utf8_bom_from_text_resources(self) -> None:
        smoke_headless = _load_module("smoke_headless_bom_cleanup_test_module", "scripts/python/smoke_headless.py")
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            scene = root / "Game.Godot" / "Examples" / "Demo.tscn"
            scene.parent.mkdir(parents=True)
            scene.write_bytes(b"\xef\xbb\xbf[gd_scene format=3]\n")

            smoke_fixed = smoke_headless._strip_utf8_bom_from_godot_text_resources(root)

            self.assertEqual(["Game.Godot/Examples/Demo.tscn"], smoke_fixed)
            self.assertEqual(b"[gd_scene format=3]\n", scene.read_bytes())

            scene.write_bytes(b"\xef\xbb\xbf[gd_scene format=3]\n")
            navigation_fixed = prototype_main_menu_navigation_smoke._strip_utf8_bom_from_godot_text_resources(root)

            self.assertEqual(["Game.Godot/Examples/Demo.tscn"], navigation_fixed)
            self.assertEqual(b"[gd_scene format=3]\n", scene.read_bytes())

    def test_godot_smoke_runners_should_ignore_non_runtime_dirs(self) -> None:
        smoke_headless = _load_module("smoke_headless_gdignore_non_runtime_test_module", "scripts/python/smoke_headless.py")
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for relative in [".agents", "backup", "docs", "logs", "_bmad"]:
                (root / relative).mkdir(parents=True)

            smoke_written = smoke_headless._ensure_non_runtime_dirs_godot_ignored(root)

            self.assertEqual(
                [".agents/.gdignore", "backup/.gdignore", "docs/.gdignore", "logs/.gdignore", "_bmad/.gdignore"],
                smoke_written,
            )
            for relative in smoke_written:
                self.assertTrue((root / relative).exists())

            for relative in smoke_written:
                (root / relative).unlink()
            navigation_written = prototype_main_menu_navigation_smoke._ensure_non_runtime_dirs_godot_ignored(root)

            self.assertEqual(smoke_written, navigation_written)
            for relative in navigation_written:
                self.assertTrue((root / relative).exists())

    def test_copy_reports_best_effort_should_collect_failures_and_continue(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            src_root = Path(tmpdir) / "src"
            dest_root = Path(tmpdir) / "dest"
            (src_root / "report_1" / "test_suites").mkdir(parents=True, exist_ok=True)
            good = src_root / "report_1" / "results.xml"
            bad = src_root / "report_1" / "test_suites" / "deep.html"
            good.write_text("<testsuites />", encoding="utf-8")
            bad.write_text("<html></html>", encoding="utf-8")

            original_copy2 = run_gdunit.shutil.copy2

            def fake_copy2(src: str, dst: str):
                if src.endswith("deep.html"):
                    raise OSError(3, "path not found")
                return original_copy2(src, dst)

            with mock.patch.object(run_gdunit.shutil, "copy2", side_effect=fake_copy2):
                failures = run_gdunit._copy_reports_best_effort(str(src_root), str(dest_root))

            self.assertEqual(1, len(failures))
            self.assertTrue((dest_root / "report_1" / "results.xml").exists())
            self.assertFalse((dest_root / "report_1" / "test_suites" / "deep.html").exists())

    def test_prototype_main_menu_navigation_smoke_write_helpers_should_support_nested_paths(self) -> None:
        tmpdir = Path(tempfile.mkdtemp())
        try:
            deep = tmpdir
            for index in range(8):
                deep = deep / f"nested-segment-{index:02d}-for-long-path-check"
            target = deep / "main_menu_navigation_smoke.gd"

            prototype_main_menu_navigation_smoke._write_text(target, "extends SceneTree\n")

            self.assertTrue(os.path.exists(prototype_main_menu_navigation_smoke._to_windows_extended_path(target.resolve())))
            self.assertEqual("extends SceneTree\n", prototype_main_menu_navigation_smoke._read_text(target))
        finally:
            shutil.rmtree(
                prototype_main_menu_navigation_smoke._to_windows_extended_path(tmpdir.resolve()),
                ignore_errors=True,
            )

    def test_prototype_main_menu_navigation_smoke_should_click_rpg_start_and_verify_visible_map(self) -> None:
        script = prototype_main_menu_navigation_smoke.SCRIPT_TEXT

        self.assertIn("StartButton", script)
        self.assertIn('start_button.emit_signal("pressed")', script)
        self.assertIn("rpg_map_scene_not_visible_after_start", script)
        self.assertIn("rpg_map_scene_has_no_visible_size_after_start", script)
        self.assertIn("RPG_START_ADVENTURE_MAP_VISIBLE PASS", script)
        self.assertIn('var map_grid = _find_node_by_name(map_scene, "Grid")', script)
        self.assertIn('var header_label = _find_node_by_name(current, "HeaderLabel")', script)
        self.assertIn('var stats_label = _find_node_by_name(current, "StatsLabel")', script)
        self.assertIn('var objective_label = _find_node_by_name(current, "ObjectiveLabel")', script)
        self.assertIn("has_legacy_map_markers", script)
        self.assertIn("has_current_rpg_markers", script)

    def test_prototype_main_menu_navigation_smoke_should_fail_when_godot_errors_exist(self) -> None:
        source = Path(prototype_main_menu_navigation_smoke.__file__).read_text(encoding="utf-8")

        self.assertIn("godot_error_markers", source)
        self.assertIn('"ERROR:"', source)
        self.assertIn('"Parse Error:"', source)
        self.assertIn("not has_godot_errors", source)
        self.assertIn('"godot_errors_detected": has_godot_errors', source)

    def test_prototype_main_menu_navigation_prewarm_timeout_defined_before_entrypoint(self) -> None:
        source = Path(prototype_main_menu_navigation_smoke.__file__).read_text(encoding="utf-8")

        self.assertLess(source.index("PREWARM_TIMEOUT_SEC = 120"), source.index('if __name__ == "__main__":'))
        self.assertEqual(120, prototype_main_menu_navigation_smoke.PREWARM_TIMEOUT_SEC)

    def test_godot_smoke_prewarm_should_use_independent_compile_timeout(self) -> None:
        smoke_headless = _load_module("smoke_headless_prewarm_cap_test_module", "scripts/python/smoke_headless.py")
        source = Path(smoke_headless.__file__).read_text(encoding="utf-8")
        navigation_source = Path(prototype_main_menu_navigation_smoke.__file__).read_text(encoding="utf-8")

        self.assertIn("prewarm_timeout = max(1, PREWARM_TIMEOUT_SEC)", source)
        self.assertIn("_prewarm_csharp(str(bin_path), project_root, timeout_sec)", source)
        self.assertIn("prewarm_timeout_sec = max(1, min(PREWARM_TIMEOUT_SEC, timeout_sec))", navigation_source)
        self.assertIn("prewarm_timeout_sec,", navigation_source)
        self.assertIn('["dotnet", "build", "GodotGame.csproj", "-c", "Debug", "-v", "minimal"]', source)
        self.assertIn('return True, "dotnet-build", dotnet_stdout, dotnet_stderr', source)
        self.assertIn('godot build-solutions prewarm timed out', source)

    def test_godot_smoke_prewarm_should_not_treat_failed_godot_build_as_success(self) -> None:
        smoke_headless = _load_module("smoke_headless_prewarm_failure_test_module", "scripts/python/smoke_headless.py")
        stdout = "Godot Engine\n[ DONE ] dotnet_build_project"
        stderr = "ERROR: Failed to create an autoload, script 'res://Game.Godot/Adapters/EventBusAdapter.cs' is not compiling."

        self.assertFalse(smoke_headless._build_output_has_success(stdout, stderr))
        self.assertTrue(smoke_headless._build_output_has_failure(stdout, stderr))

    def test_godot_smoke_prewarm_should_fail_on_scene_parse_errors_even_when_dotnet_fallback_passes(self) -> None:
        smoke_headless = _load_module("smoke_headless_parse_error_test_module", "scripts/python/smoke_headless.py")
        stdout = "Godot Engine\nBuild succeeded."
        stderr = "ERROR: res://Game.Godot/Examples/UI/ScorePanel.tscn:1 - Parse Error: Expected '['."

        self.assertTrue(smoke_headless._build_output_has_failure(stdout, stderr))

    def test_godot_smoke_runtime_should_fail_on_anchor_warning_with_backtrace(self) -> None:
        smoke_headless = _load_module("smoke_headless_runtime_warning_test_module", "scripts/python/smoke_headless.py")
        output = "WARNING: Nodes with non-equal opposite anchors will have their size overridden after _ready().\nC# backtrace"

        self.assertTrue(smoke_headless._has_runtime_failure(output))

    def test_navigation_smoke_should_fail_on_grab_focus_warning(self) -> None:
        output = "WARNING: This control can't grab focus. Use set_focus_mode().\nC# backtrace"

        self.assertTrue(prototype_main_menu_navigation_smoke._has_godot_errors(output))

    def test_godot_runners_should_create_logs_gdignore(self) -> None:
        smoke_headless = _load_module("smoke_headless_gdignore_test_module", "scripts/python/smoke_headless.py")
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            run_gdunit.ensure_runtime_logs_godot_ignored(str(root))
            smoke_headless._ensure_runtime_logs_godot_ignored(root)
            prototype_main_menu_navigation_smoke._ensure_runtime_logs_godot_ignored(root)

            self.assertTrue((root / "logs" / ".gdignore").exists())
            self.assertEqual("", (root / "logs" / ".gdignore").read_text(encoding="utf-8"))

    def test_run_gdunit_cleanup_should_ignore_taskkill_failures(self) -> None:
        with mock.patch.object(run_gdunit.subprocess, "run", side_effect=OSError("taskkill missing")):
            run_gdunit._cleanup_godot_processes(r"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe")

    def test_smoke_cleanup_should_ignore_taskkill_failures(self) -> None:
        smoke_headless = _load_module("smoke_headless_test_module", "scripts/python/smoke_headless.py")
        with mock.patch.object(smoke_headless.subprocess, "run", side_effect=OSError("taskkill missing")):
            smoke_headless._cleanup_godot_processes(r"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe")

    def test_smoke_prewarm_timeout_should_terminate_process_tree(self) -> None:
        smoke_headless = _load_module("smoke_headless_timeout_test_module", "scripts/python/smoke_headless.py")
        process = _TimedOutProcess(smoke_headless.subprocess)
        with mock.patch.object(smoke_headless.subprocess, "Popen", return_value=process), \
                mock.patch.object(smoke_headless, "_terminate_process_tree") as terminate:
            rc, stdout, stderr = smoke_headless._run_captured_process(["godot"], Path("."), 1)

        self.assertEqual(124, rc)
        self.assertIn("before timeout", stdout)
        self.assertIn("after timeout", stdout)
        self.assertIn("timeout error", stderr)
        terminate.assert_called_once_with(process)

    def test_navigation_prewarm_timeout_should_terminate_process_tree(self) -> None:
        process = _TimedOutProcess(prototype_main_menu_navigation_smoke.subprocess)
        with mock.patch.object(prototype_main_menu_navigation_smoke.subprocess, "Popen", return_value=process), \
                mock.patch.object(prototype_main_menu_navigation_smoke, "_terminate_process_tree") as terminate:
            rc, stdout, stderr = prototype_main_menu_navigation_smoke._run_captured_process(["godot"], Path("."), 1)

        self.assertEqual(124, rc)
        self.assertIn("before timeout", stdout)
        self.assertIn("after timeout", stdout)
        self.assertIn("timeout error", stderr)
        terminate.assert_called_once_with(process)


class _TimedOutProcess:
    def __init__(self, subprocess_module):
        self._subprocess = subprocess_module
        self.pid = 123
        self.returncode = None

    def communicate(self, timeout=None):
        if timeout is not None:
            raise self._subprocess.TimeoutExpired(
                cmd=["godot"],
                timeout=timeout,
                output="before timeout",
                stderr="timeout error",
            )
        return "after timeout", ""


if __name__ == "__main__":
    unittest.main()
