from __future__ import annotations

import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def _projection():
    from projection_and_segmentation import build_range_projection

    return build_range_projection(
        path="docs/authority.md",
        source=b"alpha\nbeta\ngamma\n",
        start_line=2,
        end_line=3,
        inclusion_reason="changed acceptance constraint",
        changed_set_id="sha256:" + "a" * 64,
        requirement_ids=["ARBE-007"],
        acceptance_ids=["ARBE-A15"],
        policy_identity="sha256:" + "b" * 64,
    )


def test_rejects_projection_range_or_source_mutation() -> None:
    from projection_and_segmentation import ProjectionError, validate_range_projection

    projection = _projection()
    validate_range_projection(projection, b"alpha\nbeta\ngamma\n")
    with pytest.raises(ProjectionError):
        validate_range_projection({**projection, "end_line": 2}, b"alpha\nbeta\ngamma\n")
    with pytest.raises(ProjectionError):
        validate_range_projection(projection, b"alpha\nBETA\ngamma\n")


def test_segment_identity_is_stable_across_retry_and_binds_role() -> None:
    from projection_and_segmentation import build_segment_descriptor

    projection = _projection()
    first = build_segment_descriptor(
        projection=projection,
        review_identity="sha256:" + "c" * 64,
        candidate_identity="sha256:" + "d" * 64,
        closure_identity="sha256:" + "e" * 64,
        role="blind_hunter",
        ordinal=1,
        total=2,
        model_identity="sol-high",
    )
    retry = build_segment_descriptor(
        projection=projection,
        review_identity="sha256:" + "c" * 64,
        candidate_identity="sha256:" + "d" * 64,
        closure_identity="sha256:" + "e" * 64,
        role="blind_hunter",
        ordinal=1,
        total=2,
        model_identity="sol-high",
    )
    changed_role = build_segment_descriptor(
        projection=projection,
        review_identity="sha256:" + "c" * 64,
        candidate_identity="sha256:" + "d" * 64,
        closure_identity="sha256:" + "e" * 64,
        role="edge_case_hunter",
        ordinal=1,
        total=2,
        model_identity="sol-high",
    )

    assert first["identity"] == retry["identity"]
    assert first["identity"] != changed_role["identity"]


def test_rejects_live_or_relative_segment_snapshot(tmp_path) -> None:
    from projection_and_segmentation import ProjectionError, validate_segment_snapshot

    snapshot = tmp_path / "segment.txt"
    snapshot.write_bytes(b"beta\ngamma\n")
    with pytest.raises(ProjectionError):
        validate_segment_snapshot("segment.txt", b"beta\ngamma\n")
    with pytest.raises(ProjectionError):
        validate_segment_snapshot(str(snapshot), b"beta\nGAMMA\n")
    validate_segment_snapshot(str(snapshot), b"beta\ngamma\n")
