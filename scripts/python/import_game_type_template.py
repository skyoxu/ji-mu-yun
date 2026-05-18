#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
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


def read_text(path: Path) -> str:
    with open(to_windows_extended_path(path.resolve()), "r", encoding="utf-8") as handle:
        return handle.read()


def write_text(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    with open(to_windows_extended_path(path.resolve()), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def write_json(path: Path, payload: object) -> None:
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def copy_file(src: Path, dst: Path) -> None:
    ensure_dir(dst.parent)
    shutil.copy2(to_windows_extended_path(src.resolve()), to_windows_extended_path(dst.resolve()))


def load_catalog(root: Path) -> dict[str, object]:
    catalog_path = root / "docs" / "prototype-type-kits" / "game-type-template-catalog.json"
    if not catalog_path.exists():
        raise FileNotFoundError(f"catalog missing: {catalog_path}")
    return json.loads(read_text(catalog_path))


def find_entry(catalog: dict[str, object], game_type: str) -> dict[str, object]:
    for item in list(catalog.get("entries") or []):
        if isinstance(item, dict) and str(item.get("game_type") or "").strip().lower() == game_type.lower():
            return item
    raise KeyError(f"game type not registered: {game_type}")


def rewrite_slug_text(text: str) -> str:
    replacements = [
        ("He-is-Coming", "DefaultRpgTemplate"),
        ("HeIsComingPrototype", "DefaultRpgPrototype"),
        ("HeIsComingPrototypeLoop", "DefaultRpgPrototypeLoop"),
        ("HeIsComingPrototypeState", "DefaultRpgPrototypeState"),
        ("HeIsComingEncounterResult", "DefaultRpgEncounterResult"),
        ("HeIsComingEncounter", "DefaultRpgEncounter"),
        ("HeIsComingPrototypeResult", "DefaultRpgPrototypeResult"),
        ("res://Game.Godot/Prototypes/He-is-Coming/", "res://Game.Godot/Prototypes/DefaultRpgTemplate/"),
        ("res://Prototypes/He-is-Coming/Assets/", "res://Prototypes/DefaultRpgTemplate/Assets/"),
        ("res://Game.Godot/Prototypes/He-is-Coming/Assets/", "res://Game.Godot/Prototypes/DefaultRpgTemplate/Assets/"),
        ("魔王将至  Prototype", "Default RPG Prototype"),
        ("He-is-Coming", "default-rpg-template")
    ]
    updated = text
    for old, new in replacements:
        updated = updated.replace(old, new)
    updated = re.sub(r"\bHeisComingPrototypeLoopTests\b", "DefaultRpgPrototypeLoopTests", updated)
    return updated


def import_rpg(root: Path, source_root: Path, entry: dict[str, object]) -> dict[str, object]:
    repo_template_root = root / str(entry["repo_template_path"])
    manifest_path = root / str(entry["manifest_path"])

    source_scene_root = source_root / "Game.Godot" / "Prototypes" / "He-is-Coming"
    source_core_loop = source_root / "Game.Core" / "Prototypes" / "HeIsComingPrototypeLoop.cs"
    source_core_test = source_root / "Game.Core.Tests" / "Prototypes" / "HeisComingPrototypeLoopTests.cs"
    source_gdunit_test = source_root / "Tests.Godot" / "tests" / "Prototype" / "HeIsComing" / "test_he_is_coming_scene.gd"

    if not source_scene_root.exists():
        raise FileNotFoundError(f"missing source scene root: {source_scene_root}")

    if repo_template_root.exists():
        shutil.rmtree(to_windows_extended_path(repo_template_root.resolve()))
    ensure_dir(repo_template_root)

    for path in source_scene_root.rglob("*"):
        if path.is_dir():
            continue
        rel = path.relative_to(source_scene_root)
        target = repo_template_root / rel
        if rel.name == "HeIsComingPrototype.tscn":
            target = repo_template_root / "DefaultRpgPrototype.tscn"
        elif rel.parts[:1] == ("Scripts",) and rel.name == "HeIsComingPrototype.cs":
            target = repo_template_root / "Scripts" / "DefaultRpgPrototype.cs"
        if path.suffix.lower() in {".tscn", ".cs"}:
            write_text(target, rewrite_slug_text(read_text(path)))
        else:
            copy_file(path, target)

    target_core_loop = root / "Game.Core" / "Prototypes" / "DefaultRpgPrototypeLoop.cs"
    target_core_test = root / "Game.Core.Tests" / "Prototypes" / "DefaultRpgPrototypeLoopTests.cs"
    target_gdunit_dir = root / "Tests.Godot" / "tests" / "Prototype" / "DefaultRpgPrototype"
    target_gdunit_test = target_gdunit_dir / "test_default_rpg_prototype_scene.gd"

    write_text(target_core_loop, rewrite_slug_text(read_text(source_core_loop)))
    write_text(target_core_test, rewrite_slug_text(read_text(source_core_test)))
    write_text(target_gdunit_test, rewrite_slug_text(read_text(source_gdunit_test)))

    manifest = json.loads(read_text(manifest_path))
    manifest["game_type"] = "rpg"
    manifest["slug"] = "default-rpg-template"
    manifest["label"] = "Imported RPG Template"
    manifest["description"] = "Imported from offline RPG template source and frozen into the repo-local prototype lane."
    manifest.setdefault("paths", {})
    manifest["paths"]["asset_pack_root"] = "Game.Godot/Prototypes/DefaultRpgTemplate/Assets/"
    manifest["paths"]["scene_template_root"] = "Game.Godot/Prototypes/DefaultRpgTemplate/"
    manifest["paths"]["default_scene"] = "Game.Godot/Prototypes/DefaultRpgTemplate/DefaultRpgPrototype.tscn"
    manifest["paths"]["default_script"] = "Game.Godot/Prototypes/DefaultRpgTemplate/Scripts/DefaultRpgPrototype.cs"
    manifest["paths"]["core_loop"] = "Game.Core/Prototypes/DefaultRpgPrototypeLoop.cs"
    manifest["paths"]["core_loop_test"] = "Game.Core.Tests/Prototypes/DefaultRpgPrototypeLoopTests.cs"
    manifest["paths"]["godot_scene_test"] = "Tests.Godot/tests/Prototype/DefaultRpgPrototype/test_default_rpg_prototype_scene.gd"
    write_json(manifest_path, manifest)

    return {
        "game_type": "rpg",
        "source_root": str(source_root),
        "repo_template_root": str(repo_template_root),
        "manifest_path": str(manifest_path),
        "imported_files": [
            "Game.Godot/Prototypes/DefaultRpgTemplate/**",
            "Game.Core/Prototypes/DefaultRpgPrototypeLoop.cs",
            "Game.Core.Tests/Prototypes/DefaultRpgPrototypeLoopTests.cs",
            "Tests.Godot/tests/Prototype/DefaultRpgPrototype/test_default_rpg_prototype_scene.gd"
        ]
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import an offline game-type template into the repo-local prototype baseline.")
    parser.add_argument("--game-type", required=True)
    parser.add_argument("--source-root", default="")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--out-json", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.repo_root).resolve() if str(args.repo_root).strip() else repo_root()
    catalog = load_catalog(root)
    entry = find_entry(catalog, str(args.game_type).strip().lower())
    source_root = Path(args.source_root).resolve() if str(args.source_root).strip() else Path(str(entry.get("import_source_path") or "")).resolve()
    if not source_root.exists():
        raise FileNotFoundError(f"source root missing: {source_root}")

    if str(args.game_type).strip().lower() != "rpg":
        raise NotImplementedError("only rpg is supported in phase a")

    result = import_rpg(root, source_root, entry)
    if str(args.out_json).strip():
        write_json(Path(args.out_json).resolve(), result)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
