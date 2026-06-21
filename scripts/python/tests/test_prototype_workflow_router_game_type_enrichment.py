#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.python.tests.prototype_workflow_router_test_support import load_module

class PrototypeWorkflowRouterGameTypeEnrichmentTests(unittest.TestCase):
    def test_normalize_payload_should_infer_rpg_game_type_from_unstructured_text(self) -> None:
        module = load_module("prototype_workflow_router_infer_rpg", "scripts/python/run_prototype_workflow.py")
        payload = module.normalize_prototype_payload(
            {
                "slug": "rpgdemo1",
                "hypothesis": ["复古rpg加肉鸽成长"],
                "game_feature": ["原型标识 Slug："],
                "success_criteria": ["玩家能完成一次最小循环"],
            },
            today="2026-05-14",
        )

        self.assertEqual("rpg", payload["game_type"])

    def test_enrich_payload_should_fill_legacy_rpg_specific_answers(self) -> None:
        module = load_module("prototype_workflow_router_legacy_rpg_specifics", "scripts/python/run_prototype_workflow.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            guide = root / "docs" / "game-type-guides" / "rpg.md"
            guide.parent.mkdir(parents=True, exist_ok=True)
            guide.write_text(
                """## RPG Specific Elements

### Character System
{{character_system}}
- HP
- Attack

### World and Exploration
{{world_exploration}}
- Small map

### Combat System
{{combat_system}}
- Turn based
""",
                encoding="utf-8",
            )
            payload = module.enrich_payload_with_game_type_guide(
                root=root,
                payload={
                    "slug": "rpgdemo1",
                    "game_type": "rpg",
                },
            )

        sections = {item["id"]: item["answer"] for item in payload["game_type_specifics"]["selected_sections"]}
        self.assertIn("Single playable hero", sections["character_system"])
        self.assertIn("One compact map scene", sections["world_and_exploration"])
        self.assertIn("Small-scale RPG combat loop", sections["combat_system"])

    def test_enrich_payload_should_fill_legacy_rpg_type_kit_answers(self) -> None:
        module = load_module("prototype_workflow_router_legacy_rpg_typekit", "scripts/python/run_prototype_workflow.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            kit = root / "docs" / "prototype-type-kits" / "rpg.md"
            kit.parent.mkdir(parents=True, exist_ok=True)
            kit.write_text(
                """# RPG Prototype Type Kit

## Gameplay Flow / GDD Route

### 默认最小游玩动线

1. 玩家进入地图场景。

### Round 1
- 使用随机遇怪、地图撞怪，还是二者都支持？
- 战斗是回合制指令，还是即时碰撞/自动战斗？
- 胜利后回到地图，还是进入结算后结束 prototype？
- 玩家失败后是直接 Game Over、Retry 当前战斗，还是回到地图？
- 是否需要战后奖励或肉鸽三选一来验证流派感？

## Prototype Scene UI

### Round 2
- 战斗场景需要哪些 UI：HP、指令按钮、战斗日志、技能栏？
- 地图场景需要哪些 UI：HP、任务提示、小地图、遇怪提示？
- 失败后是直接 Game Over，还是允许 Retry？
- 结算 UI 需要哪些按钮：Continue、Retry、Back to Map、End Prototype？
- 是否需要保留调试 UI 帮助快速验证 prototype？
""",
                encoding="utf-8",
            )
            payload = module.enrich_payload_with_prototype_type_kit(
                root=root,
                payload={
                    "slug": "rpgdemo1",
                    "game_type": "rpg",
                },
            )

        gameplay_answers = [item["answer"] for item in payload["prototype_type_kit"]["gameplay_flow"]]
        ui_answers = [item["answer"] for item in payload["prototype_type_kit"]["prototype_scene_ui"]]
        self.assertTrue(all(answer.strip() for answer in gameplay_answers))
        self.assertTrue(all(answer.strip() for answer in ui_answers))
        self.assertTrue(any("turn-based combat command flow" in answer for answer in gameplay_answers))
        self.assertTrue(any("player HP, enemy HP" in answer for answer in ui_answers))


if __name__ == "__main__":
    unittest.main()
