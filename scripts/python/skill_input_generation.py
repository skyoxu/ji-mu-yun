"""Immutable generation publication primitive."""

from __future__ import annotations

from pathlib import Path


def publish_generation(root: Path, *, generation_id: str, content: bytes) -> Path:
    if not isinstance(generation_id, str) or not generation_id:
        raise ValueError("generation_id is invalid")
    if not isinstance(content, bytes):
        raise ValueError("content is invalid")
    generation = root / "generations" / generation_id
    generation.mkdir(parents=True, exist_ok=False)
    (generation / "content.bin").write_bytes(content)
    return generation
