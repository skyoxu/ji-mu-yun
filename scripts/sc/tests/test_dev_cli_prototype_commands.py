#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
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


dev_cli = _load_module("dev_cli_prototype_module", "scripts/python/dev_cli.py")


class DevCliPrototypeCommandsTests(unittest.TestCase):
    def test_run_prototype_tdd_should_forward_arguments(self) -> None:
        with mock.patch.object(dev_cli, "run", return_value=0) as run_mock:
            rc = dev_cli.main(
                [
                    "run-prototype-tdd",
                    "--slug",
                    "hud-loop",
                    "--stage",
                    "red",
                    "--dotnet-target",
                    "Game.Core.Tests/Game.Core.Tests.csproj",
                    "--filter",
                    "HUDLoop",
                    "--scope-in",
                    "HUD tick loop",
                    "--success-criteria",
                    "A failing test proves the loop is not implemented yet.",
                    "--out-dir",
                    "logs/ci/demo/prototype-hud-loop",
                ]
            )

        self.assertEqual(0, rc)
        cmd = run_mock.call_args[0][0]
        self.assertEqual(["py", "-3", "scripts/python/run_prototype_tdd.py"], cmd[:3])
        self.assertIn("--slug", cmd)
        self.assertIn("hud-loop", cmd)
        self.assertIn("--stage", cmd)
        self.assertIn("red", cmd)
        self.assertIn("--dotnet-target", cmd)
        self.assertIn("Game.Core.Tests/Game.Core.Tests.csproj", cmd)
        self.assertIn("--filter", cmd)
        self.assertIn("HUDLoop", cmd)
        self.assertIn("--scope-in", cmd)
        self.assertIn("HUD tick loop", cmd)
        self.assertIn("--success-criteria", cmd)
        self.assertIn("A failing test proves the loop is not implemented yet.", cmd)
        self.assertIn("--out-dir", cmd)
        self.assertIn("logs/ci/demo/prototype-hud-loop", cmd)

    def test_create_prototype_scene_should_forward_arguments(self) -> None:
        with mock.patch.object(dev_cli, "run", return_value=0) as run_mock:
            rc = dev_cli.main(
                [
                    "create-prototype-scene",
                    "--slug",
                    "combat-loop",
                    "--scene-root",
                    "Node2D",
                    "--prototype-root",
                    "Game.Godot/Prototypes",
                    "--engine-backend",
                    "rapier_2d",
                    "--engine-apply-mode",
                    "confirm_apply",
                    "--engine-confidence",
                    "medium",
                    "--engine-reason",
                    "Prototype needs stronger 2D collision feel.",
                    "--engine-requires-plugin",
                    "true",
                    "--engine-install-target",
                    "project_local_addon",
                ]
            )

        self.assertEqual(0, rc)
        cmd = run_mock.call_args[0][0]
        self.assertEqual(["py", "-3", "scripts/python/create_prototype_scene.py"], cmd[:3])
        self.assertIn("--slug", cmd)
        self.assertIn("combat-loop", cmd)
        self.assertIn("--scene-root", cmd)
        self.assertIn("Node2D", cmd)
        self.assertIn("--prototype-root", cmd)
        self.assertIn("Game.Godot/Prototypes", cmd)
        self.assertIn("--engine-backend", cmd)
        self.assertIn("rapier_2d", cmd)
        self.assertIn("--engine-apply-mode", cmd)
        self.assertIn("confirm_apply", cmd)
        self.assertIn("--engine-confidence", cmd)
        self.assertIn("medium", cmd)
        self.assertIn("--engine-reason", cmd)
        self.assertIn("Prototype needs stronger 2D collision feel.", cmd)
        self.assertIn("--engine-requires-plugin", cmd)
        self.assertIn("true", cmd)
        self.assertIn("--engine-install-target", cmd)
        self.assertIn("project_local_addon", cmd)

    def test_run_prototype_workflow_should_forward_router_pause_arguments(self) -> None:
        with mock.patch.object(dev_cli, "run", return_value=0) as run_mock:
            rc = dev_cli.main(
                [
                    "run-prototype-workflow",
                    "--prototype-file",
                    "docs/prototypes/demo.md",
                    "--set",
                    "game_feature=gravity flip",
                    "--set",
                    "core_gameplay_loop=enter room, flip gravity, reach exit",
                    "--set",
                    "win_fail_conditions=win on exit, fail on spikes",
                    "--confirm",
                    "--resume-active",
                    "gravity-room",
                    "--godot-bin",
                    "C:/Godot/Godot.exe",
                    "--score-engine",
                    "hybrid",
                    "--stop-after-day",
                    "3",
                    "--self-check",
                ]
            )

        self.assertEqual(0, rc)
        cmd = run_mock.call_args[0][0]
        self.assertEqual(["py", "-3", "scripts/python/run_prototype_workflow.py"], cmd[:3])
        self.assertIn("--prototype-file", cmd)
        self.assertIn("docs/prototypes/demo.md", cmd)
        self.assertIn("--set", cmd)
        self.assertIn("game_feature=gravity flip", cmd)
        self.assertIn("core_gameplay_loop=enter room, flip gravity, reach exit", cmd)
        self.assertIn("win_fail_conditions=win on exit, fail on spikes", cmd)
        self.assertIn("--confirm", cmd)
        self.assertIn("--resume-active", cmd)
        self.assertIn("gravity-room", cmd)
        self.assertIn("--godot-bin", cmd)
        self.assertIn("C:/Godot/Godot.exe", cmd)
        self.assertIn("--score-engine", cmd)
        self.assertIn("hybrid", cmd)
        self.assertIn("--stop-after-day", cmd)
        self.assertIn("3", cmd)
        self.assertIn("--self-check", cmd)

    def test_generate_image_should_forward_aiartmirror_arguments(self) -> None:
        with mock.patch.object(dev_cli, "run", return_value=0) as run_mock:
            rc = dev_cli.main(
                [
                    "generate-image",
                    "--prompt",
                    "retro jrpg hero",
                    "--out",
                    "output/imagegen/hero.png",
                    "--manifest-out",
                    "output/imagegen/hero.json",
                    "--model",
                    "gpt-image-2",
                    "--group",
                    "gpt-image-2",
                    "--size",
                    "1024x1024",
                    "--quality",
                    "high",
                    "--dry-run",
                ]
            )

        self.assertEqual(0, rc)
        cmd = run_mock.call_args[0][0]
        self.assertEqual(["py", "-3", "scripts/python/aiartmirror_image_cli.py"], cmd[:3])
        self.assertIn("--prompt", cmd)
        self.assertIn("retro jrpg hero", cmd)
        self.assertIn("--out", cmd)
        self.assertIn("output/imagegen/hero.png", cmd)
        self.assertIn("--manifest-out", cmd)
        self.assertIn("output/imagegen/hero.json", cmd)
        self.assertIn("--model", cmd)
        self.assertIn("gpt-image-2", cmd)
        self.assertIn("--group", cmd)
        self.assertIn("gpt-image-2", cmd)
        self.assertIn("--dry-run", cmd)


if __name__ == "__main__":
    unittest.main()
