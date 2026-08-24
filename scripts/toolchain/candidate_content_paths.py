"""Classify repository paths for Quick Dev to Acceptance candidate custody."""

from __future__ import annotations

from pathlib import PurePosixPath


CANDIDATE_CONTENT = "candidate-content"
HISTORICAL_EVIDENCE = "historical-evidence"
GENERATED_RUN_EVIDENCE = "generated-run-evidence"


def _normalized(relative: str) -> PurePosixPath:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValueError("candidate content path must be normalized and repository-relative")
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != relative:
        raise ValueError("candidate content path must be normalized and repository-relative")
    return path


def classify_path(relative: str) -> str:
    """Return the one custody class used by Quick Dev and Acceptance."""
    path = _normalized(relative)
    parts = path.parts
    if "knowledge-context.history" in parts or "knowledge-context.freeze.history" in parts:
        return HISTORICAL_EVIDENCE
    if any(part.startswith(("skill-input", "semantic-input")) for part in parts):
        return GENERATED_RUN_EVIDENCE
    return CANDIDATE_CONTENT


def require_candidate_content(paths: list[str]) -> list[str]:
    """Normalize a unique candidate-content path set or reject non-content evidence."""
    normalized = [_normalized(path).as_posix() for path in paths]
    if normalized != sorted(set(normalized)):
        raise ValueError("candidate content paths must be sorted and unique")
    if any(classify_path(path) != CANDIDATE_CONTENT for path in normalized):
        raise ValueError("candidate content paths cannot include historical or generated evidence")
    return normalized
