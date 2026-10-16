#!/usr/bin/env python3
"""ADR-0036/0038/0061: read current authenticated machine evidence; never run routes."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request

ROUTES = {
    "gdd-question-form": {"ready", "confirmed", "succeeded"},
    "scene-route-confirmation": {"confirmed", "ready"},
    "gdd-document-generation": {"ready", "succeeded"},
    "gdd-requirements": {"ready"},
    "prototype-contract": {"fresh", "ready"},
    "prototype-skeleton": {"succeeded", "ready"},
    "ui-wiring": {"succeeded"},
}
EXECUTION_STEPS = ("iteration-plan", "module-execution", "prototype-acceptance", "preview-package")
HASH_BINDINGS = {
    "sourceContractHash": "contractHash",
    "sourceRequirementMapHash": "sourceRequirementMapHash",
    "sourceGodotUiContractHash": "sourceGodotUiContractHash",
    "sourceUiStyleContractHash": "sourceUiStyleContractHash",
    "uiStyleSnapshotHash": "uiStyleSnapshotHash",
}
HASH_FIELDS = (*HASH_BINDINGS, "sourceIterationSessionHash", "sourceValidationInputHash")


def evaluate(project_id: str, workflow: dict, contract: dict, ui: dict) -> list[str]:
    """The host validates ownership, source boundaries, ledger completeness and freshness."""
    failures: list[str] = []
    business = workflow.get("businessChain")
    if business is not None and (not isinstance(business, dict) or business.get("status") != "passed"):
        failures.append("workflow:business_chain_blocked")
    for name, payload in (("workflow", workflow), ("contract", contract), ("ui", ui)):
        if payload.get("projectId") != project_id:
            failures.append(f"{name}:project_binding_invalid")
    artifacts = workflow.get("routeStateArtifacts") or {}
    if artifacts.get("status") != "ready" or artifacts.get("blockingIssues") != []:
        failures.append("workflow:route_artifacts_blocked")
    rows = artifacts.get("artifacts") or []
    for route, statuses in ROUTES.items():
        matches = [row for row in rows if isinstance(row, dict) and row.get("route") == route]
        if len(matches) != 1:
            failures.append(f"route:{route}:missing_or_duplicate")
        elif (matches[0].get("status") not in statuses or matches[0].get("freshness") != "fresh"
              or matches[0].get("blockingIssueIds") != []):
            failures.append(f"route:{route}:not_current_and_complete")
    steps = workflow.get("steps") or []
    for step_id in EXECUTION_STEPS:
        matches = [step for step in steps if isinstance(step, dict) and step.get("id") == step_id]
        if (len(matches) != 1 or matches[0].get("status") != "done"
                or not isinstance(matches[0].get("evidence"), str) or not matches[0]["evidence"].strip()):
            failures.append(f"execution:{step_id}:not_complete")
    if any(step.get("status") in {"fix", "blocked", "continue"}
           for step in steps if isinstance(step, dict) and step.get("id") == "needs-fix-or-repair"):
        failures.append("execution:repair_not_closed")
    if (contract.get("status") != "fresh" or (contract.get("freshness") or {}).get("status") != "fresh"
            or contract.get("blockingIssues") != []):
        failures.append("contract:not_fresh")
    if (ui.get("status") != "succeeded" or ui.get("freshness") != "fresh"
            or ui.get("finalReadinessEligible") is not True or ui.get("blockingIssues") != []):
        failures.append("ui:final_readiness_blocked")
    for field in HASH_FIELDS:
        value = ui.get(field)
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            failures.append(f"ui:{field}:hash_missing_or_invalid")
    for field, source_field in HASH_BINDINGS.items():
        if not ui.get(field) or ui.get(field) != contract.get(source_field):
            failures.append(f"ui:{field}:source_changed")
    for name, payload in (("contract", contract), ("ui", ui)):
        refs = payload.get("evidenceRefs")
        if not isinstance(refs, list) or not refs or not all(
            isinstance(ref, dict) and ref.get("kind") in {"sidecar", "validator", "smoke", "artifact", "db_row", "log", "screenshot"}
            and isinstance(ref.get("path"), str) and ref["path"].strip() for ref in refs
        ):
            failures.append(f"{name}:machine_evidence_missing")
    return sorted(set(failures))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # A bearer credential must never follow a redirect.


def fetch(base_url: str, project_id: str, suffix: str, token: str, timeout: float) -> dict:
    url = base_url.rstrip("/") + "/api/projects/" + urllib.parse.quote(project_id, safe="") + "/" + suffix
    request = urllib.request.Request(url, headers={"Authorization": "Bearer " + token, "Accept": "application/json"})
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=timeout) as response:
        body = response.read(2 * 1024 * 1024 + 1)
    if len(body) > 2 * 1024 * 1024:
        raise ValueError("response_too_large")
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise ValueError("invalid_readback")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--token-env", default="PHASEA_USER_TOKEN")
    parser.add_argument("--timeout-seconds", type=float, default=10)
    parser.add_argument("--allow-http", action="store_true", help="Explicit local diagnostic override")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    parsed = urllib.parse.urlsplit(args.base_url)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or (parsed.scheme == "http" and not args.allow_http)
            or not 0 < args.timeout_seconds <= 30 or not args.project_id.strip()):
        parser.error("invalid URL, project ID, timeout, or HTTP diagnostic opt-in")
    repository = Path(__file__).resolve().parents[2]
    now = datetime.now(timezone.utc)
    output = args.output or repository / "logs" / "phase-a-business-chain-acceptance" / now.strftime("%Y-%m-%d") / now.strftime("%H%M%S-%f") / "acceptance.json"
    output = output.resolve()
    if not output.is_relative_to((repository / "logs").resolve()):
        parser.error("acceptance evidence must be written under repository logs")
    token = os.environ.get(args.token_env, "")
    failures: list[str] = []
    status = "blocked"
    if not token:
        failures.append("credential_unavailable")
        status = "unavailable"
    else:
        try:
            workflow = fetch(args.base_url, args.project_id, "workflow-route", token, args.timeout_seconds)
            contract = fetch(args.base_url, args.project_id, "prototype-contract/status", token, args.timeout_seconds)
            ui = fetch(args.base_url, args.project_id, "ui-wiring-closure/latest", token, args.timeout_seconds)
            failures = evaluate(args.project_id, workflow, contract, ui)
            status = "blocked" if failures else "passed"
        except urllib.error.HTTPError as error:
            failures = [f"readback_http_{error.code}"]
            status = "unavailable"
        except (urllib.error.URLError, OSError, ValueError, TypeError, AttributeError) as error:
            failures = ["readback_invalid_or_unavailable:" + type(error).__name__]
            status = "unavailable"
    report = {
        "schema_version": "phase-a-business-chain-acceptance.v1", "scope": "current_stored_business_chain",
        "status": status, "updated_utc": now.isoformat(), "project_id": args.project_id,
        "routes_executed": False, "live_model_invoked": False, "failures": failures,
        "readback_refs": [f"/api/projects/{urllib.parse.quote(args.project_id, safe='')}/{suffix}" for suffix in
                          ("workflow-route", "prototype-contract/status", "ui-wiring-closure/latest")],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "failures": failures, "evidence": str(output.relative_to(repository))}))
    return 0 if status == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
