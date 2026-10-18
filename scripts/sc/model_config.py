"""Resolve the shared model setting alongside the active Codex CLI config."""

from __future__ import annotations

import os
from pathlib import Path
import re
import tomllib


MODEL_FILE_NAME = "model-routing.toml"
MODEL_CONFIG_KEY = "CODEX_MODEL"
MODEL_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def is_valid_model_id(model: object) -> bool:
    return isinstance(model, str) and MODEL_ID_PATTERN.fullmatch(model) is not None


def codex_config_dir() -> Path:
    configured_home = os.environ.get("CODEX_HOME")
    return Path(configured_home).expanduser() if configured_home else Path.home() / ".codex"


def load_model(*, codex_dir: Path | None = None) -> str:
    """Prefer the adjacent model file; fall back to config.toml when it is absent."""
    directory = codex_dir or codex_config_dir()
    model_path = directory / MODEL_FILE_NAME
    config_path = directory / "config.toml"
    selected = model_path if model_path.is_file() else config_path
    if not selected.is_file():
        raise ValueError("Codex model configuration is missing")
    try:
        config = tomllib.loads(selected.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise ValueError("Codex model configuration is unreadable") from exc
    model = config.get("model")
    if not is_valid_model_id(model):
        raise ValueError("Codex model configuration must define a valid model string")
    return model
