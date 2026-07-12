from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path


PLAN_DIR = Path(__file__).resolve().parents[1]
TOP_LEVEL_PLAN = PLAN_DIR.with_suffix(".md")
LEDGER = PLAN_DIR / "97-post-split-requirements-ledger.md"
COVERAGE = PLAN_DIR / "99-source-coverage.md"
SCHEMA_DIR = PLAN_DIR / "schemas"
FINDING_REGISTRY = SCHEMA_DIR / "finding-closure-registry.v1.json"
FINDING_EVIDENCE = SCHEMA_DIR / "finding-closure-evidence.v1.json"
ORIGINAL_REGISTRY = SCHEMA_DIR / "original-requirement-family-registry.v1.json"
VALIDATION_FIXTURES = SCHEMA_DIR / "schema-validation-fixtures.v1.json"

REQUIRED_SCHEMAS = {
    "bootstrap-handoff-contract.v1.schema.json",
    "upstream-handoff-manifest.v1.schema.json",
    "upstream-handoff-state-event.v1.schema.json",
    "upstream-handoff-active-registry.v1.schema.json",
    "upstream-completion-snapshot.v1.schema.json",
    "handoff-source-map.v1.schema.json",
    "downstream-observation-snapshots.v1.schema.json",
    "finding-closure-registry.v1.schema.json",
    "finding-closure-evidence.v1.schema.json",
    "original-requirement-family-registry.v1.schema.json",
}
FINDING_PATTERN = re.compile(
    r"^(?:PF-\d{3}|F4-P[012]-\d{2}|F5-P[012]-\d{2}|F6-\d{2}|F7-P[012]-\d{2}|F8-P[012]-\d{2}|F9-P[012]-\d{2})$"
)
PBR_PATTERN = re.compile(r"^PBR-\d{3}$")
EXPECTED_PBRS = [f"PBR-{index:03d}" for index in range(1, 117)]
EXPECTED_VALID_FIXTURES = {
    "manifest-valid", "snapshot-valid", "source-map-valid", "observation-valid",
    "bootstrap-valid", "state-event-valid", "active-registry-valid",
}
EXPECTED_INVALID_FIXTURES = {
    "bad-sha256", "empty-signature", "duplicate-signer", "missing-second-snapshot",
    "illegal-source-path", "observation-business-authority-field", "deferral-finding-alias",
    "bootstrap-single-signature", "state-event-duplicate-signer", "active-registry-final-commit",
    "observation-path-traversal", "deferral-evidence-finding-alias", "source-map-duplicate-field",
    "source-map-na-upstream-class", "source-map-ads-path",
}
EXPECTED_PLAN_MUTATIONS = {
    "coverage-owner-mismatch", "coverage-phase-mismatch", "coverage-conflicting-phase-suffix",
    "finding-without-closure-evidence", "closure-review-mismatch", "active-finding-superseded",
    "schema-unsupported-keyword", "schema-ref-sibling",
}
SUPPORTED_SCHEMA_KEYWORDS = {
    "$schema", "$id", "$defs", "$ref", "title", "type", "const", "enum", "format", "pattern",
    "minLength", "minimum", "minItems", "maxItems", "uniqueItems", "minProperties", "required",
    "properties", "additionalProperties", "items", "oneOf", "allOf",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def load_json(path: Path):
    return json.loads(read_text(path))


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def atomic_write_text(path: Path, content: str) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f"{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def iter_json_nodes(value, location: str = "$"):
    yield location, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from iter_json_nodes(child, f"{location}/{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_json_nodes(child, f"{location}/{index}")


def iter_schema_nodes(schema: dict, location: str = "$"):
    yield location, schema
    for container in ("$defs", "properties"):
        for key, child in schema.get(container, {}).items():
            if isinstance(child, dict):
                yield from iter_schema_nodes(child, f"{location}/{container}/{key}")
    for keyword in ("items", "additionalProperties"):
        child = schema.get(keyword)
        if isinstance(child, dict):
            yield from iter_schema_nodes(child, f"{location}/{keyword}")
    for keyword in ("oneOf", "allOf"):
        for index, child in enumerate(schema.get(keyword, [])):
            if isinstance(child, dict):
                yield from iter_schema_nodes(child, f"{location}/{keyword}/{index}")


def resolve_local_json_pointer(document, reference: str):
    current = document
    for token in reference[2:].split("/"):
        decoded = token.replace("~1", "/").replace("~0", "~")
        current = current[int(decoded)] if isinstance(current, list) else current[decoded]
    return current


def parse_requirements(ledger_text: str) -> list[list[str]]:
    section = ledger_text.split("## Requirements", 1)[1].split("## Requirement Status Registry", 1)[0]
    return [
        cells
        for line in section.splitlines()
        if (cells := table_cells(line)) and PBR_PATTERN.fullmatch(cells[0])
    ]


def parse_status_registry(ledger_text: str) -> dict[str, dict[str, str]]:
    section = ledger_text.split("## Requirement Status Registry", 1)[1].split("## Pre-Fourth-Review", 1)[0]
    result = {}
    for line in section.splitlines():
        cells = table_cells(line)
        if len(cells) != 4:
            continue
        pbr_id = cells[0].strip("`")
        if PBR_PATTERN.fullmatch(pbr_id):
            result[pbr_id] = {"status": cells[1], "replacement": cells[2].strip("`"), "reason": cells[3]}
    return result


def parse_finding_coverage(ledger_text: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for line in ledger_text.splitlines():
        cells = table_cells(line)
        if len(cells) == 2 and FINDING_PATTERN.fullmatch(cells[0]):
            result[cells[0]] = re.findall(r"PBR-\d{3}", cells[1])
    return result


def parse_closure_evidence(value: dict) -> tuple[dict[str, dict], list[str]]:
    result: dict[str, dict] = {}
    errors: list[str] = []
    for review in value.get("reviewClosures", []):
        review_id = review.get("reviewId")
        expected_ref = f"phase-boundary://reviews/{review_id}/plan-closure"
        if review.get("closureRefs") != [expected_ref]:
            errors.append(f"WD030 closure review/ref mismatch: {review_id}")
        for finding_id in review.get("findingIds", []):
            if finding_id in result:
                errors.append(f"WD030 duplicate closure evidence: {finding_id}")
            expected_review = (
                "pre-fourth" if finding_id.startswith("PF-") else
                "fourth" if finding_id.startswith("F4-") else
                "fifth" if finding_id.startswith("F5-") else
                "sixth" if finding_id.startswith("F6-") else
                "seventh" if finding_id.startswith("F7-") else
                "eighth" if finding_id.startswith("F8-") else
                "ninth-f9" if finding_id.startswith("F9-") else None
            )
            if review_id != expected_review:
                errors.append(f"WD030 closure finding/review mismatch: {finding_id}={review_id}")
            result[finding_id] = {
                "status": review.get("status"),
                "closureRefs": review.get("closureRefs", []),
            }
    return result, errors


def expected_finding_registry(ledger_text: str, evidence_value: dict) -> tuple[dict, list[str]]:
    status_registry = parse_status_registry(ledger_text)
    evidence, errors = parse_closure_evidence(evidence_value)
    coverage = parse_finding_coverage(ledger_text)
    for extra in sorted(set(evidence) - set(coverage)):
        errors.append(f"WD030 closure evidence references unknown finding: {extra}")
    findings = []
    for finding_id, pbr_ids in sorted(coverage.items()):
        closure_ids = [status_registry.get(pbr_id, {}).get("replacement") or pbr_id for pbr_id in pbr_ids]
        evidence_row = evidence.get(finding_id)
        if evidence_row is None:
            status = "plan_open"
            closure_refs = [f"phase-boundary://requirements/{pbr_id}/acceptance" for pbr_id in closure_ids]
        else:
            superseded = all(pbr_id in status_registry for pbr_id in pbr_ids)
            if evidence_row["status"] == "superseded" and not superseded:
                errors.append(f"WD030 active finding cannot be declared superseded: {finding_id}")
                status = "plan_open"
            else:
                status = "superseded" if superseded else evidence_row["status"]
            closure_refs = [*evidence_row["closureRefs"], *[f"phase-boundary://requirements/{pbr_id}/acceptance" for pbr_id in closure_ids]]
        findings.append({"findingId": finding_id, "status": status, "pbrIds": pbr_ids, "closureRefs": closure_refs})
    return {
        "schemaVersion": "finding-closure-registry.v1",
        "scope": "plan-readiness-only",
        "generatedFrom": "97-post-split-requirements-ledger.md",
        "closureEvidenceSource": "finding-closure-evidence.v1.json",
        "findings": findings,
    }, errors


def instance_type_matches(value, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    return False


def validate_instance(value, schema: dict, root: dict, location: str = "$") -> list[str]:
    if "$ref" in schema:
        errors = validate_instance(value, resolve_local_json_pointer(root, schema["$ref"]), root, location)
        siblings = {key: child for key, child in schema.items() if key != "$ref"}
        if siblings:
            errors.extend(validate_instance(value, siblings, root, location))
        return errors
    errors: list[str] = []
    for child in schema.get("allOf", []):
        errors.extend(validate_instance(value, child, root, location))
    if "oneOf" in schema:
        branch_errors = [validate_instance(value, child, root, location) for child in schema["oneOf"]]
        matched = sum(not item for item in branch_errors)
        if matched != 1:
            errors.append(f"{location}: oneOf matched {matched} branches")
            if matched == 0:
                for child_errors in branch_errors:
                    errors.extend(child_errors)
            return errors
    expected_type = schema.get("type")
    if expected_type is not None:
        expected_types = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(instance_type_matches(value, item) for item in expected_types):
            errors.append(f"{location}: expected type {expected_type}")
            return errors
    if "const" in schema and value != schema["const"]:
        errors.append(f"{location}: const mismatch")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{location}: enum mismatch")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{location}: shorter than minLength")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            errors.append(f"{location}: pattern mismatch")
        if schema.get("format") == "date-time":
            rfc3339 = re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", value)
            try:
                if rfc3339 is None:
                    raise ValueError
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                errors.append(f"{location}: invalid RFC 3339 date-time")
    if isinstance(value, (int, float)) and not isinstance(value, bool) and "minimum" in schema and value < schema["minimum"]:
        errors.append(f"{location}: below minimum")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{location}: fewer than minItems")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{location}: more than maxItems")
        if schema.get("uniqueItems") and len({canonical_json(item) for item in value}) != len(value):
            errors.append(f"{location}: duplicate array item")
        if isinstance(schema.get("items"), dict):
            for index, item in enumerate(value):
                errors.extend(validate_instance(item, schema["items"], root, f"{location}/{index}"))
    if isinstance(value, dict):
        if len(value) < schema.get("minProperties", 0):
            errors.append(f"{location}: fewer than minProperties")
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{location}: missing required property {key}")
        properties = schema.get("properties", {})
        for key, item in value.items():
            if key in properties:
                errors.extend(validate_instance(item, properties[key], root, f"{location}/{key}"))
            elif schema.get("additionalProperties") is False:
                errors.append(f"{location}: additional property {key}")
            elif isinstance(schema.get("additionalProperties"), dict):
                errors.extend(validate_instance(item, schema["additionalProperties"], root, f"{location}/{key}"))
    return errors


def validate_schema_shape(schema: dict, name: str) -> list[str]:
    errors: list[str] = []
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema" or not isinstance(schema.get("$id"), str):
        errors.append(f"WD006 malformed Draft 2020-12 schema header: {name}")
    valid_types = {"null", "object", "array", "string", "integer", "number", "boolean"}
    for location, node in iter_schema_nodes(schema):
        unsupported = sorted(set(node) - SUPPORTED_SCHEMA_KEYWORDS)
        if unsupported:
            errors.append(f"WD025 unsupported schema keyword: {name}:{location}:{unsupported[0]}")
        if "$ref" in node:
            reference = node["$ref"]
            if not isinstance(reference, str) or not reference.startswith("#/"):
                errors.append(f"WD025 unsupported schema reference: {name}:{location}")
            else:
                try:
                    resolve_local_json_pointer(schema, reference)
                except (KeyError, IndexError, TypeError, ValueError):
                    errors.append(f"WD006 unresolved local schema reference: {name}:{reference}")
        declared = node.get("type")
        if declared is not None:
            values = declared if isinstance(declared, list) else [declared]
            if not values or any(item not in valid_types for item in values):
                errors.append(f"WD025 invalid schema type: {name}:{location}")
        if "required" in node and (not isinstance(node["required"], list) or any(not isinstance(item, str) for item in node["required"])):
            errors.append(f"WD025 invalid required keyword: {name}:{location}")
        if "properties" in node and not isinstance(node["properties"], dict):
            errors.append(f"WD025 invalid properties keyword: {name}:{location}")
        if "pattern" in node:
            try:
                re.compile(node["pattern"])
            except (TypeError, re.error):
                errors.append(f"WD025 invalid pattern: {name}:{location}")
        if "format" in node and node["format"] != "date-time":
            errors.append(f"WD025 unsupported schema format: {name}:{location}:{node['format']}")
        for keyword in ("oneOf", "allOf"):
            if keyword in node and (not isinstance(node[keyword], list) or not node[keyword]):
                errors.append(f"WD025 invalid {keyword}: {name}:{location}")
    return errors


def validate_trust_semantics(instance: dict) -> list[str]:
    signatures = instance.get("signatures")
    if not isinstance(signatures, list):
        signatures = []
    signer_ids = [item.get("signerId") for item in signatures if isinstance(item, dict)]
    key_ids = [item.get("keyId") for item in signatures if isinstance(item, dict)]
    errors = []
    if len(signer_ids) != len(set(signer_ids)):
        errors.append("duplicate signerId")
    if len(key_ids) != len(set(key_ids)):
        errors.append("duplicate keyId")
    payload_hashes = [item.get("payloadHash") for item in signatures if isinstance(item, dict)]
    if payload_hashes and len(set(payload_hashes)) != 1:
        errors.append("signatures bind different payload hashes")
    approvers = instance.get("approvers")
    if isinstance(approvers, list) and signer_ids and set(approvers) != set(signer_ids):
        errors.append("approvers do not match signers")
    snapshots = instance.get("completionSnapshots")
    if isinstance(snapshots, dict) and snapshots.get("beforeManifestHash") == snapshots.get("beforeSignatureHash"):
        errors.append("completion snapshot hashes must be distinct")
    phase_closure = instance.get("phaseClosure")
    if isinstance(phase_closure, dict):
        for deferral in phase_closure.get("capabilityDeferrals", []):
            strings = [node for _, node in iter_json_nodes(deferral) if isinstance(node, str)] if isinstance(deferral, dict) else []
            if any(FINDING_PATTERN.fullmatch(value) for value in strings):
                errors.append("capability deferral aliases a review finding")
    rows = instance.get("rows")
    if isinstance(rows, list):
        field_pointers = [row.get("fieldPointer") for row in rows if isinstance(row, dict)]
        if len(field_pointers) != len(set(field_pointers)):
            errors.append("duplicate source-map fieldPointer")
    for collection_name, identity_fields in (("surfaces", ("derivedSurfaceId",)), ("operations", ("derivedOperationId", "method", "path")), ("schemaObjects", ("derivedObjectId", "objectType", "name"))):
        rows = instance.get(collection_name)
        if isinstance(rows, list):
            identities = [tuple(row.get(field) for field in identity_fields) for row in rows if isinstance(row, dict)]
            if len(identities) != len(set(identities)):
                errors.append(f"duplicate {collection_name} semantic identity")
    return errors


def apply_mutation(instance, mutation: dict):
    tokens = [token for token in mutation["pointer"].split("/") if token]
    current = instance
    for token in tokens[:-1]:
        current = current[int(token)] if isinstance(current, list) else current[token]
    last = tokens[-1]
    if mutation.get("delete"):
        if isinstance(current, list):
            del current[int(last)]
        else:
            del current[last]
    elif isinstance(current, list):
        current[int(last)] = mutation["value"]
    else:
        current[last] = mutation["value"]


def validate_fixture_bundle(schemas: dict[str, dict], fixture_bundle: dict) -> list[str]:
    errors: list[str] = []
    valid_cases = fixture_bundle.get("validCases", [])
    invalid_cases = fixture_bundle.get("invalidCases", [])
    plan_mutations = fixture_bundle.get("planMutations", [])
    for label, cases, expected in (
        ("valid", valid_cases, EXPECTED_VALID_FIXTURES),
        ("invalid", invalid_cases, EXPECTED_INVALID_FIXTURES),
        ("plan", plan_mutations, EXPECTED_PLAN_MUTATIONS),
    ):
        ids = [case.get("id") for case in cases]
        if len(ids) != len(set(ids)) or set(ids) != expected:
            errors.append(f"WD026 {label} fixture inventory mismatch")
    valid_by_id = {case["id"]: case for case in valid_cases}
    for case in valid_by_id.values():
        schema = schemas.get(case["schema"])
        if schema is None:
            errors.append(f"WD026 fixture references missing schema: {case['id']}")
            continue
        case_errors = validate_instance(case["instance"], schema, schema) + validate_trust_semantics(case["instance"])
        if case_errors:
            errors.append(f"WD026 valid fixture rejected: {case['id']}: {case_errors[0]}")
    for case in invalid_cases:
        base = valid_by_id.get(case["baseCase"])
        schema = schemas.get(case["schema"])
        if base is None or schema is None:
            errors.append(f"WD027 invalid fixture setup: {case['id']}")
            continue
        if base.get("schema") != case.get("schema"):
            errors.append(f"WD027 invalid fixture schema mismatch: {case['id']}")
            continue
        instance = copy.deepcopy(base["instance"])
        apply_mutation(instance, case["mutation"])
        case_errors = validate_instance(instance, schema, schema) + validate_trust_semantics(instance)
        expected_error = case.get("expectedErrorContains")
        if not case_errors or not isinstance(expected_error, str) or not any(expected_error in error for error in case_errors):
            errors.append(f"{case['ruleId']} mutation unexpectedly passed: {case['id']}")
    return errors


def validate_explicit_coverage(coverage_text: str, requirements: dict[str, list[str]]) -> list[str]:
    errors: list[str] = []
    explicit = coverage_text.split("## Explicit PBR Coverage", 1)[1].split("## Original Requirement Family Coverage", 1)[0]
    counts: Counter[str] = Counter()
    for line in explicit.splitlines():
        cells = table_cells(line)
        if len(cells) != 2:
            continue
        pbr_ids = re.findall(r"PBR-\d{3}", cells[1])
        if not pbr_ids:
            continue
        owner_phase = re.fullmatch(r"([^/]+?)\s*/\s*(BH-[A-Z0-9]+)(?:\s+(.*))?", cells[0])
        if owner_phase is None:
            errors.append(f"WD029 coverage row lacks owner/phase: {cells[0]}")
            continue
        if owner_phase.group(3) and re.search(r"(?:^|\s)/\s*BH-[A-Z0-9]+", owner_phase.group(3)):
            errors.append(f"WD029 coverage row has conflicting phase suffix: {cells[0]}")
            continue
        owner, phase = owner_phase.group(1).strip(), owner_phase.group(2)
        for pbr_id in pbr_ids:
            counts[pbr_id] += 1
            row = requirements.get(pbr_id)
            if row is None or owner != row[2] or phase != row[3]:
                errors.append(f"WD029 coverage owner/phase mismatch: {pbr_id} expected={row[2]}/{row[3]} actual={owner}/{phase}" if row else f"WD029 coverage references unknown PBR: {pbr_id}")
    for pbr_id in EXPECTED_PBRS:
        if counts[pbr_id] != 1:
            errors.append(f"WD019 source coverage count {pbr_id}={counts[pbr_id]}")
    return errors


def run_named_mutation(case_id: str) -> tuple[str, bool]:
    fixtures = load_json(VALIDATION_FIXTURES)
    schemas = {path.name: load_json(path) for path in SCHEMA_DIR.glob("*.schema.json")}
    invalid = next((item for item in fixtures.get("invalidCases", []) if item["id"] == case_id), None)
    if invalid:
        base = next(item for item in fixtures["validCases"] if item["id"] == invalid["baseCase"])
        instance = copy.deepcopy(base["instance"])
        apply_mutation(instance, invalid["mutation"])
        rejected = bool(validate_instance(instance, schemas[invalid["schema"]], schemas[invalid["schema"]]) + validate_trust_semantics(instance))
        return invalid["ruleId"], rejected
    ledger_text = read_text(LEDGER)
    coverage_text = read_text(COVERAGE)
    requirements = {row[0]: row for row in parse_requirements(ledger_text)}
    if case_id == "coverage-owner-mismatch":
        mutated = coverage_text.replace("01 / BH-HANDOFF strict commit/hash", "02 / BH-HANDOFF strict commit/hash", 1)
        return "WD029", bool(validate_explicit_coverage(mutated, requirements))
    if case_id == "coverage-phase-mismatch":
        mutated = coverage_text.replace("96 / BH-HANDOFF Draft 2020-12", "96 / BH-SF0A Draft 2020-12", 1)
        return "WD029", bool(validate_explicit_coverage(mutated, requirements))
    if case_id == "coverage-conflicting-phase-suffix":
        mutated = coverage_text.replace("01 / BH-HANDOFF strict commit/hash", "01 / BH-HANDOFF / BH-SF0A strict commit/hash", 1)
        return "WD029", bool(validate_explicit_coverage(mutated, requirements))
    if case_id == "finding-without-closure-evidence":
        evidence = copy.deepcopy(load_json(FINDING_EVIDENCE))
        for review in evidence["reviewClosures"]:
            if "F9-P1-03" in review["findingIds"]:
                review["findingIds"].remove("F9-P1-03")
        registry, _ = expected_finding_registry(ledger_text, evidence)
        return "WD030", any(item["findingId"] == "F9-P1-03" and item["status"] == "plan_open" for item in registry["findings"])
    if case_id == "closure-review-mismatch":
        evidence = copy.deepcopy(load_json(FINDING_EVIDENCE))
        evidence["reviewClosures"][-1]["closureRefs"] = ["phase-boundary://reviews/eighth/plan-closure"]
        _, evidence_errors = expected_finding_registry(ledger_text, evidence)
        return "WD030", any("review/ref mismatch" in error for error in evidence_errors)
    if case_id == "active-finding-superseded":
        evidence = copy.deepcopy(load_json(FINDING_EVIDENCE))
        evidence["reviewClosures"][-1]["status"] = "superseded"
        registry, evidence_errors = expected_finding_registry(ledger_text, evidence)
        rejected = any("active finding cannot be declared superseded" in error for error in evidence_errors)
        rejected = rejected and any(item["findingId"] == "F9-P0-01" and item["status"] == "plan_open" for item in registry["findings"])
        return "WD030", rejected
    if case_id == "schema-unsupported-keyword":
        schema = copy.deepcopy(schemas["upstream-handoff-manifest.v1.schema.json"])
        schema["unevaluatedProperties"] = False
        return "WD025", any("unsupported schema keyword" in error for error in validate_schema_shape(schema, "mutated.schema.json"))
    if case_id == "schema-ref-sibling":
        schema = {"$defs": {"base": {"type": "string"}}, "$ref": "#/$defs/base", "minLength": 5}
        return "WD025", any("shorter than minLength" in error for error in validate_instance("x", schema, schema))
    raise ValueError(f"unknown mutation case: {case_id}")


def validate(write_generated: bool) -> list[str]:
    errors: list[str] = []
    markdown_files = [TOP_LEVEL_PLAN, *sorted(PLAN_DIR.glob("*.md"))]
    if len(markdown_files) != 15:
        errors.append(f"WD001 expected 15 Markdown files including top-level, found {len(markdown_files)}")
    texts: dict[Path, str] = {}
    for path in markdown_files:
        try:
            texts[path] = read_text(path)
        except UnicodeDecodeError as exc:
            errors.append(f"WD002 invalid UTF-8: {path}: {exc}")
    link_pattern = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
    for path, text in texts.items():
        for match in link_pattern.finditer(text):
            target = match.group(1).split("#", 1)[0].strip()
            if target and "://" not in target and not target.startswith("#") and not (path.parent / target).resolve().exists():
                errors.append(f"WD003 broken Markdown link: {path.name}: {target}")

    schema_names = {path.name for path in SCHEMA_DIR.glob("*.schema.json")}
    for missing in sorted(REQUIRED_SCHEMAS - schema_names):
        errors.append(f"WD004 missing schema: {missing}")
    json_values: dict[Path, object] = {}
    json_raw_texts: dict[Path, str] = {}
    for path in sorted(SCHEMA_DIR.rglob("*.json")):
        try:
            raw_text = read_text(path)
            json_raw_texts[path] = raw_text
            json_values[path] = json.loads(raw_text)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"WD005 invalid JSON: {path.name}: {exc}")
    schemas: dict[str, dict] = {}
    for path in sorted(SCHEMA_DIR.glob("*.schema.json")):
        value = json_values.get(path)
        if isinstance(value, dict):
            schemas[path.name] = value
            errors.extend(validate_schema_shape(value, path.name))
    bootstrap_identity = schemas.get("bootstrap-handoff-contract.v1.schema.json", {}).get("properties", {}).get("sourceMapSchemaId", {}).get("const")
    source_map_identity = schemas.get("handoff-source-map.v1.schema.json", {}).get("properties", {}).get("schemaId", {}).get("const")
    if bootstrap_identity != source_map_identity:
        errors.append(f"WD033 source-map schema identity mismatch: bootstrap={bootstrap_identity} instance={source_map_identity}")

    ledger_text = texts.get(LEDGER, read_text(LEDGER))
    generation_input_hashes = {
        LEDGER: hashlib.sha256(ledger_text.encode("utf-8")).hexdigest(),
        FINDING_EVIDENCE: hashlib.sha256(json_raw_texts.get(FINDING_EVIDENCE, "").encode("utf-8")).hexdigest(),
    }
    requirements = parse_requirements(ledger_text)
    actual_pbrs = [row[0] for row in requirements]
    if actual_pbrs != EXPECTED_PBRS:
        errors.append("WD007 PBR sequence must be PBR-001 through PBR-116")
    allowed_owners = {"top-level", "00", "01", "02", "03", "04", "05", "06", "07", "08", "09", "96", "97", "98", "99"}
    allowed_phases = {"BH-HANDOFF", "BH-SF0A", "BH-SF0B", "BH-SF0C", "BH-SF1", "BH-SF2", "BH-SF3", "BH-SF4", "BH-PILOT", "BH-RP1", "BH-REACT1", "BH-REACT2", "BH-ARCH", "BH-DATA", "BH-RELEASE"}
    acceptance_refs = []
    source_findings: dict[str, set[str]] = {}
    for row in requirements:
        if len(row) != 7:
            errors.append(f"WD008 PBR row must have 7 columns: {row[0]}")
            continue
        pbr_id, source_field, owner, phase, requirement, acceptance_ref, acceptance_family = row
        if owner not in allowed_owners:
            errors.append(f"WD009 invalid owner {owner}: {pbr_id}")
        if phase not in allowed_phases:
            errors.append(f"WD010 invalid phase {phase}: {pbr_id}")
        if acceptance_ref != f"phase-boundary://requirements/{pbr_id}/acceptance":
            errors.append(f"WD011 invalid acceptance ref: {pbr_id}")
        if not requirement or not acceptance_family:
            errors.append(f"WD012 incomplete requirement/acceptance: {pbr_id}")
        acceptance_refs.append(acceptance_ref)
        for finding_id in (item.strip() for item in source_field.split(",")):
            source_findings.setdefault(finding_id, set()).add(pbr_id)
    if len(acceptance_refs) != len(set(acceptance_refs)):
        errors.append("WD013 duplicate acceptance refs")

    status_registry = parse_status_registry(ledger_text)
    for pbr_id, status in status_registry.items():
        if pbr_id not in actual_pbrs or status["status"] != "superseded" or status["replacement"] not in actual_pbrs or status["replacement"] == pbr_id:
            errors.append(f"WD013 invalid requirement status registry row: {pbr_id}")
    finding_coverage = parse_finding_coverage(ledger_text)
    finding_counts = Counter()
    for line in ledger_text.splitlines():
        cells = table_cells(line)
        if len(cells) == 2 and FINDING_PATTERN.fullmatch(cells[0]):
            finding_counts[cells[0]] += 1
    for finding_id, count in finding_counts.items():
        if count != 1:
            errors.append(f"WD014 duplicate finding coverage row: {finding_id}={count}")
    if set(source_findings) != set(finding_coverage):
        errors.append("WD014 source finding set differs from coverage finding set")
    for finding_id in sorted(set(source_findings) | set(finding_coverage)):
        if source_findings.get(finding_id, set()) != set(finding_coverage.get(finding_id, [])):
            errors.append(f"WD015 finding/PBR mismatch: {finding_id}")

    evidence_value = json_values.get(FINDING_EVIDENCE, {})
    expected_registry, evidence_errors = expected_finding_registry(ledger_text, evidence_value if isinstance(evidence_value, dict) else {})
    errors.extend(evidence_errors)
    if write_generated:
        json_values[FINDING_REGISTRY] = expected_registry
    elif not FINDING_REGISTRY.exists():
        errors.append("WD016 missing finding closure registry")
    else:
        actual_registry = json_values.get(FINDING_REGISTRY)
        if actual_registry != expected_registry:
            errors.append("WD017 finding closure registry is stale")
    if any(item["status"] == "plan_open" for item in expected_registry["findings"]):
        errors.append("WD018 plan finding registry contains open items")

    coverage_text = texts.get(COVERAGE, read_text(COVERAGE))
    requirement_map = {row[0]: row for row in requirements}
    errors.extend(validate_explicit_coverage(coverage_text, requirement_map))

    fixture_schema_pairs = [
        (ORIGINAL_REGISTRY, "original-requirement-family-registry.v1.schema.json"),
        (FINDING_EVIDENCE, "finding-closure-evidence.v1.schema.json"),
    ]
    if FINDING_REGISTRY in json_values:
        fixture_schema_pairs.append((FINDING_REGISTRY, "finding-closure-registry.v1.schema.json"))
    for path, schema_name in fixture_schema_pairs:
        value = json_values.get(path)
        schema = schemas.get(schema_name)
        if value is not None and schema is not None:
            instance_errors = validate_instance(value, schema, schema)
            if instance_errors:
                errors.append(f"WD026 fixture does not match schema: {path.name}: {instance_errors[0]}")
    fixture_bundle = json_values.get(VALIDATION_FIXTURES)
    if not isinstance(fixture_bundle, dict):
        errors.append("WD026 missing schema validation fixture bundle")
    else:
        errors.extend(validate_fixture_bundle(schemas, fixture_bundle))
        for plan_case in fixture_bundle.get("planMutations", []):
            rule_id, rejected = run_named_mutation(plan_case["id"])
            if rule_id != plan_case["ruleId"] or not rejected:
                errors.append(f"{plan_case['ruleId']} plan mutation unexpectedly passed: {plan_case['id']}")

    original = json_values.get(ORIGINAL_REGISTRY, {})
    families = original.get("families", []) if isinstance(original, dict) else []
    original_ids = [item["id"] for item in families]
    if original_ids != [f"ORIG-{index:02d}" for index in range(1, 20)]:
        errors.append("WD020 original family registry must contain ORIG-01 through ORIG-19")
    payload_hash = hashlib.sha256(canonical_json(families).encode("utf-8")).hexdigest()
    if original.get("provenance", {}).get("semanticFamilyPayloadHashSha256") != payload_hash:
        errors.append("WD031 original semantic-family payload hash mismatch")
    audit_text = texts[PLAN_DIR / "98-original-to-split-audit.md"]
    audit_section = audit_text.split("## Canonical Semantic-Family Mapping", 1)[1].split("## Post-Split Additions", 1)[0]
    original_coverage_section = coverage_text.split("## Original Requirement Family Coverage", 1)[1].split("## Completion", 1)[0]
    audit_rows = {cells[0]: cells for line in audit_section.splitlines() if (cells := table_cells(line)) and re.fullmatch(r"ORIG-\d{2}", cells[0])}
    coverage_rows = {cells[0]: cells for line in original_coverage_section.splitlines() if (cells := table_cells(line)) and re.fullmatch(r"ORIG-\d{2}", cells[0])}
    for family in families:
        original_id = family["id"]
        for owner in family.get("owners", []):
            if owner not in allowed_owners:
                errors.append(f"WD034 original-family owner does not exist: {original_id}={owner}")
        expected_owners = ", ".join(family["owners"])
        expected_ref = family["acceptanceRef"]
        if len(audit_rows.get(original_id, [])) != 4 or audit_rows[original_id][2:] != [expected_owners, expected_ref]:
            errors.append(f"WD021 original-family audit mapping mismatch: {original_id}")
        if len(coverage_rows.get(original_id, [])) != 3 or coverage_rows[original_id][1:] != [expected_owners, expected_ref]:
            errors.append(f"WD021 original-family source coverage mismatch: {original_id}")
        acceptance = family.get("acceptance")
        if not isinstance(acceptance, dict) or not acceptance.get("criterion") or not acceptance.get("evidenceIntent"):
            errors.append(f"WD032 original-family acceptance object missing: {original_id}")

    review_text = texts[PLAN_DIR / "96-global-review-and-split-validation.md"]
    if "| Top-level recovery/metadata | top-level |" not in review_text:
        errors.append("WD022 top-level authority family missing")
    all_text = "\n".join(texts.values())
    forbidden = ["BH-HANDOFF and BH-SF0A through BH-SF4 complete", "upstream surfaceId/owner", "Data refactor starts from handoff schema/migration/table-owner baseline", "accepted upstream deferral", "failed_retryable -> retry ->", "recorded_prior_state"]
    for phrase in forbidden:
        if phrase in all_text:
            errors.append(f"WD023 stale terminology: {phrase}")
    for required in ["AGENTS.md", "README.md", "UpstreamHandoffActiveRegistry", "Finding Status Registry", "Plan-Readiness Review"]:
        if required not in all_text:
            errors.append(f"WD024 missing required concept: {required}")
    if write_generated and not errors:
        for input_path, expected_hash in generation_input_hashes.items():
            current_hash = hashlib.sha256(read_text(input_path).encode("utf-8")).hexdigest()
            if current_hash != expected_hash:
                errors.append(f"WD035 generated-registry input changed during validation: {input_path.name}")
    if write_generated and not errors:
        atomic_write_text(FINDING_REGISTRY, json.dumps(expected_registry, ensure_ascii=False, indent=2) + "\n")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-generated", action="store_true")
    parser.add_argument("--mutation-case")
    args = parser.parse_args()
    try:
        if args.mutation_case:
            rule_id, rejected = run_named_mutation(args.mutation_case)
            print(f"{rule_id} mutation rejected: {args.mutation_case}" if rejected else f"WD000 mutation unexpectedly passed: {args.mutation_case}")
            return 1 if rejected else 0
        errors = validate(args.write_generated)
    except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError, IndexError, KeyError, TypeError, ValueError) as exc:
        print(f"WD000 validator input structure invalid: {type(exc).__name__}: {exc}")
        return 1
    if errors:
        for error in errors:
            print(error)
        print(f"FAIL errors={len(errors)}")
        return 1
    registry = load_json(FINDING_REGISTRY)
    print(f"PASS markdown=15 schemas={len(list(SCHEMA_DIR.glob('*.schema.json')))} pbr=116 findings={len(registry['findings'])} open=0 original_families=19")
    return 0


if __name__ == "__main__":
    sys.exit(main())
