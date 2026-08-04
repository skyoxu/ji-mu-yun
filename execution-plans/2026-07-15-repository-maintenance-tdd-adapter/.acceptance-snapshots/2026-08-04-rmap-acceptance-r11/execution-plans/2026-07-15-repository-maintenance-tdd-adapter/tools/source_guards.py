from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def _finding(rule_id: str, target: str, message: str) -> dict[str, str]:
    return {"rule_id": rule_id, "target": target, "message": message}


def _expected_locations(source_id: str, source_path: Path) -> list[tuple[str, str]]:
    if source_id == "agentbuild":
        lines = source_path.read_text(encoding="utf-8").splitlines()
        separators = [index for index, line in enumerate(lines, 1) if line.strip() == "---"]
        bounds = list(zip([1, *[item + 2 for item in separators]], [*[item - 2 for item in separators], len(lines)]))
        return [(f"AGENT-SRC-{value}", f"{start}-{end}") for value, (start, end) in zip(("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"), bounds)]
    document = __import__("json").loads(source_path.read_text(encoding="utf-8"))
    decision_sets = document.get("decision_sets", {})
    creation = [item.get("id") for item in decision_sets.get("creation", []) if item.get("status") == "accepted"]
    repair = [item.get("id") for item in decision_sets.get("repair", []) if item.get("status") == "accepted"]
    repair_20260717 = [item.get("id") for item in decision_sets.get("repair_20260717", []) if item.get("status") == "accepted"]
    repair_999 = [item.get("id") for item in decision_sets.get("repair_20260717_999", []) if item.get("status") == "accepted"]
    repair_1200 = [item.get("id") for item in decision_sets.get("repair_20260717_1200", []) if item.get("status") == "accepted"]
    repair_1300 = [item.get("id") for item in decision_sets.get("repair_20260717_1300", []) if item.get("status") == "accepted"]
    repair_1500 = [item.get("id") for item in decision_sets.get("repair_20260718_1500", []) if item.get("status") == "accepted"]
    repair_1600 = [item.get("id") for item in decision_sets.get("repair_20260718_1600", []) if item.get("status") == "accepted"]
    repair_1700 = [item.get("id") for item in decision_sets.get("repair_20260718_1700", []) if item.get("status") == "accepted"]
    repair_20260722_lifecycle = [item.get("id") for item in decision_sets.get("repair_20260722_lifecycle", []) if item.get("status") == "accepted"]
    if creation != [f"CQ-{index:03d}" for index in range(1, 18)] or repair != [f"CQ-{index:03d}" for index in range(1, 6)] or repair_20260717 != [f"CQ-{index:03d}" for index in range(1, 8)] or repair_999 != [f"CQ-{index:03d}" for index in range(1, 8)] or repair_1200 != [f"CQ-{index:03d}" for index in range(1, 6)] or repair_1300 != [f"CQ-{index:03d}" for index in range(1, 6)] or repair_1500 != [f"CQ-{index:03d}" for index in range(1, 6)] or repair_1600 != ["RMAP-ARTIFACT-PROOF-CLOSURE"] or repair_1700 != ["RMAP-ARTIFACT-PROOF-EXTERNAL-ROOT-CLOSURE"] or repair_20260722_lifecycle != ["RMAP-PLAN-LIFECYCLE-PREIMPLEMENTATION", "RMAP-PLAN-LIFECYCLE-REPORT-INDEX", "RMAP-PLAN-LIFECYCLE-COMPLETION"]:
        return []
    return [
        ("CREATE-CQ-001-005", "creation:CQ-001..CQ-005"),
        ("CREATE-CQ-006-012", "creation:CQ-006..CQ-012"),
        ("CREATE-CQ-013-017", "creation:CQ-013..CQ-017"),
        ("REPAIR-CQ-001-005", "repair:CQ-001..CQ-005"),
        ("REPAIR-20260717-CQ-001-007", "repair-20260717:CQ-001..CQ-007"),
        ("REPAIR-20260717-999-CQ-001-007", "repair-20260717-999:CQ-001..CQ-007"),
        ("REPAIR-20260717-1200-CQ-001-005", "repair-20260717-1200:CQ-001..CQ-005"),
        ("REPAIR-20260717-1300-CQ-001-005", "repair-20260717-1300:CQ-001..CQ-005"),
        ("REPAIR-20260718-1500-CQ-001-005", "repair-20260718-1500:CQ-001..CQ-005"),
        ("REPAIR-20260718-1600-CLOSURE", "repair-20260718-1600:RMAP-ARTIFACT-PROOF-CLOSURE"),
        ("REPAIR-20260718-1700-EXTERNAL-ROOT-CLOSURE", "repair-20260718-1700:RMAP-ARTIFACT-PROOF-EXTERNAL-ROOT-CLOSURE"),
        ("REPAIR-20260722-PLAN-LIFECYCLE", "repair-20260722-lifecycle:RMAP-PLAN-LIFECYCLE-PREIMPLEMENTATION..RMAP-PLAN-LIFECYCLE-COMPLETION"),
    ]


def _locations_are_exact(source_id: str, sections: list[Any], source_path: Path) -> bool:
    expected = _expected_locations(source_id, source_path)
    observed = [(item.get("id"), item.get("lines")) for item in sections if isinstance(item, dict)]
    if observed != expected:
        return False
    return bool(expected)


def validate_coverage(
    plan_root: Path,
    coverage: dict[str, Any],
    requirement_ids: set[str],
    sha256_file: Callable[[Path], str],
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    sources = coverage.get("sources")
    if not isinstance(sources, list) or {item.get("source_id") for item in sources if isinstance(item, dict)} != {"agentbuild", "clarification-projection"}:
        return [_finding("RMAP-REQ-COVERAGE", "source-coverage", "required sources are missing")]
    covered: set[str] = set()
    for source in sources:
        source_id = source.get("source_id", "source")
        source_path = (plan_root / source["path"]).resolve()
        if not source_path.is_file() or sha256_file(source_path) != source.get("sha256"):
            findings.append(_finding("RMAP-HASH-SOURCE", source_id, "source is missing or stale"))
        sections = source.get("sections")
        expected_count = len(_expected_locations(source_id, source_path)) if source_path.is_file() else 0
        if not isinstance(sections, list) or len(sections) != expected_count:
            findings.append(_finding("RMAP-REQ-COVERAGE", source_id, "section coverage is incomplete")); continue
        if source_path.is_file() and not _locations_are_exact(source_id, sections, source_path):
            findings.append(_finding("RMAP-REQ-COVERAGE-LOCATION", source_id, "source section identity or selector is stale"))
        for section in sections:
            reqs = section.get("requirements") if isinstance(section, dict) else None
            if not isinstance(reqs, list) or not reqs:
                findings.append(_finding("RMAP-REQ-COVERAGE", str(section), "section has no requirements")); continue
            unknown = sorted(set(reqs) - requirement_ids)
            if unknown:
                findings.append(_finding("RMAP-REQ-COVERAGE", section.get("id", "section"), f"unknown requirements: {unknown}"))
            covered.update(reqs)
    if covered != requirement_ids:
        findings.append(_finding("RMAP-REQ-COVERAGE", "source-coverage", f"coverage mismatch: {sorted(requirement_ids - covered)}"))
    return findings


def validate_plan_lifecycle_policy(
    plan_root: Path,
    requirements: dict[str, Any],
    acceptance: dict[str, Any],
    contract: dict[str, Any],
    authority_manifest: dict[str, Any],
    predicate_closure: dict[str, Any],
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    requirement_map = {item.get("id"): item for item in requirements.get("requirements", []) if isinstance(item, dict)}
    expected_requirements = {
        "RMAP-028": {"acceptance_id": "RMAP-ACC-028", "first_phase": "P0", "owner_book": "02-executable-contracts-and-invariants.md", "failure_family": "target_plan_lifecycle_invalid", "source_refs": ["repair-20260722-lifecycle:RMAP-PLAN-LIFECYCLE-PREIMPLEMENTATION", "repair-20260722-lifecycle:RMAP-PLAN-LIFECYCLE-REPORT-INDEX"]},
        "RMAP-029": {"acceptance_id": "RMAP-ACC-029", "first_phase": "P1", "owner_book": "06-testing-observability-and-evidence.md", "failure_family": "premature_or_authoritative_completion_report", "source_refs": ["repair-20260722-lifecycle:RMAP-PLAN-LIFECYCLE-COMPLETION"]},
    }
    for requirement_id, expected in expected_requirements.items():
        item = requirement_map.get(requirement_id, {})
        if any(item.get(key) != value for key, value in expected.items()):
            findings.append(_finding("RMAP-PLAN-LIFECYCLE-POLICY", requirement_id, "requirement authority or lifecycle identity is incomplete"))

    acceptance_map = {item.get("requirement_id"): item for item in acceptance.get("acceptances", []) if isinstance(item, dict)}
    expected_acceptance = {
        "RMAP-028": {
            "owner_slice_id": "RMAP-S1", "supporting_slice_ids": ["RMAP-S2"], "phase_id": "P0", "positive_command_ids": ["rmap-s1-slice-validate"],
            "negative_fixture_ids": ["plan-lifecycle-audit-omitted", "plan-lifecycle-report-index-bypassed"], "expected_failure_ids": ["RMAP-PLAN-LIFECYCLE-POLICY"], "exit_predicate": "slice-ready",
            "evidence_required": {"plan-audit-before-freeze", "unique-target-95-report", "vdd-repair-write-gate", "target-plan-validator-pass", "target-95-append-only-change-entry", "refrozen-authority-candidate-and-validator-hashes", "report-excluded-from-authority-and-candidate-hash", "repository-report-index-first-lookup", "target-directory-only-index-miss-fallback", "target-95-index-synchronized", "index-non-authoritative"},
        },
        "RMAP-029": {
            "owner_slice_id": "RMAP-S2", "supporting_slice_ids": [], "phase_id": "P1", "positive_command_ids": ["rmap-s2-slice-validate"],
            "negative_fixture_ids": ["plan-lifecycle-terminal-predicate-bypassed"], "expected_failure_ids": ["RMAP-PLAN-LIFECYCLE-POLICY"], "exit_predicate": "slice-ready",
            "evidence_required": {"terminal-predicate-pass", "target-95-append-only-completion-entry", "completion-command-exit-test-and-hash-summary", "changed-files-evidence-and-residual-gaps", "report-non-authority"},
        },
    }
    for requirement_id, expected in expected_acceptance.items():
        item = acceptance_map.get(requirement_id, {})
        invalid = any(item.get(key) != expected[key] for key in set(expected) - {"evidence_required"})
        observed_evidence = item.get("evidence_required", [])
        invalid = invalid or not isinstance(observed_evidence, list) or not expected["evidence_required"].issubset(set(observed_evidence))
        if invalid:
            findings.append(_finding("RMAP-PLAN-LIFECYCLE-POLICY", requirement_id, "acceptance, negative fixture, or evidence binding is incomplete"))

    slices = {item.get("slice_id"): item for item in contract.get("slices", []) if isinstance(item, dict)}
    expected_slice_bindings = {"RMAP-S1": ({"RMAP-028"}, {"RMAP-ACC-028"}), "RMAP-S2": ({"RMAP-028", "RMAP-029"}, {"RMAP-ACC-028", "RMAP-ACC-029"})}
    for slice_id, (requirement_ids, acceptance_ids) in expected_slice_bindings.items():
        item = slices.get(slice_id, {})
        if not requirement_ids.issubset(set(item.get("requirement_ids", []))) or not acceptance_ids.issubset(set(item.get("acceptance_ids", []))):
            findings.append(_finding("RMAP-PLAN-LIFECYCLE-POLICY", slice_id, "owner/supporting slice mapping is incomplete"))

    reports = sorted(plan_root.glob("95-*.md"))
    if len(reports) != 1:
        findings.append(_finding("RMAP-PLAN-LIFECYCLE-POLICY", "95-report", "target plan must contain exactly one 95-*.md report"))
    else:
        repository_root = plan_root.parents[1]
        report = reports[0].resolve()
        report_relative = report.relative_to(repository_root.resolve()).as_posix()
        manifest_paths = {item.get("path") for entries in authority_manifest.get("categories", {}).values() for item in entries if isinstance(item, dict)}
        candidate_members = set(predicate_closure.get("candidate_hash_scope", {}).get("members", []))
        authority_sources = {(plan_root / relative).resolve() for relative in contract.get("authority", {}).get("source_hashes", {})}
        if report_relative in manifest_paths or report_relative in candidate_members or report in authority_sources:
            findings.append(_finding("RMAP-PLAN-LIFECYCLE-POLICY", report_relative, "95 report must remain outside authority and candidate hashes"))
        index_relative = "execution-plans/95-implementation-report-index.v1.json"
        index_path = repository_root / index_relative
        try:
            index = __import__("json").loads(index_path.read_text(encoding="utf-8"))
            entries = index.get("entries")
        except (OSError, UnicodeError, ValueError):
            entries = None
            index = {}
        execution_plans_root = (repository_root / "execution-plans").resolve()
        valid_entries = isinstance(entries, list) and all(
            isinstance(entry, dict)
            and set(entry) == {"plan_directory", "report_filename"}
            and isinstance(entry.get("plan_directory"), str)
            and Path(entry["plan_directory"]).name == entry["plan_directory"]
            and isinstance(entry.get("report_filename"), str)
            and Path(entry["report_filename"]).name == entry["report_filename"]
            and entry["report_filename"].startswith("95-")
            and entry["report_filename"].endswith(".md")
            and (repository_root / "execution-plans" / entry["plan_directory"]).resolve().is_relative_to(execution_plans_root)
            and (repository_root / "execution-plans" / entry["plan_directory"] / entry["report_filename"]).resolve().is_relative_to((repository_root / "execution-plans" / entry["plan_directory"]).resolve())
            and (repository_root / "execution-plans" / entry["plan_directory"] / entry["report_filename"]).is_file()
            for entry in entries or []
        )
        directories = [entry["plan_directory"] for entry in entries or [] if isinstance(entry, dict) and isinstance(entry.get("plan_directory"), str)]
        target_entries = [entry for entry in entries or [] if isinstance(entry, dict) and entry.get("plan_directory") == plan_root.name]
        index_is_valid = (
            index.get("schema_version") == "jimuyun.execution-plan-95-report-index.v1"
            and valid_entries
            and directories == sorted(directories, key=str.casefold)
            and len(directories) == len(set(item.casefold() for item in directories))
            and len(target_entries) == 1
            and target_entries[0].get("report_filename") == report.name
        )
        if not index_is_valid:
            findings.append(_finding("RMAP-PLAN-LIFECYCLE-POLICY", index_relative, "95 report index is missing, stale, ambiguous, escaping, or unsorted"))
        if index_relative in manifest_paths or index_relative in candidate_members or index_path.resolve() in authority_sources:
            findings.append(_finding("RMAP-PLAN-LIFECYCLE-POLICY", index_relative, "95 report index must remain a non-authoritative path hint"))
    return findings
