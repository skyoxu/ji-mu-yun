#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON_DIR = REPO_ROOT / "scripts" / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))


def load_module(name: str, relative_path: str):
    path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"failed to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def rpg_battle_scene_contract_nodes() -> str:
    return (
        "[node name=\"BattleStatusLabel\" type=\"Label\" parent=\"CanvasLayer/UI/BattleScene\"]\n"
        "[node name=\"BattleLogLabel\" type=\"Label\" parent=\"CanvasLayer/UI/BattleScene\"]\n"
        "[node name=\"ActionsVBox\" type=\"VBoxContainer\" parent=\"CanvasLayer/UI/BattleScene\"]\n"
        "[node name=\"AttackButton\" type=\"Button\" parent=\"CanvasLayer/UI/BattleScene/ActionsVBox\"]\n"
        "[node name=\"RetryButton\" type=\"Button\" parent=\"CanvasLayer/UI/BattleScene/ActionsVBox\"]\n"
        "[node name=\"RewardVBox\" type=\"VBoxContainer\" parent=\"CanvasLayer/UI/BattleScene\"]\n"
        "[node name=\"RewardInfoLabel\" type=\"Label\" parent=\"CanvasLayer/UI/BattleScene/RewardVBox\"]\n"
        "[node name=\"RewardButton1\" type=\"Button\" parent=\"CanvasLayer/UI/BattleScene/RewardVBox\"]\n"
        "[node name=\"RewardButton2\" type=\"Button\" parent=\"CanvasLayer/UI/BattleScene/RewardVBox\"]\n"
        "[node name=\"RewardButton3\" type=\"Button\" parent=\"CanvasLayer/UI/BattleScene/RewardVBox\"]\n"
    )


def rpg_battle_script_contract_bindings() -> str:
    return (
        "GetNode<Label>(\"CanvasLayer/UI/BattleScene/BattleStatusLabel\"); "
        "GetNode<Label>(\"CanvasLayer/UI/BattleScene/BattleLogLabel\"); "
        "GetNode<Button>(\"CanvasLayer/UI/BattleScene/ActionsVBox/AttackButton\"); "
        "GetNode<Button>(\"CanvasLayer/UI/BattleScene/ActionsVBox/RetryButton\"); "
        "GetNode<Label>(\"CanvasLayer/UI/BattleScene/RewardVBox/RewardInfoLabel\"); "
        "GetNode<Button>(\"CanvasLayer/UI/BattleScene/RewardVBox/RewardButton1\"); "
        "GetNode<Button>(\"CanvasLayer/UI/BattleScene/RewardVBox/RewardButton2\"); "
        "GetNode<Button>(\"CanvasLayer/UI/BattleScene/RewardVBox/RewardButton3\"); "
    )
