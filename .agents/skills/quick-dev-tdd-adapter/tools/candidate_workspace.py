"""Materialize an isolated candidate workspace from explicit repository paths."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.toolchain.candidate_content_paths import CANDIDATE_CONTENT, classify_path


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


def _sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and value.startswith("sha256:")
        and len(value) == 71
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def verify_candidate_external_trust(
    candidate_identity: Mapping[str, Any],
    independent_verification: Mapping[str, Any] | None = None,
) -> bool:
    """Accept only a separately supplied, integrity-bound trust verification.

    Candidate metadata can identify what must be checked, but cannot attest to
    itself.  The caller must obtain ``independent_verification`` from a source
    outside the candidate and bind it to the exact candidate identity.
    """
    if not isinstance(candidate_identity, Mapping) or not isinstance(independent_verification, Mapping):
        return False
    head = candidate_identity.get("head")
    contract_hash = candidate_identity.get("contract_hash")
    validator_hash = candidate_identity.get("validator_hash")
    if not isinstance(head, str) or not head or not _sha256(contract_hash) or not _sha256(validator_hash):
        return False
    source_id = independent_verification.get("source_id")
    source_hash = independent_verification.get("source_hash")
    outcome = independent_verification.get("outcome")
    verifier = independent_verification.get("verified_by")
    if (
        not isinstance(source_id, str)
        or not source_id
        or not _sha256(source_hash)
        or outcome != "passed"
        or not isinstance(verifier, str)
        or not verifier
        or verifier in {"candidate", "self"}
    ):
        return False
    return (
        independent_verification.get("candidate_head") == head
        and independent_verification.get("contract_hash") == contract_hash
        and independent_verification.get("validator_hash") == validator_hash
    )


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
        if classify_path(relative) != CANDIDATE_CONTENT:
            raise ValueError("candidate content cannot include historical or generated evidence")
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
