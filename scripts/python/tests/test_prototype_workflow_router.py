#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
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


class PrototypeWorkflowRouterTests(unittest.TestCase):
    def test_configure_stdio_utf8_should_reconfigure_stdout_and_stderr(self) -> None:
        module = _load_module("prototype_workflow_router_stdio", "scripts/python/run_prototype_workflow.py")

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
        module = _load_module("prototype_workflow_router_defaults", "scripts/python/run_prototype_workflow.py")
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
        module = _load_module("prototype_workflow_router_required", "scripts/python/run_prototype_workflow.py")
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
        module = _load_module("prototype_workflow_router_evidence_parse", "scripts/python/run_prototype_workflow.py")
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
        module = _load_module("prototype_workflow_router_evidence_normalize", "scripts/python/run_prototype_workflow.py")
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
        module = _load_module("prototype_workflow_router_questions", "scripts/python/run_prototype_workflow.py")
        questions = module.required_questions_for_missing_payload({})
        ids = [item["id"] for item in questions]

        self.assertIn("slug", ids)
        self.assertIn("hypothesis", ids)
        self.assertIn("core_player_fantasy", ids)
        self.assertIn("minimum_playable_loop", ids)
        self.assertIn("success_criteria", ids)

    def test_hard_intake_score_should_cover_feasibility_and_completeness_only(self) -> None:
        module = _load_module("prototype_workflow_router_score", "scripts/python/run_prototype_workflow.py")
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
        module = _load_module("prototype_workflow_router_score_penalty", "scripts/python/run_prototype_workflow.py")
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
        module = _load_module("prototype_workflow_router_confirm_score", "scripts/python/run_prototype_workflow.py")
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
        module = _load_module("prototype_workflow_router_codex_score", "scripts/python/run_prototype_workflow.py")
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
            with mock.patch.object(module, "_run_with_input", return_value=(0, json.dumps(fake_review, ensure_ascii=False))):
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
        module = _load_module("prototype_workflow_router_codex_args", "scripts/python/run_prototype_workflow.py")
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

        def fake_run_with_input(cmd, *, cwd, input_text, timeout_sec):
            calls.append(cmd)
            return 0, '{"total_score": 30, "max_score": 50, "recommendation": "market-cautious", "dimensions": [], "top_gaps": []}'

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with mock.patch.dict(os.environ, {"PHASEA_CODEX_DEFAULT_MODEL": "gpt-5.5", "PHASEA_CODEX_REASONING_EFFORT": "high"}):
                with mock.patch.object(module, "_run_with_input", side_effect=fake_run_with_input):
                    review = module.build_prototype_intake_llm_review(
                        payload,
                        root=root,
                        score_engine="codex",
                        timeout_sec=120,
                    )

        self.assertEqual("ok", review["status"])
        self.assertTrue(calls)
        self.assertIn("-m", calls[0])
        self.assertIn("gpt-5.5", calls[0])
        self.assertIn("-c", calls[0])
        self.assertIn('model_reasoning_effort="high"', calls[0])

    def test_resolve_codex_command_should_prefer_windows_cmd_wrapper(self) -> None:
        module = _load_module("prototype_workflow_router_codex_cmd", "scripts/python/run_prototype_workflow.py")

        with mock.patch.object(module.shutil, "which", side_effect=lambda name: {"codex.cmd": r"C:\npm\codex.cmd", "codex": r"C:\npm\codex"}.get(name)):
            resolved = module._resolve_codex_command()

        self.assertEqual(r"C:\npm\codex.cmd", resolved)

    def test_day4_codex_nonzero_should_continue_when_outputs_are_valid(self) -> None:
        module = _load_module("prototype_workflow_router_day4_recover", "scripts/python/run_prototype_workflow.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            slug = "phase-a-real-e2e-loop"
            class_name = "PhaseARealE2eLoopPrototype"
            scene_path = root / "Game.Godot" / "Prototypes" / slug / f"{class_name}.tscn"
            scene_path.parent.mkdir(parents=True, exist_ok=True)
            scene_path.write_text('[node name="PrototypeLoop" type="Node"]\n', encoding="utf-8")
            script_path = root / "Game.Godot" / "Prototypes" / slug / "Scripts" / f"{class_name}.cs"
            script_path.parent.mkdir(parents=True, exist_ok=True)
            script_path.write_text("public partial class PhaseARealE2eLoopPrototype : Node2D {}\n", encoding="utf-8")
            loop_path = root / "Game.Core" / "Prototypes" / f"{class_name}Loop.cs"
            loop_path.parent.mkdir(parents=True, exist_ok=True)
            loop_path.write_text("public sealed class PhaseARealE2eLoopPrototypeLoop {}\n", encoding="utf-8")
            dotnet_test = root / "Game.Core.Tests" / "Prototypes" / f"{class_name}LoopTests.cs"
            dotnet_test.parent.mkdir(parents=True, exist_ok=True)
            dotnet_test.write_text("public class PhaseARealE2eLoopPrototypeLoopTests {}\n", encoding="utf-8")
            gdunit_test = root / "Tests.Godot" / "tests" / "Prototype" / class_name / "test_phase_a_real_e2e_loop_prototype_scene.gd"
            gdunit_test.parent.mkdir(parents=True, exist_ok=True)
            gdunit_test.write_text("extends Node\n", encoding="utf-8")

            out_path = root / "logs" / "ci" / module.today_str() / "prototype-implementation-phase-a-real-e2e-loop" / "codex-output.txt"

            def fake_run(cmd, *, cwd):
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text("Day 4 implementation completed.\n", encoding="utf-8")
                return 1, "tool failed but files are already valid\n"

            with mock.patch.object(module, "_run", side_effect=fake_run):
                rc, output = module._run_day4_codex_implementation(
                    root=root,
                    payload={"slug": slug, "success_criteria": ["done"]},
                    record_file="docs/prototypes/2026-05-15-phase-a-real-e2e-loop.md",
                )

        self.assertEqual(0, rc)
        self.assertIn("Day 4 implementation completed.", output)
        self.assertIn("DAY4_IMPLEMENTATION_RECOVERED codex_exit_code=1", output)

    def test_day4_codex_should_apply_fallback_when_only_scaffold_script_remains(self) -> None:
        module = _load_module("prototype_workflow_router_day4_fallback", "scripts/python/run_prototype_workflow.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            slug = "phase-a-real-e2e-loop"
            class_name = "PhaseARealE2eLoopPrototype"

            module.write_text(
                root / "Game.Godot" / "Prototypes" / slug / f"{class_name}.tscn",
                "\n".join(
                    [
                        "[gd_scene load_steps=2 format=3]",
                        "",
                        f'[ext_resource type="Script" path="res://Game.Godot/Prototypes/{slug}/Scripts/{class_name}.cs" id="1"]',
                        "",
                        f'[node name="{class_name}" type="Node2D"]',
                        'script = ExtResource("1")',
                        "",
                        '[node name="PrototypeLoop" type="Node2D" parent="."]',
                        "",
                    ]
                ),
            )
            module.write_text(
                root / "Game.Godot" / "Prototypes" / slug / "Scripts" / f"{class_name}.cs",
                "using Godot;\n\nnamespace Game.Godot.Prototypes;\n\npublic partial class PhaseARealE2eLoopPrototype : Node2D\n{\n    public override void _Ready()\n    {\n        GD.Print(\"Prototype scaffold ready: replace this scene with the minimum playable loop.\");\n    }\n}\n",
            )
            module.write_text(
                root / "Game.Core" / "Prototypes" / f"{class_name}Loop.cs",
                "namespace Game.Core.Prototypes;\npublic sealed class PhaseARealE2eLoopPrototypeLoop { public string DescribePlayableLoop() => \"ok\"; }\n",
            )
            module.write_text(root / "Game.Core.Tests" / "Prototypes" / f"{class_name}LoopTests.cs", "test\n")
            module.write_text(root / "Tests.Godot" / "tests" / "Prototype" / class_name / "test_phase_a_real_e2e_loop_prototype_scene.gd", "test\n")

            out_path = root / "logs" / "ci" / module.today_str() / "prototype-implementation-phase-a-real-e2e-loop" / "codex-output.txt"

            def fake_run(cmd, *, cwd):
                module.write_text(out_path, "Day 4 implementation incomplete.\n")
                return 0, "codex left scaffold in place\n"

            with mock.patch.object(module, "_run", side_effect=fake_run):
                rc, output = module._run_day4_codex_implementation(
                    root=root,
                    payload={"slug": slug, "success_criteria": ["done"]},
                    record_file="docs/prototypes/2026-05-15-phase-a-real-e2e-loop.md",
                )

            rewritten = module.read_text(root / "Game.Godot" / "Prototypes" / slug / "Scripts" / f"{class_name}.cs", errors="ignore")

        self.assertEqual(0, rc)
        self.assertIn("DAY4_IMPLEMENTATION_FALLBACK applied=minimal_runtime_script", output)
        self.assertIn("EnsureRuntimeUi", rewritten)
        self.assertNotIn("Prototype scaffold ready: replace this scene with the minimum playable loop.", rewritten)

    def test_confirmation_message_should_tolerate_non_dict_llm_dimensions(self) -> None:
        module = _load_module("prototype_workflow_router_confirmation_llm_shape", "scripts/python/run_prototype_workflow.py")
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
        builders = _load_module("dev_cli_builders_module_for_proto_score", "scripts/python/dev_cli_builders.py")
        dev_cli = _load_module("dev_cli_module_for_proto_score", "scripts/python/dev_cli.py")
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
        module = _load_module("prototype_workflow_router_state", "scripts/python/run_prototype_workflow.py")
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
        module = _load_module("prototype_workflow_router_rpg_skill_payload", "scripts/python/run_prototype_workflow.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
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
        module = _load_module("prototype_workflow_router_non_rpg_skill_payload", "scripts/python/run_prototype_workflow.py")
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
        module = _load_module("prototype_workflow_router_rpg_skill_state", "scripts/python/run_prototype_workflow.py")
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

    def test_record_render_should_include_template_fields(self) -> None:
        module = _load_module("prototype_workflow_router_record", "scripts/python/run_prototype_tdd.py")
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
        module = _load_module("prototype_workflow_router_day_steps", "scripts/python/run_prototype_workflow.py")
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

    def test_validate_day4_outputs_should_fail_when_scaffold_or_core_files_are_missing(self) -> None:
        module = _load_module("prototype_workflow_router_day4_validation_fail", "scripts/python/run_prototype_workflow.py")
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

    def test_validate_day4_outputs_should_pass_when_project_specific_files_are_ready(self) -> None:
        module = _load_module("prototype_workflow_router_day4_validation_ok", "scripts/python/run_prototype_workflow.py")
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
                "using Godot;\n\npublic partial class DqRpgPrototype : Node2D\n{\n}\n",
                encoding="utf-8",
            )
            (root / "Game.Core" / "Prototypes" / f"{class_name}Loop.cs").write_text(
                "namespace Game.Core.Prototypes;\npublic sealed class DqRpgPrototypeLoop { public string DescribePlayableLoop() => \"ok\"; }\n",
                encoding="utf-8",
            )
            (root / "Game.Core.Tests" / "Prototypes" / f"{class_name}LoopTests.cs").write_text("test\n", encoding="utf-8")
            (root / "Tests.Godot" / "tests" / "Prototype" / class_name / "test_dq_rpg_prototype_scene.gd").write_text("test\n", encoding="utf-8")

            ok, issues = module._validate_day4_implementation_outputs(root=root, payload={"slug": "dq-rpg"})

        self.assertTrue(ok)
        self.assertEqual([], issues)

    def test_validate_day4_outputs_should_support_long_windows_paths(self) -> None:
        module = _load_module("prototype_workflow_router_day4_validation_long_path", "scripts/python/run_prototype_workflow.py")
        td = tempfile.mkdtemp()
        try:
            root = Path(td)
            for index in range(8):
                root = root / f"nested-segment-{index:02d}" / ("x" * 18)
            class_name = "DqRpgPrototype"
            module.write_text(
                root / "Game.Godot" / "Prototypes" / "dq-rpg" / f"{class_name}.tscn",
                "[gd_scene format=3]\n[node name=\"DqRpgPrototype\" type=\"Node2D\"]\n[node name=\"PrototypeLoop\" type=\"Node2D\" parent=\".\"]\n",
            )
            module.write_text(
                root / "Game.Godot" / "Prototypes" / "dq-rpg" / "Scripts" / f"{class_name}.cs",
                "using Godot;\n\nnamespace Game.Godot.Prototypes;\n\npublic partial class DqRpgPrototype : Node2D\n{\n}\n",
            )
            module.write_text(
                root / "Game.Core" / "Prototypes" / f"{class_name}Loop.cs",
                "namespace Game.Core.Prototypes;\npublic sealed class DqRpgPrototypeLoop { public string DescribePlayableLoop() => \"ok\"; }\n",
            )
            module.write_text(root / "Game.Core.Tests" / "Prototypes" / f"{class_name}LoopTests.cs", "test\n")
            module.write_text(root / "Tests.Godot" / "tests" / "Prototype" / class_name / "test_dq_rpg_prototype_scene.gd", "test\n")

            ok, issues = module._validate_day4_implementation_outputs(root=root, payload={"slug": "dq-rpg"})
            long_path = root / "Tests.Godot" / "tests" / "Prototype" / class_name / "test_dq_rpg_prototype_scene.gd"
        finally:
            shutil.rmtree(module.to_windows_extended_path(Path(td).resolve()), ignore_errors=False)

        self.assertTrue(len(str(long_path)) > 260)
        self.assertTrue(ok)
        self.assertEqual([], issues)

    def test_rpg_project_specific_fallback_should_copy_repo_baseline_for_dq_rpg(self) -> None:
        module = _load_module("prototype_workflow_router_dq_rpg_baseline_fallback", "scripts/python/run_prototype_workflow.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            expected_scene = Path("Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn").read_text(encoding="utf-8")
            expected_script = Path("Game.Godot/Prototypes/dq-rpg/Scripts/DqRpgPrototype.cs").read_text(encoding="utf-8")
            expected_core = Path("Game.Core/Prototypes/DqRpgPrototypeLoop.cs").read_text(encoding="utf-8")

            module._write_rpg_project_specific_fallback(root=root, payload={"slug": "dq-rpg"})

            scene_text = (root / "Game.Godot" / "Prototypes" / "dq-rpg" / "DqRpgPrototype.tscn").read_text(encoding="utf-8")
            script_text = (root / "Game.Godot" / "Prototypes" / "dq-rpg" / "Scripts" / "DqRpgPrototype.cs").read_text(encoding="utf-8")
            core_text = (root / "Game.Core" / "Prototypes" / "DqRpgPrototypeLoop.cs").read_text(encoding="utf-8")

        self.assertEqual(expected_scene, scene_text)
        self.assertEqual(expected_script, script_text)
        self.assertEqual(expected_core, core_text)

    def test_baseline_repo_root_should_prefer_phasea_repository_root_env(self) -> None:
        module = _load_module("prototype_workflow_router_phasea_repo_root", "scripts/python/run_prototype_workflow.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            baseline = root / "template-root"
            baseline.mkdir(parents=True, exist_ok=True)
            with mock.patch.dict(module.os.environ, {"PHASEA_REPOSITORY_ROOT": str(baseline)}):
                resolved = module.baseline_repo_root()
                self.assertTrue(os.path.samefile(baseline, resolved))

    def test_resolve_default_scene_should_prefer_repo_prototype_scene_over_manifest_default(self) -> None:
        module = _load_module("prototype_workflow_router_real_scene_preferred", "scripts/python/run_prototype_workflow.py")
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
        module = _load_module("prototype_workflow_router_packaging_current_run", "scripts/python/run_prototype_workflow.py")
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
        module = _load_module("prototype_workflow_router_packaging_latest_slug_fallback", "scripts/python/run_prototype_workflow.py")
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
        module = _load_module("prototype_workflow_router_completion_report_default_scene", "scripts/python/run_prototype_workflow.py")
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

    def test_normalize_payload_should_infer_rpg_game_type_from_unstructured_text(self) -> None:
        module = _load_module("prototype_workflow_router_infer_rpg", "scripts/python/run_prototype_workflow.py")
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
        module = _load_module("prototype_workflow_router_legacy_rpg_specifics", "scripts/python/run_prototype_workflow.py")
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
        module = _load_module("prototype_workflow_router_legacy_rpg_typekit", "scripts/python/run_prototype_workflow.py")
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

    def test_existing_day2_scaffold_should_be_skipped_during_confirmed_rerun(self) -> None:
        module = _load_module("prototype_workflow_router_rerun_skip_scene", "scripts/python/run_prototype_workflow.py")
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

    def test_unexpected_green_red_stage_should_fail_during_confirmed_run(self) -> None:
        module = _load_module("prototype_workflow_router_rerun_fail_red", "scripts/python/run_prototype_workflow.py")
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
                with mock.patch.object(module, "_run", side_effect=fake_run):
                    rc = module.main(["--prototype-file", str(prototype_file), "--confirm", "--stop-after-day", "4"])

        self.assertEqual(1, rc)

    def test_step06_and_step07_should_write_packaging_and_completion_content(self) -> None:
        module = _load_module("prototype_workflow_router_step67_outputs", "scripts/python/run_prototype_workflow.py")
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

    def test_dev_cli_should_expose_prototype_workflow_entry(self) -> None:
        builders = _load_module("dev_cli_builders_module_for_proto_workflow", "scripts/python/dev_cli_builders.py")
        dev_cli = _load_module("dev_cli_module_for_proto_workflow", "scripts/python/dev_cli.py")
        parser = dev_cli.build_parser()
        args = parser.parse_args(["run-prototype-workflow", "--prototype-file", "docs/prototypes/sample.md"])
        cmd = builders.build_run_prototype_workflow_cmd(args)

        self.assertEqual("run-prototype-workflow", args.cmd)
        self.assertIn("scripts/python/run_prototype_workflow.py", cmd)
        self.assertIn("docs/prototypes/sample.md", cmd)


if __name__ == "__main__":
    unittest.main()
