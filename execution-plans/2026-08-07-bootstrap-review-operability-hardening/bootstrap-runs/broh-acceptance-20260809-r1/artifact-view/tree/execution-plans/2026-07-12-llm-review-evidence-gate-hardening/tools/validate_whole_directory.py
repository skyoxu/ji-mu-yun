from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from typing import Any
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parents[1]
SKILL_ROOT = REPOSITORY_ROOT / ".agents/skills/run-phase-bootstrap-review"
SCHEMA_ROOT = SKILL_ROOT / "schemas"
REQUIRED_BOOKS = [
    "00-index.md",
    "01-scope-authority-and-non-goals.md",
    "02-finding-contract-and-severity.md",
    "03-code-document-and-plan-adapters.md",
    "04-gateway-dedup-verification-and-memory.md",
    "05-bmad-gds-and-codex-integration.md",
    "06-testing-observability-and-rollout.md",
    "07-implementation-phases.md",
    "08-risks-dod-and-glossary.md",
    "09-bootstrap-review-operator-guide.md",
    "96-global-review-and-validation.md",
    "97-plan-added-requirements-ledger.md",
    "98-source-to-split-audit.md",
    "99-source-coverage.md",
]
REQUIRED_JSON = [
    "schemas/review-finding.v1.schema.json",
    "schemas/review-rejection.v1.schema.json",
    "schemas/review-result.v1.schema.json",
    "schemas/bootstrap-review-gate-result.v1.schema.json",
    "schemas/bootstrap-preflight-result.v1.schema.json",
    "schemas/bootstrap-review-launch-authorization.v1.schema.json",
    "schemas/bootstrap-process-leases.v1.schema.json",
    "schemas/review-validation-fixtures.v1.json",
    "schemas/bootstrap-reviewer-output.v1.schema.json",
    "schemas/bootstrap-verifier-output.v1.schema.json",
    "bootstrap/review-profiles.v1.json",
]
REQUIRED_TOOLS = [
    "tools/run_bootstrap_review.py",
    "tools/tests/test_run_bootstrap_review.py",
]
LINK_PATTERN = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
RFG_PATTERN = re.compile(r"\bRFG-(\d{3})\b")
REVIEWER_ROLES = {
    "blind_hunter",
    "edge_case_hunter",
    "acceptance_auditor",
    "document_reviewer",
    "security_reviewer",
    "manual_reviewer",
}


def strict_json_loads(text: str) -> Any:
    def reject_non_finite(value: str) -> None:
        raise ValueError(f"Non-finite JSON number is not allowed: {value}")

    return json.loads(text, parse_constant=reject_non_finite)
TRUSTED_REVIEW_POLICIES = {
    (
        "review-policy://plan-standard/v1",
        "sha256:9191919191919191919191919191919191919191919191919191919191919191",
    ): {"blind_hunter", "edge_case_hunter"},
    (
        "review-policy://edge-only/v1",
        "sha256:9292929292929292929292929292929292929292929292929292929292929292",
    ): {"edge_case_hunter"},
    (
        "review-policy://blocker-pair/v1",
        "sha256:9393939393939393939393939393939393939393939393939393939393939393",
    ): {"blind_hunter", "acceptance_auditor"},
}


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def validate_files(errors: list[str]) -> None:
    for relative in [*REQUIRED_BOOKS, *REQUIRED_JSON, *REQUIRED_TOOLS]:
        if not (ROOT / relative).is_file():
            fail(errors, f"missing required artifact: {relative}")


def validate_json(errors: list[str]) -> None:
    for relative in REQUIRED_JSON:
        path = ROOT / relative
        if not path.is_file():
            continue
        try:
            data = strict_json_loads(path.read_text(encoding="utf-8"))
            if relative.endswith(".schema.json"):
                if data.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
                    fail(errors, f"schema is not Draft 2020-12: {relative}")
                if not data.get("$id"):
                    fail(errors, f"schema has no $id: {relative}")
        except (OSError, ValueError) as exc:
            fail(errors, f"invalid JSON {relative}: {exc}")


def validate_links(errors: list[str]) -> None:
    for path in ROOT.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        for raw_target in LINK_PATTERN.findall(text):
            target = raw_target.split("#", 1)[0].strip()
            if not target or "://" in target or target.startswith("#"):
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                fail(errors, f"broken link in {path.name}: {raw_target}")


def validate_requirements(errors: list[str]) -> None:
    ledger = (ROOT / "97-plan-added-requirements-ledger.md").read_text(encoding="utf-8")
    coverage = (ROOT / "99-source-coverage.md").read_text(encoding="utf-8")
    source_audit = (ROOT / "98-source-to-split-audit.md").read_text(encoding="utf-8")
    coverage_table = coverage.split("## 3. Requirement Coverage", 1)[1].split(
        "## 4. Cross-cutting Coverage", 1
    )[0]
    expected = [f"{number:03d}" for number in range(1, 66)]
    expected_ids = [f"RFG-{number}" for number in expected]
    ledger_rows: dict[str, tuple[str, str]] = {}
    ordered_ids: list[str] = []
    for line in ledger.splitlines():
        if not re.match(r"^\| RFG-\d{3} \|", line):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 6:
            fail(errors, f"requirement row has invalid column count: {cells[0]}")
            continue
        identifier, requirement, owner, phase, acceptance, status = cells
        ordered_ids.append(identifier)
        if identifier in ledger_rows:
            fail(errors, f"duplicate requirement ID: {identifier}")
        ledger_rows[identifier] = (owner, phase)
        if not requirement:
            fail(errors, f"requirement text is empty: {identifier}")
        if owner not in {"01", "02", "03", "04", "05", "06", "09", "96"}:
            fail(errors, f"invalid requirement owner {owner}: {identifier}")
        if phase not in {f"R{number}" for number in range(7)}:
            fail(errors, f"invalid requirement phase {phase}: {identifier}")
        expected_acceptance = rf"`review-gate://{re.escape(identifier)}/[a-z0-9-]+`"
        if re.fullmatch(expected_acceptance, acceptance) is None:
            fail(errors, f"invalid acceptance ref {acceptance}: {identifier}")
        if status not in {"active", "superseded"}:
            fail(errors, f"invalid requirement status {status}: {identifier}")
    if ordered_ids != expected_ids:
        fail(errors, f"ledger IDs differ from {expected_ids[0]}..{expected_ids[-1]}: {ordered_ids}")

    coverage_owner_phase: dict[str, tuple[str, str]] = {}
    for line in coverage_table.splitlines():
        if not line.startswith("|") or "RFG-" not in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 2 or "/" not in cells[0]:
            fail(errors, f"invalid coverage row: {line}")
            continue
        owner, phase = [part.strip() for part in cells[0].split("/", 1)]
        for identifier in re.findall(r"RFG-\d{3}", cells[1]):
            if identifier in coverage_owner_phase:
                fail(errors, f"duplicate coverage mapping: {identifier}")
            coverage_owner_phase[identifier] = (owner, phase)
    for number in expected:
        identifier = f"RFG-{number}"
        if identifier not in coverage_owner_phase:
            fail(errors, f"coverage is missing {identifier}")
        elif coverage_owner_phase[identifier] != ledger_rows.get(identifier):
            fail(
                errors,
                f"coverage owner/phase mismatch for {identifier}: "
                f"ledger={ledger_rows.get(identifier)} coverage={coverage_owner_phase[identifier]}",
            )
        source_count = len(re.findall(rf"\b{re.escape(identifier)}\b", source_audit.split("## 3.", 1)[0]))
        if source_count != 1:
            fail(errors, f"source audit must contain {identifier} exactly once, found {source_count}")


def type_matches(expected: str, instance: Any) -> bool:
    if expected == "object":
        return isinstance(instance, dict)
    if expected == "array":
        return isinstance(instance, list)
    if expected == "string":
        return isinstance(instance, str)
    if expected == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if expected == "number":
        return isinstance(instance, (int, float)) and not isinstance(instance, bool)
    return True


def schema_errors(
    schema: dict[str, Any],
    instance: Any,
    registry: dict[str, dict[str, Any]],
    path: str = "$",
    root_schema: dict[str, Any] | None = None,
) -> list[str]:
    root_schema = schema if root_schema is None else root_schema
    result: list[str] = []
    if "$ref" in schema:
        reference = schema["$ref"]
        if isinstance(reference, str) and reference.startswith("#/$defs/"):
            target_schema = root_schema.get("$defs", {}).get(reference.removeprefix("#/$defs/"))
            if not isinstance(target_schema, dict):
                return [f"{path}: unresolved $ref {reference}"]
            result.extend(schema_errors(target_schema, instance, registry, path, root_schema))
        else:
            target = Path(reference).name
            if target not in registry:
                return [f"{path}: unresolved $ref {reference}"]
            result.extend(schema_errors(registry[target], instance, registry, path, registry[target]))
    expected_type = schema.get("type")
    if expected_type and not type_matches(expected_type, instance):
        return [f"{path}: expected {expected_type}"]
    if "const" in schema and instance != schema["const"]:
        result.append(f"{path}: const mismatch")
    if "enum" in schema and instance not in schema["enum"]:
        result.append(f"{path}: enum mismatch")
    if isinstance(instance, str):
        if len(instance) < schema.get("minLength", 0):
            result.append(f"{path}: string shorter than minLength")
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            result.append(f"{path}: pattern mismatch")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            result.append(f"{path}: below minimum")
        if "maximum" in schema and instance > schema["maximum"]:
            result.append(f"{path}: above maximum")
    if isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0):
            result.append(f"{path}: fewer than minItems")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            result.append(f"{path}: more than maxItems")
        if schema.get("uniqueItems") and len({json.dumps(x, sort_keys=True) for x in instance}) != len(instance):
            result.append(f"{path}: duplicate items")
        if "items" in schema:
            for index, item in enumerate(instance):
                result.extend(schema_errors(schema["items"], item, registry, f"{path}[{index}]", root_schema))
        if "contains" in schema:
            match_count = sum(
                not schema_errors(schema["contains"], item, registry, f"{path}[{index}]", root_schema)
                for index, item in enumerate(instance)
            )
            if match_count < schema.get("minContains", 1):
                result.append(f"{path}: fewer than minContains matches")
            if "maxContains" in schema and match_count > schema["maxContains"]:
                result.append(f"{path}: more than maxContains matches")
    if isinstance(instance, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                result.append(f"{path}: missing required {key}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in properties:
                    result.append(f"{path}: unexpected property {key}")
        for key, child_schema in properties.items():
            if key in instance:
                result.extend(schema_errors(child_schema, instance[key], registry, f"{path}.{key}", root_schema))
    for child in schema.get("allOf", []):
        result.extend(schema_errors(child, instance, registry, path, root_schema))
    if "anyOf" in schema and all(schema_errors(child, instance, registry, path, root_schema) for child in schema["anyOf"]):
        result.append(f"{path}: no anyOf branch matched")
    if "not" in schema and not schema_errors(schema["not"], instance, registry, path, root_schema):
        result.append(f"{path}: prohibited schema matched")
    if "if" in schema:
        if not schema_errors(schema["if"], instance, registry, path, root_schema):
            result.extend(schema_errors(schema.get("then", {}), instance, registry, path, root_schema))
        else:
            result.extend(schema_errors(schema.get("else", {}), instance, registry, path, root_schema))
    return result


def finding_semantic_errors(instance: Any) -> list[str]:
    if not isinstance(instance, dict):
        return []
    result: list[str] = []
    start_line = instance.get("startLine")
    end_line = instance.get("endLine")
    if isinstance(start_line, int) and isinstance(end_line, int) and end_line < start_line:
        result.append("$: endLine must be greater than or equal to startLine")
    severity = instance.get("proposedSeverity")
    status = instance.get("status")
    if severity in {"P0", "P1"} and status == "advisory":
        result.append("$: P0/P1 cannot use advisory status")
    if severity == "P2" and status in {"confirmed", "unverified"}:
        result.append("$: P2 cannot use confirmed or unverified status")
    unverified_class = instance.get("unverifiedClass")
    unverified_disposition = instance.get("unverifiedDisposition")
    if status != "unverified" and (
        "unverifiedClass" in instance or "unverifiedDisposition" in instance
    ):
        result.append("$: unverified classification is gateway-owned and only valid for unverified findings")
    if unverified_class in {"security", "data_loss"} and unverified_disposition != "blocking":
        result.append("$: security and data-loss unverified findings require blocking disposition")
    if unverified_class == "other" and unverified_disposition != "manual_pause":
        result.append("$: other unverified findings require manual-pause disposition")
    if status == "unverified" and instance.get("dimension") == "security" and unverified_class != "security":
        result.append("$: security dimension requires security unverified class")
    return result


def result_semantic_errors(
    instance: Any,
    assigned_policy_key: tuple[Any, Any] | None = None,
) -> list[str]:
    if not isinstance(instance, dict):
        return []
    result: list[str] = []
    required = set(instance.get("requiredLayers", []))
    completed = set(instance.get("completedLayers", []))
    failed = set(instance.get("failedLayers", []))
    skipped_items = instance.get("skippedLayers", [])
    skipped_roles = [item.get("reviewerLayer") for item in skipped_items if isinstance(item, dict)]
    skipped = set(skipped_roles)
    policy_key = (instance.get("reviewProfile"), instance.get("policyRevision"))
    if assigned_policy_key is None:
        result.append("$: trusted review policy assignment is missing")
    elif policy_key != assigned_policy_key:
        result.append("$: reviewProfile/policyRevision must match gateway-assigned policy")
    policy_required = TRUSTED_REVIEW_POLICIES.get(assigned_policy_key)
    if assigned_policy_key is not None and policy_required is None:
        result.append("$: reviewProfile and policyRevision must resolve through trusted review policy")
    elif required != policy_required:
        result.append("$: requiredLayers must match trusted review policy")
    if len(skipped_roles) != len(skipped):
        result.append("$: skippedLayers contains duplicate reviewer roles")
    if required != completed | failed:
        result.append("$: requiredLayers must equal completedLayers union failedLayers")
    if completed & failed:
        result.append("$: completedLayers and failedLayers must be disjoint")
    if required & skipped:
        result.append("$: skippedLayers must be disjoint from requiredLayers")
    if not required.issubset(REVIEWER_ROLES):
        result.append("$: requiredLayers contains an unknown reviewer role")
    if instance.get("status") == "clean" and (required != completed or failed):
        result.append("$: clean requires every required reviewer to complete")
    findings = [item for item in instance.get("findings", []) if isinstance(item, dict)]
    blocking_unverified = [
        item
        for item in findings
        if item.get("status") == "unverified" and item.get("unverifiedDisposition") == "blocking"
    ]
    manual_pause_unverified = [
        item
        for item in findings
        if item.get("status") == "unverified" and item.get("unverifiedDisposition") == "manual_pause"
    ]
    result_status = instance.get("status")
    if blocking_unverified and result_status != "blocked":
        result.append("$: blocking unverified finding requires blocked result")
    confirmed_blockers = [
        item
        for item in findings
        if item.get("status") == "confirmed" and item.get("proposedSeverity") in {"P0", "P1"}
    ]
    if result_status == "blocked" and manual_pause_unverified:
        result.append("$: manual-pause unverified finding cannot appear in blocked result")
    return result


def validate_fixture_intent(errors: list[str]) -> None:
    path = SCHEMA_ROOT / "review-validation-fixtures.v1.json"
    if not path.is_file():
        return
    data = strict_json_loads(path.read_text(encoding="utf-8"))
    if data.get("validationMode") != "schema+gateway":
        fail(errors, "fixture suite validationMode must be schema+gateway")
    cases = data.get("cases", [])
    assignments = data.get("gatewayPolicyAssignments", {})
    ids = [case.get("id") for case in cases]
    required = {
        "zero-findings-clean",
        "document-finding-complete-triplet",
        "document-finding-missing-consumer",
        "failed-layer-cannot-be-clean",
        "p0-missing-exact-evidence",
        "p1-missing-bad-outcome",
        "p2-missing-guard-analysis",
        "schema-rejection-record",
        "low-confidence-finding",
        "blocked-result-requires-blocker",
        "advisory-result-requires-p2",
        "blocked-result-with-p1",
        "advisory-result-with-p2",
        "incomplete-result-with-failed-layer",
        "all-required-layers-skipped-clean",
        "reversed-line-range",
        "p1-cannot-be-advisory",
        "p2-cannot-be-unverified",
        "finding-missing-route-version",
        "producer-cannot-narrow-required-layers",
        "blocking-unverified-result",
        "blocking-unverified-cannot-be-incomplete",
        "manual-pause-unverified-result",
        "manual-pause-unverified-cannot-be-blocked",
        "candidate-cannot-set-unverified-disposition",
        "producer-cannot-substitute-trusted-profile",
        "security-unverified-cannot-manual-pause",
    }
    if set(ids) != required or len(ids) != len(set(ids)):
        fail(errors, f"fixture case IDs mismatch: {ids}")
    registry = {
        path.name: strict_json_loads(path.read_text(encoding="utf-8"))
        for path in SCHEMA_ROOT.glob("*.schema.json")
    }
    for case in cases:
        schema_name = case.get("schema")
        if schema_name not in registry:
            fail(errors, f"fixture {case.get('id')} references unknown schema {schema_name}")
            continue
        instance = case.get("instance")
        schema_validation_errors = schema_errors(registry[schema_name], instance, registry)
        validation_errors = list(schema_validation_errors)
        if schema_name == "review-finding.v1.schema.json":
            validation_errors.extend(finding_semantic_errors(instance))
        if schema_name == "review-result.v1.schema.json":
            assignment = assignments.get(instance.get("reviewId"), {}) if isinstance(instance, dict) else {}
            assigned_policy_key = (
                assignment.get("reviewProfile"),
                assignment.get("policyRevision"),
            ) if assignment else None
            validation_errors.extend(result_semantic_errors(instance, assigned_policy_key))
        schema_valid = not schema_validation_errors
        actual_valid = not validation_errors
        expected_schema_valid = case.get("expectedSchemaValid")
        if expected_schema_valid is not None and schema_valid is not expected_schema_valid:
            fail(
                errors,
                f"fixture {case.get('id')} expectedSchemaValid={expected_schema_valid} actualSchemaValid={schema_valid}",
            )
        if schema_valid != actual_valid and expected_schema_valid is None:
            fail(errors, f"fixture {case.get('id')} must declare expectedSchemaValid for gateway-only rejection")
        if actual_valid is not case.get("expectedValid"):
            fail(
                errors,
                f"fixture {case.get('id')} expectedValid={case.get('expectedValid')} actualValid={actual_valid}",
            )
        for expected_error in case.get("expectedErrorContains", []):
            if not any(expected_error in error for error in validation_errors):
                fail(errors, f"fixture {case.get('id')} missing expected error: {expected_error}")


def validate_semantic_contracts(errors: list[str]) -> None:
    finding_schema = strict_json_loads(
        (SCHEMA_ROOT / "review-finding.v1.schema.json").read_text(encoding="utf-8")
    )
    rejection_schema = strict_json_loads(
        (SCHEMA_ROOT / "review-rejection.v1.schema.json").read_text(encoding="utf-8")
    )
    result_schema = strict_json_loads(
        (SCHEMA_ROOT / "review-result.v1.schema.json").read_text(encoding="utf-8")
    )
    if finding_schema["properties"]["confidence"].get("minimum") != 0.8:
        fail(errors, "finding confidence minimum must be 0.8")
    if "rejected" in finding_schema["properties"]["status"].get("enum", []):
        fail(errors, "rejected must use the rejection contract, not finding status")
    if "sourceReviewers" not in finding_schema.get("required", []):
        fail(errors, "finding contract must require sourceReviewers provenance")
    if "routeVersion" not in finding_schema.get("required", []):
        fail(errors, "finding contract must require routeVersion")
    source_roles = set(finding_schema["properties"]["sourceReviewers"]["items"].get("enum", []))
    required_roles = {"blind_hunter", "edge_case_hunter", "acceptance_auditor"}
    if not required_roles.issubset(source_roles):
        fail(errors, "finding sourceReviewers must include all three routed reviewer roles")
    rejection_required = set(rejection_schema.get("required", []))
    if "suppressionFingerprint" not in rejection_required:
        fail(errors, "rejection contract must require suppressionFingerprint")
    reason_codes = set(rejection_schema["properties"]["reasonCode"].get("enum", []))
    if "low_confidence" not in reason_codes:
        fail(errors, "rejection reason codes must include low_confidence")
    if "routeVersion" not in rejection_required:
        fail(errors, "rejection contract must require routeVersion")
    rejection_roles = set(rejection_schema["properties"]["reviewerLayer"].get("enum", []))
    failed_roles = set(result_schema["properties"]["failedLayers"]["items"].get("enum", []))
    skipped_roles = set(
        result_schema["properties"]["skippedLayers"]["items"]["properties"]["reviewerLayer"].get("enum", [])
    )
    if not (source_roles == rejection_roles == failed_roles == skipped_roles):
        fail(errors, "reviewer role vocabulary must match across finding/rejection/result contracts")
    result_required = set(result_schema.get("required", []))
    for field in [
        "routeVersion",
        "reviewProfile",
        "policyRevision",
        "requiredLayers",
        "completedLayers",
        "skippedLayers",
    ]:
        if field not in result_required:
            fail(errors, f"result contract must require {field}")
    if "unverifiedDisposition" not in finding_schema["properties"]:
        fail(errors, "finding contract must define unverifiedDisposition")
    if "unverifiedClass" not in finding_schema["properties"]:
        fail(errors, "finding contract must define unverifiedClass")
    result_text = json.dumps(result_schema, sort_keys=True)
    for keyword in ["advisory", "blocked", "incomplete", "contains", "minContains"]:
        if keyword not in result_text:
            fail(errors, f"result schema is missing semantic constraint: {keyword}")

    scope_text = (ROOT / "01-scope-authority-and-non-goals.md").read_text(encoding="utf-8")
    integration_text = (ROOT / "05-bmad-gds-and-codex-integration.md").read_text(encoding="utf-8")
    if "plan-local schema/validator、Bootstrap Review CLI/fixtures/operator guide" not in scope_text:
        fail(errors, "upstream wait gate must limit pre-handoff schema work to plan-local artifacts")
    documentation_sync_markers = [
        "R1 新增 `docs/standards/llm-review-findings.md`",
        "R2 平台开发 gateway 真正 operational",
        "R3 三层 reviewer 新 route 切换",
        "R4 前台用户可见行为",
        "R6 只同步最终",
    ]
    for marker in documentation_sync_markers:
        if marker not in integration_text:
            fail(errors, f"documentation synchronization contract is missing: {marker}")

    ledger_text = (ROOT / "96-global-review-and-validation.md").read_text(encoding="utf-8")
    finding_rows = [line for line in ledger_text.splitlines() if line.startswith("| RFG-REV-")]
    seen_findings: set[str] = set()
    for row in finding_rows:
        cells = [cell.strip().replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", row.strip("|"))]
        if len(cells) != 5:
            fail(errors, f"finding row has invalid Markdown column count: {row[:80]}")
            continue
        finding_id, severity, status, evidence, closure = cells
        if finding_id in seen_findings:
            fail(errors, f"duplicate historical finding ID: {finding_id}")
        seen_findings.add(finding_id)
        match = re.fullmatch(r"RFG-REV-(\d+)-(P[012])-(\d{2})", finding_id)
        if match is None or match.group(2) != severity:
            fail(errors, f"invalid historical finding identity/severity: {finding_id}/{severity}")
        if status == "Open":
            fail(errors, f"historical finding remains open: {finding_id}")
        elif status == "Closed":
            if "Source refs:" not in evidence or "acceptance:" not in closure:
                fail(errors, f"closed finding lacks proof fields: {finding_id}")
        elif status == "Refuted":
            if "Source refs:" not in evidence or "Counterevidence:" not in closure or "acceptance:" not in closure:
                fail(errors, f"refuted finding lacks counterevidence fields: {finding_id}")
        else:
            fail(errors, f"invalid historical finding status: {finding_id}/{status}")
    gateway_text = (ROOT / "04-gateway-dedup-verification-and-memory.md").read_text(encoding="utf-8")
    if "P2 confirmed advisory" in gateway_text or "Given P2 advisory" not in gateway_text:
        fail(errors, "P2 result terminology must use advisory, never confirmed advisory")
    if "准备开始 R1–R6" not in scope_text:
        fail(errors, "upstream handoff acceptance must cover R1 through R6")
    index_text = (ROOT / "00-index.md").read_text(encoding="utf-8")
    if "7 月 7 日既有历史 review run、prompt、输出和 ledger 保持不变" not in index_text:
        fail(errors, "the current July 7 in-flight review must remain isolated")
    if "Blind Hunter" not in integration_text or "Edge Case Hunter" not in integration_text or "Acceptance Auditor" not in integration_text:
        fail(errors, "all three reviewer roles must be routed explicitly")
    if "candidate/finding/result/rejection" not in gateway_text:
        fail(errors, "routeVersion must bind candidate, finding, result, and rejection")
    if "fingerprint 输入至少包含 routeVersion" not in gateway_text or "routeVersion、candidate hash" not in gateway_text:
        fail(errors, "finding and suppression fingerprints must include routeVersion")


def validate_bootstrap_contracts(errors: list[str]) -> None:
    profile_path = SKILL_ROOT / "references/review-profiles.v1.json"
    reviewer_schema_path = SCHEMA_ROOT / "bootstrap-reviewer-output.v1.schema.json"
    verifier_schema_path = SCHEMA_ROOT / "bootstrap-verifier-output.v1.schema.json"
    preflight_schema_path = SCHEMA_ROOT / "bootstrap-preflight-result.v1.schema.json"
    gate_schema_path = SCHEMA_ROOT / "bootstrap-review-gate-result.v1.schema.json"
    tool_path = SKILL_ROOT / "scripts/bootstrap_review.py"
    helper_path = SKILL_ROOT / "scripts/_control_plane.py"
    test_path = SKILL_ROOT / "tests/test_bootstrap_review.py"
    if not all(path.is_file() for path in [
        profile_path, reviewer_schema_path, verifier_schema_path, preflight_schema_path,
        gate_schema_path, tool_path, helper_path, test_path,
    ]):
        return

    profile_registry = strict_json_loads(profile_path.read_text(encoding="utf-8"))
    if profile_registry.get("schemaVersion") != "bootstrap-review-profiles.v1":
        fail(errors, "bootstrap profile registry schemaVersion is invalid")
        return
    profiles = profile_registry.get("profiles")
    if not isinstance(profiles, dict):
        fail(errors, "bootstrap profile registry profiles are missing")
        return
    expected_profiles = {
        "bootstrap-upstream-plan": (
            "review-policy://bootstrap-upstream-plan/v1",
            "plan-authority",
            "authority-graph-and-current-state",
            ["plan-source", "original-requirements", "repository-rules", "current-state", "referenced-standards", "schemas-and-fixtures"],
            "gpt-5.6-terra",
            {"blind_hunter": "medium", "edge_case_hunter": "high", "acceptance_auditor": "high", "independent_verifier": "high"},
        ),
        "bootstrap-implementation-conformance": (
            "review-policy://bootstrap-implementation-conformance/v1",
            "implementation-conformance",
            "contract-to-runtime-closure",
            ["implementation-plan", "changed-production-code", "affected-consumers", "tests-and-acceptance", "runtime-evidence", "repository-rules", "referenced-standards"],
            "gpt-5.6-terra",
            {"blind_hunter": "high", "edge_case_hunter": "high", "acceptance_auditor": "high", "independent_verifier": "high"},
        ),
        "bootstrap-skill-route": (
            "review-policy://bootstrap-skill-route/v1",
            "skill-route",
            "instruction-route-contract-closure",
            ["skill-source", "operator-guide", "route-or-cli", "profiles-and-config", "schemas", "tests", "usage-evidence", "repository-rules"],
            "gpt-5.6-terra",
            {"blind_hunter": "high", "edge_case_hunter": "high", "acceptance_auditor": "high", "independent_verifier": "high"},
        ),
        "bootstrap-focused-change": (
            "review-policy://bootstrap-focused-change/v1",
            "focused-change",
            "change-impact-closure",
            ["change-intent", "changed-files", "affected-consumers", "targeted-tests", "repository-rules", "referenced-standards"],
            "gpt-5.6-terra",
            {"blind_hunter": "medium", "edge_case_hunter": "high", "acceptance_auditor": "medium", "independent_verifier": "high"},
        ),
    }
    if set(profiles) != set(expected_profiles) | {"bootstrap-focused-repair-verification"}:
        fail(errors, "bootstrap review object profile set is invalid")
        return
    required_layers = ["blind_hunter", "edge_case_hunter", "acceptance_auditor"]
    completeness_policy = {
        "artifactCoverage": "all",
        "samplingAllowed": False,
        "missingContextDisposition": "failed",
        "contextClosureRequired": True,
    }
    review_cycle_policy = {
        "repairMode": "batch_all_accepted_findings",
        "intermediateValidation": "deterministic_targeted_only",
        "defaultFullReviewRoundLimit": 2,
        "hardFullReviewRoundLimit": 3,
        "p2OnlyTriggersFullReview": False,
        "onHardLimit": "manual_pause",
        "roundIdentity": "lineage_family",
        "successorResetsRoundBudget": False,
        "roundThreeEntryReasons": [
            "novel_p0_p1",
            "authority_context_graph_changed",
            "high_risk_boundary_changed",
        ],
        "repairReviewScope": "repair_delta_closure",
    }
    content_trust_policy = {
        "reviewedArtifacts": "untrusted_data",
        "embeddedInstructions": "ignore",
        "forbiddenAuthorityChanges": [
            "role", "scope", "output-target", "model", "tools", "severity", "finding-count",
        ],
    }
    verifier_policy = {
        "preferredModel": "gpt-5.6-terra",
        "escalatedModel": "gpt-5.6-sol",
        "fallbackModels": [],
        "modelEscalateOnSeverities": ["P0"],
        "modelEscalateOnDimensions": ["security"],
        "modelEscalateOnRiskClasses": [
            "authority_control", "lifecycle_control", "protected_path", "shared_entrypoint",
        ],
        "defaultReasoningEffort": "high",
        "escalatedReasoningEffort": "max",
        "escalateOnSeverities": ["P0"],
        "escalateOnDimensions": ["security"],
    }
    access_probe_policy = {
        "discoverySidecar": "access-proof.json",
        "verifierSidecar": "verifier-access-proof.json",
        "verifierRequiresGate": True,
    }
    round_model_overrides = {"3": "gpt-5.6-sol"}
    round_reasoning_overrides = {"3": {layer: "high" for layer in required_layers}}
    focused_profile = profiles["bootstrap-focused-repair-verification"]
    expected_focused_keys = set(profiles["bootstrap-implementation-conformance"]) - {"companionCapabilities"}
    focused_instruction = focused_profile.get("reviewerInstructionPolicy")
    focused_rubrics = focused_instruction.get("roleRubrics") if isinstance(focused_instruction, dict) else None
    focused_codex = focused_profile.get("codexExecPolicy")
    focused_revision_payload = {
        key: value for key, value in focused_profile.items() if key != "policyRevision"
    }
    focused_canonical = json.dumps(
        focused_revision_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    focused_expected_revision = "sha256:" + hashlib.sha256(focused_canonical).hexdigest()
    if (
        set(focused_profile) != expected_focused_keys
        or focused_profile.get("reviewProfile") != "review-policy://bootstrap-focused-repair-verification/v1"
        or focused_profile.get("routeVersion") != "bootstrap-review-route.v2"
        or focused_profile.get("controlPlaneRevision") != "bootstrap-control-plane.v2"
        or focused_profile.get("reviewObjectType") != "focused-repair-verification"
        or focused_profile.get("reviewDepth") != "predecessor-finding-to-repair-closure"
        or focused_profile.get("requiredLayers") != ["focused_repair_verifier"]
        or focused_profile.get("readOnly") is not True
        or focused_profile.get("automaticInvocation") is not False
        or focused_profile.get("completenessPolicy") != completeness_policy
        or focused_profile.get("reviewCyclePolicy") != review_cycle_policy
        or not isinstance(focused_instruction, dict)
        or focused_instruction.get("contentTrustPolicy") != content_trust_policy
        or not isinstance(focused_rubrics, dict)
        or set(focused_rubrics) != {"focused_repair_verifier"}
        or not focused_rubrics["focused_repair_verifier"]
        or not isinstance(focused_instruction.get("falsePositiveRules"), list)
        or not focused_instruction["falsePositiveRules"]
        or not isinstance(focused_codex, dict)
        or focused_codex.get("preferredModel") != "gpt-5.6-terra"
        or focused_codex.get("fallbackModels") != []
        or focused_codex.get("forbiddenModels") != []
        or focused_codex.get("toolProbeRequired") is not True
        or focused_codex.get("roundModelOverrides") != {}
        or focused_codex.get("roundReasoningEffortOverrides") != {}
        or focused_codex.get("reasoningEffortByRole") != {
            "focused_repair_verifier": "high", "independent_verifier": "high"
        }
        or focused_profile.get("verifierPolicy") != verifier_policy
        or focused_profile.get("accessProbePolicy") != access_probe_policy
        or focused_profile.get("policyRevision") != focused_expected_revision
    ):
        fail(errors, "bootstrap focused repair materialized profile is invalid")
        return
    for name, (uri, object_type, depth, contexts, preferred_model, reasoning) in expected_profiles.items():
        profile = profiles[name]
        if profile.get("requiredLayers") != required_layers:
            fail(errors, f"{name} must require all three reviewer layers")
        if profile.get("readOnly") is not True or profile.get("automaticInvocation") is not False:
            fail(errors, f"{name} must be read-only with automatic invocation disabled")
        if profile.get("reviewProfile") != uri or profile.get("routeVersion") != "bootstrap-review-route.v2":
            fail(errors, f"{name} profile or route identity is invalid")
        if profile.get("controlPlaneRevision") != "bootstrap-control-plane.v2":
            fail(errors, f"{name} control-plane revision is invalid")
        if profile.get("reviewObjectType") != object_type or profile.get("reviewDepth") != depth:
            fail(errors, f"{name} review object type or depth is invalid")
        if profile.get("requiredContextClasses") != contexts:
            fail(errors, f"{name} required context classes are invalid")
        if profile.get("completenessPolicy") != completeness_policy:
            fail(errors, f"{name} must prohibit sampling and require complete context closure")
        if profile.get("reviewCyclePolicy") != review_cycle_policy:
            fail(errors, f"{name} full-review cycle policy is invalid")
        instruction_policy = profile.get("reviewerInstructionPolicy")
        role_rubrics = instruction_policy.get("roleRubrics") if isinstance(instruction_policy, dict) else None
        false_positive_rules = (
            instruction_policy.get("falsePositiveRules") if isinstance(instruction_policy, dict) else None
        )
        if (
            not isinstance(instruction_policy, dict)
            or instruction_policy.get("contentTrustPolicy") != content_trust_policy
            or not isinstance(role_rubrics, dict)
            or set(role_rubrics) != set(required_layers)
            or any(not isinstance(items, list) or not items for items in role_rubrics.values())
            or not isinstance(false_positive_rules, list)
            or not false_positive_rules
            or len(false_positive_rules) != len(set(false_positive_rules))
        ):
            fail(errors, f"{name} reviewer instruction/false-positive policy is invalid")
        preflight_policy = profile.get("deterministicPreflightPolicy")
        required_checks = preflight_policy.get("requiredChecks") if isinstance(preflight_policy, dict) else None
        if (
            not isinstance(preflight_policy, dict)
            or preflight_policy.get("requiredBeforeReviewerLaunch") is not True
            or preflight_policy.get("failureDisposition") != "stop_before_reviewers"
            or preflight_policy.get("evidenceDirectory") != "preflight"
            or not isinstance(required_checks, list)
            or not required_checks
            or len(required_checks) != len(set(required_checks))
        ):
            fail(errors, f"{name} deterministic preflight policy is invalid")
        codex_policy = profile.get("codexExecPolicy")
        if not isinstance(codex_policy, dict) or {
            key: codex_policy.get(key) for key in ("preferredModel", "fallbackModels", "forbiddenModels", "toolProbeRequired")
        } != {
            "preferredModel": preferred_model,
            "fallbackModels": ["gpt-5.5", "gpt-5.4"],
            "forbiddenModels": [],
            "toolProbeRequired": True,
        } or codex_policy.get("reasoningEffortByRole") != reasoning \
                or codex_policy.get("roundModelOverrides") != round_model_overrides \
                or codex_policy.get("roundReasoningEffortOverrides") != round_reasoning_overrides:
            fail(errors, f"{name} Codex exec model/reasoning policy is invalid")
        if profile.get("verifierPolicy") != verifier_policy:
            fail(errors, f"{name} independent verifier policy is invalid")
        if profile.get("accessProbePolicy") != access_probe_policy:
            fail(errors, f"{name} role-specific access probe policy is invalid")
        revision_payload = {key: value for key, value in profile.items() if key != "policyRevision"}
        canonical = json.dumps(revision_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        expected_revision = "sha256:" + hashlib.sha256(canonical).hexdigest()
        if profile.get("policyRevision") != expected_revision:
            fail(errors, f"{name} policyRevision must hash canonical profile content")

    registry = {
        path.name: strict_json_loads(path.read_text(encoding="utf-8"))
        for path in SCHEMA_ROOT.glob("*.schema.json")
    }
    reviewer_template = {
        "schemaVersion": "bootstrap-reviewer-output.v1",
        "reviewId": "bootstrap-contract-001",
        "reviewerLayer": "blind_hunter",
        "routeVersion": profile.get("routeVersion"),
        "authorityRevision": "0123456789abcdef",
        "inputHash": "sha256:" + "1" * 64,
        "status": "pending",
        "coverage": {
            "requiredArtifacts": ["example.md"],
            "readArtifacts": [],
            "missingArtifacts": ["example.md"],
        },
        "candidates": [],
    }
    for schema_name, instance in [
        (reviewer_schema_path.name, reviewer_template),
        (
            verifier_schema_path.name,
            {
                "schemaVersion": "bootstrap-verifier-output.v1",
                "reviewId": "bootstrap-contract-001",
                "routeVersion": profile.get("routeVersion"),
                "authorityRevision": "0123456789abcdef",
                "inputHash": "sha256:" + "1" * 64,
                "decisions": [],
            },
        ),
        (
            preflight_schema_path.name,
            {
                "schemaVersion": "bootstrap-preflight-result.v1",
                "reviewId": "bootstrap-contract-001",
                "routeVersion": profile.get("routeVersion"),
                "policyRevision": profile.get("policyRevision"),
                "authorityRevision": "0123456789abcdef",
                "inputHash": "sha256:" + "1" * 64,
                "status": "pending",
                "checks": [{"checkId": "targeted-tests", "status": "pending"}],
            },
        ),
        (
            gate_schema_path.name,
            {
                "schemaVersion": "bootstrap-review-gate-result.v1",
                "authorityClass": "supplemental_bootstrap",
                "reviewId": "bootstrap-contract-001",
                "routeVersion": profile.get("routeVersion"),
                "reviewProfile": profile.get("reviewProfile"),
                "policyRevision": profile.get("policyRevision"),
                "authorityRevision": "0123456789abcdef",
                "inputHash": "sha256:" + "1" * 64,
                "requiredLayers": required_layers,
                "completedLayers": required_layers,
                "failedLayers": [],
                "layerFailures": [],
                "status": "awaiting_verification",
                "candidateCount": 1,
                "blockerCandidateCount": 1,
                "rejectionCount": 0,
                "preflightResultHash": "sha256:" + "4" * 64,
                "candidatesHash": "sha256:" + "2" * 64,
                "rejectionsHash": "sha256:" + "3" * 64,
            },
        ),
    ]:
        contract_errors = schema_errors(registry[schema_name], instance, registry)
        if contract_errors:
            fail(errors, f"bootstrap template violates {schema_name}: {'; '.join(contract_errors)}")

    source = tool_path.read_text(encoding="utf-8")
    helper_source = helper_path.read_text(encoding="utf-8")
    trees = [
        ast.parse(source, filename=str(tool_path)),
        ast.parse(helper_source, filename=str(helper_path)),
    ]
    forbidden_import_roots = {"urllib", "requests", "httpx", "openai", "anthropic"}
    for node in (node for tree in trees for node in ast.walk(tree)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".", 1)[0] in forbidden_import_roots:
                    fail(errors, f"bootstrap tool imports forbidden network/LLM module: {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".", 1)[0] in forbidden_import_roots:
                fail(errors, f"bootstrap tool imports forbidden network/LLM module: {node.module}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess" and node.func.attr == "Popen":
                shell_keywords = [item for item in node.keywords if item.arg == "shell"]
                if not shell_keywords or not isinstance(shell_keywords[0].value, ast.Constant) or shell_keywords[0].value.value is not False:
                    fail(errors, "Bootstrap runner Popen must set shell=False explicitly")
    required_source_markers = [
        'AUTHORITY_CLASS = "supplemental_bootstrap"',
        '"bootstrap-reviewer-output.v1.schema.json"',
        '"bootstrap-verifier-output.v1.schema.json"',
        '"bootstrap-review-gate-result.v1.schema.json"',
        "bootstrap_sidecar_binding(manifest)",
        "PLACEHOLDER_TEXT_VALUES",
        '"missing_failure_tuple"',
        "reference_covers(checked_reference, reference)",
        "parse_constant=reject_non_finite",
        "math.isfinite(confidence)",
        "contextClassArtifacts",
        "build_context_class_artifacts",
        "validate_profile_context_semantics",
        "Refusing to gate an already finalized review",
        "validate_scope_references(candidate.get(\"contextRead\")",
        "validate_scope_references(checked, manifest, \"evidenceChecked\")",
        'CONTROL_PLANE_REVISION = "bootstrap-control-plane.v2"',
        "create_artifact_view",
        "validate_repair_closure",
        "command_run_layer",
        "command_list_runs",
        "command_inspect_run",
        "command_seal_run",
        "completed readArtifacts must exactly match prepared manifest order",
        "A run with an active attempt or acquired lease cannot be sealed",
        "revalidate frozen authority before publishing verifier evidence",
    ]
    for marker in required_source_markers:
        if marker not in source:
            fail(errors, f"bootstrap tool is missing required guard: {marker}")
    for marker in ["ENVIRONMENT_ALLOWLIST", "TYPED_PLACEHOLDERS", "shell=False", "process-events.jsonl"]:
        if marker not in helper_source and marker not in source:
            fail(errors, f"bootstrap control plane is missing execution guard: {marker}")
    adapter_source = (ROOT / "tools/run_bootstrap_review.py").read_text(encoding="utf-8")
    for marker in ["EXPECTED_CONTROL_PLANE_REVISION", "CORE_PATH", "revision mismatch"]:
        if marker not in adapter_source:
            fail(errors, f"bootstrap compatibility adapter is missing revision binding: {marker}")
    test_source = test_path.read_text(encoding="utf-8")
    for marker in [
        "test_prepare_records_binary_artifacts_without_decoding_them",
        "test_gate_rejects_context_outside_prepared_scope",
        "test_gate_applies_reviewer_json_schema",
        "test_gate_rejects_completed_layer_with_incomplete_coverage",
        "test_gate_maps_failed_missing_context_layer_to_incomplete",
        "test_finalize_rejects_verifier_evidence_outside_scope",
        "test_gate_schema_rejects_awaiting_verification_without_blocker",
        "test_gate_rejects_placeholder_failure_tuple",
        "test_gate_rejects_completed_coverage_out_of_manifest_order",
        "test_gate_rejects_duplicate_completed_coverage",
        "test_active_attempt_blocks_abandon_and_same_round_replacement",
        "test_verifier_authority_drift_before_publication_preserves_formal_output",
        "test_finalize_rejects_unrelated_in_scope_verifier_evidence",
        "test_gate_rejects_non_finite_json_confidence",
        "test_finalize_requires_whole_artifact_for_path_only_context",
        "test_prepare_rejects_missing_context_class_assignments",
        "test_prepare_rejects_spoofed_skill_route_context_classes",
        "test_gate_refuses_to_reopen_finalized_result",
    ]:
        if marker not in test_source:
            fail(errors, f"bootstrap regression suite is missing: {marker}")
    operator_text = (ROOT / "09-bootstrap-review-operator-guide.md").read_text(encoding="utf-8")
    quota_markers = ["禁止把“至少输出十条”", "固定数量最多只能用于首轮内部假设探索", "零 candidate 合法"]
    for marker in quota_markers:
        if marker not in operator_text:
            fail(errors, f"bootstrap operator guide is missing no-quota policy: {marker}")


def main() -> int:
    errors: list[str] = []
    validate_files(errors)
    validate_json(errors)
    validate_links(errors)
    validate_requirements(errors)
    validate_fixture_intent(errors)
    validate_semantic_contracts(errors)
    validate_bootstrap_contracts(errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("PASS: whole-directory plan validation succeeded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
