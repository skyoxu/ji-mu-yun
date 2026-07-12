from __future__ import annotations

import json
import re
import sys
from typing import Any
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
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
    "96-global-review-and-validation.md",
    "97-plan-added-requirements-ledger.md",
    "98-source-to-split-audit.md",
    "99-source-coverage.md",
]
REQUIRED_JSON = [
    "schemas/review-finding.v1.schema.json",
    "schemas/review-rejection.v1.schema.json",
    "schemas/review-result.v1.schema.json",
    "schemas/review-validation-fixtures.v1.json",
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
    for relative in [*REQUIRED_BOOKS, *REQUIRED_JSON]:
        if not (ROOT / relative).is_file():
            fail(errors, f"missing required artifact: {relative}")


def validate_json(errors: list[str]) -> None:
    for relative in REQUIRED_JSON:
        path = ROOT / relative
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if relative.endswith(".schema.json"):
                if data.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
                    fail(errors, f"schema is not Draft 2020-12: {relative}")
                if not data.get("$id"):
                    fail(errors, f"schema has no $id: {relative}")
        except (OSError, json.JSONDecodeError) as exc:
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
    expected = [f"{number:03d}" for number in range(1, 33)]
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
        if owner not in {"01", "02", "03", "04", "05", "06", "96"}:
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
) -> list[str]:
    result: list[str] = []
    if "$ref" in schema:
        target = Path(schema["$ref"]).name
        if target not in registry:
            return [f"{path}: unresolved $ref {schema['$ref']}"]
        result.extend(schema_errors(registry[target], instance, registry, path))
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
        if "pattern" in schema and re.fullmatch(schema["pattern"], instance) is None:
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
                result.extend(schema_errors(schema["items"], item, registry, f"{path}[{index}]"))
        if "contains" in schema:
            match_count = sum(
                not schema_errors(schema["contains"], item, registry, f"{path}[{index}]")
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
                result.extend(schema_errors(child_schema, instance[key], registry, f"{path}.{key}"))
    for child in schema.get("allOf", []):
        result.extend(schema_errors(child, instance, registry, path))
    if "anyOf" in schema and all(schema_errors(child, instance, registry, path) for child in schema["anyOf"]):
        result.append(f"{path}: no anyOf branch matched")
    if "not" in schema and not schema_errors(schema["not"], instance, registry, path):
        result.append(f"{path}: prohibited schema matched")
    if "if" in schema:
        if not schema_errors(schema["if"], instance, registry, path):
            result.extend(schema_errors(schema.get("then", {}), instance, registry, path))
        else:
            result.extend(schema_errors(schema.get("else", {}), instance, registry, path))
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
    path = ROOT / "schemas/review-validation-fixtures.v1.json"
    if not path.is_file():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
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
        Path(relative).name: json.loads((ROOT / relative).read_text(encoding="utf-8"))
        for relative in REQUIRED_JSON
        if relative.endswith(".schema.json")
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
    finding_schema = json.loads(
        (ROOT / "schemas/review-finding.v1.schema.json").read_text(encoding="utf-8")
    )
    rejection_schema = json.loads(
        (ROOT / "schemas/review-rejection.v1.schema.json").read_text(encoding="utf-8")
    )
    result_schema = json.loads(
        (ROOT / "schemas/review-result.v1.schema.json").read_text(encoding="utf-8")
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
    if "本目录 plan-local schema/validator" not in scope_text:
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
    if "当前针对 7 月 7 日目录运行中的三层审查继续按其现有规则完成" not in index_text:
        fail(errors, "the current July 7 in-flight review must remain isolated")
    if "Blind Hunter" not in integration_text or "Edge Case Hunter" not in integration_text or "Acceptance Auditor" not in integration_text:
        fail(errors, "all three reviewer roles must be routed explicitly")
    if "candidate/finding/result/rejection" not in gateway_text:
        fail(errors, "routeVersion must bind candidate, finding, result, and rejection")
    if "fingerprint 输入至少包含 routeVersion" not in gateway_text or "routeVersion、candidate hash" not in gateway_text:
        fail(errors, "finding and suppression fingerprints must include routeVersion")


def main() -> int:
    errors: list[str] = []
    validate_files(errors)
    validate_json(errors)
    validate_links(errors)
    validate_requirements(errors)
    validate_fixture_intent(errors)
    validate_semantic_contracts(errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("PASS: whole-directory plan validation succeeded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
