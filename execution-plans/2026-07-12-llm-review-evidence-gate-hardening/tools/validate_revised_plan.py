from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


PLAN_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLAN_ROOT.parents[1]
PHASE_PLAN = REPOSITORY_ROOT / "execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan"
REPORT_INDEX = REPOSITORY_ROOT / "execution-plans/95-implementation-report-index.v1.json"


class ValidationError(RuntimeError):
    pass


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValidationError(f"invalid JSON: {path.relative_to(REPOSITORY_ROOT)}: {exc}") from exc


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def run_validator(relative: str) -> None:
    completed = subprocess.run(
        [sys.executable, "-B", str(REPOSITORY_ROOT / relative)],
        cwd=REPOSITORY_ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        detail = completed.stdout.strip() or completed.stderr.strip()
        raise ValidationError(f"subvalidator failed: {relative}: {detail}")


def validate_requirements() -> None:
    value = load_json(PLAN_ROOT / "requirements.v2.json")
    requirements = value.get("requirements")
    acceptance = value.get("acceptance")
    require(isinstance(requirements, list), "requirements must be an array")
    require(isinstance(acceptance, list), "acceptance must be an array")
    requirement_ids = [item.get("id") for item in requirements]
    acceptance_ids = [item.get("id") for item in acceptance]
    require(requirement_ids == [f"RFG2-{index:03d}" for index in range(1, 7)], "requirement IDs are not closed")
    require(acceptance_ids == [f"RFG2-A{index:02d}" for index in range(1, 11)], "acceptance IDs are not closed")
    require(len(set(acceptance_ids)) == len(acceptance_ids), "acceptance IDs are duplicated")
    used_acceptance: list[str] = []
    for item in requirements:
        refs = item.get("acceptance_ids")
        slices = item.get("slice_ids")
        require(isinstance(refs, list) and refs, f"{item.get('id')} has no acceptance")
        require(isinstance(slices, list) and slices, f"{item.get('id')} has no slice")
        require(set(refs).issubset(set(acceptance_ids)), f"{item.get('id')} references unknown acceptance")
        used_acceptance.extend(refs)
    require(set(used_acceptance) == set(acceptance_ids), "acceptance coverage is incomplete")
    require(value.get("authorizes") == [], "requirements must be non-authorizing")


def validate_contract() -> None:
    contract = load_json(PLAN_ROOT / "implementation-contract.v2.json")
    state = load_json(PLAN_ROOT / "plan-state.v1.json")
    registry = load_json(PLAN_ROOT / "command-registry.v2.json")
    route_decision = load_json(PLAN_ROOT / "model-route-decision.v1.json")
    legacy = load_json(PLAN_ROOT / "implementation-contract.v1.json")
    require(legacy.get("authoritative") is False, "legacy implementation contract became authoritative")
    require(legacy.get("state_change_authorized") is False, "legacy implementation contract authorizes state")
    slices = contract.get("slices")
    require(isinstance(slices, list), "implementation slices are missing")
    slice_ids = [item.get("id") for item in slices]
    require(slice_ids == ["RFG2-S0", "RFG2-S1", "RFG2-S2", "RFG2-S3"], "slice order is invalid")
    for item in slices:
        for field in ("behavior", "red_or_legacy", "green", "recovery"):
            require(field in item and item[field] not in (None, ""), f"{item.get('id')} is missing {field}")
        require(isinstance(item.get("downstream_dependents"), list), f"{item.get('id')} has invalid downstream_dependents")
    state_slices = [item.get("id") for item in state.get("slices", [])]
    require(state_slices == slice_ids, "plan state slice order differs from implementation contract")
    require(contract.get("authorizes") == [], "implementation contract must be non-authorizing")
    require(registry.get("authorizes") == [], "command registry must be non-authorizing")
    require(route_decision.get("authorizes") == [], "model route decision must be non-authorizing")
    routing_path = REPOSITORY_ROOT / ".agents/skills/vdd-execution-plan/scripts/model_routing.py"
    spec = importlib.util.spec_from_file_location("vdd_plan_model_routing", routing_path)
    require(spec is not None and spec.loader is not None, "VDD model router is unavailable")
    routing = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(routing)
    require(route_decision == routing.build_route_decision("self-hosted"), "VDD model route decision drifted")
    commands = {item.get("id"): item.get("command") for item in registry.get("commands", [])}
    require(set(commands) == {"legacy-compatibility", "r4-relocation", "terminal-revised-plan"}, "command registry is incomplete")
    require(commands["terminal-revised-plan"] == contract.get("terminal_validation"), "terminal command binding differs")
    forbidden = "\n".join(contract.get("global_forbidden_changes", []))
    for marker in (
        ".agents/skills/bmad-*/**",
        ".agents/skills/gds-*/**",
        ".agents/skills/maintain-toolchain-workflow-evidence-catalog/**",
        "PhaseA.Platform/**",
    ):
        require(marker in forbidden, f"missing non-overlap boundary: {marker}")


def validate_documents() -> None:
    index = (PLAN_ROOT / "00-index.md").read_text(encoding="utf-8")
    scope = (PLAN_ROOT / "10-current-scope-revision.md").read_text(encoding="utf-8")
    combined_phase = "\n".join(
        (PHASE_PLAN / name).read_text(encoding="utf-8")
        for name in (
            "03-profiles-preflight-and-containment.md",
            "04-mutation-lease-journal-and-acceptance.md",
            "07-evidence-telemetry-and-performance.md",
            "08-implementation-phases.md",
        )
    )
    for marker in ("R4 Relocation", "Existing 7-31 Evidence Catalog", "TC-D1", "TC-D2", "TC-D3", "TC-D6"):
        require(marker in index or marker in scope, f"missing current scope marker: {marker}")
    require("cannot publish a knowledge generation" in index, "knowledge publication authority is misstated")
    require("maintain-knowledge-base" in index, "knowledge publication owner is missing")
    require("does not automatically select review" in load_json(PLAN_ROOT / "requirements.v2.json")["acceptance"][6]["assertion"], "high-risk routing would automatically select review")
    for marker in ("PBR-026", "PBR-044", "PBR-024", "PBR-062", "Relocated 7-12 R4"):
        require(marker in combined_phase, f"7-11 receiving contract is missing {marker}")
    report_index = load_json(REPORT_INDEX)
    entries = report_index.get("entries", [])
    matches = [
        item for item in entries
        if item.get("plan_directory") == PLAN_ROOT.name
        and item.get("report_filename") == "95-implementation-evolution-and-completion-report.md"
    ]
    require(len(matches) == 1, "95 report index entry must exist exactly once")


def validate_knowledge(*, allow_draft: bool) -> str:
    state = load_json(PLAN_ROOT / "plan-state.v1.json")
    context_path = PLAN_ROOT / "knowledge-context.v1.json"
    freeze_path = PLAN_ROOT / "knowledge-context.freeze.v1.json"
    if not context_path.exists() or not freeze_path.exists():
        require(allow_draft and state.get("state") == "draft", "ready knowledge context and freeze receipt are required")
        require(bool(state.get("blocking_conditions")), "draft knowledge block is not recorded")
        return "draft-blocked"
    context = load_json(context_path)
    freeze = load_json(freeze_path)
    require(context.get("preflight", {}).get("status") == "ready", "knowledge preflight is not ready")
    expected = "sha256:" + hashlib.sha256(context_path.read_bytes()).hexdigest()
    require(freeze.get("context_sha256") == expected, "knowledge freeze does not bind current context bytes")
    require(freeze.get("authorizes") == [], "knowledge freeze must be non-authorizing")
    require(state.get("state") == "plan-ready", "knowledge-ready plan must publish plan-ready")
    return "ready"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-draft", action="store_true")
    args = parser.parse_args()
    try:
        validate_requirements()
        validate_contract()
        validate_documents()
        run_validator("execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/validate_whole_directory.py")
        run_validator("execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/tools/validate_whole_directory.py")
        knowledge_status = validate_knowledge(allow_draft=args.allow_draft)
    except ValidationError as exc:
        print(json.dumps({"status": "fail", "error": str(exc), "authorizes": []}, sort_keys=True))
        return 1
    print(json.dumps({"status": "pass", "knowledge": knowledge_status, "authorizes": []}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
