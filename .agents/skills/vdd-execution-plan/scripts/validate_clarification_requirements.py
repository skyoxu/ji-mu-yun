#!/usr/bin/env python3
"""Validate the frozen VDD clarification requirements registry."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


EXPECTED_IDS = {f"VCR-{number:03d}" for number in range(1, 36)}
MODIFIED_IDS = {
    "VCR-001", "VCR-007", "VCR-008", "VCR-009", "VCR-011", "VCR-012",
    "VCR-013", "VCR-014", "VCR-015", "VCR-016", "VCR-024",
}
IDENTITY = re.compile(r"^100644/[0-9a-f]{40}$")


def validate(payload: object) -> list[str]:
    if not isinstance(payload, dict) or payload.get("schema_version") != "vdd.clarification-requirements.v1":
        return ["VDD-CLARIFICATION-REQUIREMENTS-SCHEMA"]
    requirements = payload.get("requirements")
    if not isinstance(requirements, list):
        return ["VDD-CLARIFICATION-REQUIREMENTS-REGISTRY"]
    findings: list[str] = []
    ids = [item.get("id") for item in requirements if isinstance(item, dict)]
    if set(ids) != EXPECTED_IDS or len(ids) != len(set(ids)):
        findings.append("VDD-CLARIFICATION-REQUIREMENTS-COVERAGE")
    owners = [item.get("owner") for item in requirements if isinstance(item, dict)]
    acceptances = [item.get("acceptance_id") for item in requirements if isinstance(item, dict)]
    if any(not isinstance(value, str) or not value for value in owners + acceptances) or len(acceptances) != len(set(acceptances)):
        findings.append("VDD-CLARIFICATION-REQUIREMENTS-OWNER")
    for item in requirements:
        if not isinstance(item, dict):
            findings.append("VDD-CLARIFICATION-REQUIREMENTS-REGISTRY")
            continue
        required = {"id", "approved_source", "owner", "first_phase", "affected_consumers", "acceptance_id", "failure_family", "delta", "status", "evidence_intent"}
        if not required <= set(item) or item.get("approved_source") != "INTENT-KERNEL-VCR-20260721" or item.get("status") != "approved":
            findings.append("VDD-CLARIFICATION-REQUIREMENTS-REGISTRY")
        identifier = item.get("id")
        if identifier in MODIFIED_IDS:
            prior = item.get("prior_provenance")
            if not isinstance(prior, dict) or set(prior) != {"path", "locator", "baseline_git_identity", "replacement"} or not IDENTITY.fullmatch(str(prior.get("baseline_git_identity", ""))):
                findings.append("VDD-CLARIFICATION-REQUIREMENTS-PROVENANCE")
        elif item.get("delta") != "ADDED":
            findings.append("VDD-CLARIFICATION-REQUIREMENTS-PROVENANCE")
    return sorted(set(findings))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True)
    args = parser.parse_args()
    try:
        payload = json.loads(Path(args.registry).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"VDD-CLARIFICATION-REQUIREMENTS-PARSE: {exc}")
        return 1
    findings = validate(payload)
    print(json.dumps({"status": "PASS" if not findings else "FAIL", "findings": findings}))
    return 0 if not findings else 1


if __name__ == "__main__":
    sys.exit(main())
