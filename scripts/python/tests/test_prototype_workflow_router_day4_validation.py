#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.python.tests.prototype_workflow_router_test_support import load_module, rpg_battle_scene_contract_nodes, rpg_battle_script_contract_bindings

class PrototypeWorkflowRouterDay4ValidationTests(unittest.TestCase):
    def test_validate_day4_outputs_should_fail_when_scaffold_or_core_files_are_missing(self) -> None:
        module = load_module("prototype_workflow_router_day4_validation_fail", "scripts/python/run_prototype_workflow.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            scene_path = root / "Game.Godot" / "Prototypes" / "dq-rpg" / "DqRpgPrototype.tscn"
            script_path = root / "Game.Godot" / "Prototypes" / "dq-rpg" / "Scripts" / "DqRpgPrototype.cs"
            scene_path.parent.mkdir(parents=True, exist_ok=True)
            script_path.parent.mkdir(parents=True, exist_ok=True)
            scene_path.write_text("[gd_scene format=3]\n[node name=\"DqRpgPrototype\" type=\"Node2D\"]\n", encoding="utf-8")
            script_path.write_text(
                "using Godot;\n\npublic partial class DqRpgPrototype : Node2D\n{\n    public override void _Ready()\n    {\n        GD.Print(\"Prototype scaffold ready: replace this scene with the minimum playable loop.\");\n    }\n}\n",
                encoding="utf-8",
            )

            ok, issues = module._validate_day4_implementation_outputs(root=root, payload={"slug": "dq-rpg"})

        self.assertFalse(ok)
        self.assertTrue(any("missing_files=" in issue for issue in issues))
        self.assertIn("missing_prototype_loop_node=Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn", issues)
        self.assertIn("scaffold_script_not_replaced=Game.Godot/Prototypes/dq-rpg/Scripts/DqRpgPrototype.cs", issues)

    def test_validate_day4_outputs_should_fail_when_scene_ext_resource_is_missing(self) -> None:
        module = load_module("prototype_workflow_router_day4_missing_ext_resource", "scripts/python/run_prototype_workflow.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            slug = "mirgame1"
            class_name = "Mirgame1Prototype"
            (root / "Game.Godot" / "Prototypes" / slug / "Scripts").mkdir(parents=True, exist_ok=True)
            (root / "Game.Core" / "Prototypes").mkdir(parents=True, exist_ok=True)
            (root / "Game.Core.Tests" / "Prototypes").mkdir(parents=True, exist_ok=True)
            (root / "Tests.Godot" / "tests" / "Prototype" / class_name).mkdir(parents=True, exist_ok=True)
            (root / "Game.Godot" / "Prototypes" / slug / f"{class_name}.tscn").write_text(
                "[gd_scene load_steps=3 format=3]\n"
                f'[ext_resource type="Script" path="res://Game.Godot/Prototypes/{slug}/Scripts/{class_name}.cs" id="1"]\n'
                f'[ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/{slug}/Assets/{slug}_map.png" id="2"]\n'
                f'[node name="{class_name}" type="Node2D"]\n'
                'script = ExtResource("1")\n'
                '[node name="PrototypeLoop" type="Node2D" parent="."]\n',
                encoding="utf-8",
            )
            (root / "Game.Godot" / "Prototypes" / slug / "Scripts" / f"{class_name}.cs").write_text(
                "using Godot;\n\npublic partial class Mirgame1Prototype : Node2D\n{\n    private void AdvanceLoop() { }\n}\n",
                encoding="utf-8",
            )
            (root / "Game.Core" / "Prototypes" / f"{class_name}Loop.cs").write_text(
                "namespace Game.Core.Prototypes;\npublic sealed class Mirgame1PrototypeLoop { public string DescribePlayableLoop() => \"ok\"; }\n",
                encoding="utf-8",
            )
            (root / "Game.Core.Tests" / "Prototypes" / f"{class_name}LoopTests.cs").write_text("test\n", encoding="utf-8")
            (root / "Tests.Godot" / "tests" / "Prototype" / class_name / "test_mirgame1_prototype_scene.gd").write_text(
                f'var scene := preload("res://Game.Godot/Prototypes/{slug}/{class_name}.tscn").instantiate()\n',
                encoding="utf-8",
            )

            ok, issues = module._validate_day4_implementation_outputs(root=root, payload={"slug": slug})

        self.assertFalse(ok)
        self.assertIn(
            f"missing_scene_ext_resources=Game.Godot/Prototypes/{slug}/{class_name}.tscn->res://Game.Godot/Prototypes/{slug}/Assets/{slug}_map.png",
            issues,
        )

    def test_validate_day4_outputs_should_pass_when_project_specific_files_are_ready(self) -> None:
        module = load_module("prototype_workflow_router_day4_validation_ok", "scripts/python/run_prototype_workflow.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            class_name = "DqRpgPrototype"
            (root / "Game.Godot" / "Prototypes" / "dq-rpg" / "Scripts").mkdir(parents=True, exist_ok=True)
            (root / "Game.Core" / "Prototypes").mkdir(parents=True, exist_ok=True)
            (root / "Game.Core.Tests" / "Prototypes").mkdir(parents=True, exist_ok=True)
            (root / "Tests.Godot" / "tests" / "Prototype" / class_name).mkdir(parents=True, exist_ok=True)
            (root / "Game.Godot" / "Prototypes" / "dq-rpg" / f"{class_name}.tscn").write_text(
                "[gd_scene format=3]\n"
                "[node name=\"DqRpgPrototype\" type=\"Node2D\"]\n"
                "[node name=\"PrototypeLoop\" type=\"Node2D\" parent=\".\"]\n"
                "[node name=\"CanvasLayer\" type=\"CanvasLayer\" parent=\".\"]\n"
                "[node name=\"UI\" type=\"Control\" parent=\"CanvasLayer\"]\n"
                "[node name=\"StartButton\" type=\"Button\" parent=\"CanvasLayer/UI\"]\n"
                "text = \"Start Adventure\"\n"
                "[node name=\"MapScene\" type=\"Control\" parent=\"CanvasLayer/UI\"]\n"
                "[node name=\"Title\" type=\"Label\" parent=\"CanvasLayer/UI/MapScene\"]\n"
                "[node name=\"RpgMapAsset\" type=\"ColorRect\" parent=\"CanvasLayer/UI/MapScene\"]\n"
                "[node name=\"Grid\" type=\"GridContainer\" parent=\"CanvasLayer/UI/MapScene\"]\n"
                "[node name=\"StatusLabel\" type=\"Label\" parent=\"CanvasLayer/UI/MapScene\"]\n"
                "[node name=\"RpgPlayerAsset\" type=\"ColorRect\" parent=\"CanvasLayer/UI/MapScene\"]\n"
                "[node name=\"RpgEnemyAsset\" type=\"ColorRect\" parent=\"CanvasLayer/UI/MapScene\"]\n"
                "[node name=\"BattleScene\" type=\"Control\" parent=\"CanvasLayer/UI\"]\n"
                + rpg_battle_scene_contract_nodes(),
                encoding="utf-8",
            )
            (root / "Game.Godot" / "Prototypes" / "dq-rpg" / "Scripts" / f"{class_name}.cs").write_text(
                "using Godot;\n\npublic partial class DqRpgPrototype : Node2D\n{\n    private Button? _retryButton;\n    private string _rewardText = \"reward\";\n    private void BindNodes() { GetNode<Control>(\"CanvasLayer/UI/MapScene\"); GetNode<Control>(\"CanvasLayer/UI/BattleScene\"); GetNode<Label>(\"CanvasLayer/UI/MapScene/Title\"); GetNode<Label>(\"CanvasLayer/UI/MapScene/StatusLabel\"); GetNode<Button>(\"CanvasLayer/UI/StartPanel/StartVBox/StartButton\").Text = \"Start Adventure\"; GetNode<ColorRect>(\"CanvasLayer/UI/MapScene/RpgMapAsset\"); GetNode<ColorRect>(\"CanvasLayer/UI/MapScene/RpgPlayerAsset\"); GetNode<ColorRect>(\"CanvasLayer/UI/MapScene/RpgEnemyAsset\"); "
                    + rpg_battle_script_contract_bindings()
                    + "}\n    private void ReadMovementInput() { }\n    private void StartEncounter() { }\n    private void Attack() { }\n    private void Restart() { }\n}\n",
                encoding="utf-8",
            )
            (root / "Game.Core" / "Prototypes" / f"{class_name}Loop.cs").write_text(
                "namespace Game.Core.Prototypes;\npublic sealed class DqRpgPrototypeLoop { public int WinBattleTarget => 15; public string[] RewardOptions => []; public string DescribePlayableLoop() => \"ok\"; }\n",
                encoding="utf-8",
            )
            (root / "Game.Core.Tests" / "Prototypes" / f"{class_name}LoopTests.cs").write_text(
                "MoveOnMap(); StartEncounter(); ResolveAttackTurn(); ApplyReward(); state.BattlesWon.ToString(); state.RewardOptions.Count.ToString(); state.StatusText.ToString();\n",
                encoding="utf-8",
            )
            (root / "Tests.Godot" / "tests" / "Prototype" / class_name / "test_dq_rpg_prototype_scene.gd").write_text(
                'var scene := preload("res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn").instantiate()\nassert_object(scene.get_node_or_null("PrototypeLoop")).is_not_null()\n',
                encoding="utf-8",
            )

            ok, issues = module._validate_day4_implementation_outputs(root=root, payload={"slug": "dq-rpg"})

        self.assertTrue(ok)
        self.assertEqual([], issues)

    def test_validate_day4_outputs_should_fail_when_rpg_map_visible_markers_are_missing(self) -> None:
        module = load_module("prototype_workflow_router_day4_validation_missing_rpg_markers", "scripts/python/run_prototype_workflow.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            class_name = "DqRpgPrototype"
            (root / "Game.Godot" / "Prototypes" / "dq-rpg" / "Scripts").mkdir(parents=True, exist_ok=True)
            (root / "Game.Core" / "Prototypes").mkdir(parents=True, exist_ok=True)
            (root / "Game.Core.Tests" / "Prototypes").mkdir(parents=True, exist_ok=True)
            (root / "Tests.Godot" / "tests" / "Prototype" / class_name).mkdir(parents=True, exist_ok=True)
            (root / "Game.Godot" / "Prototypes" / "dq-rpg" / f"{class_name}.tscn").write_text(
                "[gd_scene format=3]\n"
                "[node name=\"DqRpgPrototype\" type=\"Node2D\"]\n"
                "[node name=\"PrototypeLoop\" type=\"Node2D\" parent=\".\"]\n"
                "[node name=\"CanvasLayer\" type=\"CanvasLayer\" parent=\".\"]\n"
                "[node name=\"UI\" type=\"Control\" parent=\"CanvasLayer\"]\n"
                "[node name=\"StartButton\" type=\"Button\" parent=\"CanvasLayer/UI\"]\n"
                "text = \"Start Adventure\"\n"
                "[node name=\"MapScene\" type=\"Control\" parent=\"CanvasLayer/UI\"]\n"
                "[node name=\"RpgMapAsset\" type=\"ColorRect\" parent=\"CanvasLayer/UI/MapScene\"]\n"
                "[node name=\"RpgPlayerAsset\" type=\"ColorRect\" parent=\"CanvasLayer/UI/MapScene\"]\n"
                "[node name=\"RpgEnemyAsset\" type=\"ColorRect\" parent=\"CanvasLayer/UI/MapScene\"]\n"
                "[node name=\"BattleScene\" type=\"Control\" parent=\"CanvasLayer/UI\"]\n"
                + rpg_battle_scene_contract_nodes(),
                encoding="utf-8",
            )
            (root / "Game.Godot" / "Prototypes" / "dq-rpg" / "Scripts" / f"{class_name}.cs").write_text(
                "using Godot;\n\npublic partial class DqRpgPrototype : Node2D\n{\n    private Button? _retryButton;\n    private string _rewardText = \"reward\";\n    private void BindNodes() { GetNode<Control>(\"CanvasLayer/UI/MapScene\"); GetNode<Control>(\"CanvasLayer/UI/BattleScene\"); GetNode<Button>(\"CanvasLayer/UI/StartPanel/StartVBox/StartButton\").Text = \"Start Adventure\"; GetNode<ColorRect>(\"CanvasLayer/UI/MapScene/RpgMapAsset\"); GetNode<ColorRect>(\"CanvasLayer/UI/MapScene/RpgPlayerAsset\"); GetNode<ColorRect>(\"CanvasLayer/UI/MapScene/RpgEnemyAsset\"); "
                    + rpg_battle_script_contract_bindings()
                    + "}\n    private void ReadMovementInput() { }\n    private void StartEncounter() { }\n    private void Attack() { }\n    private void Restart() { }\n}\n",
                encoding="utf-8",
            )
            (root / "Game.Core" / "Prototypes" / f"{class_name}Loop.cs").write_text(
                "namespace Game.Core.Prototypes;\npublic sealed class DqRpgPrototypeLoop { public int WinBattleTarget => 15; public string[] RewardOptions => []; public string DescribePlayableLoop() => \"ok\"; }\n",
                encoding="utf-8",
            )
            (root / "Game.Core.Tests" / "Prototypes" / f"{class_name}LoopTests.cs").write_text(
                "MoveOnMap(); StartEncounter(); ResolveAttackTurn(); ApplyReward(); state.BattlesWon.ToString(); state.RewardOptions.Count.ToString(); state.StatusText.ToString();\n",
                encoding="utf-8",
            )
            (root / "Tests.Godot" / "tests" / "Prototype" / class_name / "test_dq_rpg_prototype_scene.gd").write_text(
                'var scene := preload("res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn").instantiate()\nassert_object(scene.get_node_or_null("PrototypeLoop")).is_not_null()\n',
                encoding="utf-8",
            )

            ok, issues = module._validate_day4_implementation_outputs(root=root, payload={"slug": "dq-rpg"})

        self.assertFalse(ok)
        self.assertIn("rpg_scene_node_contract_drift=Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn", issues)
        self.assertIn("rpg_script_node_contract_drift=Game.Godot/Prototypes/dq-rpg/Scripts/DqRpgPrototype.cs", issues)

    def test_validate_day4_outputs_should_fail_when_rpg_test_contract_drifts(self) -> None:
        module = load_module("prototype_workflow_router_day4_validation_contract_drift", "scripts/python/run_prototype_workflow.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            class_name = "DqRpgPrototype"
            (root / "Game.Godot" / "Prototypes" / "dq-rpg" / "Scripts").mkdir(parents=True, exist_ok=True)
            (root / "Game.Core" / "Prototypes").mkdir(parents=True, exist_ok=True)
            (root / "Game.Core.Tests" / "Prototypes").mkdir(parents=True, exist_ok=True)
            (root / "Tests.Godot" / "tests" / "Prototype" / class_name).mkdir(parents=True, exist_ok=True)
            (root / "Game.Godot" / "Prototypes" / "dq-rpg" / f"{class_name}.tscn").write_text(
                "[gd_scene format=3]\n[node name=\"DqRpgPrototype\" type=\"Node2D\"]\n[node name=\"PrototypeLoop\" type=\"Node2D\" parent=\".\"]\n",
                encoding="utf-8",
            )
            (root / "Game.Godot" / "Prototypes" / "dq-rpg" / "Scripts" / f"{class_name}.cs").write_text(
                "using Godot;\n\npublic partial class DqRpgPrototype : Node2D\n{\n    private Button? _retryButton;\n    private string _rewardText = \"reward\";\n    private void ReadMovementInput() { }\n    private void StartEncounter() { }\n    private void Attack() { }\n    private void Restart() { }\n}\n",
                encoding="utf-8",
            )
            (root / "Game.Core" / "Prototypes" / f"{class_name}Loop.cs").write_text(
                "namespace Game.Core.Prototypes;\npublic sealed class DqRpgPrototypeLoop { public int WinBattleTarget => 15; public string[] RewardOptions => []; public string DescribePlayableLoop() => \"ok\"; }\n",
                encoding="utf-8",
            )
            (root / "Game.Core.Tests" / "Prototypes" / f"{class_name}LoopTests.cs").write_text(
                "ResolvePlayerAttack(); RetryFromMap(); state.CanRetry.ToString(); state.MaxHp.ToString(); state.Victories.ToString(); state.Defense.ToString();\n",
                encoding="utf-8",
            )
            (root / "Tests.Godot" / "tests" / "Prototype" / class_name / "test_dq_rpg_prototype_scene.gd").write_text(
                'var scene := preload("res://Game.Godot/Prototypes/DefaultRpgTemplate/DefaultRpgPrototype.tscn").instantiate()\n',
                encoding="utf-8",
            )

            ok, issues = module._validate_day4_implementation_outputs(root=root, payload={"slug": "dq-rpg"})

        self.assertFalse(ok)
        self.assertIn("rpg_dotnet_test_contract_drift=Game.Core.Tests/Prototypes/DqRpgPrototypeLoopTests.cs", issues)
        self.assertIn("rpg_gdunit_test_contract_drift=Tests.Godot/tests/Prototype/DqRpgPrototype/test_dq_rpg_prototype_scene.gd", issues)

    def test_validate_day4_outputs_should_fail_when_component_slots_exist_but_root_does_not_use_them(self) -> None:
        module = load_module("prototype_workflow_router_component_slots_not_wired", "scripts/python/run_prototype_workflow.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            slug = "combat-loop"
            class_name = "CombatLoopPrototype"
            (root / "Game.Godot" / "Prototypes" / slug / "Scripts" / "Components").mkdir(parents=True, exist_ok=True)
            (root / "Game.Godot" / "Prototypes" / slug / "Scripts" / "Systems").mkdir(parents=True, exist_ok=True)
            (root / "Game.Godot" / "Prototypes" / slug / "Scripts" / "Data").mkdir(parents=True, exist_ok=True)
            (root / "Game.Core" / "Prototypes").mkdir(parents=True, exist_ok=True)
            (root / "Game.Core.Tests" / "Prototypes").mkdir(parents=True, exist_ok=True)
            (root / "Tests.Godot" / "tests" / "Prototype" / class_name).mkdir(parents=True, exist_ok=True)
            (root / "Game.Godot" / "Prototypes" / slug / f"{class_name}.tscn").write_text(
                "[gd_scene load_steps=3 format=3]\n"
                f'[ext_resource type="Script" path="res://Game.Godot/Prototypes/{slug}/Scripts/{class_name}.cs" id="1"]\n'
                f'[ext_resource type="Script" path="res://Game.Godot/Prototypes/{slug}/Scripts/Components/HudView.cs" id="2"]\n'
                f'[node name="{class_name}" type="Node2D"]\n'
                'script = ExtResource("1")\n'
                '[node name="HudView" type="Node" parent="."]\n'
                'script = ExtResource("2")\n'
                '[node name="PrototypeLoop" type="Node2D" parent="."]\n',
                encoding="utf-8",
            )
            (root / "Game.Godot" / "Prototypes" / slug / "Scripts" / f"{class_name}.cs").write_text(
                "using Game.Godot.Prototypes.Components;\n\nnamespace Game.Godot.Prototypes;\n\npublic partial class CombatLoopPrototype : global::Godot.Node2D\n{\n    public override void _Ready()\n    {\n        global::Godot.GD.Print(\"ready\");\n    }\n}\n",
                encoding="utf-8",
            )
            (root / "Game.Godot" / "Prototypes" / slug / "Scripts" / "Components" / "HudView.cs").write_text(
                "namespace Game.Godot.Prototypes.Components;\n\npublic partial class HudView : global::Godot.Node\n{\n    public void RenderStatus(string statusText, string hintText) { }\n}\n",
                encoding="utf-8",
            )
            (root / "Game.Godot" / "Prototypes" / slug / "Scripts" / "Systems" / f"{class_name}System.cs").write_text(
                "namespace Game.Godot.Prototypes.Systems;\n\npublic sealed class CombatLoopPrototypeSystem { }\n",
                encoding="utf-8",
            )
            (root / "Game.Godot" / "Prototypes" / slug / "Scripts" / "Data" / f"{class_name}State.cs").write_text(
                "namespace Game.Godot.Prototypes.Data;\n\npublic sealed record CombatLoopPrototypeState(string Phase, string StatusText, string HintText);\n",
                encoding="utf-8",
            )
            (root / "Game.Core" / "Prototypes" / f"{class_name}Loop.cs").write_text(
                "namespace Game.Core.Prototypes;\npublic sealed class CombatLoopPrototypeLoop { public string DescribePlayableLoop() => \"ok\"; }\n",
                encoding="utf-8",
            )
            (root / "Game.Core.Tests" / "Prototypes" / f"{class_name}LoopTests.cs").write_text("test\n", encoding="utf-8")
            (root / "Tests.Godot" / "tests" / "Prototype" / class_name / "test_combat_loop_prototype_scene.gd").write_text(
                'var scene := preload("res://Game.Godot/Prototypes/combat-loop/CombatLoopPrototype.tscn").instantiate()\n',
                encoding="utf-8",
            )

            ok, issues = module._validate_day4_implementation_outputs(root=root, payload={"slug": slug})

        self.assertFalse(ok)
        self.assertIn("component_slots_not_wired=Game.Godot/Prototypes/combat-loop/Scripts/CombatLoopPrototype.cs", issues)

    def test_validate_day4_outputs_should_support_long_windows_paths(self) -> None:
        module = load_module("prototype_workflow_router_day4_validation_long_path", "scripts/python/run_prototype_workflow.py")
        td = tempfile.mkdtemp()
        try:
            root = Path(td)
            for index in range(8):
                root = root / f"nested-segment-{index:02d}" / ("x" * 18)
            class_name = "DqRpgPrototype"
            module.write_text(
                root / "Game.Godot" / "Prototypes" / "dq-rpg" / f"{class_name}.tscn",
                "[gd_scene format=3]\n"
                "[node name=\"DqRpgPrototype\" type=\"Node2D\"]\n"
                "[node name=\"PrototypeLoop\" type=\"Node2D\" parent=\".\"]\n"
                "[node name=\"CanvasLayer\" type=\"CanvasLayer\" parent=\".\"]\n"
                "[node name=\"UI\" type=\"Control\" parent=\"CanvasLayer\"]\n"
                "[node name=\"StartButton\" type=\"Button\" parent=\"CanvasLayer/UI\"]\n"
                "text = \"Start Adventure\"\n"
                "[node name=\"MapScene\" type=\"Control\" parent=\"CanvasLayer/UI\"]\n"
                "[node name=\"Title\" type=\"Label\" parent=\"CanvasLayer/UI/MapScene\"]\n"
                "[node name=\"RpgMapAsset\" type=\"ColorRect\" parent=\"CanvasLayer/UI/MapScene\"]\n"
                "[node name=\"Grid\" type=\"GridContainer\" parent=\"CanvasLayer/UI/MapScene\"]\n"
                "[node name=\"StatusLabel\" type=\"Label\" parent=\"CanvasLayer/UI/MapScene\"]\n"
                "[node name=\"RpgPlayerAsset\" type=\"ColorRect\" parent=\"CanvasLayer/UI/MapScene\"]\n"
                "[node name=\"RpgEnemyAsset\" type=\"ColorRect\" parent=\"CanvasLayer/UI/MapScene\"]\n"
                "[node name=\"BattleScene\" type=\"Control\" parent=\"CanvasLayer/UI\"]\n"
                + rpg_battle_scene_contract_nodes(),
            )
            module.write_text(
                root / "Game.Godot" / "Prototypes" / "dq-rpg" / "Scripts" / f"{class_name}.cs",
                "using Godot;\n\nnamespace Game.Godot.Prototypes;\n\npublic partial class DqRpgPrototype : Node2D\n{\n    private Button? _retryButton;\n    private string _rewardText = \"reward\";\n    private void BindNodes() { GetNode<Control>(\"CanvasLayer/UI/MapScene\"); GetNode<Control>(\"CanvasLayer/UI/BattleScene\"); GetNode<Label>(\"CanvasLayer/UI/MapScene/Title\"); GetNode<Label>(\"CanvasLayer/UI/MapScene/StatusLabel\"); GetNode<Button>(\"CanvasLayer/UI/StartPanel/StartVBox/StartButton\").Text = \"Start Adventure\"; GetNode<ColorRect>(\"CanvasLayer/UI/MapScene/RpgMapAsset\"); GetNode<ColorRect>(\"CanvasLayer/UI/MapScene/RpgPlayerAsset\"); GetNode<ColorRect>(\"CanvasLayer/UI/MapScene/RpgEnemyAsset\"); "
                    + rpg_battle_script_contract_bindings()
                    + "}\n    private void ReadMovementInput() { }\n    private void StartEncounter() { }\n    private void Attack() { }\n    private void Restart() { }\n}\n",
            )
            module.write_text(
                root / "Game.Core" / "Prototypes" / f"{class_name}Loop.cs",
                "namespace Game.Core.Prototypes;\npublic sealed class DqRpgPrototypeLoop { public int WinBattleTarget => 15; public string[] RewardOptions => []; public string DescribePlayableLoop() => \"ok\"; }\n",
            )
            module.write_text(
                root / "Game.Core.Tests" / "Prototypes" / f"{class_name}LoopTests.cs",
                "MoveOnMap(); StartEncounter(); ResolveAttackTurn(); ApplyReward(); state.BattlesWon.ToString(); state.RewardOptions.Count.ToString(); state.StatusText.ToString();\n",
            )
            module.write_text(
                root / "Tests.Godot" / "tests" / "Prototype" / class_name / "test_dq_rpg_prototype_scene.gd",
                'var scene := preload("res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn").instantiate()\nassert_object(scene.get_node_or_null("PrototypeLoop")).is_not_null()\n',
            )

            ok, issues = module._validate_day4_implementation_outputs(root=root, payload={"slug": "dq-rpg"})
            long_path = root / "Tests.Godot" / "tests" / "Prototype" / class_name / "test_dq_rpg_prototype_scene.gd"
        finally:
            shutil.rmtree(module.to_windows_extended_path(Path(td).resolve()), ignore_errors=False)

        self.assertTrue(len(str(long_path)) > 260)
        self.assertTrue(ok)
        self.assertEqual([], issues)

    def test_rpg_project_specific_fallback_should_copy_repo_baseline_for_dq_rpg(self) -> None:
        module = load_module("prototype_workflow_router_dq_rpg_baseline_fallback", "scripts/python/run_prototype_workflow.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            expected_scene = Path("Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn").read_text(encoding="utf-8")
            expected_script = Path("Game.Godot/Prototypes/dq-rpg/Scripts/DqRpgPrototype.cs").read_text(encoding="utf-8")
            expected_core = Path("Game.Core/Prototypes/DqRpgPrototypeLoop.cs").read_text(encoding="utf-8")
            expected_dotnet_test = Path("Game.Core.Tests/Prototypes/DqRpgPrototypeLoopTests.cs").read_text(encoding="utf-8")
            expected_gdunit_test = Path("Tests.Godot/tests/Prototype/DqRpgPrototype/test_dq_rpg_prototype_scene.gd").read_text(encoding="utf-8")

            module._write_rpg_project_specific_fallback(root=root, payload={"slug": "dq-rpg"})

            scene_text = (root / "Game.Godot" / "Prototypes" / "dq-rpg" / "DqRpgPrototype.tscn").read_text(encoding="utf-8")
            script_text = (root / "Game.Godot" / "Prototypes" / "dq-rpg" / "Scripts" / "DqRpgPrototype.cs").read_text(encoding="utf-8")
            core_text = (root / "Game.Core" / "Prototypes" / "DqRpgPrototypeLoop.cs").read_text(encoding="utf-8")
            dotnet_test_text = (root / "Game.Core.Tests" / "Prototypes" / "DqRpgPrototypeLoopTests.cs").read_text(encoding="utf-8")
            gdunit_test_text = (root / "Tests.Godot" / "tests" / "Prototype" / "DqRpgPrototype" / "test_dq_rpg_prototype_scene.gd").read_text(encoding="utf-8")

        self.assertEqual(expected_scene, scene_text)
        self.assertEqual(expected_script, script_text)
        self.assertEqual(expected_core, core_text)
        self.assertEqual(expected_dotnet_test, dotnet_test_text)
        self.assertEqual(expected_gdunit_test, gdunit_test_text)
        self.assertIn("[node name=\"BattleStatusLabel\" type=\"Label\" parent=\"CanvasLayer/UI/BattleScene\"]", scene_text)
        self.assertIn("[node name=\"RewardButton3\" type=\"Button\" parent=\"CanvasLayer/UI/BattleScene/RewardVBox\"]", scene_text)
        self.assertIn("CanvasLayer/UI/BattleScene/RewardVBox/RewardButton3", script_text)
        self.assertNotIn("CanvasLayer/UI/RewardPanel/RewardVBox/RewardOption", script_text)


if __name__ == "__main__":
    unittest.main()
