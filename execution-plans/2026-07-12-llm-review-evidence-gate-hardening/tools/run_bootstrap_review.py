#!/usr/bin/env python3
"""Revision-bound compatibility adapter for the repository Bootstrap Skill."""

from pathlib import Path


EXPECTED_CONTROL_PLANE_REVISION = "bootstrap-control-plane.v2"
CORE_PATH = (
    Path(__file__).resolve().parents[3]
    / ".agents"
    / "skills"
    / "run-phase-bootstrap-review"
    / "scripts"
    / "bootstrap_review.py"
)

if not CORE_PATH.is_file():
    raise RuntimeError(f"Bootstrap Review control plane is missing: {CORE_PATH}")

_adapter_name = __name__
_adapter_file = __file__
__name__ = "bootstrap_review_control_plane"
__file__ = str(CORE_PATH)
exec(compile(CORE_PATH.read_bytes(), str(CORE_PATH), "exec"), globals(), globals())
__name__ = _adapter_name
__file__ = _adapter_file

if CONTROL_PLANE_REVISION != EXPECTED_CONTROL_PLANE_REVISION:
    raise RuntimeError(
        "Bootstrap Review adapter revision mismatch: "
        f"expected {EXPECTED_CONTROL_PLANE_REVISION}, got {CONTROL_PLANE_REVISION}"
    )

if __name__ == "__main__":
    main()
