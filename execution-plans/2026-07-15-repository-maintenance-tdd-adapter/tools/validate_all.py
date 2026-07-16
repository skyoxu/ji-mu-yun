from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fixture_checks import evaluate_fixture, validate_fixture_suite
from evidence_guards import validate_candidate_review_documents
from slice_guards import validate_slice_outputs
from rmap_checks import (
    PREDICATE_AUTHORITY,
    VALIDATOR_VERSION,
    candidate_hash,
    load_machine,
    sha256_file,
    validate_static,
)


PLAN_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLAN_ROOT.parents[1]


def validator_identity() -> str:
    digest = hashlib.sha256()
    names = ["validate_all.py", "rmap_checks.py", "contract_guards.py", "evidence_guards.py", "shadow_guards.py", "source_guards.py", "slice_guards.py", "fixture_checks.py"]
    for path in (Path(__file__).with_name(name) for name in names):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"{VALIDATOR_VERSION}+sha256:{digest.hexdigest()}"


def run_unit_tests() -> tuple[dict[str, Any], list[dict[str, str]]]:
    command = [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        str(PLAN_ROOT / "tools" / "tests"),
        "-p",
        "test_*.py",
    ]
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    temp_root = REPOSITORY_ROOT / "logs" / "vdd-test-temp"
    temp_root.mkdir(parents=True, exist_ok=True)
    env["TEMP"] = str(temp_root)
    env["TMP"] = str(temp_root)
    result = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=120,
        check=False,
    )
    evidence = (result.stdout + result.stderr).strip().splitlines()
    check = {
        "rule_id": "RMAP-UNIT-TESTS",
        "status": "pass" if result.returncode == 0 else "fail",
        "evidence": [f"exit_code={result.returncode}", *(evidence[-3:] or ["no test output"])],
    }
    findings = [] if result.returncode == 0 else [{
        "rule_id": "RMAP-UNIT-TESTS",
        "target": "tools/tests",
        "message": f"unit tests failed with exit code {result.returncode}",
    }]
    return check, findings


def all_exclusions() -> list[str]:
    return ["plan-ready", "slice-ready", "bootstrap-review", "implementation-accepted", "protected-handoff", "release-ready"]


def build_result(predicate: str, checks: list[dict[str, Any]], findings: list[dict[str, str]]) -> dict[str, Any]:
    current_hash = candidate_hash(PLAN_ROOT)
    source_hash = sha256_file(REPOSITORY_ROOT / "agentbuild.txt")
    passed = not findings
    authorizes, excludes = PREDICATE_AUTHORITY[predicate]
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "schema_version": "rmap.validation-result.v1",
        "run_id": "rmap-plan-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "predicate": predicate,
        "status": "pass" if passed else "fail",
        "candidate_hash": current_hash,
        "current_candidate_hash": current_hash,
        "source_hash": source_hash,
        "validator_version": validator_identity(),
        "authorizes": authorizes if passed else [],
        "does_not_authorize": excludes if passed else all_exclusions(),
        "checks": checks,
        "diagnostics": findings,
        "generated_at": timestamp,
    }


def strict_load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)))
    if not isinstance(value, dict):
        raise ValueError("document root must be object")
    return value


def run_predicate(predicate: str, slice_id: str | None = None, candidate_result: str | None = None, bootstrap_run: str | None = None) -> tuple[dict[str, Any], int]:
    checks, findings, data = validate_static(PLAN_ROOT)
    fixture_findings = validate_fixture_suite(PLAN_ROOT, data) if data else []
    findings.extend(fixture_findings)
    checks.append({"rule_id": "RMAP-FIXTURES", "status": "pass" if not fixture_findings else "fail", "evidence": ["positive, negative, boundary, stale, and mutation cases"]})
    if slice_id:
        contract_slice = next((item for item in data.get("contract", {}).get("slices", []) if item.get("slice_id") == slice_id), None)
        if contract_slice is None or contract_slice.get("exit_predicate") != predicate:
            slice_check = {"rule_id": "RMAP-AUTH-SLICE", "status": "fail", "evidence": ["slice/predicate binding"]}
            slice_findings = [{"rule_id": "RMAP-TDD-EXIT-PROOF", "target": slice_id, "message": "requested predicate does not match slice exit"}]
        else:
            slice_check, slice_findings = validate_slice_outputs(REPOSITORY_ROOT, slice_id, data.get("shadow"))
            if slice_id in {"RMAP-S6", "RMAP-S7"}:
                if not candidate_result or not bootstrap_run:
                    slice_findings.append({"rule_id": "RMAP-REVIEW-EVIDENCE-BINDING", "target": slice_id, "message": "explicit candidate result and Bootstrap run are required"})
                else:
                    try:
                        run_dir = (REPOSITORY_ROOT / bootstrap_run).resolve()
                        candidate_path = (REPOSITORY_ROOT / candidate_result).resolve()
                        candidate_relative = candidate_path.relative_to(REPOSITORY_ROOT).as_posix()
                        run_relative = run_dir.relative_to(REPOSITORY_ROOT).as_posix()
                        if not candidate_relative.startswith("logs/tdd-adapter/") or not run_relative.startswith("logs/ci/"):
                            raise ValueError("evidence paths must stay in their declared logs roots")
                        documents = [strict_load(candidate_path), strict_load(run_dir / "review-input.json"), strict_load(run_dir / "preflight-result.json"), strict_load(run_dir / "review-gate-result.json"), strict_load(run_dir / "review-dispositions.json")]
                        slice_findings.extend(validate_candidate_review_documents(
                            PLAN_ROOT, candidate_relative, *documents, predicate,
                            data["contract"].get("acceptance_policy", {}).get("p2_deferrals", []),
                            candidate_hash(PLAN_ROOT), sha256_file(REPOSITORY_ROOT / "agentbuild.txt"), "RMAP-S6",
                        ))
                    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
                        slice_findings.append({"rule_id": "RMAP-REVIEW-EVIDENCE-BINDING", "target": slice_id, "message": str(exc)})
            slice_check["status"] = "pass" if not slice_findings else "fail"
        checks.append(slice_check)
        findings.extend(slice_findings)
    elif predicate != "plan-ready":
        findings.append({
            "rule_id": "RMAP-AUTH-EVIDENCE-MISSING",
            "target": predicate,
            "message": "implementation-time evidence is not present during plan creation",
        })
        checks.append({"rule_id": "RMAP-AUTH-RUNTIME-EVIDENCE", "status": "fail", "evidence": ["plan creation has no implementation evidence"]})
    test_check, test_findings = run_unit_tests()
    checks.append(test_check)
    findings.extend(test_findings)
    result = build_result(predicate, checks, findings)
    return result, 0 if result["status"] == "pass" else 1


def run_fixture(fixture_id: str) -> tuple[dict[str, Any], int]:
    data, load_findings = load_machine(PLAN_ROOT)
    findings = load_findings or evaluate_fixture(PLAN_ROOT, fixture_id, data)
    check = {
        "rule_id": "RMAP-FIXTURE-OBSERVATION",
        "status": "fail" if findings else "pass",
        "evidence": [f"fixture={fixture_id}", *[item["rule_id"] for item in findings]],
    }
    current_hash = candidate_hash(PLAN_ROOT)
    result = {
        "schema_version": "rmap.fixture-observation.v1",
        "run_id": "rmap-fixture-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "fixture": fixture_id,
        "status": "fail" if findings else "pass",
        "candidate_hash": current_hash,
        "source_hash": sha256_file(REPOSITORY_ROOT / "agentbuild.txt"),
        "validator_version": validator_identity(),
        "checks": [check],
        "diagnostics": findings,
        "authorizes": [],
        "does_not_authorize": all_exclusions(),
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    return result, 1 if findings else 0


def write_output(path: str | None, result: dict[str, Any]) -> None:
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if path:
        output = Path(path).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the Repository Maintenance TDD Adapter VDD plan.")
    parser.add_argument("--predicate", choices=sorted(PREDICATE_AUTHORITY), default="plan-ready")
    parser.add_argument("--slice-id")
    parser.add_argument("--fixture")
    parser.add_argument("--candidate-result")
    parser.add_argument("--bootstrap-run")
    parser.add_argument("--output")
    args = parser.parse_args()
    result, exit_code = run_fixture(args.fixture) if args.fixture else run_predicate(args.predicate, args.slice_id, args.candidate_result, args.bootstrap_run)
    write_output(args.output, result)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
