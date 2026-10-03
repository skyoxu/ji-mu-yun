"""CER coverage for runtime snapshot fail-closed and append-only evidence."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[4] / ".agents" / "skills" / "quick-dev-tdd-adapter" / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from runtime_evidence import create_immutable, current_snapshot  # noqa: E402


@pytest.mark.cer_assertion("A-O-54980B218554-fail-closed-unknown-fact")
def test_unknown_snapshot_root_fails_closed() -> None:
    roots = [{"root_kind": "candidate_tree", "repository_relative_posix_path": "missing", "inclusion_reason": "unknown"}]
    with pytest.raises(ValueError):
        current_snapshot(Path(__file__).resolve().parents[4], roots, source_commit="TEST")


@pytest.mark.cer_assertion("A-O-3C132B7C6354-runtime-evidence-append-boundary")
def test_immutable_evidence_writer_preserves_existing_bytes() -> None:
    target = Path(__file__).with_suffix(".s16-evidence.tmp")
    try:
        create_immutable(target, b"historical\n")
        with pytest.raises(ValueError):
            create_immutable(target, b"overwrite\n")
        assert target.read_bytes() == b"historical\n"
    finally:
        if target.exists():
            target.unlink()
