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
from contract_guards import contained_file, schema_error
from fixture_checks import evaluate_fixture, validate_fixture_suite
from candidate_diff_guards import validate_candidate_fixture_suite
from protocol_guards import evaluate_protocol_fixture
from evidence_guards import validate_candidate_review_documents
from slice_guards import validate_slice_outputs
from validation_result_guards import (
    build_result as build_validation_result,
    validate_authorizing_result as validate_result_guard,
    value_hash as _value_hash,
)
from rmap_checks import (
    PREDICATE_AUTHORITY,
    VALIDATOR_VERSION,
    candidate_hash,
    load_machine,
    sha256_file,
    validate_plan_state,
    validate_static,
)
PLAN_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLAN_ROOT.parents[1]
UNIT_TEST_TIMEOUT_SECONDS = 300
def validator_identity() -> str:
    digest = hashlib.sha256()
    names = ["validate_all.py", "rmap_checks.py", "contract_guards.py", "authority_guards.py", "review_reentry_environment.py", "artifact_proof_guards.py", "artifact_proof_verdicts.py", "artifact_proof_inventory_support.py", "validation_result_guards.py", "evidence_guards.py", "candidate_diff_guards.py", "candidate_lineage_guards.py", "current_state_guards.py", "shadow_guards.py", "source_guards.py", "slice_guards.py", "fixture_checks.py", "protocol_guards.py", "protocol_validation_guards.py", "protocol_fixture_support.py", "protocol_fixture_cases.py", "protocol_fixture_mutations.py", "protocol_artifact_guards.py", "attempt_lineage_guards.py"]
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
    try:
        result = subprocess.run(
            command,
            cwd=REPOSITORY_ROOT,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=UNIT_TEST_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        check = {
            "rule_id": "RMAP-UNIT-TESTS",
            "status": "fail",
            "evidence": [f"timeout_seconds={UNIT_TEST_TIMEOUT_SECONDS}"],
        }
        return check, [{
            "rule_id": "RMAP-UNIT-TESTS",
            "target": "tools/tests",
            "message": f"unit tests exceeded timeout of {UNIT_TEST_TIMEOUT_SECONDS} seconds",
        }]
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
    validator = validator_identity()
    return {
        "candidate_hash": candidate_hash(PLAN_ROOT),
        "source_hash": sha256_file(REPOSITORY_ROOT / "agentbuild.txt"),
        "validator_version": validator,
        "predicate_input_root": candidate_hash(PLAN_ROOT),
        "closure_definition_hash": sha256_file(PLAN_ROOT / "schemas" / "predicate-artifact-closure.v1.json"),
        "authority_root": sha256_file(PLAN_ROOT / "schemas" / "authority-manifest.v1.json"),
        "validator_root": "sha256:" + validator.rsplit("sha256:", 1)[1],
    }

def validate_authorizing_result(result: dict[str, Any], current: dict[str, str], runtime_evidence_root: str | None = None, predecessor_result: dict[str, Any] | None = None) -> list[dict[str, str]]:
    return validate_result_guard(
        result, current, PREDICATE_AUTHORITY, all_exclusions(), runtime_evidence_root,
        predecessor_result, strict_load(PLAN_ROOT / "schemas" / "validation-result.v1.schema.json"),
    )


def build_result(predicate: str, checks: list[dict[str, Any]], findings: list[dict[str, str]], validated: dict[str, str], current: dict[str, str], status_override: str | None = None, capabilities: dict[str, bool] | None = None, runtime_evidence_root: str | None = None, predecessor_result: dict[str, Any] | None = None) -> dict[str, Any]:
    return build_validation_result(
        PLAN_ROOT, predicate, checks, findings, validated, current,
        PREDICATE_AUTHORITY, all_exclusions(), strict_load,
        status_override, capabilities, runtime_evidence_root, predecessor_result,
    )


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


def run_predicate(predicate: str, slice_id: str | None = None, candidate_result: str | None = None, candidate_ref: str | None = None, bootstrap_run: str | None = None, run_dir: str | None = None, red_result: str | None = None, green_result: str | None = None, refactor_result: str | None = None, predecessor_result_path: str | None = None) -> tuple[dict[str, Any], int]:
    predecessor_path = contained_file(REPOSITORY_ROOT, predecessor_result_path) if predecessor_result_path else None
    if predecessor_result_path and predecessor_path is None:
        raise ValueError("predecessor result must be a repository-contained file")
    predecessor_result = strict_load(predecessor_path) if predecessor_path else None
    runtime_evidence_root = _value_hash({
        "slice_id": slice_id,
        "candidate_result": candidate_result,
        "candidate_ref": candidate_ref,
        "bootstrap_run": bootstrap_run,
        "run_dir": run_dir,
        "red_result": red_result,
        "green_result": green_result,
        "refactor_result": refactor_result,
        "predecessor_result_hash": _value_hash(predecessor_result) if predecessor_result else None,
    })
    validated_snapshot = validation_snapshot()
    checks, findings, data = validate_static(PLAN_ROOT)
    fixture_findings = validate_fixture_suite(PLAN_ROOT, data) if data else []
    fixture_findings.extend(validate_candidate_fixture_suite(PLAN_ROOT) if data else [])
    findings.extend(fixture_findings)
    checks.append({"rule_id": "RMAP-FIXTURES", "status": "pass" if not fixture_findings else "fail", "evidence": ["positive, negative, boundary, stale, and mutation cases"]})
    reentry_authorized = data.get("review_reentry", {}).get("state") == "reentry_authorized"
    declared_review_blocks = set(data.get("review_blocker", {}).get("blocks_predicates", []))
    review_targeted = predicate == "implementation-accepted" and predicate in declared_review_blocks
    if review_targeted:
        reentry_findings = validate_plan_state(data["state"], data["review_blocker"], data["review_reentry"])
        findings.extend(reentry_findings)
        checks.append({
            "rule_id": "RMAP-REVIEW-REENTRY",
            "status": "pass" if not reentry_findings else "fail",
            "evidence": ["successor policy and semantic closure independently recomputed"],
        })
        reentry_authorized = reentry_authorized and not reentry_findings
    review_blocked_predicates = set() if reentry_authorized else declared_review_blocks & {"implementation-accepted"}
    identity_blockers = [
        item for item in data.get("state", {}).get("open_blockers", [])
        if isinstance(item, dict) and item.get("blocker_id") == "RMAP-BLOCK-PROTECTED-VERIFIER-IDENTITY"
    ]
    identity_blocked_predicates = {
        item for blocker in identity_blockers for item in blocker.get("blocks_predicates", [])
        if isinstance(item, str)
    }
    blocked_predicates = review_blocked_predicates | identity_blocked_predicates
    if predicate in review_blocked_predicates:
        findings.append({"rule_id": "RMAP-REVIEW-MANUAL-PAUSE", "target": predicate, "message": "Round 3 manual pause requires a new review policy decision"})
        checks.append({"rule_id": "RMAP-REVIEW-MANUAL-PAUSE", "status": "blocked", "evidence": [data.get("review_blocker", {}).get("review_id", "missing review id")]})
    if predicate in identity_blocked_predicates:
        findings.append({"rule_id": "RMAP-PROTECTED-VERIFIER-IDENTITY", "target": predicate, "message": "protected handoff or release requires an independent execution identity or a trusted signed verification envelope"})
        checks.append({"rule_id": "RMAP-PROTECTED-VERIFIER-IDENTITY", "status": "blocked", "evidence": [identity_blockers[0].get("current_verifier", "missing verifier identity")]})
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
                        if slice_id == "RMAP-S6":
                            from candidate_diff_guards import validate_candidate_diff
                            evidence_dir = candidate_path.parent
                            manifest_path, lineage_path, test_path = (evidence_dir / name for name in ("changed-files.json", "candidate-lineage-manifest.json", "test-diff.patch"))
                            slice_findings.extend(validate_candidate_diff(
                                PLAN_ROOT, REPOSITORY_ROOT, data["contract"], strict_load(manifest_path),
                                manifest_path.relative_to(REPOSITORY_ROOT).as_posix(), test_path.read_bytes(),
                                strict_load(lineage_path), current, evidence_dir.name,
                            ))
                        else:
                            candidate = strict_load(candidate_path)
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
    blocking_rules = {"RMAP-REVIEW-MANUAL-PAUSE", "RMAP-PROTECTED-VERIFIER-IDENTITY"}
    status_override = "blocked" if predicate in blocked_predicates and not [item for item in findings if item["rule_id"] not in blocking_rules] else None
    derived_capabilities = {name: False for name in ("common_schema_skill_owned", "adapter_operational", "old_plan_backfill_complete", "implementation_accepted", "release_ready")}
    if not findings and status_override is None and slice_id:
        order = {f"RMAP-S{index}": index for index in range(8)}
        for name, rule in data.get("state", {}).get("capability_projection", {}).get("capabilities", {}).items():
            first_slice = rule.get("first_slice") if isinstance(rule, dict) else None
            if first_slice in order and order[slice_id] >= order[first_slice]:
                derived_capabilities[name] = True
    result = build_result(
        predicate, checks, findings, validated_snapshot, current_snapshot,
        status_override, derived_capabilities, runtime_evidence_root, predecessor_result,
    )
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
        "capabilities": {name: False for name in ("common_schema_skill_owned", "adapter_operational", "old_plan_backfill_complete", "implementation_accepted", "release_ready")},
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
    for option in ("--red-result", "--green-result", "--refactor-result", "--predecessor-result"):
        parser.add_argument(option)
    parser.add_argument("--output")
    args = parser.parse_args()
    result, exit_code = run_fixture(args.fixture) if args.fixture else run_predicate(args.predicate, args.slice_id, args.candidate_result, args.candidate_ref, args.bootstrap_run, args.run_dir, args.red_result, args.green_result, args.refactor_result, args.predecessor_result)
    write_output(args.output, result)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
