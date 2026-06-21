#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.python.tests.prototype_workflow_router_test_support import load_module

class PrototypeWorkflowRouterPackagingAndCompletionTests(unittest.TestCase):
    def test_baseline_repo_root_should_prefer_phasea_repository_root_env(self) -> None:
        module = load_module("prototype_workflow_router_phasea_repo_root", "scripts/python/run_prototype_workflow.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            baseline = root / "template-root"
            baseline.mkdir(parents=True, exist_ok=True)
            with mock.patch.dict(module.os.environ, {"PHASEA_REPOSITORY_ROOT": str(baseline)}):
                resolved = module.baseline_repo_root()
                self.assertTrue(os.path.samefile(baseline, resolved))

    def test_resolve_default_scene_should_prefer_repo_prototype_scene_over_manifest_default(self) -> None:
        module = load_module("prototype_workflow_router_real_scene_preferred", "scripts/python/run_prototype_workflow.py")
        payload = {
            "slug": "dq-rpg",
            "prototype_type_kit": {
                "paths": {
                    "default_scene": "res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
                },
                "manifest": {
                    "paths": {
                        "default_scene": "res://Game.Godot/Prototypes/DefaultRpgTemplate/DefaultRpgPrototype.tscn"
                    }
                }
            }
        }

        scene = module._resolve_default_scene(payload)

        self.assertEqual("res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn", scene)

    def test_packaging_summary_should_only_include_current_run_tdd_summaries(self) -> None:
        module = load_module("prototype_workflow_router_packaging_current_run", "scripts/python/run_prototype_workflow.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "docs" / "prototypes").mkdir(parents=True, exist_ok=True)
            (root / "logs" / "ci" / "2026-05-15" / "prototype-tdd-dq-rpg-green").mkdir(parents=True, exist_ok=True)
            (root / "logs" / "ci" / "2026-05-15" / "prototype-tdd-dq-rpg-green" / "summary.json").write_text(
                json.dumps({"stage": "green", "status": "ok", "message": "current green", "steps": [{"name": "x"}]}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            (root / "logs" / "ci" / "2026-05-14" / "prototype-tdd-dq-rpg-red").mkdir(parents=True, exist_ok=True)
            (root / "logs" / "ci" / "2026-05-14" / "prototype-tdd-dq-rpg-red" / "summary.json").write_text(
                json.dumps({"stage": "red", "status": "unexpected_green", "message": "old red", "steps": [{"name": "x"}]}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            payload = {
                "slug": "dq-rpg",
                "success_criteria": ["30秒理解目标"],
                "prototype_type_kit": {
                    "paths": {
                        "default_scene": "res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
                    },
                    "manifest": {
                        "paths": {
                            "default_scene": "res://Game.Godot/Prototypes/DefaultRpgTemplate/DefaultRpgPrototype.tscn"
                        }
                    }
                }
            }
            steps_run = [
                {"day": 3, "title": "执行 prototype red", "status": "skipped"},
                {"day": 4, "title": "执行 prototype green", "status": "ok", "summary_path": "logs/ci/2026-05-15/prototype-tdd-dq-rpg-green/summary.json"},
            ]

            summary_path, summary_paths = module._write_packaging_summary(
                root=root,
                payload=payload,
                record_file="docs/prototypes/2026-05-15-dq-rpg.md",
                prototype_spec="docs/prototypes/dq-rpg.prototype.json",
                steps_run=steps_run,
            )
            packaging = json.loads((root / summary_path.replace("/", os.sep)).read_text(encoding="utf-8"))

        self.assertEqual(["logs/ci/2026-05-15/prototype-tdd-dq-rpg-green/summary.json"], summary_paths)
        self.assertEqual("res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn", packaging["default_scene"])
        self.assertEqual(1, len(packaging["tdd_summaries"]))
        self.assertEqual("green", packaging["tdd_summaries"][0]["stage"])

    def test_packaging_summary_should_fallback_to_latest_slug_tdd_outputs_when_steps_do_not_carry_paths(self) -> None:
        module = load_module("prototype_workflow_router_packaging_latest_slug_fallback", "scripts/python/run_prototype_workflow.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            scene_path = root / "Game.Godot" / "Prototypes" / "dq-rpg" / "DqRpgPrototype.tscn"
            scene_path.parent.mkdir(parents=True, exist_ok=True)
            scene_path.write_text("[gd_scene format=3]\n", encoding="utf-8")
            green_dir = root / "logs" / "ci" / "2026-05-15" / "prototype-tdd-dq-rpg-green"
            green_dir.mkdir(parents=True, exist_ok=True)
            (green_dir / "summary.json").write_text(
                json.dumps({"stage": "green", "status": "ok", "message": "current green", "steps": [{"name": "x"}]}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            red_dir = root / "logs" / "ci" / "2026-05-15" / "prototype-tdd-dq-rpg-red"
            red_dir.mkdir(parents=True, exist_ok=True)
            (red_dir / "summary.json").write_text(
                json.dumps({"stage": "red", "status": "unexpected_green", "message": "latest red", "steps": [{"name": "x"}]}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            payload = {
                "slug": "dq-rpg",
                "success_criteria": ["30秒理解目标"],
                "prototype_type_kit": {
                    "manifest": {
                        "paths": {
                            "default_scene": "res://Game.Godot/Prototypes/DefaultRpgTemplate/DefaultRpgPrototype.tscn"
                        }
                    }
                }
            }

            summary_path, summary_paths = module._write_packaging_summary(
                root=root,
                payload=payload,
                record_file="docs/prototypes/2026-05-15-dq-rpg.md",
                prototype_spec="docs/prototypes/dq-rpg.prototype.json",
                steps_run=[{"day": 4, "title": "执行 prototype green", "status": "ok"}],
            )
            packaging = json.loads((root / summary_path.replace("/", os.sep)).read_text(encoding="utf-8"))

        self.assertEqual(
            [
                "logs/ci/2026-05-15/prototype-tdd-dq-rpg-red/summary.json",
                "logs/ci/2026-05-15/prototype-tdd-dq-rpg-green/summary.json",
            ],
            summary_paths,
        )
        self.assertEqual("res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn", packaging["default_scene"])

    def test_completion_report_should_prefer_packaging_default_scene_over_template_manifest_scene(self) -> None:
        module = load_module("prototype_workflow_router_completion_report_default_scene", "scripts/python/run_prototype_workflow.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            scene_path = root / "Game.Godot" / "Prototypes" / "dq-rpg" / "DqRpgPrototype.tscn"
            scene_path.parent.mkdir(parents=True, exist_ok=True)
            scene_path.write_text("[gd_scene format=3]\n", encoding="utf-8")
            payload = {
                "slug": "dq-rpg",
                "success_criteria": ["奖励3选1可以正确理解"],
                "prototype_type_kit": {
                    "manifest": {
                        "paths": {
                            "default_scene": "res://Game.Godot/Prototypes/DefaultRpgTemplate/DefaultRpgPrototype.tscn"
                        }
                    }
                }
            }
            packaging_path, summary_paths = module._write_packaging_summary(
                root=root,
                payload=payload,
                record_file="docs/prototypes/2026-05-15-dq-rpg.md",
                prototype_spec="docs/prototypes/dq-rpg.prototype.json",
                steps_run=[],
            )

            completion_path, _ = module._write_completion_report(
                root=root,
                payload=payload,
                record_file="docs/prototypes/2026-05-15-dq-rpg.md",
                prototype_spec="docs/prototypes/dq-rpg.prototype.json",
                packaging_summary_path=packaging_path,
                tdd_summary_paths=summary_paths,
                steps_run=[],
            )
            completion = (root / completion_path.replace("/", os.sep)).read_text(encoding="utf-8")

        self.assertIn("Default Scene: res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn", completion)
        self.assertNotIn("Default Scene: res://Game.Godot/Prototypes/DefaultRpgTemplate/DefaultRpgPrototype.tscn", completion)

    def test_completion_report_should_replace_placeholder_next_step_with_actionable_rpg_advice(self) -> None:
        module = load_module("prototype_workflow_router_completion_report_actionable_next_step", "scripts/python/run_prototype_workflow.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            scene_path = root / "Game.Godot" / "Prototypes" / "dq-rpg" / "DqRpgPrototype.tscn"
            scene_path.parent.mkdir(parents=True, exist_ok=True)
            scene_path.write_text("[gd_scene format=3]\n", encoding="utf-8")
            payload = {
                "slug": "dq-rpg",
                "game_type": "rpg",
                "next_step": "Stay in prototype lane until explicitly promoted later.",
                "success_criteria": ["奖励3选1可以正确理解"],
                "core_gameplay_loop": "地图移动，概率撞怪，打赢怪物，选择成长",
                "win_fail_conditions": "打赢15场战斗赢得游戏胜利；任一战斗失败就游戏失败",
            }
            packaging_path, summary_paths = module._write_packaging_summary(
                root=root,
                payload=payload,
                record_file="docs/prototypes/2026-05-16-dq-rpg.md",
                prototype_spec="docs/prototypes/dq-rpg.prototype.json",
                steps_run=[],
            )

            completion_path, completion_summary = module._write_completion_report(
                root=root,
                payload=payload,
                record_file="docs/prototypes/2026-05-16-dq-rpg.md",
                prototype_spec="docs/prototypes/dq-rpg.prototype.json",
                packaging_summary_path=packaging_path,
                tdd_summary_paths=summary_paths,
                steps_run=[],
            )
            completion = (root / completion_path.replace("/", os.sep)).read_text(encoding="utf-8")

        self.assertNotIn("Stay in prototype lane until explicitly promoted later.", completion_summary)
        self.assertIn("奖励 3 选 1", completion_summary)
        self.assertIn("触发遇敌", completion_summary)
        self.assertIn("当前 RPG 原型", completion_summary)
        self.assertIn("下一步建议：", completion)
        self.assertNotIn("Stay in prototype lane until explicitly promoted later.", completion)

    def test_completion_report_should_fallback_when_codex_next_step_is_internal_execution_noise(self) -> None:
        module = load_module("prototype_workflow_router_completion_report_internal_codex_next_step", "scripts/python/run_prototype_workflow.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            scene_path = root / "Game.Godot" / "Prototypes" / "dq-rpg" / "DqRpgPrototype.tscn"
            scene_path.parent.mkdir(parents=True, exist_ok=True)
            scene_path.write_text("[gd_scene format=3]\n", encoding="utf-8")
            codex_output = root / "logs" / "ci" / module.today_str() / "prototype-implementation-dq-rpg" / "codex-output.txt"
            codex_output.parent.mkdir(parents=True, exist_ok=True)
            codex_output.write_text(
                """已完成 Day 4 的最小实现。

如果你要，我下一步可以继续处理这个工作区的 obj/tmp 写权限问题，或者直接转去补 Day 5 的 Godot/GdUnit 最小验证。
""",
                encoding="utf-8",
            )
            payload = {
                "slug": "dq-rpg",
                "game_type": "rpg",
                "next_step": "Stay in prototype lane until explicitly promoted later.",
                "success_criteria": ["奖励3选1可以正确理解"],
                "core_gameplay_loop": "地图移动，概率撞怪，打赢怪物，选择成长",
            }
            packaging_path, summary_paths = module._write_packaging_summary(
                root=root,
                payload=payload,
                record_file="docs/prototypes/2026-05-16-dq-rpg.md",
                prototype_spec="docs/prototypes/dq-rpg.prototype.json",
                steps_run=[],
            )

            completion_path, completion_summary = module._write_completion_report(
                root=root,
                payload=payload,
                record_file="docs/prototypes/2026-05-16-dq-rpg.md",
                prototype_spec="docs/prototypes/dq-rpg.prototype.json",
                packaging_summary_path=packaging_path,
                tdd_summary_paths=summary_paths,
                steps_run=[],
            )
            completion = (root / completion_path.replace("/", os.sep)).read_text(encoding="utf-8")

        self.assertNotIn("写权限问题", completion_summary)
        self.assertNotIn("Day 5", completion_summary)
        self.assertIn("当前 RPG 原型补成一个完整首轮闭环", completion_summary)
        self.assertIn("下一步建议：", completion)
        self.assertEqual(
            "请继续把当前 RPG 原型补成一个完整首轮闭环：优先让玩家能稳定移动、触发遇敌、完成一场战斗，并在胜利后完成一次奖励 3 选 1 再返回地图。 完成后先重点验证“奖励3选1可以正确理解”是否真的成立。",
            payload["next_step"],
        )
        self.assertEqual("system", payload["next_step_source"])
        self.assertEqual("not_recommended", payload["next_step_evaluation"])

    def test_completion_report_should_keep_real_product_next_step_from_codex(self) -> None:
        module = load_module("prototype_workflow_router_completion_report_product_codex_next_step", "scripts/python/run_prototype_workflow.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            scene_path = root / "Game.Godot" / "Prototypes" / "dq-rpg" / "DqRpgPrototype.tscn"
            scene_path.parent.mkdir(parents=True, exist_ok=True)
            scene_path.write_text("[gd_scene format=3]\n", encoding="utf-8")
            codex_output = root / "logs" / "ci" / module.today_str() / "prototype-implementation-dq-rpg" / "codex-output.txt"
            codex_output.parent.mkdir(parents=True, exist_ok=True)
            codex_output.write_text(
                """本轮已经打通主菜单进入原型场景。

下一步建议：继续补齐战斗胜利后的奖励三选一反馈，并把失败提示做得更明确，确保玩家能完成一次完整闭环。
""",
                encoding="utf-8",
            )
            payload = {
                "slug": "dq-rpg",
                "game_type": "rpg",
                "next_step": "Stay in prototype lane until explicitly promoted later.",
                "success_criteria": ["奖励3选1可以正确理解"],
                "core_gameplay_loop": "地图移动，概率撞怪，打赢怪物，选择成长",
            }
            packaging_path, summary_paths = module._write_packaging_summary(
                root=root,
                payload=payload,
                record_file="docs/prototypes/2026-05-16-dq-rpg.md",
                prototype_spec="docs/prototypes/dq-rpg.prototype.json",
                steps_run=[],
            )

            module._write_completion_report(
                root=root,
                payload=payload,
                record_file="docs/prototypes/2026-05-16-dq-rpg.md",
                prototype_spec="docs/prototypes/dq-rpg.prototype.json",
                packaging_summary_path=packaging_path,
                tdd_summary_paths=summary_paths,
                steps_run=[],
            )

        self.assertEqual(
            "继续补齐战斗胜利后的奖励三选一反馈，并把失败提示做得更明确，确保玩家能完成一次完整闭环。",
            payload["next_step"],
        )
        self.assertEqual("codex", payload["next_step_source"])
        self.assertEqual("recommended", payload["next_step_evaluation"])

    def test_completion_report_should_mark_system_source_when_using_fallback(self) -> None:
        module = load_module("prototype_workflow_router_completion_report_source_fallback", "scripts/python/run_prototype_workflow.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            scene_path = root / "Game.Godot" / "Prototypes" / "dq-rpg" / "DqRpgPrototype.tscn"
            scene_path.parent.mkdir(parents=True, exist_ok=True)
            scene_path.write_text("[gd_scene format=3]\n", encoding="utf-8")
            payload = {
                "slug": "dq-rpg",
                "game_type": "rpg",
                "next_step": "Stay in prototype lane until explicitly promoted later.",
                "success_criteria": ["奖励3选1可以正确理解"],
                "core_gameplay_loop": "地图移动，概率撞怪，打赢怪物，选择成长",
                "win_fail_conditions": "打赢15场战斗赢得游戏胜利；任一战斗失败就游戏失败",
            }
            packaging_path, summary_paths = module._write_packaging_summary(
                root=root,
                payload=payload,
                record_file="docs/prototypes/2026-05-16-dq-rpg.md",
                prototype_spec="docs/prototypes/dq-rpg.prototype.json",
                steps_run=[],
            )

            module._write_completion_report(
                root=root,
                payload=payload,
                record_file="docs/prototypes/2026-05-16-dq-rpg.md",
                prototype_spec="docs/prototypes/dq-rpg.prototype.json",
                packaging_summary_path=packaging_path,
                tdd_summary_paths=summary_paths,
                steps_run=[],
            )

        self.assertEqual("system", payload["next_step_source"])
        self.assertEqual("not_recommended", payload["next_step_evaluation"])
        self.assertIn("当前原型验收证据不足", payload["next_step_evaluation_reason"])


if __name__ == "__main__":
    unittest.main()
