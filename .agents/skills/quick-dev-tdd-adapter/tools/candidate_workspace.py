"""Materialize an isolated candidate workspace from explicit repository paths."""

from __future__ import annotations

import shutil
from pathlib import Path, PurePosixPath
from typing import Iterable


def _relative_path(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("candidate path must be normalized and repository-relative")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or value != path.as_posix():
        raise ValueError("candidate path must be normalized and repository-relative")
    return path


def _contained(root: Path, relative: str) -> Path:
    target = (root / Path(*_relative_path(relative).parts)).resolve()
    target.relative_to(root.resolve())
    return target


def materialize(source_root: Path, candidate_root: Path, paths: Iterable[str], *, remove: Iterable[str] = ()) -> Path:
    """Copy only explicit source paths, then apply candidate-only removals."""
    source = source_root.resolve()
    candidate = candidate_root.resolve()
    if source == candidate:
        raise ValueError("candidate workspace must differ from source workspace")
    if candidate.exists():
        raise FileExistsError(f"candidate workspace already exists: {candidate}")
    candidate.mkdir(parents=True)
    for relative in paths:
        source_path = _contained(source, relative)
        if not source_path.exists():
            raise FileNotFoundError(f"candidate source path is missing: {relative}")
        destination = _contained(candidate, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source_path.is_dir():
            shutil.copytree(
                source_path,
                destination,
                copy_function=shutil.copy2,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
        else:
            shutil.copy2(source_path, destination)
    for relative in remove:
        target = _contained(candidate, relative)
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
    return candidate
