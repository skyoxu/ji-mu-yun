#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


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


prototype_scene = _load_module("prototype_scene_module", "scripts/python/create_prototype_scene.py")


class CreatePrototypeSceneTests(unittest.TestCase):
    def test_should_create_scene_and_script_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rc = prototype_scene.main(
                [
                    "--repo-root",
                    str(root),
                    "--slug",
                    "combat-loop",
                ]
            )

            self.assertEqual(0, rc)
            scene_path = root / "Game.Godot" / "Prototypes" / "combat-loop" / "CombatLoopPrototype.tscn"
            script_path = root / "Game.Godot" / "Prototypes" / "combat-loop" / "Scripts" / "CombatLoopPrototype.cs"
            components_dir = root / "Game.Godot" / "Prototypes" / "combat-loop" / "Scripts" / "Components"
            systems_dir = root / "Game.Godot" / "Prototypes" / "combat-loop" / "Scripts" / "Systems"
            data_dir = root / "Game.Godot" / "Prototypes" / "combat-loop" / "Scripts" / "Data"
            hud_view_path = components_dir / "HudView.cs"
            map_view_path = components_dir / "MapView.cs"
            battle_view_path = components_dir / "BattleView.cs"
            reward_view_path = components_dir / "RewardView.cs"
            log_view_path = components_dir / "LogView.cs"
            state_path = data_dir / "CombatLoopPrototypeState.cs"
            system_path = systems_dir / "CombatLoopPrototypeSystem.cs"
            assets_dir = root / "Game.Godot" / "Prototypes" / "combat-loop" / "Assets"
            dotnet_test_path = root / "Game.Core.Tests" / "Prototypes" / "CombatLoopPrototypeLoopTests.cs"
            gdunit_test_path = root / "Tests.Godot" / "tests" / "Prototype" / "CombatLoopPrototype" / "test_combat_loop_prototype_scene.gd"

            self.assertTrue(scene_path.exists())
            self.assertTrue(script_path.exists())
            self.assertTrue(components_dir.is_dir())
            self.assertTrue(systems_dir.is_dir())
            self.assertTrue(data_dir.is_dir())
            self.assertTrue(hud_view_path.exists())
            self.assertTrue(map_view_path.exists())
            self.assertTrue(battle_view_path.exists())
            self.assertTrue(reward_view_path.exists())
            self.assertTrue(log_view_path.exists())
            self.assertTrue(state_path.exists())
            self.assertTrue(system_path.exists())
            self.assertTrue(assets_dir.is_dir())
            self.assertTrue(dotnet_test_path.exists())
            self.assertTrue(gdunit_test_path.exists())

            scene_text = scene_path.read_text(encoding="utf-8")
            script_text = script_path.read_text(encoding="utf-8")
            hud_view_text = hud_view_path.read_text(encoding="utf-8")
            system_text = system_path.read_text(encoding="utf-8")
            dotnet_test_text = dotnet_test_path.read_text(encoding="utf-8")
            gdunit_test_text = gdunit_test_path.read_text(encoding="utf-8")
            self.assertIn('type="Control"', scene_text)
            self.assertIn('res://Game.Godot/Prototypes/combat-loop/Scripts/CombatLoopPrototype.cs', scene_text)
            self.assertIn('res://Game.Godot/Prototypes/combat-loop/Scripts/Components/HudView.cs', scene_text)
            self.assertIn('[node name="HudView" type="Node" parent="."]', scene_text)
            self.assertIn("public partial class CombatLoopPrototype : global::Godot.Control", script_text)
            self.assertIn("global::Godot.GD.Print", script_text)
            self.assertIn("private readonly CombatLoopPrototypeSystem _system = new();", script_text)
            self.assertIn('private CombatLoopPrototypeState _state = new("boot", "Booting", "Waiting for prototype setup.");', script_text)
            self.assertIn('var hudView = GetNodeOrNull<HudView>("HudView");', script_text)
            self.assertIn("hudView?.RenderStatus(_state.StatusText, _state.HintText);", script_text)
            self.assertIn("namespace Game.Godot.Prototypes.Components;", hud_view_text)
            self.assertIn("public partial class HudView : global::Godot.Node", hud_view_text)
            self.assertIn("public void RenderStatus(string statusText, string hintText)", hud_view_text)
            self.assertIn("public string LastStatus => _lastStatus;", hud_view_text)
            self.assertIn("namespace Game.Godot.Prototypes.Systems;", system_text)
            self.assertIn("using Game.Godot.Prototypes.Data;", system_text)
            self.assertIn("public sealed class CombatLoopPrototypeSystem", system_text)
            self.assertIn("CombatLoopPrototypeLoopTests", dotnet_test_text)
            self.assertIn("CombatLoopPrototypeLoop", dotnet_test_text)
            self.assertIn('preload("res://Game.Godot/Prototypes/combat-loop/CombatLoopPrototype.tscn")', gdunit_test_text)
            self.assertIn('scene.get_node_or_null("PrototypeHint")', gdunit_test_text)
            self.assertTrue(gdunit_test_path.parent.is_dir())

    def test_should_fail_when_scene_exists_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = prototype_scene.main(
                [
                    "--repo-root",
                    str(root),
                    "--slug",
                    "combat-loop",
                ]
            )
            second = prototype_scene.main(
                [
                    "--repo-root",
                    str(root),
                    "--slug",
                    "combat-loop",
                ]
            )

            self.assertEqual(0, first)
            self.assertEqual(1, second)

    def test_should_create_node2d_scaffold_with_prototype_loop_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rc = prototype_scene.main(
                [
                    "--repo-root",
                    str(root),
                    "--slug",
                    "field-loop",
                    "--scene-root",
                    "Node2D",
                ]
            )

            self.assertEqual(0, rc)
            scene_path = root / "Game.Godot" / "Prototypes" / "field-loop" / "FieldLoopPrototype.tscn"
            script_path = root / "Game.Godot" / "Prototypes" / "field-loop" / "Scripts" / "FieldLoopPrototype.cs"
            hud_view_path = root / "Game.Godot" / "Prototypes" / "field-loop" / "Scripts" / "Components" / "HudView.cs"
            gdunit_test_path = root / "Tests.Godot" / "tests" / "Prototype" / "FieldLoopPrototype" / "test_field_loop_prototype_scene.gd"

            scene_text = scene_path.read_text(encoding="utf-8")
            script_text = script_path.read_text(encoding="utf-8")
            hud_view_text = hud_view_path.read_text(encoding="utf-8")
            gdunit_test_text = gdunit_test_path.read_text(encoding="utf-8")

            self.assertIn('type="Node2D"', scene_text)
            self.assertIn('[node name="HudView" type="Node" parent="."]', scene_text)
            self.assertIn('[node name="PrototypeLoop" type="Node2D" parent="."]', scene_text)
            self.assertIn("public partial class FieldLoopPrototype : global::Godot.Node2D", script_text)
            self.assertIn("private readonly FieldLoopPrototypeSystem _system = new();", script_text)
            self.assertIn('var hudView = GetNodeOrNull<HudView>("HudView");', script_text)
            self.assertIn("public void RenderStatus(string statusText, string hintText)", hud_view_text)
            self.assertIn('scene.get_node_or_null("PrototypeLoop")', gdunit_test_text)

    @unittest.skipUnless(os.name == "nt", "Windows long-path regression only")
    def test_should_write_gdunit_test_under_long_workspace_path(self) -> None:
        base = Path(tempfile.mkdtemp())
        try:
            long_root = base
            while len(str(long_root / "Tests.Godot" / "tests" / "Prototype" / "PhaseARealE2eLoopPrototype" / "test_phase_a_real_e2e_loop_prototype_scene.gd")) <= 265:
                long_root = long_root / "deepsegment"

            rc = prototype_scene.main(
                [
                    "--repo-root",
                    str(long_root),
                    "--slug",
                    "phase-a-real-e2e-loop",
                ]
            )

            self.assertEqual(0, rc)
            gdunit_test_path = (
                long_root
                / "Tests.Godot"
                / "tests"
                / "Prototype"
                / "PhaseARealE2eLoopPrototype"
                / "test_phase_a_real_e2e_loop_prototype_scene.gd"
            )
            self.assertTrue(len(str(gdunit_test_path)) > 260)
            self.assertTrue(os.path.exists(prototype_scene.to_windows_extended_path(gdunit_test_path.resolve())))
        finally:
            shutil.rmtree(prototype_scene.to_windows_extended_path(base.resolve()), ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
