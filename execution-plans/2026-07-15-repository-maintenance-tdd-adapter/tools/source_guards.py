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
    if creation != [f"CQ-{index:03d}" for index in range(1, 18)] or repair != [f"CQ-{index:03d}" for index in range(1, 6)]:
        return []
    return [
        ("CREATE-CQ-001-005", "creation:CQ-001..CQ-005"),
        ("CREATE-CQ-006-012", "creation:CQ-006..CQ-012"),
        ("CREATE-CQ-013-017", "creation:CQ-013..CQ-017"),
        ("REPAIR-CQ-001-005", "repair:CQ-001..CQ-005"),
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
        expected_count = 9 if source_id == "agentbuild" else 4
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
