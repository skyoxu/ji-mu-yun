"""Approval-gated retention planning."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def plan_retention(root: Path, *, dry_run: bool = True) -> dict[str, Any]:
    if not isinstance(root, Path):
        raise ValueError("retention root is invalid")
    return {"root": root.as_posix(), "mode": "dry-run" if dry_run else "apply", "candidates": []}


def apply_retention(root: Path, *, approval: object | None) -> dict[str, str]:
    if not isinstance(root, Path):
        raise ValueError("retention root is invalid")
    if approval is None:
        return {"status": "approval-required"}
    return {"status": "no-op"}
