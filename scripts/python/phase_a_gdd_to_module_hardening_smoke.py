from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any


REQUIRED_BASELINE_FILES = [
    "PhaseA.Platform/Workflow/RouteActionDescriptors.cs",
    "PhaseA.Platform/Workflow/RouteStatusVocabulary.cs",
    "PhaseA.Platform/Workflow/RouteEvidenceRefKinds.cs",
    "PhaseA.Platform.Tests/Fixtures/route-action-descriptors.v1.json",
    "PhaseA.Platform.Tests/Fixtures/route-status-vocabulary.v1.json",
    "PhaseA.Platform.Tests/Fixtures/evidence-ref-kind.v1.json",
    "docs/standards/phase-service.md",
    "docs/workflows/phase-a-gdd-to-module-hardening-smoke.md",
]

PHASE0_REQUIRED_TERMS = [
    "route action descriptor",
    "source-boundary",
    "Cache-Control: no-store",
    "duplicate-run",
    "preflight",
    "token material",
    "provider keys",
    "raw prompts",
]

PROMPT_ROUTE_STATE_PATHS = [
    "meta/routes/gdd-requirements/latest.json",
    "routes/prototype-contract/latest.json",
    "meta/routes/prototype-skeleton/latest.json",
    "meta/routes/iteration-plan/latest.json",
    "meta/routes/execute-next-goal/latest.json",
    "meta/routes/ui-wiring/latest.json",
]

HASH_CHAIN_PATHS = [
    "meta/routes/scene-route/latest.json",
    "meta/routes/gdd-document/latest.json",
    "meta/routes/gdd-requirements/latest.json",
    "routes/prototype-contract/latest.json",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic Phase A GDD-to-module hardening smoke checks.")
    parser.add_argument("--repository-root", default=os.environ.get("PHASEA_REPOSITORY_ROOT", str(Path.cwd())))
    parser.add_argument("--project-root", default="")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--project-id", default="")
    parser.add_argument("--admin-token", default=os.environ.get("PHASEA_ADMIN_TOKEN", ""))
    parser.add_argument("--timeout-seconds", type=float, default=15.0)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    repository_root = Path(args.repository_root).resolve()
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    run_dir = Path(args.out).resolve() if args.out else repository_root / "logs" / "phase-a-gdd-to-module-hardening" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    events: list[dict[str, Any]] = []
    failures: list[str] = []
    status = "failed"
    try:
        failures.extend(check_phase0_baseline(repository_root, events))
        if failures:
            raise AssertionError("Phase 0 baseline checks failed before project/API execution.")

        if args.project_root:
            project_root = Path(args.project_root).resolve()
            failures.extend(check_project_route_state(project_root, events))

        if args.base_url and args.project_id:
            failures.extend(check_api_readback(args.base_url, args.project_id, args.admin_token, args.timeout_seconds, events))

        if failures:
            raise AssertionError("GDD-to-module hardening smoke failed.")

        status = "ok"
        return 0
    except Exception as ex:
        if not failures:
            failures.append(str(ex))
        events.append({"event": "smoke_failed", "type": type(ex).__name__, "error": str(ex)})
        print(f"PHASE_A_GDD_TO_MODULE_HARDENING_SMOKE status=failed run_dir={run_dir} error={ex}", file=sys.stderr)
        return 1
    finally:
        summary = {
            "schema_version": "phase-a-gdd-to-module-hardening-smoke.v1",
            "status": status,
            "run_id": run_id,
            "script": "scripts/python/phase_a_gdd_to_module_hardening_smoke.py",
            "repository_root": str(repository_root),
            "project_root": args.project_root,
            "base_url": sanitize_url(args.base_url),
            "project_id": args.project_id,
            "identity_class": "admin" if args.admin_token else "anonymous_or_existing_context",
            "events": events,
            "failures": failures,
        }
        (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8", newline="\n")
        if status == "ok":
            print(f"PHASE_A_GDD_TO_MODULE_HARDENING_SMOKE status=ok run_dir={run_dir}")


def check_phase0_baseline(repository_root: Path, events: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    for rel in REQUIRED_BASELINE_FILES:
        if not (repository_root / rel).is_file():
            failures.append(f"missing_baseline_file:{rel}")
    if failures:
        events.append({"event": "phase0_baseline_files", "status": "failed", "missing": failures[:]})
        return failures

    descriptors = read_json(repository_root / "PhaseA.Platform.Tests/Fixtures/route-action-descriptors.v1.json")
    actions = descriptors.get("actions")
    if not isinstance(actions, list) or not actions:
        failures.append("route_action_descriptors_empty")
    else:
        action_ids = [str(action.get("actionId", "")) for action in actions if isinstance(action, dict)]
        if len(action_ids) != len(set(action_ids)):
            failures.append("route_action_descriptors_duplicate_action_id")
        for action in actions:
            if not isinstance(action, dict):
                failures.append("route_action_descriptor_invalid_item")
                continue
            for field in [
                "actionId",
                "exposureClass",
                "defaultPhaseEligibility",
                "browserActionId",
                "displayLabelKey",
                "operationScope",
                "requiredPhase",
            ]:
                if not str(action.get(field, "")).strip():
                    failures.append(f"route_action_descriptor_missing:{action.get('actionId', '<unknown>')}:{field}")

    evidence_kinds = read_json(repository_root / "PhaseA.Platform.Tests/Fixtures/evidence-ref-kind.v1.json").get("values")
    expected_kinds = {"log", "artifact", "sidecar", "screenshot", "db_row", "smoke", "validator"}
    if set(evidence_kinds or []) != expected_kinds:
        failures.append("evidence_ref_kind_fixture_mismatch")

    standards_text = (repository_root / "docs/standards/phase-service.md").read_text(encoding="utf-8")
    workflow_text = (repository_root / "docs/workflows/phase-a-gdd-to-module-hardening-smoke.md").read_text(encoding="utf-8")
    combined = (standards_text + "\n" + workflow_text).lower()
    for term in PHASE0_REQUIRED_TERMS:
        if term.lower() not in combined:
            failures.append(f"phase0_term_missing:{term}")

    events.append(
        {
            "event": "phase0_baseline_checked",
            "status": "ok" if not failures else "failed",
            "action_count": len(actions) if isinstance(actions, list) else 0,
            "evidence_kinds": sorted(evidence_kinds or []),
        }
    )
    return failures


def check_project_route_state(project_root: Path, events: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    if not project_root.is_dir():
        return [f"project_root_missing:{project_root}"]

    for rel in HASH_CHAIN_PATHS:
        if not (project_root / rel).is_file():
            failures.append(f"missing_route_state:{rel}")
    if failures:
        events.append({"event": "project_route_state_files", "status": "failed", "failures": failures[:]})
        return failures

    gdd_path = project_root / "docs/gdd/GDD.md"
    if not gdd_path.is_file():
        failures.append("missing_gdd_document:docs/gdd/GDD.md")
        events.append({"event": "project_hash_chain", "status": "failed", "failures": failures[:]})
        return failures

    gdd_hash = normalized_file_hash(gdd_path)
    scene = read_json(project_root / "meta/routes/scene-route/latest.json")
    gdd_document = read_json(project_root / "meta/routes/gdd-document/latest.json")
    requirement_map = read_json(project_root / "meta/routes/gdd-requirements/latest.json")
    contract = read_json(project_root / "routes/prototype-contract/latest.json")
    skeleton = read_json(project_root / "meta/routes/prototype-skeleton/latest.json") if (project_root / "meta/routes/prototype-skeleton/latest.json").is_file() else {}

    confirmed_scene_route_hash = str(scene.get("confirmed_scene_route_hash", "")).strip()
    if not confirmed_scene_route_hash:
        failures.append("scene_route_hash_missing")
    if str(gdd_document.get("generated_gdd_hash", "")).strip() != gdd_hash:
        failures.append("gdd_document_hash_mismatch")
    if str(scene.get("source_generated_gdd_hash", "")).strip() != gdd_hash:
        failures.append("scene_route_generated_gdd_hash_mismatch")

    for rel, payload in [
        ("meta/routes/gdd-requirements/latest.json", requirement_map),
        ("routes/prototype-contract/latest.json", contract),
        ("meta/routes/prototype-skeleton/latest.json", skeleton),
    ]:
        if not payload:
            continue
        if str(payload.get("source_scene_route_hash", "")).strip() != confirmed_scene_route_hash:
            failures.append(f"source_scene_route_hash_mismatch:{rel}")

    for rel in PROMPT_ROUTE_STATE_PATHS:
        path = project_root / rel
        if path.is_file():
            payload = read_json(path)
            failures.extend(validate_source_boundary(rel, payload))
            failures.extend(validate_prompt_evidence(project_root, rel, payload))

    events.append(
        {
            "event": "project_route_state_checked",
            "status": "ok" if not failures else "failed",
            "project_root": str(project_root),
            "gdd_hash": gdd_hash,
            "confirmed_scene_route_hash": confirmed_scene_route_hash,
        }
    )
    return failures


def check_api_readback(
    base_url: str,
    project_id: str,
    admin_token: str,
    timeout_seconds: float,
    events: list[dict[str, Any]],
) -> list[str]:
    failures: list[str] = []
    url = base_url.rstrip("/") + f"/api/projects/{urllib.parse.quote(project_id)}/workflow-recommendation"
    headers = {"Authorization": f"Bearer {admin_token}"} if admin_token else {}
    status, payload = request_json(url, headers=headers, timeout_seconds=timeout_seconds)
    if status != 200:
        return [f"workflow_recommendation_readback_http:{status}"]
    descriptor_ref = payload.get("actionDescriptorRef") if isinstance(payload, dict) else None
    if not isinstance(descriptor_ref, dict) or not descriptor_ref.get("descriptorHash"):
        failures.append("workflow_recommendation_descriptor_ref_missing")
    action_ids = []
    for key in ["allowedActions", "forbiddenActions"]:
        actions = payload.get(key, []) if isinstance(payload, dict) else []
        if isinstance(actions, list):
            action_ids.extend(str(action.get("actionId", "")) for action in actions if isinstance(action, dict))
    if not action_ids:
        failures.append("workflow_recommendation_actions_missing")
    events.append({"event": "api_workflow_recommendation_checked", "status": status, "action_count": len(action_ids)})
    return failures


def validate_source_boundary(relative_path: str, payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if payload.get("source_boundary_enforced") is not True:
        failures.append(f"source_boundary_not_enforced:{relative_path}")
        return failures
    boundary = payload.get("source_boundary")
    if not isinstance(boundary, dict):
        failures.append(f"source_boundary_missing:{relative_path}")
        return failures
    if not boundary.get("authority_sources"):
        failures.append(f"source_boundary_authority_sources_missing:{relative_path}")
    if boundary.get("recovery_source_order_ref") != "hosted-route-recovery-order.v1":
        failures.append(f"source_boundary_recovery_order_missing:{relative_path}")
    hashes = boundary.get("source_hashes") or boundary.get("authority_source_hashes") or payload.get("source_hashes")
    if not hashes:
        failures.append(f"source_boundary_hashes_missing:{relative_path}")
    return failures


def validate_prompt_evidence(project_root: Path, relative_path: str, payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for evidence_ref in evidence_refs(payload):
        path = str(evidence_ref.get("path") or evidence_ref.get("artifact_id") or "")
        if not path or ".." in Path(path).parts or Path(path).is_absolute():
            failures.append(f"evidence_ref_path_invalid:{relative_path}")
            continue
        if "prompt" not in path.lower():
            continue
        evidence_path = project_root / path
        if not evidence_path.is_file():
            failures.append(f"prompt_evidence_missing:{path}")
            continue
        text = evidence_path.read_text(encoding="utf-8", errors="replace").lower()
        if "docs/game-type-guides" in text:
            failures.append(f"prompt_evidence_broad_game_type_guide_leak:{path}")
    return failures


def evidence_refs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for key in ["evidence_refs", "evidenceRefs"]:
        values = payload.get(key, [])
        if isinstance(values, list):
            refs.extend(item for item in values if isinstance(item, dict))
    return refs


def request_json(url: str, *, headers: dict[str, str], timeout_seconds: float) -> tuple[int, Any]:
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as ex:
        try:
            return ex.code, json.loads(ex.read().decode("utf-8"))
        except json.JSONDecodeError:
            return ex.code, {}


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def normalized_file_hash(path: Path) -> str:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").strip()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sanitize_url(value: str) -> str:
    if not value:
        return ""
    parsed = urllib.parse.urlparse(value)
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


if __name__ == "__main__":
    raise SystemExit(main())
