"""Refactor Acceptance projection into the workflow model router."""

from __future__ import annotations

import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SC_ROOT = REPOSITORY_ROOT / "scripts" / "sc"
if str(SC_ROOT) not in sys.path:
    sys.path.insert(0, str(SC_ROOT))

import workflow_model_routing as routing  # noqa: E402


def build_route_decision(*, complex_recovery_trigger: str | None = None) -> dict[str, object]:
    """Keep normal orchestration deterministic and project typed recovery only."""
    return routing.refactor_acceptance_decision(
        complex_recovery_trigger=complex_recovery_trigger
    )
