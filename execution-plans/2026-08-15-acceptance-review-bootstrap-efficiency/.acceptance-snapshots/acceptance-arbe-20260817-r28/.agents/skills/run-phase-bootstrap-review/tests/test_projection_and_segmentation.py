from __future__ import annotations

import sys
import json
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def _projection():
    from projection_and_segmentation import build_range_projection

    return build_range_projection(
        path="docs/authority.md",
        source=b"alpha\nbeta\ngamma\n",
        start_byte=6,
        end_byte=16,
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
        validate_range_projection({**projection, "end_byte": 10}, b"alpha\nbeta\ngamma\n")
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


def test_projection_uses_zero_based_inclusive_bytes_and_utf8_boundaries() -> None:
    from projection_and_segmentation import ProjectionError, build_range_projection, validate_range_projection

    source = "a\u4e2db\n".encode("utf-8")
    projection = build_range_projection(
        path="docs/authority.md", source=source, start_byte=1, end_byte=3,
        inclusion_reason="required context", changed_set_id="sha256:" + "a" * 64,
        requirement_ids=["ARBE-007"], acceptance_ids=["ARBE-A15"],
        policy_identity="sha256:" + "b" * 64,
    )
    assert projection["extracted_bytes_base64"] == "5Lit"
    validate_range_projection(projection, source)
    with pytest.raises(ProjectionError, match="boundary"):
        build_range_projection(
            path="docs/authority.md", source=source, start_byte=2, end_byte=3,
            inclusion_reason="required context", changed_set_id="sha256:" + "a" * 64,
            requirement_ids=["ARBE-007"], acceptance_ids=["ARBE-A15"],
            policy_identity="sha256:" + "b" * 64,
        )


def test_segment_descriptor_uses_adopted_domain() -> None:
    from projection_and_segmentation import _SEGMENT_DOMAIN

    assert _SEGMENT_DOMAIN == "jimuyun.bootstrap.segment-descriptor.v1"


def test_bootstrap_segment_plan_consumes_byte_projection_and_descriptor(tmp_path) -> None:
    import bootstrap_review

    run_dir = tmp_path / "run"
    snapshot = run_dir / "artifact-view" / "authority.md"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_bytes("a\u4e2db".encode("utf-8"))
    view_path = run_dir / "artifact-view-manifest.json"
    view_path.write_text(json.dumps({"entries": [{
        "originalPath": "docs/authority.md", "snapshotPath": "artifact-view/authority.md",
        "snapshotSha256": bootstrap_review.file_hash(snapshot), "contentKind": "text",
    }]}), encoding="utf-8")
    manifest = {
        "artifacts": [{"artifact": "docs/authority.md"}],
        "artifactView": {"manifestPath": "artifact-view-manifest.json", "manifestHash": bootstrap_review.file_hash(view_path)},
        "inputHash": "sha256:" + "a" * 64, "policyRevision": "test-policy", "processLeasePolicy": {},
        "authorityContextHash": "sha256:" + "b" * 64, "candidateBindingHash": "sha256:" + "c" * 64,
    }
    segments = bootstrap_review.artifact_view_segment_plan(run_dir, manifest, max_segment_bytes=3)
    assert [(item["startByte"], item["endByte"]) for item in segments] == [(0, 3), (4, 4)]
    receipt = bootstrap_review.artifact_view_segment_receipt(segments[0], manifest, "blind_hunter")
    assert receipt["rangeProjectionIdentity"] == segments[0]["rangeProjectionIdentity"]
    assert receipt["segmentDescriptorIdentity"].startswith("sha256:")


def test_rejects_live_or_relative_segment_snapshot(tmp_path) -> None:
    from projection_and_segmentation import ProjectionError, validate_segment_snapshot

    snapshot = tmp_path / "segment.txt"
    snapshot.write_bytes(b"beta\ngamma\n")
    with pytest.raises(ProjectionError):
        validate_segment_snapshot("segment.txt", b"beta\ngamma\n")
    with pytest.raises(ProjectionError):
        validate_segment_snapshot(str(snapshot), b"beta\nGAMMA\n")
    validate_segment_snapshot(str(snapshot), b"beta\ngamma\n")
