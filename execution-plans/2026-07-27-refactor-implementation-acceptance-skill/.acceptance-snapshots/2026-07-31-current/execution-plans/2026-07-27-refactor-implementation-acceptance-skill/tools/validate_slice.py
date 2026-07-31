"""Validate a completed 7-27 implementation slice without granting acceptance authority."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from validate_plan import REPOSITORY_ROOT, validate


def validate_slice(slice_id: str) -> list[str]:
    findings = list(validate())
    if slice_id == "RMAP-S0":
        test_path = REPOSITORY_ROOT / ".agents/skills/run-phase-bootstrap-review/tests/test_bootstrap_companion_capability.py"
        result = subprocess.run(
            [sys.executable, "-B", str(test_path)],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode != 0:
            findings.append("RIA-S0-PROTOCOL-TEST:" + (result.stderr or result.stdout).strip()[-400:])
        profile_path = REPOSITORY_ROOT / ".agents/skills/run-phase-bootstrap-review/references/review-profiles.v1.json"
        schema_path = REPOSITORY_ROOT / ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-acceptance-inventory-attestation.v1.schema.json"
        try:
            profile = json.loads(profile_path.read_text(encoding="utf-8"))["profiles"]["bootstrap-implementation-conformance"]
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            capabilities = profile.get("companionCapabilities", [])
            expected = {"capabilityId": "acceptance-inventory-attestation", "capabilityVersion": "1.0", "producerRole": "acceptance_auditor"}
            if sum(isinstance(item, dict) and all(item.get(key) == value for key, value in expected.items()) for item in capabilities) != 1:
                findings.append("RIA-S0-CAPABILITY-PROFILE")
            if schema.get("properties", {}).get("scopeHash", {}).get("pattern") != "^sha256:[0-9a-f]{64}$":
                findings.append("RIA-S0-ATTESTATION-SCHEMA")
        except (KeyError, TypeError, json.JSONDecodeError, OSError):
            findings.append("RIA-S0-COMPANION-CONTRACT")
        for relative in (
            "docs/standards/bootstrap-review-control-plane.md",
            "docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md",
            "execution-plans/2026-07-12-llm-review-evidence-gate-hardening/09-bootstrap-review-operator-guide.md",
        ):
            if not (REPOSITORY_ROOT / relative).is_file():
                findings.append("RIA-S0-DURABLE-PROJECTION:" + relative)
    elif slice_id == "RMAP-S1":
        skill_root = REPOSITORY_ROOT / ".agents/skills/run-refactor-implementation-acceptance"
        schema_names = {
            "acceptance-run-input.v1.schema.json", "acceptance-source-inventory.v1.schema.json",
            "acceptance-baseline-content-manifest.v1.schema.json", "acceptance-candidate-content-manifest.v1.schema.json",
            "code-review-policy-pack.v1.schema.json", "code-review-policy-binding.v1.schema.json",
            "phase-diff-coverage-result.v1.schema.json", "task-checklist-closure.v1.schema.json",
            "phase-scan-bundle-result.v1.schema.json", "check-id-lineage.v1.schema.json",
            "acceptance-source-clauses.v1.schema.json",
        }
        for name in schema_names:
            try:
                schema = json.loads((skill_root / "schemas" / name).read_text(encoding="utf-8"))
                if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema" or schema.get("type") != "object":
                    findings.append("RIA-S1-SCHEMA:" + name)
            except (OSError, json.JSONDecodeError):
                findings.append("RIA-S1-SCHEMA:" + name)
        suite = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "discover", "-s", str(skill_root / "tests"), "-p", "test_*.py"],
            cwd=REPOSITORY_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        )
        if suite.returncode != 0:
            findings.append("RIA-S1-TEST-SUITE:" + (suite.stderr or suite.stdout).strip()[-400:])
        package = subprocess.run(
            [sys.executable, "-B", str(skill_root / "scripts" / "acceptance_cli.py"), "validate-package"],
            cwd=REPOSITORY_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        )
        if package.returncode != 0:
            findings.append("RIA-S1-PACKAGE:" + (package.stderr or package.stdout).strip()[-400:])
    elif slice_id == "RMAP-S2":
        required = {
            ".agents/skills/run-refactor-implementation-acceptance/scripts/matrix_phase.py": "three_level_dod",
            ".agents/skills/run-refactor-implementation-acceptance/tests/test_matrix_phase.py": "test_join_phase_waits_for_all_predecessors",
        }
        for relative, marker in required.items():
            path = REPOSITORY_ROOT / relative
            if not path.is_file() or marker not in path.read_text(encoding="utf-8"):
                findings.append("RIA-S2-MATRIX-PHASE:" + relative)
    elif slice_id == "RMAP-S3":
        required = {
            ".agents/skills/run-refactor-implementation-acceptance/scripts/execution_control.py": "validate_recovery_state",
            ".agents/skills/run-refactor-implementation-acceptance/tests/test_control.py": "test_lock_is_exclusive",
        }
        for relative, marker in required.items():
            path = REPOSITORY_ROOT / relative
            if not path.is_file() or marker not in path.read_text(encoding="utf-8"):
                findings.append("RIA-S3-EXECUTION-CONTROL:" + relative)
    elif slice_id == "RMAP-S4":
        required = {
            ".agents/skills/run-refactor-implementation-acceptance/scripts/bootstrap_integration.py": "bind_capabilities",
            ".agents/skills/run-refactor-implementation-acceptance/tests/test_bootstrap_integration.py": "test_required_decision_binds_profile_companion_identity",
        }
        for relative, marker in required.items():
            path = REPOSITORY_ROOT / relative
            if not path.is_file() or marker not in path.read_text(encoding="utf-8"):
                findings.append("RIA-S4-BOOTSTRAP-INTEGRATION:" + relative)
    elif slice_id == "RMAP-S5":
        required = {
            ".agents/skills/run-refactor-implementation-acceptance/scripts/package_validation.py": "validate_package",
            ".agents/skills/run-refactor-implementation-acceptance/tests/test_package.py": "test_package_validator_requires_all_slice_modules",
        }
        for relative, marker in required.items():
            path = REPOSITORY_ROOT / relative
            if not path.is_file() or marker not in path.read_text(encoding="utf-8"):
                findings.append("RIA-S5-PACKAGE:" + relative)
    elif slice_id == "R2-baseline-propagation":
        suite = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "discover", "-s", str(REPOSITORY_ROOT / ".agents/skills/run-refactor-implementation-acceptance/tests"), "-p", "test_*.py"],
            cwd=REPOSITORY_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        )
        if suite.returncode != 0:
            findings.append("RIA-R2-BASELINE:" + (suite.stderr or suite.stdout).strip()[-400:])
    elif slice_id == "R2-checklist-contract":
        suite = subprocess.run([sys.executable, "-B", str(REPOSITORY_ROOT / ".agents/skills/run-refactor-implementation-acceptance/tests/test_task_checklist.py")], cwd=REPOSITORY_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        if suite.returncode != 0:
            findings.append("RIA-R2-CHECKLIST:" + (suite.stderr or suite.stdout).strip()[-400:])
    elif slice_id == "R2-bootstrap-dispatch":
        suite = subprocess.run([sys.executable, "-B", str(REPOSITORY_ROOT / ".agents/skills/run-refactor-implementation-acceptance/tests/test_package.py")], cwd=REPOSITORY_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        if suite.returncode != 0:
            findings.append("RIA-R2-DISPATCH:" + (suite.stderr or suite.stdout).strip()[-400:])
    elif slice_id == "R2-attestation-scope":
        suite = subprocess.run([sys.executable, "-B", str(REPOSITORY_ROOT / ".agents/skills/run-refactor-implementation-acceptance/tests/test_bootstrap_integration.py")], cwd=REPOSITORY_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        if suite.returncode != 0:
            findings.append("RIA-R2-ATTESTATION:" + (suite.stderr or suite.stdout).strip()[-400:])
    elif slice_id == "R3-candidate-completeness-and-policy":
        suite = subprocess.run([sys.executable, "-B", str(REPOSITORY_ROOT / ".agents/skills/run-refactor-implementation-acceptance/tests/test_run_input.py")], cwd=REPOSITORY_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        if suite.returncode != 0:
            findings.append("RIA-R3-CANDIDATE:" + (suite.stderr or suite.stdout).strip()[-400:])
    elif slice_id == "R3-phase-coverage-completeness":
        suite = subprocess.run([sys.executable, "-B", str(REPOSITORY_ROOT / ".agents/skills/run-refactor-implementation-acceptance/tests/test_evidence_analysis.py")], cwd=REPOSITORY_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        if suite.returncode != 0:
            findings.append("RIA-R3-COVERAGE:" + (suite.stderr or suite.stdout).strip()[-400:])
    elif slice_id == "SUC1-policy-path-coverage":
        suite = subprocess.run([sys.executable, "-B", str(REPOSITORY_ROOT / ".agents/skills/run-refactor-implementation-acceptance/tests/test_run_input.py")], cwd=REPOSITORY_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        if suite.returncode != 0:
            findings.append("RIA-SUC1-POLICY:" + (suite.stderr or suite.stdout).strip()[-400:])
    elif slice_id == "SUC1-changed-line-manifest-binding":
        suite = subprocess.run([sys.executable, "-B", str(REPOSITORY_ROOT / ".agents/skills/run-refactor-implementation-acceptance/tests/test_evidence_analysis.py")], cwd=REPOSITORY_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        if suite.returncode != 0:
            findings.append("RIA-SUC1-COVERAGE:" + (suite.stderr or suite.stdout).strip()[-400:])
    else:
        findings.append("RIA-SLICE-NOT-IMPLEMENTED:" + slice_id)
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slice-id", required=True)
    args = parser.parse_args()
    findings = validate_slice(args.slice_id)
    print(json.dumps({"status": "pass" if not findings else "fail", "predicate": "slice-ready", "slice_id": args.slice_id, "findings": findings, "authorizes": []}, sort_keys=True))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
