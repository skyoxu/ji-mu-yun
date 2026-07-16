from __future__ import annotations

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from shadow_guards import validate_shadow_protected_trees


def _finding(rule_id: str, target: str, message: str) -> dict[str, str]:
    return {"rule_id": rule_id, "target": target, "message": message}


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_time(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _validate_stage_evidence(repository_root: Path, slice_id: str, evidence: dict[str, str | None], contract_slice: dict[str, Any], current_identity: dict[str, str]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    run_dir_value = evidence.get("run_dir")
    if not run_dir_value:
        return [_finding("RMAP-AUTH-SLICE-EVIDENCE", slice_id, "explicit run directory is required")]
    run_dir = (repository_root / run_dir_value).resolve()
    try:
        run_relative = run_dir.relative_to(repository_root).as_posix()
    except ValueError:
        return [_finding("RMAP-AUTH-SLICE-EVIDENCE", slice_id, "run directory escapes repository")]
    if not run_relative.startswith("logs/tdd-adapter/"):
        return [_finding("RMAP-AUTH-SLICE-EVIDENCE", slice_id, "run directory is outside logs/tdd-adapter")]
    expected = {
        "red_result": ("red", "red-observed"),
        "green_result": ("green", "green-observed"),
        "refactor_result": ("refactor", "refactor-verified"),
    }
    run_id: str | None = None
    prior_path: Path | None = None
    prior_time: datetime | None = None
    stage_documents: list[dict[str, Any]] = []
    for key, (stage, status) in expected.items():
        value = evidence.get(key)
        if not value:
            findings.append(_finding("RMAP-AUTH-SLICE-EVIDENCE", f"{slice_id}:{stage}", "explicit stage result is required")); continue
        path = (repository_root / value).resolve()
        try:
            path.relative_to(run_dir)
        except ValueError:
            findings.append(_finding("RMAP-AUTH-SLICE-EVIDENCE", value, "stage result is outside the declared run")); continue
        document = _load_json(path)
        required_fields = {"schema_version", "plan_id", "slice_id", "run_id", "stage", "status", "command_id", "exit_code", "contract_hash", "validator_hash", "observed_at", "predecessor_stage_hash"}
        if document is None or not required_fields.issubset(document) or document.get("schema_version") != "rmap.tdd-stage-result.v1" or document.get("plan_id") != "repository-maintenance-tdd-adapter" or document.get("slice_id") != slice_id or document.get("stage") != stage or document.get("status") != status:
            findings.append(_finding("RMAP-AUTH-SLICE-EVIDENCE", value, "stage evidence identity or status is invalid")); continue
        if document.get("contract_hash") != current_identity.get("contract_hash") or document.get("validator_hash") != current_identity.get("validator_hash"):
            findings.append(_finding("RMAP-HASH-CANDIDATE-IDENTITY", value, "stage evidence contract or validator identity is stale"))
        stage_time = _parse_time(document.get("observed_at"))
        if stage_time is None or (prior_time is not None and stage_time <= prior_time):
            findings.append(_finding("RMAP-TDD-STAGE-ORDER", value, "stage observation order is invalid"))
        expected_predecessor = None if prior_path is None else _sha256(prior_path)
        if document.get("predecessor_stage_hash") != expected_predecessor:
            findings.append(_finding("RMAP-TDD-STAGE-ORDER", value, "stage predecessor hash is invalid"))
        tdd = contract_slice.get("tdd", {})
        if stage == "red":
            red = tdd.get("red", {})
            if document.get("command_id") != red.get("command_id") or document.get("test_selector") != red.get("test_selector") or set(document.get("expected_failure_ids", [])) != set(red.get("expected_failure_ids", [])) or not isinstance(document.get("exit_code"), int) or document.get("exit_code") == 0:
                findings.append(_finding("RMAP-TDD-RED-NOT-OBSERVED", value, "RED command, selector, failure, or exit evidence is invalid"))
        elif stage == "green":
            if document.get("command_id") != tdd.get("green", {}).get("command_id") or document.get("exit_code") != 0:
                findings.append(_finding("RMAP-TDD-EXIT-PROOF", value, "GREEN command or exit evidence is invalid"))
        else:
            expected_commands = [item.get("command_id") for item in tdd.get("refactor", {}).get("invocations", []) if isinstance(item, dict)]
            if document.get("command_ids") != expected_commands or document.get("exit_code") != 0:
                findings.append(_finding("RMAP-TDD-EXIT-PROOF", value, "REFACTOR command set or exit evidence is invalid"))
        if run_id is None:
            run_id = document.get("run_id")
            if not isinstance(run_id, str) or not run_id:
                findings.append(_finding("RMAP-AUTH-SLICE-EVIDENCE", value, "stage run identity is missing"))
        elif document.get("run_id") != run_id:
            findings.append(_finding("RMAP-AUTH-SLICE-EVIDENCE", value, "stage evidence run identity differs"))
        prior_path = path
        prior_time = stage_time
        stage_documents.append(document)
    recovery = _load_json(run_dir / "recovery-state.json")
    if recovery is None or recovery.get("schema_version") != "rmap.recovery-state.v1" or recovery.get("run_id") != run_id or recovery.get("state") not in {"initialized", "active", "complete"} or recovery.get("contract_hash") != current_identity.get("contract_hash") or recovery.get("validator_hash") != current_identity.get("validator_hash"):
        findings.append(_finding("RMAP-RECOVERY-NEW-RUN-STATE", slice_id, "current recovery state is missing, stale, or invalid"))
    else:
        predecessor = recovery.get("predecessor_run_id")
        supersedes = recovery.get("supersedes_run_id")
        if (predecessor is None) != (supersedes is None) or (predecessor is not None and (predecessor != supersedes or predecessor == run_id)):
            findings.append(_finding("RMAP-RECOVERY-NEW-RUN-STATE", slice_id, "successor lineage is incomplete or self-referential"))
    return findings


def _validate_declared_outputs(repository_root: Path, slice_id: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    required = {
        "RMAP-S0": ["docs/adr/ADR-0041-repository-maintenance-agent-protocol-ownership.md", "docs/standards/repository-maintenance-agent-protocol.md", "docs/standards/_index.md", "docs/PROJECT_DOCUMENTATION_INDEX.md"],
        "RMAP-S1": [".agents/skills/quick-dev-tdd-adapter/SKILL.md", ".agents/skills/quick-dev-tdd-adapter/references/implementation-backend-contract.md", ".agents/skills/quick-dev-tdd-adapter/references/tdd-run-protocol.md", ".agents/skills/quick-dev-tdd-adapter/references/evidence-and-freshness.md"],
        "RMAP-S2": [".agents/skills/quick-dev-tdd-adapter/tools/validate_adapter_contract.py"],
        "RMAP-S3": ["execution-plans/2026-07-12-llm-review-evidence-gate-hardening/implementation-contract.v1.json", "execution-plans/2026-07-12-llm-review-evidence-gate-hardening/fixtures/tdd-adapter-shadow.v1.json"],
        "RMAP-S4": ["execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/implementation-contract.v1.json", "execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/fixtures/tdd-adapter-shadow.v1.json"],
        "RMAP-S5": ["execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/implementation-contract.v1.json", "execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/fixtures/tdd-adapter-shadow.v1.json"],
    }
    for relative in required.get(slice_id, []):
        path = repository_root / relative
        if not path.is_file():
            findings.append(_finding("RMAP-AUTH-SLICE-EVIDENCE", relative, "required slice output is missing"))
    if slice_id == "RMAP-S0" and not findings:
        adr = (repository_root / required[slice_id][0]).read_text(encoding="utf-8")
        standard = (repository_root / required[slice_id][1]).read_text(encoding="utf-8")
        indexes = [(repository_root / path).read_text(encoding="utf-8") for path in required[slice_id][2:]]
        if "Status: Accepted" not in adr or "Three-Layer Ownership" not in standard or any("repository-maintenance-agent-protocol" not in text for text in indexes):
            findings.append(_finding("RMAP-AUTH-SLICE-BEHAVIOR", slice_id, "S0 ownership authority is not semantically closed"))
    if slice_id in {"RMAP-S3", "RMAP-S4", "RMAP-S5"} and not findings:
        for relative in required[slice_id]:
            document = _load_json(repository_root / relative)
            if document is None or document.get("authoritative") is not False or not document.get("schema_version"):
                findings.append(_finding("RMAP-AUTH-SLICE-BEHAVIOR", relative, "shadow contract or fixture is invalid or authoritative"))
    return findings


def validate_slice_outputs(repository_root: Path, slice_id: str, shadow: dict[str, Any] | None = None, evidence: dict[str, str | None] | None = None, contract_slice: dict[str, Any] | None = None, current_identity: dict[str, str] | None = None) -> tuple[dict[str, Any], list[dict[str, str]]]:
    findings = _validate_declared_outputs(repository_root, slice_id)
    if contract_slice is None or current_identity is None:
        findings.append(_finding("RMAP-AUTH-SLICE-EVIDENCE", slice_id, "current slice contract and identity are required"))
    else:
        findings.extend(_validate_stage_evidence(repository_root, slice_id, evidence or {}, contract_slice, current_identity))
    if slice_id in {"RMAP-S3", "RMAP-S4", "RMAP-S5"}:
        findings.extend(validate_shadow_protected_trees(repository_root / "execution-plans" / "2026-07-15-repository-maintenance-tdd-adapter", shadow or {}))
    check = {"rule_id": "RMAP-AUTH-SLICE", "status": "pass" if not findings else "fail", "evidence": [f"{slice_id} parsed outputs and explicit stage evidence"]}
    return check, findings
