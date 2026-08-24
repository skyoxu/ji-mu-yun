"""Deterministic maintainer closure for a declined later discovery proposal."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from acceptance_core import InputError, canonical_hash
from repair_completeness import audit_repair_completeness


_HASH = re.compile(r"sha256:[0-9a-f]{64}")
_ALLOWED_REASONS = {
    "authority_context_graph_changed",
    "high_risk_boundary_changed",
}
_DOES_NOT_AUTHORIZE = ["commit", "release", "archived"]


def _file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_ref(root: Path, value: Any, label: str) -> tuple[Path, dict[str, Any]]:
    if not isinstance(value, dict) or set(value) != {"path", "sha256"}:
        raise InputError(f"{label} reference is invalid")
    relative = value.get("path")
    expected_hash = value.get("sha256")
    if (
        not isinstance(relative, str)
        or not relative.strip()
        or Path(relative).is_absolute()
        or not isinstance(expected_hash, str)
        or _HASH.fullmatch(expected_hash) is None
    ):
        raise InputError(f"{label} reference is invalid")
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise InputError(f"{label} escapes repository root") from exc
    if not path.is_file() or _file_hash(path) != expected_hash:
        raise InputError(f"{label} reference is missing or stale")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InputError(f"{label} is not readable JSON") from exc
    if not isinstance(document, dict):
        raise InputError(f"{label} must reference a JSON object")
    return path, document


def close_declined_review_reentry(request: Any) -> dict[str, Any]:
    required = {
        "schemaVersion",
        "repositoryRoot",
        "acceptanceTarget",
        "acceptanceRepairRoute",
        "repairCompleteness",
        "decision",
        "userConfirmed",
        "authorityRole",
        "rationale",
        "recordedAt",
        "authorizes",
    }
    if not isinstance(request, dict) or set(request) != required:
        raise InputError("review re-entry decline request fields are invalid")
    if (
        request.get("schemaVersion") != "acceptance-review-reentry-decline-request.v1"
        or request.get("decision") != "decline-finding-mode-reentry"
        or request.get("userConfirmed") is not True
        or request.get("authorityRole") != "maintainer"
        or request.get("authorizes") != ["review-reentry-decline-closure"]
    ):
        raise InputError("review re-entry decline acknowledgement is invalid")
    for field in ("repositoryRoot", "acceptanceTarget", "rationale", "recordedAt"):
        if not isinstance(request.get(field), str) or not request[field].strip():
            raise InputError(f"review re-entry decline {field} is invalid")

    root = Path(request["repositoryRoot"]).resolve()
    target = request["acceptanceTarget"]
    if Path(target).is_absolute() or not target.startswith("execution-plans/"):
        raise InputError("review re-entry decline target is invalid")
    target_path = (root / target).resolve()
    try:
        target_path.relative_to(root)
    except ValueError as exc:
        raise InputError("review re-entry decline target escapes repository root") from exc
    if not target_path.is_dir():
        raise InputError("review re-entry decline target is missing")

    route_path, route = _resolve_ref(root, request["acceptanceRepairRoute"], "Acceptance repair route")
    completeness_path, completeness = _resolve_ref(root, request["repairCompleteness"], "repair completeness")

    if (
        route.get("schemaVersion") != "implementation-acceptance-bootstrap-route.v1"
        or route.get("routeKind") != "full_implementation_conformance"
        or route.get("nextAction") != "run-phase-bootstrap-review"
        or route.get("findingMode") != "discovery"
        or route.get("findingModeReentry") != "user_confirmation_required"
        or route.get("semanticRoundsConsumed") != 1
        or route.get("nextFullReviewRound") != 2
        or route.get("roundEntryReason") not in _ALLOWED_REASONS
        or route.get("maintenanceMode") != "ai-native-single-maintainer"
        or route.get("authorizes") != []
    ):
        raise InputError("Acceptance route is not an eligible later-discovery proposal")

    repair_request = route.get("repairCompletenessRequest")
    if (
        not isinstance(repair_request, dict)
        or canonical_hash(repair_request) != route.get("repairCompletenessRequestHash")
    ):
        raise InputError("Acceptance route repair request binding is invalid")
    replayed = audit_repair_completeness(repair_request)
    if replayed != completeness:
        raise InputError("repair completeness is stale or not producer-reproducible")
    if (
        completeness.get("schemaVersion") != "acceptance-repair-completeness.v1"
        or completeness.get("status") != "passed"
        or completeness.get("acceptanceTarget") != target
        or completeness.get("semanticRoundsConsumed") != 1
        or completeness.get("lineageFamilyId") != route.get("lineageFamilyId")
        or completeness.get("novelP0P1FindingIds") != []
        or not (
            completeness.get("authorityGraphChanged") is True
            or completeness.get("highRiskBoundaryChanged") is True
        )
        or canonical_hash(completeness) != route.get("repairCompletenessHash")
        or completeness.get("authorizes") != []
    ):
        raise InputError("repair completeness cannot close a declined discovery proposal")

    acknowledgement = {
        "schemaVersion": "acceptance-review-reentry-maintainer-ack.v1",
        "decision": request["decision"],
        "userConfirmed": True,
        "authorityRole": "maintainer",
        "rationale": request["rationale"],
        "recordedAt": request["recordedAt"],
        "authorizes": ["review-reentry-decline-closure"],
    }
    binding = {
        "acceptanceTarget": target,
        "lineageFamilyId": route["lineageFamilyId"],
        "semanticRoundsConsumed": 1,
        "roundEntryReason": route["roundEntryReason"],
        "acceptanceRepairRouteHash": _file_hash(route_path),
        "repairCompletenessHash": _file_hash(completeness_path),
        "repairCompletenessDocumentHash": canonical_hash(completeness),
        "maintainerAcknowledgement": acknowledgement,
    }
    return {
        "schemaVersion": "acceptance-review-reentry-decline-closure.v1",
        "status": "passed",
        **binding,
        "closureBindingHash": canonical_hash(binding),
        "skippedAction": "round-2-finding-discovery",
        "residualRiskAccepted": True,
        "lifecycleTransition": "acceptance-passed",
        "authorizes": ["acceptance-passed"],
        "doesNotAuthorize": _DOES_NOT_AUTHORIZE,
    }
