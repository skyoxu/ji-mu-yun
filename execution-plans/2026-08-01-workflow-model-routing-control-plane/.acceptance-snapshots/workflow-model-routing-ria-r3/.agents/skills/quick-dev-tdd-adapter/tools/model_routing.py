"""Quick Dev projection into the repository workflow model router."""

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
    facts: dict[str, Any], *, requested_class: str | None = None
) -> dict[str, Any]:
    """Classify typed task facts without acquiring model-launch authority."""
    return routing.quick_dev_decision(facts, requested_class=requested_class)
