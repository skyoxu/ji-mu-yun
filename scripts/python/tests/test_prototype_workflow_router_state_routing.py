#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from scripts.python.tests.prototype_workflow_router_test_support import load_module

class PrototypeWorkflowRouterStateAndRoutingTests(unittest.TestCase):
    def test_confirmation_message_should_tolerate_non_dict_llm_dimensions(self) -> None:
        module = load_module("prototype_workflow_router_confirmation_llm_shape", "scripts/python/run_prototype_workflow.py")
        payload = module.normalize_prototype_payload(
            {
                "slug": "combat-loop",
                "hypothesis": "验证战斗循环是否值得继续。",
                "core_player_fantasy": "玩家在第一分钟内感受到紧凑战斗节奏。",
                "minimum_playable_loop": "进入场景，接近敌人，攻击一次，看到受击反馈。",
                "success_criteria": ["玩家能完成一次最小循环"],
            },
            today="2026-04-21",
        )
        hard_score = {
            "total_score": 40,
            "max_score": 50,
            "recommendation": "ready-for-tdd",
            "dimensions": [
                {"id": "prototype_feasibility", "label": "Prototype feasibility", "score": 20, "max_score": 25},
                {"id": "content_completeness", "label": "Content completeness", "score": 20, "max_score": 25},
            ],
        }
        llm_review = {
            "status": "ok",
            "review": {
                "total_score": 30,
                "max_score": 50,
                "recommendation": "market-cautious",
                "dimensions": ["market_potential: 18/25", {"id": "commercialization_cost", "label": "Commercialization cost", "score": 12, "max_score": 25}],
            },
        }

        message = module._build_confirmation_message(
            payload,
            file_path="docs/prototypes/combat-loop.md",
            intake_score=hard_score,
            llm_review=llm_review,
        )

        self.assertIn("AI market/commercial score: 30/50", message)
        self.assertIn("market_potential: 18/25", message)
        self.assertIn("Commercialization cost: 12/25", message)

    def test_dev_cli_should_forward_optional_score_engine_args(self) -> None:
        builders = load_module("dev_cli_builders_module_for_proto_score", "scripts/python/dev_cli_builders.py")
        dev_cli = load_module("dev_cli_module_for_proto_score", "scripts/python/dev_cli.py")
        parser = dev_cli.build_parser()
        args = parser.parse_args(
            [
                "run-prototype-workflow",
                "--prototype-file",
                "docs/prototypes/sample.md",
                "--score-engine",
                "codex",
                "--score-timeout-sec",
                "120",
            ]
        )
        cmd = builders.build_run_prototype_workflow_cmd(args)

        self.assertIn("--score-engine", cmd)
        self.assertIn("codex", cmd)
        self.assertIn("--score-timeout-sec", cmd)
        self.assertIn("120", cmd)

    def test_active_state_should_round_trip(self) -> None:
        module = load_module("prototype_workflow_router_state", "scripts/python/run_prototype_workflow.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state = {
                "status": "needs-confirmation",
                "prototype": {"slug": "combat-loop", "day": 1},
                "missing_required_fields": [],
            }
            path = module.write_active_state(repo_root=root, slug="combat-loop", payload=state)
            loaded = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(state["status"], loaded["status"])
        self.assertEqual("combat-loop", loaded["prototype"]["slug"])

    def test_rpg_payload_should_attach_repo_local_implementation_skill(self) -> None:
        module = load_module("prototype_workflow_router_rpg_skill_payload", "scripts/python/run_prototype_workflow.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            catalog = root / "docs" / "prototype-type-kits" / "game-type-template-catalog.json"
            catalog.parent.mkdir(parents=True, exist_ok=True)
            catalog.write_text(
                '{"schema_version":1,"entries":[{"game_type":"rpg","template_id":"default-rpg-template","source_mode":"repo-imported","repo_template_path":"Game.Godot/Prototypes/DefaultRpgTemplate","manifest_path":"docs/prototype-type-kits/default-rpg-template.manifest.json","import_source_path":"C:/gametype/rpgdemo","enabled":true}]}\n',
                encoding="utf-8",
            )
            manifest_path = root / "docs" / "prototype-type-kits" / "default-rpg-template.manifest.json"
            manifest_path.write_text(
                '{"schema_version":1,"paths":{"skill_path":".agents/skills/prototype-rpg-godot-zh/SKILL.md","contract_path":".agents/skills/prototype-rpg-godot-zh/references/rpg-prototype-contract.md"}}\n',
                encoding="utf-8",
            )
            skill_path = root / ".agents" / "skills" / "prototype-rpg-godot-zh" / "SKILL.md"
            skill_path.parent.mkdir(parents=True, exist_ok=True)
            skill_path.write_text("# skill\n", encoding="utf-8")
            contract_path = skill_path.parent / "references" / "rpg-prototype-contract.md"
            contract_path.parent.mkdir(parents=True, exist_ok=True)
            contract_path.write_text("# contract\n", encoding="utf-8")

            payload = module.normalize_prototype_payload(
                {
                    "slug": "default-rpg-template",
                    "game_type": "rpg",
                    "hypothesis": "test",
                    "core_player_fantasy": "test",
                    "minimum_playable_loop": "test",
                    "game_feature": "test",
                    "core_gameplay_loop": "test",
                    "win_fail_conditions": "test",
                    "success_criteria": ["test"],
                },
                today="2026-05-05",
            )
            enriched = module.enrich_payload_with_repo_local_skill(root=root, payload=payload)

        self.assertEqual("prototype-rpg-godot-zh", enriched["implementation_skill"]["name"])
        self.assertEqual(".agents/skills/prototype-rpg-godot-zh/SKILL.md", enriched["implementation_skill"]["path"])
        self.assertEqual(
            ".agents/skills/prototype-rpg-godot-zh/references/rpg-prototype-contract.md",
            enriched["implementation_skill"]["contract_path"],
        )

    def test_non_rpg_payload_should_not_attach_repo_local_implementation_skill(self) -> None:
        module = load_module("prototype_workflow_router_non_rpg_skill_payload", "scripts/python/run_prototype_workflow.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            payload = module.normalize_prototype_payload(
                {
                    "slug": "gravity-room",
                    "game_type": "puzzle",
                    "hypothesis": "test",
                    "core_player_fantasy": "test",
                    "minimum_playable_loop": "test",
                    "game_feature": "test",
                    "core_gameplay_loop": "test",
                    "win_fail_conditions": "test",
                    "success_criteria": ["test"],
                },
                today="2026-05-05",
            )
            enriched = module.enrich_payload_with_repo_local_skill(root=root, payload=payload)

        self.assertNotIn("implementation_skill", enriched)

    def test_confirm_pause_should_persist_rpg_skill_metadata_in_active_state(self) -> None:
        module = load_module("prototype_workflow_router_rpg_skill_state", "scripts/python/run_prototype_workflow.py")
        template = """# Prototype: default-rpg-template

## Hypothesis
- test hypothesis

## Core Player Fantasy
- test fantasy

## Minimum Playable Loop
- test loop

## Game Type
- rpg

## Game Feature
- test feature

## Core Gameplay Loop
- test gameplay loop

## Win / Fail Conditions
- test win fail

## Success Criteria
- test criteria
"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            catalog = root / "docs" / "prototype-type-kits" / "game-type-template-catalog.json"
            catalog.parent.mkdir(parents=True, exist_ok=True)
            catalog.write_text(
                '{"schema_version":1,"entries":[{"game_type":"rpg","template_id":"default-rpg-template","source_mode":"repo-imported","repo_template_path":"Game.Godot/Prototypes/DefaultRpgTemplate","manifest_path":"docs/prototype-type-kits/default-rpg-template.manifest.json","import_source_path":"C:/gametype/rpgdemo","enabled":true}]}\n',
                encoding="utf-8",
            )
            skill_path = root / ".agents" / "skills" / "prototype-rpg-godot-zh" / "SKILL.md"
            skill_path.parent.mkdir(parents=True, exist_ok=True)
            skill_path.write_text("# skill\n", encoding="utf-8")
            contract_path = skill_path.parent / "references" / "rpg-prototype-contract.md"
            contract_path.parent.mkdir(parents=True, exist_ok=True)
            contract_path.write_text("# contract\n", encoding="utf-8")
            manifest_path = root / "docs" / "prototype-type-kits" / "default-rpg-template.manifest.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text('{"schema_version":1,"slug":"default-rpg-template","paths":{"default_scene":"Game.Godot/Prototypes/DefaultRpgTemplate/DefaultRpgPrototype.tscn"}}\n', encoding="utf-8")
            prototype_file = root / "docs" / "prototypes" / "default-rpg-template.md"
            prototype_file.parent.mkdir(parents=True, exist_ok=True)
            prototype_file.write_text(template, encoding="utf-8")
            module.repo_root = lambda: root
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = module.main(["--prototype-file", str(prototype_file)])
            active_path = root / "logs" / "ci" / "active-prototypes" / "default-rpg-template.active.json"
            active_state = json.loads(active_path.read_text(encoding="utf-8"))

        self.assertEqual(0, rc)
        self.assertEqual(
            ".agents/skills/prototype-rpg-godot-zh/SKILL.md",
            active_state["prototype"]["implementation_skill"]["path"],
        )
        self.assertEqual(
            "docs/prototype-type-kits/default-rpg-template.manifest.json",
            active_state["prototype"]["prototype_type_kit"]["manifest_path"],
        )
        self.assertIn("prototype-rpg-godot-zh", active_state["confirmation_summary"])

    def test_catalog_should_drive_default_manifest_lookup(self) -> None:
        module = load_module("prototype_workflow_router_manifest_catalog", "scripts/python/run_prototype_workflow.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            catalog = root / "docs" / "prototype-type-kits" / "game-type-template-catalog.json"
            catalog.parent.mkdir(parents=True, exist_ok=True)
            catalog.write_text(
                '{"schema_version":1,"entries":[{"game_type":"rpg","template_id":"default-rpg-template","source_mode":"repo-imported","repo_template_path":"Game.Godot/Prototypes/DefaultRpgTemplate","manifest_path":"docs/prototype-type-kits/default-rpg-template.manifest.json","import_source_path":"C:/gametype/rpgdemo","enabled":true}]}\n',
                encoding="utf-8",
            )
            manifest = root / "docs" / "prototype-type-kits" / "default-rpg-template.manifest.json"
            manifest.write_text('{"schema_version":1,"slug":"default-rpg-template"}\n', encoding="utf-8")

            payload = module.enrich_payload_with_prototype_manifest(
                root=root,
                payload={"slug": "demo", "game_type": "rpg", "prototype_type_kit": {}},
            )

        self.assertEqual(
            "docs/prototype-type-kits/default-rpg-template.manifest.json",
            payload["prototype_type_kit"]["manifest_path"],
        )

    def test_record_render_should_include_template_fields(self) -> None:
        module = load_module("prototype_workflow_router_record", "scripts/python/run_prototype_tdd.py")
        rendered = module._render_record(
            slug="combat-loop",
            owner="operator",
            related_task_ids=["none yet"],
            hypothesis="验证战斗循环是否值得继续",
            core_player_fantasy="第一分钟内感受到战斗节奏",
            minimum_playable_loop="进入战斗，攻击一次，看到受击反馈",
            game_feature="快速反馈战斗",
            core_gameplay_loop="接近敌人，攻击，反馈，继续",
            win_fail_conditions="击败敌人胜利；HP 归零失败",
            game_type_specific_game_type="",
            game_type_specific_guide_path="",
            game_type_specific_sections=[],
            implementation_skill_name="prototype-rpg-godot-zh",
            implementation_skill_path=".agents/skills/prototype-rpg-godot-zh/SKILL.md",
            implementation_skill_contract_path=".agents/skills/prototype-rpg-godot-zh/references/rpg-prototype-contract.md",
            scope_in=["移动", "攻击"],
            scope_out=["正式任务"],
            success_criteria=["玩家能完成一次最小循环"],
            promote_signals=["试玩后仍值得继续"],
            archive_signals=["方向有价值但不够强"],
            discard_signals=["循环无趣且不清晰"],
            evidence=["Game.Godot/Prototypes/combat-loop/CombatLoopPrototype.tscn"],
            decision="pending",
            next_step="进入 Day 2 场景脚手架",
        )

        self.assertIn("## Core Player Fantasy", rendered)
        self.assertIn("## Minimum Playable Loop", rendered)
        self.assertIn("## Implementation Skill", rendered)
        self.assertIn("## Promote Signals", rendered)
        self.assertIn("## Archive Signals", rendered)
        self.assertIn("## Discard Signals", rendered)

    def test_day_steps_should_use_project_specific_filter_and_gdunit_path(self) -> None:
        module = load_module("prototype_workflow_router_day_steps", "scripts/python/run_prototype_workflow.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            scene_path = root / "Game.Godot" / "Prototypes" / "dq-rpg" / "DqRpgPrototype.tscn"
            scene_path.parent.mkdir(parents=True, exist_ok=True)
            scene_path.write_text("[gd_scene format=3]\n", encoding="utf-8")
            payload = {
                "slug": "dq-rpg",
                "prototype_type_kit": {
                    "manifest": {
                        "default_scene": "res://Game.Godot/Prototypes/DefaultRpgTemplate/DefaultRpgPrototype.tscn"
                    }
                }
            }

            steps = module._day_steps(payload, root=root, record_file="docs/prototypes/2026-05-15-dq-rpg.md")

        red_step = next(step for step in steps if step["day"] == 3)
        implementation_step = next(step for step in steps if step["day"] == 4)
        green_step = next(step for step in steps if step["day"] == 5)
        self.assertIn("DqRpgPrototypeLoopTests", red_step["cmd"])
        self.assertEqual("codex_implementation", implementation_step["internal_action"])
        self.assertIn("DqRpgPrototypeLoopTests", green_step["cmd"])
        self.assertIn("tests/Prototype/DqRpgPrototype", green_step["cmd"])
        self.assertEqual("res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn", green_step["default_scene"])

    def test_implementation_prompt_should_require_main_menu_navigation_to_default_scene(self) -> None:
        module = load_module("prototype_workflow_router_prompt_main_menu_navigation", "scripts/python/run_prototype_workflow.py")
        payload = {
            "slug": "dq-rpg",
            "hypothesis": "验证战斗循环是否成立",
            "core_player_fantasy": "玩家在一分钟内感到探索与战斗压力",
            "minimum_playable_loop": "移动，遇敌，战斗，结算",
            "success_criteria": ["玩家能完成一轮最小循环"],
            "game_feature": "地图探索加遭遇战",
            "core_gameplay_loop": "移动，战斗，奖励选择",
            "win_fail_conditions": "获胜继续，失败重试",
        }

        prompt = module._build_implementation_prompt(
            payload=payload,
            record_file="docs/prototypes/2026-05-16-dq-rpg.md",
            default_scene="res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn",
        )

        self.assertIn("Main.tscn", prompt)
        self.assertIn("主菜单里的“原型 / Prototype”按钮", prompt)
        self.assertIn("PrototypeCatalog + ScreenNavigator", prompt)
        self.assertIn("Prototype lightweight component preference", prompt)
        self.assertIn("HudView", prompt)
        self.assertIn("Do not introduce ECS", prompt)
        self.assertIn("Prefer exported NodePath fields", prompt)
        self.assertIn("Use EventBus only for true cross-route/global notifications", prompt)
        self.assertIn("default_scene", prompt)
        self.assertIn("不允许只生成 prototype 场景文件而不接通 Main.tscn 的主菜单原型入口", prompt)
        self.assertIn("a Grid when grid movement is used", prompt)
        self.assertIn("one accepted visible marker set", prompt)
        self.assertIn("HeaderLabel + StatsLabel + ObjectiveLabel", prompt)


if __name__ == "__main__":
    unittest.main()
