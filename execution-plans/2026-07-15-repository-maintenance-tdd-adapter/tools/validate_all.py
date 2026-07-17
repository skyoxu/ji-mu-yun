from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from contract_guards import schema_error
from fixture_checks import evaluate_fixture, validate_fixture_suite
from candidate_diff_guards import validate_candidate_fixture_suite
from protocol_guards import evaluate_protocol_fixture
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
    names = ["validate_all.py", "rmap_checks.py", "contract_guards.py", "authority_guards.py", "evidence_guards.py", "candidate_diff_guards.py", "candidate_lineage_guards.py", "current_state_guards.py", "shadow_guards.py", "source_guards.py", "slice_guards.py", "fixture_checks.py", "protocol_guards.py", "protocol_validation_guards.py", "protocol_fixture_support.py", "protocol_fixture_cases.py", "protocol_fixture_mutations.py", "protocol_artifact_guards.py", "attempt_lineage_guards.py"]
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
    return ["plan-repair-verified", "plan-ready", "slice-ready", "bootstrap-review", "implementation-accepted", "protected-handoff", "release-ready"]


def validation_snapshot() -> dict[str, str]:
    return {
        "candidate_hash": candidate_hash(PLAN_ROOT),
        "source_hash": sha256_file(REPOSITORY_ROOT / "agentbuild.txt"),
        "validator_version": validator_identity(),
    }


def build_result(predicate: str, checks: list[dict[str, Any]], findings: list[dict[str, str]], validated: dict[str, str], current: dict[str, str], status_override: str | None = None) -> dict[str, Any]:
    passed = not findings and status_override is None
    authorizes, excludes = PREDICATE_AUTHORITY[predicate]
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    result = {
        "schema_version": "rmap.validation-result.v1",
        "run_id": "rmap-plan-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "predicate": predicate,
        "status": status_override or ("pass" if passed else "fail"),
        "candidate_hash": validated["candidate_hash"],
        "current_candidate_hash": current["candidate_hash"],
        "source_hash": validated["source_hash"],
        "validator_version": validated["validator_version"],
        "authorizes": authorizes if passed else [],
        "does_not_authorize": excludes if passed else all_exclusions(),
        "checks": checks,
        "diagnostics": findings,
        "generated_at": timestamp,
    }
    result_schema = strict_load(PLAN_ROOT / "schemas" / "validation-result.v1.schema.json")
    envelope_error = schema_error(result, result_schema)
    if envelope_error:
        result["status"] = "fail"
        result["authorizes"] = []
        result["does_not_authorize"] = all_exclusions()
        result["diagnostics"].append({"rule_id": "RMAP-RESULT-ENVELOPE", "target": "validation-result", "message": envelope_error})
    return result


def _hash_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _git_bytes(*args: str) -> bytes:
    result = subprocess.run(["git", *args], cwd=REPOSITORY_ROOT, capture_output=True, check=False)
    if result.returncode != 0:
        raise ValueError(result.stderr.decode("utf-8", errors="replace"))
    return result.stdout


def _normalize_scope_pattern(pattern: str) -> str | None:
    normalized = pattern.replace("\\", "/").strip("/")
    if not normalized or "<" in normalized or normalized.casefold().startswith("logs/"):
        return None
    repository_prefixes = (".agents/", ".github/", "docs/", "execution-plans/", "scripts/", "runtime/", "PhaseA.Platform/", "Game.", "Tests.")
    if normalized in {"AGENTS.md", "README.md", "agentbuild.txt"} or normalized.startswith(repository_prefixes):
        return normalized
    plan_relative = PLAN_ROOT.relative_to(REPOSITORY_ROOT).as_posix()
    return f"{plan_relative}/{normalized}"


def _matches_scope(relative: str, patterns: set[str]) -> bool:
    folded = relative.replace("\\", "/").casefold()
    for pattern in patterns:
        candidate = pattern.casefold()
        if candidate.endswith("/**") and (folded == candidate[:-3] or folded.startswith(candidate[:-2])):
            return True
        if fnmatch.fnmatchcase(folded, candidate):
            return True
    return False


def _manifest_hash(paths: list[str]) -> str:
    digest = hashlib.sha256()
    for relative in sorted(paths, key=str.casefold):
        path = REPOSITORY_ROOT / relative
        digest.update(relative.encode("utf-8")); digest.update(b"\0")
        digest.update(path.read_bytes() if path.is_file() else b"<deleted>"); digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def current_candidate_identity(slice_id: str = "RMAP-S6") -> dict[str, str]:
    head = _git_bytes("rev-parse", "HEAD").decode("utf-8").strip()
    index_tree = _git_bytes("write-tree").decode("utf-8").strip()
    contract = strict_load(PLAN_ROOT / "implementation-contract.v1.json")
    slices = contract.get("slices", [])
    selected = next((index for index, item in enumerate(slices) if item.get("slice_id") == slice_id), None)
    if selected is None:
        raise ValueError(f"unknown slice identity scope: {slice_id}")
    patterns: set[str] = set()
    for item in slices[: selected + 1]:
        allowed = item.get("allowed_changes", {})
        raw_patterns = [*allowed.get("production", []), *allowed.get("tests", []), *allowed.get("documentation", []), *item.get("execution_read_set", []), *item.get("dependency_closure", []), *item.get("forbidden_changes", [])]
        patterns.update(filter(None, (_normalize_scope_pattern(pattern) for pattern in raw_patterns)))
    tracked_names = _git_bytes("diff", "--name-only", "HEAD").decode("utf-8").splitlines()
    tracked_names = [name for name in tracked_names if _matches_scope(name, patterns)]
    untracked_names = _git_bytes("ls-files", "--others", "--exclude-standard").decode("utf-8").splitlines()
    untracked_names = [name for name in untracked_names if _matches_scope(name, patterns)]
    tracked_diff_hash = _manifest_hash(tracked_names)
    untracked_manifest_hash = _manifest_hash(untracked_names)
    worktree = hashlib.sha256()
    for value in (head, index_tree, tracked_diff_hash, untracked_manifest_hash):
        worktree.update(value.encode("utf-8")); worktree.update(b"\0")
    return {
        "head": head,
        "index_tree": index_tree,
        "tracked_diff_hash": tracked_diff_hash,
        "untracked_manifest_hash": untracked_manifest_hash,
        "contract_hash": sha256_file(PLAN_ROOT / "implementation-contract.v1.json"),
        "command_registry_hash": sha256_file(PLAN_ROOT / "schemas" / "command-registry.v1.json"),
        "validator_hash": "sha256:" + validator_identity().rsplit("sha256:", 1)[1],
        "authority_manifest_hash": sha256_file(PLAN_ROOT / "schemas" / "authority-manifest.v1.json"),
        "candidate_worktree_hash": "sha256:" + worktree.hexdigest(),
        "plan_hash": candidate_hash(PLAN_ROOT),
        "source_hash": sha256_file(REPOSITORY_ROOT / "agentbuild.txt"),
    }


def strict_load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)))
    if not isinstance(value, dict):
        raise ValueError("document root must be object")
    return value


def run_predicate(predicate: str, slice_id: str | None = None, candidate_result: str | None = None, candidate_ref: str | None = None, bootstrap_run: str | None = None, run_dir: str | None = None, red_result: str | None = None, green_result: str | None = None, refactor_result: str | None = None) -> tuple[dict[str, Any], int]:
    validated_snapshot = validation_snapshot()
    checks, findings, data = validate_static(PLAN_ROOT)
    fixture_findings = validate_fixture_suite(PLAN_ROOT, data) if data else []
    fixture_findings.extend(validate_candidate_fixture_suite(PLAN_ROOT) if data else [])
    findings.extend(fixture_findings)
    checks.append({"rule_id": "RMAP-FIXTURES", "status": "pass" if not fixture_findings else "fail", "evidence": ["positive, negative, boundary, stale, and mutation cases"]})
    reentry_authorized = data.get("review_reentry", {}).get("state") == "reentry_authorized"
    blocked_predicates = set() if reentry_authorized else set(data.get("review_blocker", {}).get("blocks_predicates", []))
    if predicate in blocked_predicates:
        findings.append({"rule_id": "RMAP-REVIEW-MANUAL-PAUSE", "target": predicate, "message": "Round 3 manual pause requires a new review policy decision"})
        checks.append({"rule_id": "RMAP-REVIEW-MANUAL-PAUSE", "status": "blocked", "evidence": [data.get("review_blocker", {}).get("review_id", "missing review id")]})
    elif slice_id:
        contract_slice = next((item for item in data.get("contract", {}).get("slices", []) if item.get("slice_id") == slice_id), None)
        if contract_slice is None or contract_slice.get("exit_predicate") != predicate:
            slice_check = {"rule_id": "RMAP-AUTH-SLICE", "status": "fail", "evidence": ["slice/predicate binding"]}
            slice_findings = [{"rule_id": "RMAP-TDD-EXIT-PROOF", "target": slice_id, "message": "requested predicate does not match slice exit"}]
        else:
            evidence = {"run_dir": run_dir, "red_result": red_result, "green_result": green_result, "refactor_result": refactor_result}
            slice_identity = current_candidate_identity(slice_id)
            slice_check, slice_findings = validate_slice_outputs(REPOSITORY_ROOT, slice_id, data.get("shadow"), evidence, contract_slice, slice_identity)
            stage_documents = []
            for stage_path in (red_result, green_result, refactor_result):
                if stage_path:
                    try:
                        stage_documents.append(strict_load((REPOSITORY_ROOT / stage_path).resolve()))
                    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
                        pass
            if slice_id in {"RMAP-S6", "RMAP-S7"}:
                if not candidate_result or (slice_id == "RMAP-S7" and (not bootstrap_run or not candidate_ref)):
                    slice_findings.append({"rule_id": "RMAP-REVIEW-EVIDENCE-BINDING", "target": slice_id, "message": "explicit candidate result and required review evidence are missing"})
                else:
                    try:
                        current = current_candidate_identity()
                        candidate_path = (REPOSITORY_ROOT / candidate_result).resolve()
                        candidate_relative = candidate_path.relative_to(REPOSITORY_ROOT).as_posix()
                        if not candidate_relative.startswith("logs/tdd-adapter/"):
                            raise ValueError("candidate evidence path must stay in logs/tdd-adapter")
                        candidate = strict_load(candidate_path)
                        if slice_id == "RMAP-S6":
                            from evidence_guards import validate_candidate_document
                            slice_findings.extend(validate_candidate_document(PLAN_ROOT, candidate_relative, candidate, current, stage_documents))
                        else:
                            review_dir = (REPOSITORY_ROOT / str(bootstrap_run)).resolve()
                            review_relative = review_dir.relative_to(REPOSITORY_ROOT).as_posix()
                            if not review_relative.startswith("logs/ci/"):
                                raise ValueError("Bootstrap evidence path must stay in logs/ci")
                            candidate_ref_path = (REPOSITORY_ROOT / str(candidate_ref)).resolve()
                            candidate_ref_relative = candidate_ref_path.relative_to(REPOSITORY_ROOT).as_posix()
                            if not candidate_ref_relative.startswith("logs/tdd-adapter/"):
                                raise ValueError("candidate reference must stay in logs/tdd-adapter")
                            documents = [strict_load(review_dir / "finalized-run-validation.json"), strict_load(review_dir / "review-input.json"), strict_load(review_dir / "review-gate-result.json"), strict_load(review_dir / "review-dispositions.json")]
                            candidate_ref_document = strict_load(candidate_ref_path)
                            slice_findings.extend(validate_candidate_review_documents(PLAN_ROOT, candidate_relative, candidate, *documents, current, stage_documents, review_dir, candidate_ref_document, candidate_ref_relative))
                    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
                        slice_findings.append({"rule_id": "RMAP-REVIEW-EVIDENCE-BINDING", "target": slice_id, "message": str(exc)})
            slice_check["status"] = "pass" if not slice_findings else "fail"
        checks.append(slice_check)
        findings.extend(slice_findings)
    elif predicate not in {"plan-ready", "plan-repair-verified"}:
        findings.append({
            "rule_id": "RMAP-AUTH-EVIDENCE-MISSING",
            "target": predicate,
            "message": "implementation-time evidence is not present during plan creation",
        })
        checks.append({"rule_id": "RMAP-AUTH-RUNTIME-EVIDENCE", "status": "fail", "evidence": ["plan creation has no implementation evidence"]})
    test_check, test_findings = run_unit_tests()
    checks.append(test_check)
    findings.extend(test_findings)
    current_snapshot = validation_snapshot()
    if current_snapshot != validated_snapshot:
        findings.append({"rule_id": "RMAP-HASH-VALIDATION-DRIFT", "target": "validation-run", "message": "plan, source, or validator changed during validation"})
        checks.append({"rule_id": "RMAP-HASH-VALIDATION-DRIFT", "status": "fail", "evidence": ["pre/post validation snapshots differ"]})
    status_override = "blocked" if predicate in blocked_predicates and not [item for item in findings if item["rule_id"] != "RMAP-REVIEW-MANUAL-PAUSE"] else None
    result = build_result(predicate, checks, findings, validated_snapshot, current_snapshot, status_override)
    return result, 0 if result["status"] == "pass" else 1


def run_fixture(fixture_id: str) -> tuple[dict[str, Any], int]:
    data, load_findings = load_machine(PLAN_ROOT)
    protocol_ids = {item.get("id") for item in data.get("protocol_fixtures", {}).get("cases", []) if isinstance(item, dict)}
    findings = load_findings or (evaluate_protocol_fixture(PLAN_ROOT, fixture_id, data["protocol_fixtures"]) if fixture_id in protocol_ids else evaluate_fixture(PLAN_ROOT, fixture_id, data))
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
    parser.add_argument("--candidate-ref")
    parser.add_argument("--bootstrap-run")
    parser.add_argument("--run-dir")
    parser.add_argument("--red-result")
    parser.add_argument("--green-result")
    parser.add_argument("--refactor-result")
    parser.add_argument("--output")
    args = parser.parse_args()
    result, exit_code = run_fixture(args.fixture) if args.fixture else run_predicate(args.predicate, args.slice_id, args.candidate_result, args.candidate_ref, args.bootstrap_run, args.run_dir, args.red_result, args.green_result, args.refactor_result)
    write_output(args.output, result)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
