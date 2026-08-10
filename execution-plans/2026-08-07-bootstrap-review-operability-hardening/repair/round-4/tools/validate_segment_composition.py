from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
MODULE_PATH = (
    REPOSITORY_ROOT
    / ".agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py"
)
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location("broh_round4_bootstrap_review", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Bootstrap review module is unavailable")
BOOTSTRAP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BOOTSTRAP)


def main() -> int:
    digest = "sha256:" + "1" * 64
    manifest = {
        "artifactView": {"manifestHash": digest},
        "artifacts": [{"artifact": "example.py", "sha256": digest}],
    }
    segments = [
        {
            "segmentId": "sha256:" + str(index) * 64,
            "ordinal": index,
            "totalSegments": 2,
            "originalPath": "example.py",
            "snapshotPath": "artifact-view/files/example.py",
            "artifactSha256": digest,
            "startLine": index,
            "endLine": index,
            "sizeBytes": 1,
            "contentSha256": "sha256:" + str(index + 2) * 64,
        }
        for index in (1, 2)
    ]
    role = "blind_hunter"
    receipts = [
        BOOTSTRAP.artifact_view_segment_receipt(segment, manifest, role)
        for segment in segments
    ]
    aggregate = BOOTSTRAP.validate_artifact_view_segment_receipts(
        receipts, segments, manifest, role
    )
    if aggregate != BOOTSTRAP.artifact_view_read_receipt(manifest):
        raise RuntimeError("segment receipt composition is invalid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
