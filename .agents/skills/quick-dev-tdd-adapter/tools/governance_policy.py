from __future__ import annotations

from collections.abc import Mapping
import os
from typing import Final


PHASE_SERVICE_STATE_ENV: Final = "PHASEA_SERVICE_STATE"
GOVERNANCE_MODE_ENV: Final = "JIMUYUN_GOVERNANCE_MODE"
PHASE_SERVICE_STATES: Final = ("development", "test", "production")
GOVERNANCE_MODES: Final = ("auto", "on", "off")
GOVERNANCE_CHECKS: Final = (
    "plan-report-lifecycle",
    "knowledge-freeze-lineage",
    "skill-input-attestation",
    "external-semantic-review",
    "candidate-binding",
    "implementation-authorization",
    "source-freeze-conformance",
    "repair-review-handoff",
)


def _normalized(value: object, *, name: str, allowed: tuple[str, ...]) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be one of: {', '.join(allowed)}")
    normalized = value.strip().lower()
    if normalized not in allowed:
        raise ValueError(f"{name} must be one of: {', '.join(allowed)}")
    return normalized


def resolve_governance_policy(
    requested_mode: str | None = None,
    *,
    environment: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Resolve governance without weakening local TDD or semantic validation."""

    values = os.environ if environment is None else environment
    raw_state = values.get(PHASE_SERVICE_STATE_ENV, "")
    state = _normalized(
        raw_state if isinstance(raw_state, str) and raw_state.strip() else "development",
        name=PHASE_SERVICE_STATE_ENV,
        allowed=PHASE_SERVICE_STATES,
    )

    if requested_mode is not None:
        raw_mode = requested_mode
        source = "parameter"
    else:
        environment_mode = values.get(GOVERNANCE_MODE_ENV, "")
        if isinstance(environment_mode, str) and environment_mode.strip():
            raw_mode = environment_mode
            source = "environment"
        else:
            raw_mode = "auto"
            source = "phase-service-state"

    mode = _normalized(raw_mode, name="governance mode", allowed=GOVERNANCE_MODES)
    enabled = mode == "on" or (mode == "auto" and state in {"test", "production"})
    return {
        "mode": mode,
        "phase_service_state": state,
        "enabled": enabled,
        "source": source,
        "checks": list(GOVERNANCE_CHECKS),
    }
