#!/usr/bin/env python3
"""Create a minimal Godot prototype scene scaffold under Game.Godot/Prototypes."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def to_windows_extended_path(path: Path) -> str:
    raw = str(path)
    if os.name != "nt":
        return raw
    if raw.startswith("\\\\?\\"):
        return raw
    if raw.startswith("\\\\"):
        return "\\\\?\\UNC\\" + raw[2:]
    return "\\\\?\\" + raw


def ensure_dir(path: Path) -> None:
    os.makedirs(to_windows_extended_path(path.resolve()), exist_ok=True)


def write_text(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    with open(to_windows_extended_path(path.resolve()), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def write_json(path: Path, payload: dict[str, object]) -> None:
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def sanitize_slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", str(value or "").strip())
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-_")
    return cleaned or "prototype"


def slug_to_pascal(slug: str) -> str:
    parts = [part for part in re.split(r"[-_]+", slug) if part]
    return "".join(part[:1].upper() + part[1:] for part in parts) or "Prototype"


def _bool_arg(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def normalize_engine_recommendation(args: argparse.Namespace) -> dict[str, object]:
    backend = str(getattr(args, "engine_backend", "") or "none").strip() or "none"
    apply_mode = str(getattr(args, "engine_apply_mode", "") or "recommend_only").strip() or "recommend_only"
    confidence = str(getattr(args, "engine_confidence", "") or "low").strip() or "low"
    install_target = str(getattr(args, "engine_install_target", "") or "project_local_addon").strip() or "project_local_addon"
    reason = str(getattr(args, "engine_reason", "") or "").strip()
    if not reason:
        reason = "No engine-specific physics backend was recommended for this prototype scaffold."
    requires_plugin = _bool_arg(str(getattr(args, "engine_requires_plugin", "") or "false"))
    if backend in {"rapier_2d", "rapier_3d"}:
        requires_plugin = True
        if apply_mode == "auto_apply_prototype_only":
            apply_mode = "confirm_apply"
    return {
        "domain": "physics",
        "recommended_backend": backend,
        "confidence": confidence,
        "reason": reason,
        "requires_plugin": requires_plugin,
        "apply_mode": apply_mode,
        "scope": "prototype_only",
        "install_target": install_target,
    }


def render_script(*, class_name: str, scene_root: str) -> str:
    base_type = f"global::Godot.{scene_root}"
    state_class_name = f"{class_name}State"
    system_class_name = f"{class_name}System"
    return "\n".join(
        [
            "using Game.Godot.Prototypes.Components;",
            "using Game.Godot.Prototypes.Data;",
            "using Game.Godot.Prototypes.Systems;",
            "",
            "namespace Game.Godot.Prototypes;",
            "",
            f"public partial class {class_name} : {base_type}",
            "{",
            f"    private readonly {system_class_name} _system = new();",
            f"    private {state_class_name} _state = new(\"boot\", \"Booting\", \"Waiting for prototype setup.\");",
            "",
            "    public override void _Ready()",
            "    {",
            "        _state = _system.CreateInitialState();",
            "",
            "        var hudView = GetNodeOrNull<HudView>(\"HudView\");",
            "        hudView?.RenderStatus(_state.StatusText, _state.HintText);",
            "",
            '        global::Godot.GD.Print("Prototype scaffold ready: replace this scene with the minimum playable loop.");',
            "    }",
            "}",
            "",
        ]
    )


def render_component_script(*, namespace_suffix: str, class_name: str, base_type: str, body_lines: list[str]) -> str:
    lines = [
        f"namespace Game.Godot.Prototypes.{namespace_suffix};",
        "",
        f"public partial class {class_name} : {base_type}",
        "{",
    ]
    lines.extend(f"    {line}" if line else "" for line in body_lines)
    lines += [
        "}",
        "",
    ]
    return "\n".join(lines)


def render_state_script(*, class_name: str) -> str:
    return "\n".join(
        [
            "namespace Game.Godot.Prototypes.Data;",
            "",
            f"public sealed record {class_name}(string Phase, string StatusText, string HintText);",
            "",
        ]
    )


def render_system_script(*, class_name: str, state_class_name: str) -> str:
    return "\n".join(
        [
            "using Game.Godot.Prototypes.Data;",
            "",
            "namespace Game.Godot.Prototypes.Systems;",
            "",
            f"public sealed class {class_name}",
            "{",
            f"    public {state_class_name} CreateInitialState()",
            "    {",
            f'        return new {state_class_name}(\"ready\", \"Ready\", \"Replace this scaffold with the minimum playable loop.\");',
            "    }",
            "",
            f"    public {state_class_name} Advance({state_class_name} state)",
            "    {",
            "        return state with { Phase = \"next-step\", StatusText = \"Advanced\", HintText = \"Implement the first readable player action here.\" };",
            "    }",
            "}",
            "",
        ]
    )


def render_view_script(*, class_name: str) -> str:
    return render_component_script(
        namespace_suffix="Components",
        class_name=class_name,
        base_type="global::Godot.Node",
        body_lines=[
            "private string _lastStatus = string.Empty;",
            "",
            "public override void _Ready()",
            "{",
            "}",
            "",
            "public void RenderStatus(string statusText, string hintText)",
            "{",
            "    _lastStatus = string.IsNullOrWhiteSpace(hintText) ? statusText : $\"{statusText} - {hintText}\";",
            "}",
            "",
            "public string LastStatus => _lastStatus;",
        ],
    )


def render_scene(*, class_name: str, scene_root: str, script_res_path: str, hud_view_res_path: str) -> str:
    lines = [
        "[gd_scene load_steps=3 format=3]",
        "",
        f'[ext_resource type="Script" path="{script_res_path}" id="1"]',
        f'[ext_resource type="Script" path="{hud_view_res_path}" id="2"]',
        "",
        f'[node name="{class_name}" type="{scene_root}"]',
        'script = ExtResource("1")',
    ]
    if scene_root == "Control":
        lines += [
            "layout_mode = 3",
            "anchors_preset = 15",
            "anchor_right = 1.0",
            "anchor_bottom = 1.0",
            "grow_horizontal = 2",
            "grow_vertical = 2",
            "",
            '[node name="PrototypeHint" type="Label" parent="."]',
            "layout_mode = 0",
            "offset_left = 24.0",
            "offset_top = 24.0",
            "offset_right = 640.0",
            "offset_bottom = 80.0",
            'text = "Replace this scaffold with your minimum playable loop."',
            "",
            '[node name="HudView" type="Node" parent="."]',
            'script = ExtResource("2")',
        ]
    else:
        lines += [
            "",
            '[node name="HudView" type="Node" parent="."]',
            "script = ExtResource(\"2\")",
            "",
            '[node name="PrototypeLoop" type="Node2D" parent="."]',
        ]
    lines.append("")
    return "\n".join(lines)


def render_dotnet_test(*, class_name: str) -> str:
    loop_class_name = f"{class_name}Loop"
    return "\n".join(
        [
            "using Game.Core.Prototypes;",
            "using Xunit;",
            "",
            "namespace Game.Core.Tests.Prototypes;",
            "",
            f"public class {class_name}LoopTests",
            "{",
            "    [Fact]",
            "    public void ShouldDescribePlayableLoop_WhenPrototypeImplementationIsReady()",
            "    {",
            f"        var loop = new {loop_class_name}();",
            "        var summary = loop.DescribePlayableLoop();",
            "",
            "        Assert.False(string.IsNullOrWhiteSpace(summary));",
            '        Assert.DoesNotContain("TODO", summary);',
            "    }",
            "}",
            "",
        ]
    )


def render_gdunit_test(*, scene_res_path: str, scene_root: str) -> str:
    expected_child = "PrototypeHint" if scene_root == "Control" else "PrototypeLoop"
    return "\n".join(
        [
            'extends "res://addons/gdUnit4/src/GdUnitTestSuite.gd"',
            "",
            "func _spawn_scene():",
            f'    var scene := preload("{scene_res_path}").instantiate()',
            "    add_child(auto_free(scene))",
            "    await get_tree().process_frame",
            "    await get_tree().process_frame",
            "    return scene",
            "",
            "func test_prototype_scene_instantiates() -> void:",
            "    var scene = await _spawn_scene()",
            "    assert_bool(scene.is_inside_tree()).is_true()",
            "",
            "func test_prototype_scene_contains_prototype_loop_node() -> void:",
            "    var scene = await _spawn_scene()",
            f'    assert_object(scene.get_node_or_null("{expected_child}")).is_not_null()',
            "",
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Create a minimal prototype scene scaffold.")
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--slug", required=True)
    ap.add_argument("--prototype-root", default="Game.Godot/Prototypes")
    ap.add_argument("--scene-root", default="Control", choices=["Control", "Node2D"])
    ap.add_argument("--engine-backend", default="none")
    ap.add_argument("--engine-apply-mode", default="recommend_only")
    ap.add_argument("--engine-confidence", default="low")
    ap.add_argument("--engine-reason", default="")
    ap.add_argument("--engine-requires-plugin", default="false")
    ap.add_argument("--engine-install-target", default="project_local_addon")
    ap.add_argument("--force", action="store_true", help="Overwrite the scaffold when files already exist.")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = (Path(args.repo_root).resolve() if str(args.repo_root or "").strip() else repo_root())
    slug = sanitize_slug(args.slug)
    pascal = slug_to_pascal(slug)
    class_name = f"{pascal}Prototype"
    prototype_dir = root / args.prototype_root / slug
    scene_path = prototype_dir / f"{class_name}.tscn"
    script_path = prototype_dir / "Scripts" / f"{class_name}.cs"
    components_dir = prototype_dir / "Scripts" / "Components"
    systems_dir = prototype_dir / "Scripts" / "Systems"
    data_dir = prototype_dir / "Scripts" / "Data"
    assets_dir = prototype_dir / "Assets"
    hud_view_path = components_dir / "HudView.cs"
    map_view_path = components_dir / "MapView.cs"
    battle_view_path = components_dir / "BattleView.cs"
    reward_view_path = components_dir / "RewardView.cs"
    log_view_path = components_dir / "LogView.cs"
    state_path = data_dir / f"{class_name}State.cs"
    system_path = systems_dir / f"{class_name}System.cs"
    engine_recommendation_path = prototype_dir / "engine-recommendation.json"
    dotnet_test_path = root / "Game.Core.Tests" / "Prototypes" / f"{class_name}LoopTests.cs"
    gdunit_test_path = root / "Tests.Godot" / "tests" / "Prototype" / class_name / f"test_{slug.replace('-', '_')}_prototype_scene.gd"
    scene_res_path = f"res://{args.prototype_root.strip('/').replace(chr(92), '/')}/{slug}/{class_name}.tscn"
    scaffold_exists = scene_path.exists() or script_path.exists()

    if not scaffold_exists or args.force:
        ensure_dir(assets_dir)
        ensure_dir(components_dir)
        ensure_dir(systems_dir)
        ensure_dir(data_dir)
        script_res_path = f"res://{args.prototype_root.strip('/').replace(chr(92), '/')}/{slug}/Scripts/{class_name}.cs"
        hud_view_res_path = f"res://{args.prototype_root.strip('/').replace(chr(92), '/')}/{slug}/Scripts/Components/HudView.cs"
        write_text(script_path, render_script(class_name=class_name, scene_root=str(args.scene_root)))
        write_text(
            scene_path,
            render_scene(
                class_name=class_name,
                scene_root=str(args.scene_root),
                script_res_path=script_res_path,
                hud_view_res_path=hud_view_res_path,
            ),
        )
        write_text(hud_view_path, render_view_script(class_name="HudView"))
        write_text(map_view_path, render_view_script(class_name="MapView"))
        write_text(battle_view_path, render_view_script(class_name="BattleView"))
        write_text(reward_view_path, render_view_script(class_name="RewardView"))
        write_text(log_view_path, render_view_script(class_name="LogView"))
        write_text(state_path, render_state_script(class_name=f"{class_name}State"))
        write_text(system_path, render_system_script(class_name=f"{class_name}System", state_class_name=f"{class_name}State"))
        write_json(engine_recommendation_path, normalize_engine_recommendation(args))

    if args.force or not dotnet_test_path.exists():
        write_text(dotnet_test_path, render_dotnet_test(class_name=class_name))
    if args.force or not gdunit_test_path.exists():
        ensure_dir(gdunit_test_path.parent)
        write_text(gdunit_test_path, render_gdunit_test(scene_res_path=scene_res_path, scene_root=str(args.scene_root)))

    if scaffold_exists and not args.force:
        write_json(engine_recommendation_path, normalize_engine_recommendation(args))
        print(
            f"PROTOTYPE_SCENE ERROR: scaffold already exists for slug={slug}; pass --force to overwrite.",
            file=sys.stderr,
        )
        return 1

    print(
        "PROTOTYPE_SCENE created "
        f"scene={scene_path.relative_to(root).as_posix()} "
        f"script={script_path.relative_to(root).as_posix()} "
        f"dotnet_test={dotnet_test_path.relative_to(root).as_posix()} "
        f"gdunit_test={gdunit_test_path.relative_to(root).as_posix()}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
