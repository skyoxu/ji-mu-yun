from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from contract_guards import glob_patterns_overlap, schema_error, typed_path_is_safe
from source_guards import validate_coverage as validate_source_coverage
from shadow_guards import validate_shadow_protected_trees


VALIDATOR_VERSION = "rmap-plan-validator.v1"
HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
REQ_RE = re.compile(r"^RMAP-(\d{3})$")
PLACEHOLDER_RE = re.compile(r"\$\{[^}]+\}")
ALLOWED_ENV = {"PYTHONDONTWRITEBYTECODE", "GODOT_BIN"}
ALLOWED_PLACEHOLDERS = {"repo_path", "plan_path", "run_path", "slice_id", "literal_enum"}
REQUIRED_FILES = {
    "00-index.md", "01-intent-authority-and-non-goals.md",
    "02-executable-contracts-and-invariants.md", "03-validators-fixtures-and-control-gates.md",
    "04-behavior-slices-and-implementation-order.md", "05-diagnostics-repair-and-reentry.md",
    "06-testing-observability-and-evidence.md", "07-implementation-phases.md",
    "08-risks-dod-and-glossary.md", "96-global-review-and-validation.md",
    "97-requirements-ledger.md", "98-source-to-split-audit.md", "99-source-coverage.md",
    "implementation-contract.v1.json", "schemas/plan-state.v1.json",
    "schemas/requirements.v1.json", "schemas/source-coverage.v1.json",
    "schemas/spec-deltas.v1.json", "schemas/requirement-quality.v1.json",
    "schemas/create-baseline-manifest.v1.json", "schemas/shadow-backfill.v1.json",
    "schemas/command-registry.v1.json", "schemas/implementation-contract.v1.schema.json",
    "schemas/shadow-protected-baseline.v1.json",
    "schemas/validation-result.v1.schema.json", "schemas/diagnostic.v1.schema.json",
    "fixtures/fixture-cases.v1.json", "tools/validate_all.py", "tools/rmap_checks.py",
    "tools/contract_guards.py", "tools/evidence_guards.py", "tools/shadow_guards.py", "tools/source_guards.py", "tools/slice_guards.py",
    "tools/fixture_checks.py", "tools/tests/test_plan_validator.py",
}
PREDICATE_AUTHORITY = {
    "plan-ready": (["plan-ready"], ["slice-ready", "bootstrap-review", "implementation-accepted", "protected-handoff", "release-ready"]),
    "slice-ready": (["slice-ready"], ["bootstrap-review", "implementation-accepted", "protected-handoff", "release-ready"]),
    "implementation-candidate": (["bootstrap-review"], ["implementation-accepted", "protected-handoff", "release-ready"]),
    "implementation-accepted": (["implementation-accepted"], ["protected-handoff", "release-ready"]),
}


def finding(rule_id: str, target: str, message: str) -> dict[str, str]:
    return {"rule_id": rule_id, "target": target, "message": message}


def strict_json(path: Path) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-standard JSON constant: {value}")
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def candidate_hash(plan_root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(plan_root.rglob("*"), key=lambda item: item.as_posix().lower()):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        rel = path.relative_to(plan_root).as_posix()
        digest.update(rel.encode("utf-8")); digest.update(b"\0")
        digest.update(path.read_bytes()); digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def validate_required_files(plan_root: Path) -> list[dict[str, str]]:
    missing = sorted(rel for rel in REQUIRED_FILES if not (plan_root / rel).is_file())
    return [finding("RMAP-STRUCT-MISSING", rel, "required artifact is missing") for rel in missing]


def load_machine(plan_root: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    names = {
        "state": "schemas/plan-state.v1.json", "requirements": "schemas/requirements.v1.json",
        "coverage": "schemas/source-coverage.v1.json", "deltas": "schemas/spec-deltas.v1.json",
        "quality": "schemas/requirement-quality.v1.json", "baseline": "schemas/create-baseline-manifest.v1.json",
        "shadow": "schemas/shadow-backfill.v1.json", "commands": "schemas/command-registry.v1.json",
        "contract": "implementation-contract.v1.json", "fixtures": "fixtures/fixture-cases.v1.json",
    }
    data: dict[str, Any] = {}
    findings: list[dict[str, str]] = []
    for key, rel in names.items():
        try:
            value = strict_json(plan_root / rel)
            if not isinstance(value, dict):
                raise ValueError("root must be an object")
            data[key] = value
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            findings.append(finding("RMAP-STRUCT-JSON", rel, str(exc)))
    return data, findings


def validate_links(plan_root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    for path in plan_root.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        for raw in pattern.findall(text):
            target = raw.strip().split("#", 1)[0]
            if not target or "://" in target or target.startswith("#"):
                continue
            if not (path.parent / target).resolve().exists():
                findings.append(finding("RMAP-STRUCT-LINK", path.name, f"missing link target: {target}"))
    return findings


def validate_requirements(plan_root: Path, registry: dict[str, Any], quality: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    items = registry.get("requirements")
    if not isinstance(items, list):
        return [finding("RMAP-REQ-SHAPE", "requirements", "requirements must be a list")]
    expected = [f"RMAP-{index:03d}" for index in range(1, 25)]
    ids = [item.get("id") for item in items if isinstance(item, dict)]
    if ids != expected:
        findings.append(finding("RMAP-REQ-SEQUENCE", "requirements", f"expected exact sequence {expected}"))
    acceptances: set[str] = set()
    required_fields = {"id", "summary", "owner", "owner_book", "first_phase", "acceptance_id", "status", "source_refs", "consumers", "failure_family", "evidence_intent", "quality_check"}
    for item in items:
        if not isinstance(item, dict):
            findings.append(finding("RMAP-REQ-SHAPE", "requirements", "entry must be an object")); continue
        rid = str(item.get("id"))
        missing = sorted(required_fields - set(item))
        if missing:
            findings.append(finding("RMAP-REQ-FIELD", rid, f"missing fields: {missing}")); continue
        if item["first_phase"] not in {"P0", "P1", "P2", "P3"} or item["status"] != "active":
            findings.append(finding("RMAP-REQ-STATE", rid, "invalid phase or status"))
        if not (plan_root / item["owner_book"]).is_file():
            findings.append(finding("RMAP-REQ-OWNER", rid, "owner book does not exist"))
        if item["acceptance_id"] in acceptances:
            findings.append(finding("RMAP-REQ-ACCEPTANCE", rid, "duplicate acceptance id"))
        acceptances.add(item["acceptance_id"])
        if not item["source_refs"] or not item["consumers"] or item["quality_check"] != "pass":
            findings.append(finding("RMAP-REQ-CLOSURE", rid, "source, consumer, or quality closure is missing"))
    checks = quality.get("checks") if isinstance(quality, dict) else None
    if not isinstance(checks, list) or [item.get("requirement_id") for item in checks if isinstance(item, dict)] != expected:
        findings.append(finding("RMAP-REQ-QUALITY", "requirement-quality", "quality checklist IDs do not match registry"))
    else:
        for item in checks:
            if any(item.get(field) is not True for field in ("observable", "executable_acceptance", "negative_or_boundary", "no_implementation_leakage", "single_owner")):
                findings.append(finding("RMAP-REQ-QUALITY", item["requirement_id"], "quality check is not fully satisfied"))
            if item.get("normative_strength") not in {"must", "must_not"}:
                findings.append(finding("RMAP-REQ-QUALITY", item["requirement_id"], "invalid normative strength"))
    return findings


def validate_coverage(plan_root: Path, coverage: dict[str, Any], requirement_ids: set[str]) -> list[dict[str, str]]:
    return validate_source_coverage(plan_root, coverage, requirement_ids, sha256_file)


def validate_deltas(deltas: dict[str, Any], requirement_ids: set[str]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    items = deltas.get("deltas")
    if not isinstance(items, list):
        return [finding("RMAP-REQ-DELTA", "spec-deltas", "deltas must be a list")]
    mapped: list[str] = []
    operations: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            findings.append(finding("RMAP-REQ-DELTA", "spec-deltas", "delta must be an object")); continue
        operations.add(str(item.get("operation")))
        reqs = item.get("requirements")
        if not isinstance(reqs, list) or not reqs or set(reqs) - requirement_ids:
            findings.append(finding("RMAP-REQ-DELTA", str(item.get("id")), "invalid requirement mapping")); continue
        mapped.extend(reqs)
        if not item.get("acceptance_ids") or not item.get("consumers") or not item.get("compatibility"):
            findings.append(finding("RMAP-REQ-DELTA", str(item.get("id")), "delta closure is incomplete"))
    if operations != {"ADDED", "MODIFIED", "REMOVED", "RENAMED"}:
        findings.append(finding("RMAP-REQ-DELTA", "spec-deltas", "all delta operations must be represented"))
    if sorted(mapped) != sorted(requirement_ids) or len(mapped) != len(set(mapped)):
        findings.append(finding("RMAP-REQ-DELTA", "spec-deltas", "each requirement must map exactly once"))
    return findings


def validate_plan_state(state: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if state.get("status") not in {"draft", "plan-ready"} or state.get("open_blockers") != []:
        findings.append(finding("RMAP-AUTH-PLAN-STATE", "plan-state", "invalid status or open blocker"))
    predicates = state.get("predicates")
    if not isinstance(predicates, dict) or set(predicates) != set(PREDICATE_AUTHORITY):
        return findings + [finding("RMAP-AUTH-PREDICATE", "plan-state", "predicate set mismatch")]
    for name, (authorizes, excludes) in PREDICATE_AUTHORITY.items():
        item = predicates.get(name, {})
        if item.get("authorizes") != authorizes or item.get("does_not_authorize") != excludes:
            findings.append(finding("RMAP-AUTH-PREDICATE", name, "predicate authority set mismatch"))
    if any(state.get("current_capabilities", {}).values()):
        findings.append(finding("RMAP-AUTH-FUTURE-CLAIM", "plan-state", "future capability is marked current"))
    return findings


def validate_commands(registry: dict[str, Any], plan_root: Path | None = None) -> list[dict[str, str]]:
    plan_root = plan_root or Path(__file__).resolve().parents[1]; findings: list[dict[str, str]] = []
    if registry.get("shell") is not False:
        findings.append(finding("RMAP-CMD-SHELL", "command-registry", "shell must be false"))
    env = registry.get("environment_allowlist")
    if not isinstance(env, list) or set(env) - ALLOWED_ENV:
        findings.append(finding("RMAP-CMD-ENV", "command-registry", "environment key is not allowlisted"))
    if registry.get("secret_values_allowed") is not False or set(registry.get("placeholder_types", [])) != ALLOWED_PLACEHOLDERS:
        findings.append(finding("RMAP-CMD-PLACEHOLDER", "command-registry", "secret or placeholder policy mismatch"))
    commands = registry.get("commands")
    if not isinstance(commands, list):
        return findings + [finding("RMAP-CMD-SHAPE", "command-registry", "commands must be a list")]
    seen: set[str] = set()
    allowed_fields = {"id", "executable", "argv", "cwd", "timeout_seconds", "expected_exit", "expected_failure_ids", "declared_predicate", "slice_id"}
    for command in commands:
        cid = command.get("id") if isinstance(command, dict) else "command"
        if not isinstance(command, dict) or set(command) - allowed_fields:
            findings.append(finding("RMAP-CMD-RAW", str(cid), "raw or unsupported command field")); continue
        if cid in seen or not isinstance(cid, str):
            findings.append(finding("RMAP-CMD-SHAPE", str(cid), "duplicate or invalid command id"))
        seen.add(cid)
        if not isinstance(command.get("executable"), str) or not isinstance(command.get("argv"), list) or command.get("expected_exit") not in {"zero", "nonzero"}:
            findings.append(finding("RMAP-CMD-SHAPE", str(cid), "command shape is invalid"))
        if not isinstance(command.get("timeout_seconds"), int) or command["timeout_seconds"] <= 0:
            findings.append(finding("RMAP-CMD-SHAPE", str(cid), "timeout must be positive"))
        unsafe_path = False
        for arg in command.get("argv", []):
            if isinstance(arg, str) and PLACEHOLDER_RE.search(arg):
                findings.append(finding("RMAP-CMD-PLACEHOLDER", str(cid), "untyped interpolation is forbidden"))
            elif isinstance(arg, dict) and (set(arg) != {"type", "value"} or arg.get("type") not in ALLOWED_PLACEHOLDERS):
                findings.append(finding("RMAP-CMD-PLACEHOLDER", str(cid), "invalid typed placeholder"))
            elif isinstance(arg, dict) and arg.get("type") in {"repo_path", "plan_path", "run_path"} and not typed_path_is_safe(arg.get("value"), arg.get("type"), plan_root):
                unsafe_path = True
            elif not isinstance(arg, (str, dict)):
                findings.append(finding("RMAP-CMD-SHAPE", str(cid), "argv item is invalid"))
        cwd = command.get("cwd")
        if not isinstance(cwd, dict) or set(cwd) != {"type", "value"} or cwd.get("type") not in ALLOWED_PLACEHOLDERS:
            findings.append(finding("RMAP-CMD-PLACEHOLDER", str(cid), "cwd must be typed"))
        elif cwd.get("type") in {"repo_path", "plan_path", "run_path"} and not typed_path_is_safe(cwd.get("value"), cwd.get("type"), plan_root):
            unsafe_path = True
        if unsafe_path:
            findings.append(finding("RMAP-CMD-PATH-CONTAINMENT", str(cid), "typed path escapes its declared root"))
        declared_predicate = command.get("declared_predicate")
        if declared_predicate is not None and declared_predicate not in PREDICATE_AUTHORITY:
            findings.append(finding("RMAP-CMD-SHAPE", str(cid), "declared predicate is invalid"))
        if command.get("slice_id") is not None and not re.fullmatch(r"RMAP-S[0-9]+", str(command.get("slice_id"))):
            findings.append(finding("RMAP-CMD-SHAPE", str(cid), "slice id is invalid"))
    return findings


def validate_contract(plan_root: Path, contract: dict[str, Any], registry: dict[str, Any], commands: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    schema = strict_json(plan_root / "schemas" / "implementation-contract.v1.schema.json")
    contract_schema_error = schema_error(contract, schema)
    if contract_schema_error:
        return [finding("RMAP-STRUCT-SCHEMA", "implementation-contract", contract_schema_error)]
    source = (plan_root / "../../agentbuild.txt").resolve()
    if contract.get("source_revision") != sha256_file(source):
        findings.append(finding("RMAP-HASH-SOURCE", "implementation-contract", "source revision is stale"))
    source_hashes = contract.get("authority", {}).get("source_hashes", {})
    if not isinstance(source_hashes, dict) or not source_hashes:
        findings.append(finding("RMAP-HASH-AUTHORITY", "authority.source_hashes", "authority hashes are missing"))
    else:
        for relative_path, expected_hash in source_hashes.items():
            authority_path = (plan_root / relative_path).resolve()
            if not HASH_RE.fullmatch(str(expected_hash)) or not authority_path.is_file() or sha256_file(authority_path) != expected_hash:
                findings.append(finding("RMAP-HASH-AUTHORITY", relative_path, "authority hash is missing or stale"))
    ownership = contract.get("ownership", {})
    owner_values = [ownership.get(key) for key in ("framework_adr", "standard_owner", "common_protocol_owner", "plan_instance_owner", "runtime_evidence_owner")]
    if any(not isinstance(value, str) or not value for value in owner_values) or len(owner_values) != len(set(owner_values)):
        findings.append(finding("RMAP-OWNERSHIP-DUPLICATE", "ownership", "ownership paths must be nonempty and unique"))
    backend = contract.get("backend", {})
    if backend.get("hidden_state") is not False or backend.get("provider_scheduling") is not False or backend.get("subprocess_ownership") is not False:
        findings.append(finding("RMAP-BACKEND-STATE", "backend", "backend must be stateless and scheduler-free"))
    forbidden_backend = {"semantic-review", "done", "commit", "implementation-accepted", "protected-handoff", "release-ready"}
    if set(backend.get("authorities", [])) & forbidden_backend or not forbidden_backend.issubset(set(backend.get("forbidden_authorities", []))):
        findings.append(finding("RMAP-BACKEND-AUTHORITY", "backend", "backend authority escaped"))
    recovery = contract.get("recovery", {})
    if recovery.get("initial_state") != "initialized" or recovery.get("successor_initial_state") != "initialized" or recovery.get("stale_state") != "stale" or recovery.get("append_only") is not True:
        findings.append(finding("RMAP-RECOVERY-NEW-RUN-STATE", "recovery", "successor or state contract is invalid"))
    drift = contract.get("drift_policy", {})
    required_drift = {"block_git_index_drift", "block_authority_drift", "block_contract_drift", "block_validator_drift", "block_command_registry_drift", "block_write_set_overlap", "block_execution_read_set_drift", "block_dependency_closure_drift", "allow_unrelated_worktree_drift"}
    if set(drift) != required_drift or any(drift.get(key) is not True for key in required_drift):
        findings.append(finding("RMAP-HASH-DRIFT-POLICY", "drift-policy", "drift policy is incomplete"))
    policy = contract.get("acceptance_policy", {})
    if policy.get("high_risk_p2_deferrable") is not False:
        findings.append(finding("RMAP-REVIEW-P2-HIGH-RISK", "acceptance-policy", "high-risk P2 cannot be deferred"))
    if policy.get("release_authorized") is not False or policy.get("confidence_authoritative") is not False:
        findings.append(finding("RMAP-AUTH-ACCEPTANCE", "acceptance-policy", "confidence or release authority escaped"))
    now = datetime.now(timezone.utc)
    for deferred in policy.get("p2_deferrals", []):
        try:
            expires = datetime.fromisoformat(deferred["expires_at"].replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError):
            findings.append(finding("RMAP-REVIEW-P2-DISPOSITION", "p2-deferral", "invalid deferral")); continue
        required = {"finding_id", "risk", "owner", "non_impact_proof", "expires_at", "closure_test", "status"}
        if set(deferred) != required or deferred.get("status") != "deferred" or not all(deferred.get(key) for key in required):
            findings.append(finding("RMAP-REVIEW-P2-DISPOSITION", str(deferred.get("finding_id")), "deferral is incomplete"))
        elif expires <= now:
            findings.append(finding("RMAP-REVIEW-P2-EXPIRED", deferred["finding_id"], "deferral is expired"))
        elif deferred.get("risk") in {"security", "data_loss", "authority_bypass", "evidence_integrity", "irreversible_mutation", "release_bypass"}:
            findings.append(finding("RMAP-REVIEW-P2-HIGH-RISK", deferred["finding_id"], "high-risk P2 is deferred"))
    shadows = contract.get("shadow_backfills")
    expected_shadow = ["llm-review-evidence-gate-hardening", "phase-a-frontend-gdd-to-module-workflow-hardening", "phase-frontend-boundary-hardening"]
    if not isinstance(shadows, list) or [item.get("plan_id") for item in shadows] != expected_shadow:
        findings.append(finding("RMAP-SHADOW-ORDER", "shadow-backfills", "shadow plan order mismatch"))
    elif any(item.get("authoritative") is not False or item.get("mode") != "additive-metadata-shadow-only" for item in shadows):
        findings.append(finding("RMAP-SHADOW-AUTHORITY", "shadow-backfills", "shadow backfill gained authority"))
    req_map = {item["id"]: item for item in registry.get("requirements", [])}
    command_map = {item["id"]: item for item in commands.get("commands", [])}
    command_ids = set(command_map)
    slices = contract.get("slices")
    if not isinstance(slices, list):
        return findings + [finding("RMAP-TDD-SLICE", "slices", "slices must be a list")]
    slice_ids = [item.get("slice_id") for item in slices if isinstance(item, dict)]
    if slice_ids != [f"RMAP-S{index}" for index in range(8)]:
        findings.append(finding("RMAP-TDD-SLICE", "slices", "slice sequence mismatch"))
    seen: set[str] = set()
    for item in slices:
        sid = item.get("slice_id", "slice")
        deps = item.get("depends_on", [])
        if any(dep not in seen for dep in deps):
            findings.append(finding("RMAP-TDD-DEPENDENCY", sid, "dependency is missing or forward"))
        seen.add(sid)
        reqs = item.get("requirement_ids", [])
        expected_acceptance = {req_map[rid]["acceptance_id"] for rid in reqs if rid in req_map}
        if set(reqs) - set(req_map) or set(item.get("acceptance_ids", [])) != expected_acceptance:
            findings.append(finding("RMAP-TDD-ACCEPTANCE", sid, "requirement or acceptance mapping mismatch"))
        tdd = item.get("tdd", {})
        used_commands = [tdd.get("red", {}).get("command_id"), tdd.get("green", {}).get("command_id"), *tdd.get("refactor", {}).get("command_ids", [])]
        if any(command not in command_ids for command in used_commands):
            findings.append(finding("RMAP-CMD-UNKNOWN", sid, "slice references unknown command"))
        proof_command = command_map.get(tdd.get("green", {}).get("command_id"), {})
        if proof_command.get("declared_predicate") != item.get("exit_predicate") or proof_command.get("slice_id") != sid:
            findings.append(finding("RMAP-TDD-EXIT-PROOF", sid, "GREEN command cannot prove its exit predicate"))
        allowed = item.get("allowed_changes", {})
        write_paths = allowed.get("production", []) + allowed.get("tests", []) + allowed.get("documentation", [])
        forbidden_paths = item.get("forbidden_changes", [])
        overlap = next(((write_path, forbidden_path) for write_path in write_paths for forbidden_path in forbidden_paths if glob_patterns_overlap(write_path, forbidden_path)), None)
        if overlap:
            findings.append(finding("RMAP-PATH-OVERLAP", sid, f"write/forbidden overlap: {overlap[0]} <> {overlap[1]}"))
        if not item.get("execution_read_set") or not item.get("dependency_closure") or item.get("exit_predicate") not in PREDICATE_AUTHORITY:
            findings.append(finding("RMAP-PATH-CLOSURE", sid, "read/dependency/predicate closure is missing"))
    slice_requirements = {rid for item in slices for rid in item.get("requirement_ids", [])}
    if slice_requirements != set(req_map):
        findings.append(finding("RMAP-TDD-REQUIREMENT-COVERAGE", "slices", "active requirement union differs from slice coverage"))
    return findings


def validate_shadow_registry(shadow: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    expected = ["llm-review-evidence-gate-hardening", "phase-a-frontend-gdd-to-module-workflow-hardening", "phase-frontend-boundary-hardening"]
    plans = shadow.get("plans")
    if shadow.get("authoritative") is not False or shadow.get("mode") != "additive-metadata-shadow-only":
        findings.append(finding("RMAP-SHADOW-AUTHORITY", "shadow-backfill", "shadow registry is authoritative"))
    if not isinstance(plans, list) or [item.get("plan_id") for item in plans] != expected or [item.get("order") for item in plans] != [1, 2, 3]:
        findings.append(finding("RMAP-SHADOW-ORDER", "shadow-backfill", "shadow order mismatch"))
    elif any(item.get("state_change_authorized") is not False for item in plans):
        findings.append(finding("RMAP-SHADOW-AUTHORITY", "shadow-backfill", "shadow state change is authorized"))
    findings.extend(validate_shadow_protected_trees(Path(__file__).resolve().parents[1], shadow))
    return findings


def validate_script_sizes(plan_root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for path in (plan_root / "tools").rglob("*.py"):
        lines = len(path.read_text(encoding="utf-8").splitlines())
        if lines > 400:
            findings.append(finding("RMAP-STRUCT-SCRIPT-SIZE", path.relative_to(plan_root).as_posix(), f"script has {lines} lines"))
    return findings


def validate_static(plan_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    findings = validate_required_files(plan_root)
    checks.append({"rule_id": "RMAP-STRUCT-REQUIRED", "status": "pass" if not findings else "fail", "evidence": ["required artifact inventory"]})
    data, load_findings = load_machine(plan_root); findings.extend(load_findings)
    if load_findings:
        return checks, findings, data
    requirement_ids = {item["id"] for item in data["requirements"].get("requirements", []) if isinstance(item, dict) and "id" in item}
    groups = [
        ("RMAP-STRUCT-LINKS", validate_links(plan_root)),
        ("RMAP-REQ-REGISTRY", validate_requirements(plan_root, data["requirements"], data["quality"])),
        ("RMAP-REQ-COVERAGE", validate_coverage(plan_root, data["coverage"], requirement_ids)),
        ("RMAP-REQ-DELTAS", validate_deltas(data["deltas"], requirement_ids)),
        ("RMAP-AUTH-PREDICATES", validate_plan_state(data["state"])),
        ("RMAP-CMD-REGISTRY", validate_commands(data["commands"], plan_root)),
        ("RMAP-CONTRACT", validate_contract(plan_root, data["contract"], data["requirements"], data["commands"])),
        ("RMAP-SHADOW", validate_shadow_registry(data["shadow"])),
        ("RMAP-SCRIPT-SIZE", validate_script_sizes(plan_root)),
    ]
    for check_id, group_findings in groups:
        findings.extend(group_findings)
        checks.append({"rule_id": check_id, "status": "pass" if not group_findings else "fail", "evidence": [f"{check_id} deterministic checks"]})
    return checks, findings, data
