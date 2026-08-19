"""Resolve a generation pointer only after a complete publication."""

from __future__ import annotations

import json
from pathlib import Path


def resolve_current(root: Path) -> dict[str, str] | None:
    pointer = root / "current.v1.json"
    if not pointer.is_file():
        return None
    value = json.loads(pointer.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) and isinstance(value.get("generation_id"), str) else None
