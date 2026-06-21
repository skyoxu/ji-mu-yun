#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.python.tests.prototype_workflow_router_test_support import load_module

class PrototypeWorkflowRouterDay4ImplementationTests(unittest.TestCase):
    def test_day4_codex_nonzero_should_continue_when_outputs_are_valid(self) -> None:
        module = load_module("prototype_workflow_router_day4_recover", "scripts/python/run_prototype_workflow.py")
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

            codex_calls: list[dict[str, object]] = []

            def fake_run_llm_exec(**kwargs):
                codex_calls.append(kwargs)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text("Day 4 implementation completed.\n", encoding="utf-8")
                return 1, "tool failed but files are already valid\n", ["codex", "exec", "-"]

            with mock.patch.object(module, "run_llm_exec", side_effect=fake_run_llm_exec):
                rc, output = module._run_day4_codex_implementation(
                    root=root,
                    payload={"slug": slug, "success_criteria": ["done"]},
                    record_file="docs/prototypes/2026-05-15-phase-a-real-e2e-loop.md",
                )

        self.assertEqual(0, rc)
        self.assertIn("Day 4 implementation completed.", output)
        self.assertIn("DAY4_IMPLEMENTATION_RECOVERED codex_exit_code=1", output)
        self.assertEqual("workspace-write", codex_calls[0]["codex_sandbox"])
        self.assertEqual("-o", codex_calls[0]["codex_output_arg"])
        self.assertEqual("--cd", codex_calls[0]["codex_cd_arg"])
        self.assertIn("prototype lane 的 Day 4 最小实现步骤", str(codex_calls[0]["prompt"]))

    def test_day4_codex_should_apply_fallback_when_only_scaffold_script_remains(self) -> None:
        module = load_module("prototype_workflow_router_day4_fallback", "scripts/python/run_prototype_workflow.py")
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

            codex_calls: list[dict[str, object]] = []

            def fake_run_llm_exec(**kwargs):
                codex_calls.append(kwargs)
                module.write_text(out_path, "Day 4 implementation incomplete.\n")
                return 0, "codex left scaffold in place\n", ["codex", "exec", "-"]

            with mock.patch.object(module, "run_llm_exec", side_effect=fake_run_llm_exec):
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
        self.assertEqual("workspace-write", codex_calls[0]["codex_sandbox"])
        self.assertEqual("-o", codex_calls[0]["codex_output_arg"])
        self.assertIn("prototype lane 的 Day 4 最小实现步骤", str(codex_calls[0]["prompt"]))

    def test_day4_normalizes_godot_namespace_aliases_for_generated_scripts(self) -> None:
        module = load_module("prototype_workflow_router_godot_namespace_aliases", "scripts/python/run_prototype_workflow.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            slug = "mir"
            class_name = "MirPrototype"
            script_path = root / "Game.Godot" / "Prototypes" / slug / "Scripts" / f"{class_name}.cs"
            module.write_text(
                script_path,
                "\n".join(
                    [
                        "using Godot;",
                        "",
                        "namespace Game.Godot.Prototypes;",
                        "",
                        f"public partial class {class_name} : Node2D",
                        "{",
                        "    public Godot.Collections.Array<string> RewardOptions",
                        "    {",
                        "        get",
                        "        {",
                        "            var values = new Godot.Collections.Array<string>();",
                        "            return values;",
                        "        }",
                        "    }",
                        "}",
                        "",
                    ]
                ),
            )

            changed = module._normalize_godot_csharp_namespace_aliases(root)
            rewritten = module.read_text(script_path, errors="ignore")

        self.assertEqual([f"Game.Godot/Prototypes/{slug}/Scripts/{class_name}.cs"], changed)
        self.assertIn("public global::Godot.Collections.Array<string> RewardOptions", rewritten)
        self.assertIn("new global::Godot.Collections.Array<string>()", rewritten)
        self.assertNotIn("public Godot.Collections.Array<string>", rewritten)


if __name__ == "__main__":
    unittest.main()
