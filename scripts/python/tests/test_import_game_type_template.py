#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
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


class ImportGameTypeTemplateTests(unittest.TestCase):
    def test_import_rpg_should_freeze_source_into_repo_template(self) -> None:
        module = _load_module("import_game_type_template", "scripts/python/import_game_type_template.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "repo"
            source = Path(td) / "source"
            (root / "docs" / "prototype-type-kits").mkdir(parents=True, exist_ok=True)
            (root / "Game.Core" / "Prototypes").mkdir(parents=True, exist_ok=True)
            (root / "Game.Core.Tests" / "Prototypes").mkdir(parents=True, exist_ok=True)
            (root / "Tests.Godot" / "tests" / "Prototype" / "DefaultRpgPrototype").mkdir(parents=True, exist_ok=True)
            (source / "Game.Godot" / "Prototypes" / "He-is-Coming" / "Scripts").mkdir(parents=True, exist_ok=True)
            (source / "Game.Godot" / "Prototypes" / "He-is-Coming" / "Assets").mkdir(parents=True, exist_ok=True)
            (source / "Game.Core" / "Prototypes").mkdir(parents=True, exist_ok=True)
            (source / "Game.Core.Tests" / "Prototypes").mkdir(parents=True, exist_ok=True)
            (source / "Tests.Godot" / "tests" / "Prototype" / "HeIsComing").mkdir(parents=True, exist_ok=True)

            (root / "docs" / "prototype-type-kits" / "game-type-template-catalog.json").write_text(
                '{"schema_version":1,"entries":[{"game_type":"rpg","template_id":"default-rpg-template","source_mode":"repo-imported","repo_template_path":"Game.Godot/Prototypes/DefaultRpgTemplate","manifest_path":"docs/prototype-type-kits/default-rpg-template.manifest.json","import_source_path":"C:/gametype/rpgdemo","enabled":true}]}\n',
                encoding="utf-8",
            )
            (root / "docs" / "prototype-type-kits" / "default-rpg-template.manifest.json").write_text(
                '{"schema_version":1,"paths":{"default_scene":"Game.Godot/Prototypes/DefaultRpgTemplate/DefaultRpgPrototype.tscn"}}\n',
                encoding="utf-8",
            )

            (source / "Game.Godot" / "Prototypes" / "He-is-Coming" / "HeIsComingPrototype.tscn").write_text(
                '[gd_scene]\n[ext_resource type="Script" path="res://Game.Godot/Prototypes/He-is-Coming/Scripts/HeIsComingPrototype.cs" id="1"]\n[node name="HeIsComingPrototype" type="Node2D"]\n',
                encoding="utf-8",
            )
            (source / "Game.Godot" / "Prototypes" / "He-is-Coming" / "Scripts" / "HeIsComingPrototype.cs").write_text(
                'public partial class HeIsComingPrototype : Node2D {}\n',
                encoding="utf-8",
            )
            (source / "Game.Godot" / "Prototypes" / "He-is-Coming" / "Assets" / "map_player.png").write_bytes(b"png")
            (source / "Game.Core" / "Prototypes" / "HeIsComingPrototypeLoop.cs").write_text(
                'public sealed class HeIsComingPrototypeLoop {}\npublic sealed record HeIsComingPrototypeState(int StepIndex);\n',
                encoding="utf-8",
            )
            (source / "Game.Core.Tests" / "Prototypes" / "HeisComingPrototypeLoopTests.cs").write_text(
                'public class HeisComingPrototypeLoopTests {}\n',
                encoding="utf-8",
            )
            (source / "Tests.Godot" / "tests" / "Prototype" / "HeIsComing" / "test_he_is_coming_scene.gd").write_text(
                'extends "res://addons/gdUnit4/src/GdUnitTestSuite.gd"\n',
                encoding="utf-8",
            )

            rc = module.main(["--game-type", "rpg", "--source-root", str(source), "--repo-root", str(root)])

            self.assertEqual(0, rc)
            self.assertTrue((root / "Game.Godot" / "Prototypes" / "DefaultRpgTemplate" / "DefaultRpgPrototype.tscn").exists())
            self.assertTrue((root / "Game.Godot" / "Prototypes" / "DefaultRpgTemplate" / "Scripts" / "DefaultRpgPrototype.cs").exists())
            self.assertTrue((root / "Game.Core" / "Prototypes" / "DefaultRpgPrototypeLoop.cs").exists())
            self.assertTrue((root / "Game.Core.Tests" / "Prototypes" / "DefaultRpgPrototypeLoopTests.cs").exists())
            self.assertTrue((root / "Tests.Godot" / "tests" / "Prototype" / "DefaultRpgPrototype" / "test_default_rpg_prototype_scene.gd").exists())

            manifest = json.loads((root / "docs" / "prototype-type-kits" / "default-rpg-template.manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("Game.Godot/Prototypes/DefaultRpgTemplate/DefaultRpgPrototype.tscn", manifest["paths"]["default_scene"])


if __name__ == "__main__":
    unittest.main()
