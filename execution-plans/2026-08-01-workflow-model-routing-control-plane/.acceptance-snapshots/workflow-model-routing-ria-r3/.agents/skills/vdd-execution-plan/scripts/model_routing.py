"""VDD profile projection into the repository workflow model router."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SC_ROOT = REPOSITORY_ROOT / "scripts" / "sc"
if str(SC_ROOT) not in sys.path:
    sys.path.insert(0, str(SC_ROOT))

import workflow_model_routing as routing  # noqa: E402


def build_route_decision(
    profile: str,
    *,
    complex_recovery_trigger: str | None = None,
    capability_proof: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Project an already-selected VDD profile without reclassifying it."""
    return routing.vdd_decision(
        profile,
        complex_recovery=complex_recovery_trigger is not None,
        recovery_trigger=complex_recovery_trigger,
        capability_proof=capability_proof,
    )
