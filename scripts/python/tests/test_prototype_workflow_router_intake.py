#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import os
import unittest
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from scripts.python.tests.prototype_workflow_router_test_support import load_module

class PrototypeWorkflowRouterIntakeTests(unittest.TestCase):
    def test_configure_stdio_utf8_should_reconfigure_stdout_and_stderr(self) -> None:
        module = load_module("prototype_workflow_router_stdio", "scripts/python/run_prototype_workflow.py")

        calls: list[tuple[str, str, str]] = []

        class FakeStream:
            def __init__(self, name: str) -> None:
                self.name = name

            def reconfigure(self, *, encoding: str, errors: str) -> None:
                calls.append((self.name, encoding, errors))

        with mock.patch.object(module.sys, "stdout", FakeStream("stdout")), mock.patch.object(module.sys, "stderr", FakeStream("stderr")):
            module.configure_stdio_utf8()

        self.assertEqual(
            [("stdout", "utf-8", "replace"), ("stderr", "utf-8", "replace")],
            calls,
        )

    def test_template_defaults_should_fill_optional_fields(self) -> None:
        module = load_module("prototype_workflow_router_defaults", "scripts/python/run_prototype_workflow.py")
        content = """# 原型：combat-loop

- 假设
- <验证战斗循环是否值得继续>

## 核心玩家幻想
- <第一分钟内感受到战斗节奏>

## 最小可玩循环
- <进入战斗，攻击一次，看到受击反馈>

## 成功标准
- <玩家能完成一次最小循环>
"""
        parsed = module.parse_template_content(content)
        normalized = module.normalize_prototype_payload(parsed, today="2026-04-21")

        self.assertEqual("combat-loop", normalized["slug"])
        self.assertEqual("active", normalized["status"])
        self.assertEqual("operator", normalized["owner"])
        self.assertEqual("2026-04-21", normalized["date"])
        self.assertEqual(["none yet"], normalized["related_formal_task_ids"])
        self.assertEqual(["TBD"], normalized["scope_in"])
        self.assertEqual(["TBD"], normalized["scope_out"])
        self.assertEqual("pending", normalized["decision"])

    def test_template_missing_required_fields_should_block_progress(self) -> None:
        module = load_module("prototype_workflow_router_required", "scripts/python/run_prototype_workflow.py")
        content = """# 原型：combat-loop

## 假设
- <验证战斗循环是否值得继续>
"""
        parsed = module.parse_template_content(content)
        normalized = module.normalize_prototype_payload(parsed, today="2026-04-21")
        missing = module.required_field_names(normalized)

        self.assertIn("core_player_fantasy", missing)
        self.assertIn("minimum_playable_loop", missing)
        self.assertIn("success_criteria", missing)

    def test_parse_template_content_should_ignore_evidence_headings_and_placeholders(self) -> None:
        module = load_module("prototype_workflow_router_evidence_parse", "scripts/python/run_prototype_workflow.py")
        content = """# 原型：combat-loop

## 假设
- 验证战斗循环是否值得继续。

## 核心玩家幻想
- 第一分钟内感受到战斗节奏。

## 最小可玩循环
- 进入战斗，攻击一次，看到受击反馈。

## 成功标准
- 玩家能完成一次最小循环

## 证据
- Code paths:
  - docs/prototypes
- Logs / media / notes:
  - logs/ci/active-prototypes
  - TBD
"""
        parsed = module.parse_template_content(content)
        normalized = module.normalize_prototype_payload(parsed, today="2026-05-15")

        self.assertEqual(["docs/prototypes", "logs/ci/active-prototypes"], normalized["evidence"])

    def test_normalize_prototype_payload_should_dedup_evidence_noise(self) -> None:
        module = load_module("prototype_workflow_router_evidence_normalize", "scripts/python/run_prototype_workflow.py")
        payload = module.normalize_prototype_payload(
            {
                "slug": "combat-loop",
                "hypothesis": "验证战斗循环是否值得继续。",
                "core_player_fantasy": "第一分钟内感受到战斗节奏。",
                "minimum_playable_loop": "进入战斗，攻击一次，看到受击反馈。",
                "success_criteria": ["玩家能完成一次最小循环"],
                "evidence": ["Code paths:", "docs/prototypes", "docs/prototypes", "Logs / media / notes:", "TBD", "logs/ci/active-prototypes"],
            },
            today="2026-05-15",
        )

        self.assertEqual(["docs/prototypes", "logs/ci/active-prototypes"], payload["evidence"])

    def test_collecting_answers_without_file_should_require_required_fields(self) -> None:
        module = load_module("prototype_workflow_router_questions", "scripts/python/run_prototype_workflow.py")
        questions = module.required_questions_for_missing_payload({})
        ids = [item["id"] for item in questions]

        self.assertIn("slug", ids)
        self.assertIn("hypothesis", ids)
        self.assertIn("core_player_fantasy", ids)
        self.assertIn("minimum_playable_loop", ids)
        self.assertIn("success_criteria", ids)

    def test_hard_intake_score_should_cover_feasibility_and_completeness_only(self) -> None:
        module = load_module("prototype_workflow_router_score", "scripts/python/run_prototype_workflow.py")
        payload = module.normalize_prototype_payload(
            {
                "slug": "combat-loop",
                "owner": "solo-dev",
                "hypothesis": "验证战斗循环是否值得继续。",
                "core_player_fantasy": "玩家在第一分钟内感受到紧凑战斗节奏，并愿意继续下一轮。",
                "minimum_playable_loop": "进入场景，接近敌人，攻击一次，看到受击反馈，然后可以立即重试。",
                "scope_in": ["移动", "攻击", "受击反馈"],
                "scope_out": ["正式任务拆分", "完整数值平衡"],
                "success_criteria": ["玩家能完成一次最小循环", "试玩后愿意继续"],
                "promote_signals": ["试玩后仍觉得值得继续"],
                "archive_signals": ["方向有信号但反馈还不稳定"],
                "discard_signals": ["循环无趣且反馈不清楚"],
                "evidence": ["docs/prototypes/2026-04-21-combat-loop.md"],
                "decision": "pending",
                "next_step": "先进入 Day 2 做最小可操作场景。",
            },
            today="2026-04-21",
        )

        score = module.build_prototype_intake_score(payload)

        self.assertLess(score["total_score"], 50)
        self.assertGreaterEqual(score["total_score"], 35)
        self.assertEqual(50, score["max_score"])
        self.assertEqual("ready-for-tdd", score["recommendation"])
        self.assertEqual(2, len(score["dimensions"]))
        self.assertEqual(
            [
                "prototype_feasibility",
                "content_completeness",
            ],
            [item["id"] for item in score["dimensions"]],
        )
        self.assertTrue(all(item["max_score"] == 25 for item in score["dimensions"]))

    def test_hard_intake_score_should_block_thin_payload(self) -> None:
        module = load_module("prototype_workflow_router_score_penalty", "scripts/python/run_prototype_workflow.py")
        payload = module.normalize_prototype_payload(
            {
                "slug": "mystery-cave",
                "hypothesis": "验证解谜原型是否值得继续。",
                "core_player_fantasy": "玩家感受到神秘 cave 氛围。",
                "minimum_playable_loop": "进入场景后点击机关通关。",
                "scope_in": ["单场景", "点击交互"],
                "scope_out": ["多章节", "正式商业化"],
                "success_criteria": ["玩家能完成一次最小循环"],
                "promote_signals": ["玩家愿意继续"],
                "archive_signals": ["有气质但不好玩"],
                "discard_signals": ["玩家不愿继续"],
                "next_step": "先做 Day 2 场景。",
            },
            today="2026-04-21",
        )

        score = module.build_prototype_intake_score(payload)

        self.assertEqual("refine-before-tdd", score["recommendation"])
        self.assertLess(score["total_score"], 35)
        by_id = {item["id"]: item for item in score["dimensions"]}
        self.assertLess(by_id["prototype_feasibility"]["score"], 18)
        self.assertLess(by_id["content_completeness"]["score"], 18)

    def test_complete_payload_should_pause_with_score_before_tdd(self) -> None:
        module = load_module("prototype_workflow_router_confirm_score", "scripts/python/run_prototype_workflow.py")
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

## 范围
- 纳入：
  - 移动
  - 攻击
  - 受击反馈
- 排除：
  - 正式任务拆分
  - 完整数值平衡

## 成功标准
- 玩家能完成一次最小循环
- 试玩后愿意继续

## 进入 Promote 的信号
- 试玩后仍觉得值得继续

## 进入 Archive 的信号
- 方向有信号但反馈还不稳定

## 进入 Discard 的信号
- 循环无趣且反馈不清楚

## 证据
- 代码路径：
  - Game.Godot/Prototypes/combat-loop/CombatLoopPrototype.tscn

## 下一步
- 先进入 Day 2 做最小可操作场景。
"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            prototype_file = root / "docs" / "prototypes" / "combat-loop.md"
            prototype_file.parent.mkdir(parents=True, exist_ok=True)
            prototype_file.write_text(template, encoding="utf-8")
            module.repo_root = lambda: root
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = module.main(["--prototype-file", str(prototype_file)])
            active_path = root / "logs" / "ci" / "active-prototypes" / "combat-loop.active.json"
            active_state = json.loads(active_path.read_text(encoding="utf-8"))

        self.assertEqual(0, rc)
        self.assertEqual("needs-confirmation", active_state["status"])
        self.assertLess(active_state["prototype_intake_score"]["total_score"], 50)
        self.assertIn("硬评分：", active_state["confirmation_summary"])
        self.assertIn("Prototype feasibility:", active_state["confirmation_summary"])
        self.assertIn("AI 市场/商业化评估：未运行", active_state["confirmation_summary"])
        self.assertIn("PROTOTYPE_WORKFLOW 状态=需要确认", stdout.getvalue())

    def test_codex_score_engine_should_add_optional_llm_review_without_replacing_hard_score(self) -> None:
        module = load_module("prototype_workflow_router_codex_score", "scripts/python/run_prototype_workflow.py")
        payload = module.normalize_prototype_payload(
            {
                "slug": "combat-loop",
                "hypothesis": "验证战斗循环是否值得继续。",
                "core_player_fantasy": "玩家在第一分钟内感受到紧凑战斗节奏。",
                "minimum_playable_loop": "进入场景，接近敌人，攻击一次，看到受击反馈。",
                "scope_in": ["移动", "攻击"],
                "scope_out": ["正式任务拆分"],
                "success_criteria": ["玩家能完成一次最小循环"],
                "promote_signals": ["试玩后仍值得继续"],
                "archive_signals": ["方向有信号但反馈还不稳定"],
                "discard_signals": ["循环无趣且反馈不清楚"],
                "evidence": ["docs/prototypes/combat-loop.md"],
                "next_step": "进入 Day 2 场景脚手架。",
            },
            today="2026-04-21",
        )
        fake_review = {
            "total_score": 31,
            "max_score": 50,
            "recommendation": "market-cautious",
            "dimensions": [
                {"id": "market_potential", "label": "Market potential", "score": 18, "max_score": 25},
                {"id": "commercialization_cost", "label": "Commercialization cost", "score": 13, "max_score": 25},
            ],
            "top_gaps": ["缩小 Day 2 场景目标"],
        }

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with mock.patch.object(module, "run_llm_exec", return_value=(0, json.dumps(fake_review, ensure_ascii=False), ["codex", "exec", "-"])):
                review = module.build_prototype_intake_llm_review(
                    payload,
                    root=root,
                    score_engine="codex",
                    timeout_sec=120,
                )

        self.assertEqual("codex", review["engine"])
        self.assertEqual("ok", review["status"])
        self.assertEqual(31, review["review"]["total_score"])
        self.assertEqual("market-cautious", review["review"]["recommendation"])

    def test_codex_score_engine_should_forward_model_and_reasoning_effort(self) -> None:
        module = load_module("prototype_workflow_router_codex_args", "scripts/python/run_prototype_workflow.py")
        payload = module.normalize_prototype_payload(
            {
                "slug": "combat-loop",
                "hypothesis": "test hypothesis",
                "core_player_fantasy": "test fantasy",
                "minimum_playable_loop": "test loop",
                "success_criteria": ["test criteria"],
            },
            today="2026-04-21",
        )
        calls = []

        def fake_run_llm_exec(**kwargs):
            calls.append(kwargs)
            return 0, '{"total_score": 30, "max_score": 50, "recommendation": "market-cautious", "dimensions": [], "top_gaps": []}', ["codex", "exec", "-"]

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with mock.patch.dict(os.environ, {"PHASEA_CODEX_DEFAULT_MODEL": "gpt-5.5", "PHASEA_CODEX_REASONING_EFFORT": "high"}):
                with mock.patch.object(module, "run_llm_exec", side_effect=fake_run_llm_exec):
                    review = module.build_prototype_intake_llm_review(
                        payload,
                        root=root,
                        score_engine="codex",
                        timeout_sec=120,
                    )

        self.assertEqual("ok", review["status"])
        self.assertTrue(calls)
        self.assertEqual("codex-cli", calls[0]["backend"])
        self.assertEqual("gpt-5.5", calls[0]["codex_model"])
        self.assertEqual(['model_reasoning_effort="high"'], calls[0]["codex_configs"])
        self.assertTrue(calls[0]["codex_json"])
        self.assertEqual("read-only", calls[0]["codex_sandbox"])
        self.assertTrue(calls[0]["codex_skip_git_repo_check"])


if __name__ == "__main__":
    unittest.main()
