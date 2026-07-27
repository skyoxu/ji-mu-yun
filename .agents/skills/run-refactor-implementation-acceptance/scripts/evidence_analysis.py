"""Deterministic evidence analyzers for Phase changed-line coverage."""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from typing import Any

from acceptance_core import InputError, canonical_hash


_EXCLUSION_REASONS = {
    "blank_line",
    "comment_only",
    "compiler_generated",
    "obj_or_bin",
    "unchanged_rename",
}


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _phase_source(path: Any) -> bool:
    return isinstance(path, str) and path.startswith("PhaseA.Platform/") and path.endswith(".cs")


def validate_changed_line_set(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, dict) or value.get("schemaVersion") != "phase-changed-line-set.v1":
        raise InputError("changed-line set schemaVersion is invalid")
    if not isinstance(value.get("candidateContentManifestHash"), str):
        raise InputError("changed-line set candidate manifest hash is invalid")
    entries = value.get("lines")
    if not isinstance(entries, list):
        raise InputError("changed-line set lines are invalid")
    observed: set[tuple[str, int]] = set()
    normalized: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict) or not _phase_source(entry.get("path")):
            raise InputError("changed-line set contains a non-Phase C# path")
        line = entry.get("line")
        classification = entry.get("classification")
        reason = entry.get("exclusionReason")
        if not isinstance(line, int) or isinstance(line, bool) or line < 1:
            raise InputError("changed-line set line number is invalid")
        identity = (entry["path"], line)
        if identity in observed:
            raise InputError("changed-line set contains duplicate lines")
        observed.add(identity)
        if classification == "measurable":
            if reason is not None:
                raise InputError("measurable changed line cannot have an exclusion reason")
        elif classification == "excluded":
            if reason not in _EXCLUSION_REASONS:
                raise InputError("excluded changed line has an invalid reason")
        else:
            raise InputError("changed-line classification is invalid")
        normalized.append({"path": entry["path"], "line": line, "classification": classification, "exclusionReason": reason})
    return normalized


def _coverage_lines(cobertura: bytes) -> dict[str, dict[int, int]]:
    try:
        root = ElementTree.fromstring(cobertura)
    except ElementTree.ParseError as exc:
        raise InputError("Cobertura report is malformed") from exc
    result: dict[str, dict[int, int]] = {}
    for class_node in root.findall(".//class"):
        filename = class_node.attrib.get("filename")
        if not filename:
            continue
        key = filename.replace("\\", "/")
        lines = result.setdefault(key, {})
        for line_node in class_node.findall("./lines/line"):
            try:
                number, hits = int(line_node.attrib["number"]), int(line_node.attrib["hits"])
            except (KeyError, ValueError) as exc:
                raise InputError("Cobertura line record is invalid") from exc
            if number < 1 or hits < 0:
                raise InputError("Cobertura line record is invalid")
            lines[number] = max(lines.get(number, 0), hits)
    return result


def analyze_diff_coverage(
    *,
    acceptance_run_id: str,
    baseline_revision: str,
    candidate_revision: str,
    candidate_manifest_hash: str,
    changed_line_set: Any,
    cobertura_path: Path,
    source_map: dict[str, str],
    test_run_evidence_id: str,
) -> dict[str, Any]:
    """Calculate the fixed 85 percent gate from frozen changed lines and Cobertura."""
    entries = validate_changed_line_set(changed_line_set)
    if changed_line_set["candidateContentManifestHash"] != candidate_manifest_hash:
        raise InputError("changed-line set is bound to another candidate manifest")
    if not isinstance(acceptance_run_id, str) or not acceptance_run_id or not isinstance(test_run_evidence_id, str) or not test_run_evidence_id:
        raise InputError("coverage run identity is invalid")
    if not cobertura_path.is_file():
        raise InputError("Cobertura report is missing")
    report_bytes = cobertura_path.read_bytes()
    coverage = _coverage_lines(report_bytes)
    measurable = [entry for entry in entries if entry["classification"] == "measurable"]
    missing_sources = sorted({entry["path"] for entry in measurable if source_map.get(entry["path"]) not in coverage})
    base = {
        "schemaVersion": "phase-diff-coverage-result.v1",
        "acceptanceRunId": acceptance_run_id,
        "baselineRevision": baseline_revision,
        "candidateRevision": candidate_revision,
        "candidateContentManifestHash": candidate_manifest_hash,
        "changedLineSetHash": canonical_hash(changed_line_set),
        "coverageReportPath": str(cobertura_path).replace("\\", "/"),
        "coverageReportHash": _sha256_bytes(report_bytes),
        "testRunEvidenceId": test_run_evidence_id,
        "thresholdSource": "user-requirement://phase-diff-coverage-85",
        "minimumChangedLineCoveragePct": 85.0,
        "exclusions": [entry for entry in entries if entry["classification"] == "excluded"],
        "authorizes": [],
    }
    if missing_sources:
        return {
            **base,
            "status": "incomplete",
            "reasonCodes": ["coverage_source_mapping_missing"],
            "missingSourcePaths": missing_sources,
            "counts": {"measurableChangedExecutableLines": len(measurable), "coveredChangedExecutableLines": 0},
            "changedLineCoveragePct": None,
        }
    if not measurable:
        return {
            **base,
            "status": "not_applicable",
            "reasonCodes": [],
            "missingSourcePaths": [],
            "counts": {"measurableChangedExecutableLines": 0, "coveredChangedExecutableLines": 0},
            "changedLineCoveragePct": None,
        }
    covered = sum(coverage[source_map[entry["path"]]].get(entry["line"], 0) > 0 for entry in measurable)
    percent = covered / len(measurable) * 100
    return {
        **base,
        "status": "passed" if percent >= 85.0 else "failed",
        "reasonCodes": [] if percent >= 85.0 else ["coverage_below_threshold"],
        "missingSourcePaths": [],
        "counts": {"measurableChangedExecutableLines": len(measurable), "coveredChangedExecutableLines": covered},
        "changedLineCoveragePct": percent,
    }
