#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from scripts.python.tests.prototype_workflow_router_test_support import load_module, rpg_battle_scene_contract_nodes, rpg_battle_script_contract_bindings

class PrototypeWorkflowRouterConfirmedWorkflowTests(unittest.TestCase):
    def test_existing_day2_scaffold_should_be_skipped_during_confirmed_rerun(self) -> None:
        module = load_module("prototype_workflow_router_rerun_skip_scene", "scripts/python/run_prototype_workflow.py")
        template = """# 原型：rpgdemo1

## 假设
- 验证默认 RPG 原型是否能继续迭代。

## 核心玩家幻想
- 玩家可以立即进入可玩战斗循环。

## 最小可玩循环
- 进入场景，移动，交互并完成一次战斗。

## 游戏类型
- rpg

## 游戏特色
- 默认 RPG 骨架。

## 核心游戏循环
- 探索，接触敌人，完成战斗。

## 胜利/失败条件
- 击败敌人胜利；角色倒下失败。

## 成功标准
- 玩家能完成一次最小循环
"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest_path = root / "docs" / "prototype-type-kits" / "default-rpg-template.manifest.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                '{"schema_version":1,"slug":"default-rpg-template","paths":{"default_scene":"res://Game.Godot/Prototypes/DefaultRpgTemplate/DefaultRpgPrototype.tscn"}}\n',
                encoding="utf-8",
            )
            prototype_file = root / "docs" / "prototypes" / "2026-05-14-rpgdemo1.md"
            prototype_file.parent.mkdir(parents=True, exist_ok=True)
            prototype_file.write_text(template, encoding="utf-8")
            module.repo_root = lambda: root

            run_calls: list[list[str]] = []

            def fake_run(cmd, *, cwd):
                run_calls.append(list(cmd))
                if "create-prototype-scene" in cmd:
                    return 1, "PROTOTYPE_SCENE ERROR: scaffold already exists for slug=rpgdemo1; pass --force to overwrite.\n"
                return 0, "ok\n"

            stdout = io.StringIO()
            with mock.patch.object(module, "_ensure_prototype_record", return_value=(0, "record ok\n")):
                with mock.patch.object(module, "_run", side_effect=fake_run):
                    with redirect_stdout(stdout):
                        rc = module.main(["--prototype-file", str(prototype_file), "--confirm", "--stop-after-day", "3"])

            active_path = root / "logs" / "ci" / "active-prototypes" / "rpgdemo1.active.json"
            active_state = json.loads(active_path.read_text(encoding="utf-8"))

        self.assertEqual(0, rc)
        self.assertEqual("completed-through-day", active_state["status"])
        day2 = next(step for step in active_state["steps_run"] if step["day"] == 2)
        day3 = next(step for step in active_state["steps_run"] if step["day"] == 3)
        self.assertEqual("skipped", day2["status"])
        self.assertEqual("prototype_scaffold_already_exists", day2["reason"])
        self.assertEqual("ok", day3["status"])
        self.assertTrue(any("create-prototype-scene" in call for call in run_calls))

    def test_unexpected_green_red_stage_should_continue_with_recorded_reason(self) -> None:
        module = load_module("prototype_workflow_router_rerun_fail_red", "scripts/python/run_prototype_workflow.py")
        template = """# 原型：rpgdemo1

## 假设
- 验证默认 RPG 原型是否能继续迭代。

## 核心玩家幻想
- 玩家可以立即进入可玩战斗循环。

## 最小可玩循环
- 进入场景，移动，交互并完成一次战斗。

## 游戏类型
- rpg

## 游戏特色
- 默认 RPG 骨架。

## 核心游戏循环
- 探索，接触敌人，完成战斗。

## 胜利/失败条件
- 击败敌人胜利；角色倒下失败。

## 成功标准
- 玩家能完成一次最小循环
"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest_path = root / "docs" / "prototype-type-kits" / "default-rpg-template.manifest.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                '{"schema_version":1,"paths":{"default_scene":"res://Game.Godot/Prototypes/DefaultRpgTemplate/DefaultRpgPrototype.tscn"}}\n',
                encoding="utf-8",
            )
            kit_path = root / "docs" / "prototype-type-kits" / "rpg.md"
            kit_path.write_text(
                """## 两轮确认问题

### Round 1：Gameplay Flow / GDD Route
1. 使用随机遇怪、地图撞怪，还是二者都支持？

### Round 2：Prototype Scene UI
1. 战斗场景需要哪些 UI：HP、指令按钮、战斗日志、技能栏？
""",
                encoding="utf-8",
            )
            guide_path = root / "docs" / "game-type-guides" / "rpg.md"
            guide_path.parent.mkdir(parents=True, exist_ok=True)
            guide_path.write_text(
                """## RPG Specific Elements

### Character System
{{character_system}}
- HP

### World and Exploration
{{world_exploration}}
- Small map

### Combat System
{{combat_system}}
- Turn based
""",
                encoding="utf-8",
            )
            prototype_file = root / "docs" / "prototypes" / "2026-05-14-rpgdemo1.md"
            prototype_file.parent.mkdir(parents=True, exist_ok=True)
            prototype_file.write_text(template, encoding="utf-8")
            module.repo_root = lambda: root

            def fake_run(cmd, *, cwd):
                if "create-prototype-scene" in cmd:
                    return 0, "scene ok\n"
                if "--stage" in cmd and "red" in cmd:
                    return 1, "PROTOTYPE_TDD status=unexpected_green stage=red expected=fail out=logs/ci/demo\n"
                return 0, "ok\n"

            with mock.patch.object(module, "_ensure_prototype_record", return_value=(0, "record ok\n")):
                with mock.patch.object(module, "_run_day4_codex_implementation", return_value=(0, "implementation ok\n")):
                    with mock.patch.object(module, "_run", side_effect=fake_run):
                        rc = module.main(
                            [
                                "--prototype-file",
                                str(prototype_file),
                                "--confirm",
                                "--stop-after-day",
                                "5",
                                "--godot-bin",
                                r"C:\Godot\Godot.exe",
                            ]
                        )

            active_path = root / "logs" / "ci" / "active-prototypes" / "rpgdemo1.active.json"
            active_state = json.loads(active_path.read_text(encoding="utf-8"))

        self.assertEqual(0, rc)
        day3 = next(step for step in active_state["steps_run"] if step["day"] == 3)
        self.assertEqual("ok", day3["status"])
        self.assertEqual("prototype_tdd_red_unexpected_green_continued", day3["reason"])

    def test_expected_red_stage_capture_should_continue_workflow(self) -> None:
        module = load_module("prototype_workflow_router_expected_red_continue", "scripts/python/run_prototype_workflow.py")
        template = """# 原型：rpgdemo1

## 假设
- 验证默认 RPG 原型是否能继续迭代。

## 核心玩家幻想
- 玩家可以立即进入可玩战斗循环。

## 最小可玩循环
- 进入场景，移动，交互并完成一次战斗。

## 游戏类型
- rpg

## 游戏特色
- 默认 RPG 骨架。

## 核心游戏循环
- 探索，接触敌人，完成战斗。

## 胜利/失败条件
- 击败敌人胜利；角色倒下失败。

## 成功标准
- 玩家能完成一次最小循环
"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            prototype_file = root / "docs" / "prototypes" / "2026-05-14-rpgdemo1.md"
            prototype_file.parent.mkdir(parents=True, exist_ok=True)
            prototype_file.write_text(template, encoding="utf-8")
            module.repo_root = lambda: root

            run_calls: list[list[str]] = []

            def fake_run(cmd, *, cwd):
                run_calls.append(list(cmd))
                if "create-prototype-scene" in cmd:
                    return 0, "scene ok\n"
                if "--stage" in cmd and "red" in cmd:
                    return 1, "PROTOTYPE_TDD status=ok stage=red expected=fail out=logs/ci/demo/prototype-tdd-rpgdemo1-red/summary.json\n"
                return 0, "ok\n"

            with mock.patch.object(module, "_ensure_prototype_record", return_value=(0, "record ok\n")):
                with mock.patch.object(module, "_run_day4_codex_implementation", return_value=(0, "implementation ok\n")):
                    with mock.patch.object(module, "_run", side_effect=fake_run):
                        rc = module.main(
                            [
                                "--prototype-file",
                                str(prototype_file),
                                "--confirm",
                                "--stop-after-day",
                                "5",
                                "--godot-bin",
                                r"C:\Godot\Godot.exe",
                            ]
                        )

            active_path = root / "logs" / "ci" / "active-prototypes" / "rpgdemo1.active.json"
            active_state = json.loads(active_path.read_text(encoding="utf-8"))

        self.assertEqual(0, rc)
        self.assertEqual("completed-through-day", active_state["status"])
        self.assertEqual(5, active_state["completed_through_day"])
        day3 = next(step for step in active_state["steps_run"] if step["day"] == 3)
        day4 = next(step for step in active_state["steps_run"] if step["day"] == 4)
        day5 = next(step for step in active_state["steps_run"] if step["day"] == 5)
        self.assertEqual("ok", day3["status"])
        self.assertEqual("prototype_tdd_red_expected_fail_captured", day3["reason"])
        self.assertEqual("ok", day4["status"])
        self.assertEqual("ok", day5["status"])
        self.assertTrue(any("--stage" in call and "red" in call for call in run_calls))
        self.assertTrue(any("--stage" in call and "green" in call for call in run_calls))

    def test_existing_project_specific_prototype_should_skip_red_and_day4(self) -> None:
        module = load_module("prototype_workflow_router_skip_existing_red", "scripts/python/run_prototype_workflow.py")
        template = """# 原型：dq-rpg

## 假设
- 验证默认 RPG 原型是否能继续迭代。

## 核心玩家幻想
- 玩家可以立即进入可玩战斗循环。

## 最小可玩循环
- 进入场景，移动，交互并完成一次战斗。

## 游戏类型
- rpg

## 游戏特色
- 默认 RPG 骨架。

## 核心游戏循环
- 探索，接触敌人，完成战斗。

## 胜利/失败条件
- 击败敌人胜利；角色倒下失败。

## 成功标准
- 玩家能完成一次最小循环
"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            class_name = "DqRpgPrototype"
            prototype_file = root / "docs" / "prototypes" / "2026-05-27-dq-rpg.md"
            prototype_file.parent.mkdir(parents=True, exist_ok=True)
            prototype_file.write_text(template, encoding="utf-8")
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
            module.repo_root = lambda: root

            run_calls: list[list[str]] = []

            def fake_run(cmd, *, cwd):
                run_calls.append(list(cmd))
                return 0, "ok\n"

            with mock.patch.object(module, "_ensure_prototype_record", return_value=(0, "record ok\n")):
                with mock.patch.object(module, "_run", side_effect=fake_run):
                    rc = module.main(
                        [
                            "--prototype-file",
                            str(prototype_file),
                            "--confirm",
                            "--stop-after-day",
                            "5",
                            "--godot-bin",
                            r"C:\Godot\Godot.exe",
                        ]
                    )

            active_path = root / "logs" / "ci" / "active-prototypes" / "dq-rpg.active.json"
            active_state = json.loads(active_path.read_text(encoding="utf-8"))

        self.assertEqual(0, rc)
        day3 = next(step for step in active_state["steps_run"] if step["day"] == 3)
        day4 = next(step for step in active_state["steps_run"] if step["day"] == 4)
        day5 = next(step for step in active_state["steps_run"] if step["day"] == 5)
        self.assertEqual("skipped", day3["status"])
        self.assertEqual("existing_project_specific_prototype_ready_for_green", day3["reason"])
        self.assertEqual("skipped", day4["status"])
        self.assertEqual("existing_project_specific_prototype_ready_for_green", day4["reason"])
        self.assertEqual("ok", day5["status"])
        self.assertFalse(any("--stage" in call and "red" in call for call in run_calls))
        self.assertTrue(any("--stage" in call and "green" in call for call in run_calls))

    def test_step06_and_step07_should_write_packaging_and_completion_content(self) -> None:
        module = load_module("prototype_workflow_router_step67_outputs", "scripts/python/run_prototype_workflow.py")
        template = """# 原型：combat-loop

## 假设
- 验证战斗循环是否值得继续。

## 核心玩家幻想
- 玩家在第一分钟内感受到紧凑战斗节奏，并愿意继续下一轮。

## 最小可玩循环
- 进入场景，接近敌人，攻击一次，看到受击反馈，然后可以立即重试。

## 游戏特色
- 快速反馈战斗。

## 核心游戏循环
- 接近敌人，攻击，观察反馈，继续下一轮。

## 胜利/失败条件
- 击败敌人胜利；HP 归零失败。

## 成功标准
- 玩家能完成一次最小循环
- 试玩后愿意继续
"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            prototype_file = root / "docs" / "prototypes" / "combat-loop.md"
            prototype_file.parent.mkdir(parents=True, exist_ok=True)
            prototype_file.write_text(template, encoding="utf-8")
            summary_dir = root / "logs" / "ci" / module.today_str() / "prototype-tdd-combat-loop-green"
            summary_dir.mkdir(parents=True, exist_ok=True)
            (summary_dir / "summary.json").write_text(
                json.dumps(
                    {
                        "stage": "green",
                        "status": "ok",
                        "message": "Prototype verification steps passed.",
                        "steps": [{"name": "dotnet-1", "rc": 0}],
                    },
                    ensure_ascii=False,
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )
            module.repo_root = lambda: root

            def fake_run(cmd, *, cwd):
                if "create-prototype-scene" in cmd:
                    return 0, "scene ok\n"
                if "--stage" in cmd and "green" in cmd:
                    return 0, f"PROTOTYPE_TDD status=ok stage=green out=logs/ci/{module.today_str()}/prototype-tdd-combat-loop-green/summary.json\n"
                return 0, "ok\n"

            with mock.patch.object(module, "_ensure_prototype_record", return_value=(0, "record ok\n")):
                with mock.patch.object(module, "_run_day4_codex_implementation", return_value=(0, "implementation ok\n")):
                    with mock.patch.object(module, "_run", side_effect=fake_run):
                        rc = module.main(["--prototype-file", str(prototype_file), "--confirm", "--stop-after-day", "7", "--godot-bin", "C:/Godot/Godot.exe"])

            active_path = root / "logs" / "ci" / "active-prototypes" / "combat-loop.active.json"
            active_state = json.loads(active_path.read_text(encoding="utf-8"))
            packaging_path = root / active_state["packaging_summary"]
            completion_path = root / active_state["completion_report"]
            packaging = json.loads(packaging_path.read_text(encoding="utf-8"))
            completion = completion_path.read_text(encoding="utf-8")

        self.assertEqual(0, rc)
        self.assertEqual("completed-through-day", active_state["status"])
        self.assertIn("prototype_artifacts", packaging)
        self.assertIn("playtest_focus_points", packaging)
        self.assertEqual("green", packaging["tdd_summaries"][0]["stage"])
        self.assertIn("Acceptance Snapshot", completion)
        self.assertIn("Suggested Playtest Focus", completion)


if __name__ == "__main__":
    unittest.main()
