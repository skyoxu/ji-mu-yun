from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_SUITE = Path("knowledge/evaluation/repository-knowledge-query-suite.v1.json")
DEFAULT_CATALOG = Path("knowledge/catalogs/repository-knowledge-catalog.v2.json")
DEFAULT_POLICIES = Path("knowledge/policies/consumer-policies.v2.json")
DEFAULT_PROJECTIONS = Path("knowledge/projections/consumer-projections.v1.json")
LOCATOR = Path("scripts/python/knowledge_locator.py")
EXPECTED_CATEGORIES = ("adr", "execution-plan", "architecture", "toolchain")
FORBIDDEN_RESPONSE_KEYS = {"answer", "content", "facts", "response", "summary", "synthesis"}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _forbidden_response_paths(value: Any, prefix: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{prefix}.{key}"
            if key.casefold() in FORBIDDEN_RESPONSE_KEYS:
                found.append(child_path)
            found.extend(_forbidden_response_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_forbidden_response_paths(child, f"{prefix}[{index}]"))
    return found


def _git(repository_root: Path, *args: str, input_bytes: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(repository_root), *args],
        input=input_bytes,
        capture_output=True,
        check=False,
    )


def _main_blob(repository_root: Path, commit: str, path: str) -> bytes:
    completed = _git(repository_root, "show", f"{commit}:{path}")
    if completed.returncode:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"cannot read main blob {path}: {detail}")
    return completed.stdout


def _validate_suite(suite: dict[str, Any]) -> None:
    if suite.get("schema_version") != "jimuyun.repository-knowledge-query-suite.v1":
        raise ValueError("unsupported query suite schema")
    categories = suite.get("categories")
    if categories != list(EXPECTED_CATEGORIES):
        raise ValueError("query suite categories must be the four canonical categories in order")
    minimum = suite.get("minimum_positive_cases_per_category")
    if not isinstance(minimum, int) or minimum < 25:
        raise ValueError("minimum_positive_cases_per_category must be at least 25")
    cases = suite.get("cases")
    if not isinstance(cases, list):
        raise ValueError("query suite cases must be an array")
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError(f"query suite case {index} must be an object")
        required = {"case_id", "category", "consumer", "query", "expected"}
        if not required.issubset(case):
            raise ValueError(f"query suite case {index} is incomplete")
        if case["category"] not in EXPECTED_CATEGORIES:
            raise ValueError(f"query suite case {case['case_id']} has an invalid category")
        if case["consumer"] not in {"vdd", "bootstrap", "refactor-acceptance"}:
            raise ValueError(f"query suite case {case['case_id']} has an invalid consumer")
        if not isinstance(case["query"], str) or not case["query"].strip():
            raise ValueError(f"query suite case {case['case_id']} has an empty query")
        expected = case["expected"]
        if not isinstance(expected, dict):
            raise ValueError(f"query suite case {case['case_id']} has an incomplete expectation")
        result_status = expected.get("result_status", "matched")
        if result_status == "matched":
            expected_fields = {"module_id", "max_rank", "kind", "status", "path", "source_terms"}
            if not expected_fields.issubset(expected):
                raise ValueError(f"query suite case {case['case_id']} has an incomplete matched expectation")
            if not isinstance(expected["source_terms"], list) or not expected["source_terms"]:
                raise ValueError(f"query suite case {case['case_id']} has no source terms")
        elif result_status == "insufficient_match":
            if set(expected) != {"result_status"}:
                raise ValueError(f"query suite case {case['case_id']} has an invalid negative expectation")
        else:
            raise ValueError(f"query suite case {case['case_id']} has an invalid result status")
    identifiers = [case.get("case_id") for case in cases if isinstance(case, dict)]
    if len(identifiers) != len(cases) or len(set(identifiers)) != len(identifiers):
        raise ValueError("query suite case_id values must be present and unique")
    counts = Counter(
        case.get("category")
        for case in cases
        if case.get("expected", {}).get("result_status", "matched") == "matched"
    )
    missing = [category for category in EXPECTED_CATEGORIES if counts[category] < minimum]
    if missing:
        raise ValueError(f"positive query suite category coverage is below {minimum}: {', '.join(missing)}")


def _run_locator(
    repository_root: Path,
    request: dict[str, Any],
    catalog_path: Path,
    policies_path: Path,
    projections_path: Path,
) -> tuple[int, bytes, str]:
    completed = subprocess.run(
        [
            sys.executable,
            str(repository_root / LOCATOR),
            "--repository-root",
            str(repository_root),
            "--catalog",
            str(catalog_path),
            "--policies",
            str(policies_path),
            "--projections",
            str(projections_path),
            "--allow-unpublished-inputs",
        ],
        cwd=repository_root,
        input=(_canonical_json(request) + "\n").encode("utf-8"),
        capture_output=True,
        check=False,
    )
    return completed.returncode, completed.stdout, completed.stderr.decode("utf-8", errors="replace").strip()


def _check_hashes_and_terms(
    repository_root: Path,
    commit: str,
    candidates: list[dict[str, Any]],
    expected_module_id: str,
    source_terms: list[str],
) -> tuple[list[str], int, dict[str, list[dict[str, Any]]]]:
    failures: list[str] = []
    verified = 0
    evidence_locations: dict[str, list[dict[str, Any]]] = {term: [] for term in source_terms}
    blob_cache: dict[str, bytes] = {}
    expected_primary_path: str | None = None
    verified_bound_resource = False
    for candidate in candidates:
        read_set = candidate.get("read_set")
        if not isinstance(read_set, list) or not read_set:
            failures.append(f"candidate {candidate.get('module_id')} has no read_set")
            continue
        for item in read_set:
            path = item.get("path") if isinstance(item, dict) else None
            digest = item.get("source_sha256") if isinstance(item, dict) else None
            if not isinstance(path, str) or not isinstance(digest, str):
                failures.append(f"candidate {candidate.get('module_id')} has an invalid read_set item")
                continue
            if path.replace("\\", "/").startswith("docs/migration/"):
                failures.append(f"migration path leaked into read_set: {path}")
                continue
            try:
                blob = blob_cache.setdefault(path, _main_blob(repository_root, commit, path))
            except ValueError as error:
                failures.append(str(error))
                continue
            if hashlib.sha256(blob).hexdigest() != digest:
                failures.append(f"source hash mismatch: {path}")
            else:
                verified += 1
                if candidate.get("module_id") == expected_module_id and item.get("role") != "primary":
                    verified_bound_resource = True
            if candidate.get("module_id") == expected_module_id:
                if item.get("role") == "primary":
                    expected_primary_path = path
                decoded_blob = blob.decode("utf-8", errors="replace")
                for term in source_terms:
                    for line_number, line in enumerate(decoded_blob.splitlines(), 1):
                        if term.casefold() in line.casefold():
                            evidence_locations[term].append({"path": path, "line": line_number})
        candidate_path = candidate.get("path")
        if isinstance(candidate_path, str) and candidate_path.replace("\\", "/").startswith("docs/migration/"):
            failures.append(f"migration path leaked into candidates: {candidate_path}")
    for term in source_terms:
        if not evidence_locations[term]:
            failures.append(f"expected source term not found: {term}")
    body_evidence = verified_bound_resource or any(
        location["path"] != expected_primary_path or location["line"] > 3
        for locations in evidence_locations.values()
        for location in locations
    )
    if not body_evidence:
        failures.append("semantic evidence is title-only")
    return failures, verified, evidence_locations


def _consumption_decisions(
    case_id: str,
    candidates: list[dict[str, Any]],
    expected_module_id: str,
    semantic_evidence_valid: bool,
) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    for candidate in candidates:
        accepted = candidate.get("module_id") == expected_module_id and semantic_evidence_valid
        decisions.append(
            {
                "owner": "adapter",
                "candidate": {
                    "module_id": candidate.get("module_id"),
                    "path": candidate.get("path"),
                    "source_sha256": candidate.get("source_sha256"),
                },
                "decision": "accepted" if accepted else "rejected",
                "satisfies": [case_id] if accepted else [],
                "rejection_reason": None if accepted else "insufficient_specificity",
            }
        )
    return decisions


def _protocol_request(snapshot: dict[str, Any], *, request_id: str, policy_revision: str) -> dict[str, Any]:
    return {
        "schema_version": "jimuyun.knowledge-locator-request.v1",
        "request_id": request_id,
        "consumer": "vdd",
        "query": "repository knowledge authority",
        "snapshot": {"ref": snapshot["ref"], "commit": snapshot["commit"]},
        "policy_revision": policy_revision,
    }


def evaluate(
    repository_root: Path,
    suite_path: Path,
    catalog_path: Path,
    policies_path: Path,
    projections_path: Path,
    repeat: int,
    categories: set[str] | None = None,
    case_ids: set[str] | None = None,
    allow_ancestor_snapshot: bool = False,
) -> dict[str, Any]:
    suite = _read_json(suite_path)
    _validate_suite(suite)
    catalog = _read_json(catalog_path)
    policies = _read_json(policies_path)
    projections = _read_json(projections_path)
    snapshot = catalog.get("source_snapshot")
    if not isinstance(snapshot, dict) or snapshot.get("ref") != "refs/heads/main":
        raise ValueError("catalog has no valid main source snapshot")
    commit = snapshot.get("commit")
    if not isinstance(commit, str):
        raise ValueError("catalog source snapshot has no commit")
    current_main = _git(repository_root, "rev-parse", "refs/heads/main")
    current_commit = current_main.stdout.decode("ascii").strip() if not current_main.returncode else ""
    if current_commit != commit and allow_ancestor_snapshot:
        ancestry = _git(repository_root, "merge-base", "--is-ancestor", commit, current_commit)
        if ancestry.returncode:
            raise ValueError("catalog source snapshot does not match refs/heads/main")
        for item in snapshot.get("sources", []):
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                raise ValueError("catalog source snapshot does not match refs/heads/main")
            if hashlib.sha256(_main_blob(repository_root, current_commit, item["path"])).hexdigest() != item.get("sha256"):
                raise ValueError("catalog source snapshot does not match refs/heads/main")
    elif current_commit != commit:
        raise ValueError("catalog source snapshot does not match refs/heads/main")
    # The Locator binds every request to the catalog's source snapshot. The
    # ancestry and complete source-byte checks above prove that the snapshot
    # remains a valid projection of current main after publication is committed.
    request_snapshot = {"ref": "refs/heads/main", "commit": commit}
    policy_revision = suite.get("policy_revision")
    if policies.get("policy_revision") != policy_revision:
        raise ValueError("suite and policy revisions differ")
    projection_by_consumer = {
        item.get("consumer"): set(item.get("eligible_module_ids", []))
        for item in projections.get("projections", [])
        if isinstance(item, dict)
    }
    protocol_results: list[dict[str, Any]] = []

    def record_protocol(name: str, failures: list[str]) -> None:
        protocol_results.append({"check": name, "status": "passed" if not failures else "failed", "failures": failures})

    catalog_failures: list[str] = []
    if catalog.get("authority_class") != "derived_cache" or catalog.get("instruction_authority") is not False or catalog.get("may_override_source") is not False:
        catalog_failures.append("catalog authority is not derived_cache-only")
    for module in catalog.get("modules", []):
        if module.get("lifecycle") != "repository-source" or module.get("enforcement_level") != "E1":
            catalog_failures.append(f"module exceeds repository-source E1: {module.get('module_id')}")
        path = str(module.get("source_path", "")).replace("\\", "/")
        if path.startswith("docs/migration/"):
            catalog_failures.append(f"migration module leaked into catalog: {path}")
    if any(str(item.get("path", "")).replace("\\", "/").startswith("docs/migration/") for item in snapshot.get("sources", [])):
        catalog_failures.append("migration source leaked into snapshot")
    record_protocol("derived-cache-e1-and-migration-boundary", catalog_failures)
    quick_dev_cases = [case["case_id"] for case in suite["cases"] if case.get("consumer") == "quick-dev"]
    record_protocol("quick-dev-does-not-query", [] if not quick_dev_cases else [f"quick-dev query cases present: {quick_dev_cases}"])

    for check_name, protocol_request in (
        (
            "stale-snapshot-blocked",
            {
                **_protocol_request(request_snapshot, request_id="knowledge-query-protocol:stale-snapshot", policy_revision=policy_revision),
                "snapshot": {"ref": request_snapshot["ref"], "commit": "0" * 40},
            },
        ),
        (
            "policy-drift-blocked",
            _protocol_request(request_snapshot, request_id="knowledge-query-protocol:policy-drift", policy_revision="unknown-policy-revision"),
        ),
    ):
        protocol_runs = [
            _run_locator(repository_root, protocol_request, catalog_path, policies_path, projections_path)
            for _ in range(repeat)
        ]
        protocol_failures: list[str] = []
        if any(code != 0 for code, _, _ in protocol_runs):
            protocol_failures.append("protocol Locator invocation failed")
        if any(stdout != protocol_runs[0][1] for _, stdout, _ in protocol_runs[1:]):
            protocol_failures.append("protocol Locator output is not deterministic")
        try:
            protocol_response = json.loads(protocol_runs[0][1].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            protocol_response = {}
            protocol_failures.append("protocol Locator output is not UTF-8 JSON")
        if protocol_response.get("status") != "blocked" or protocol_response.get("candidates") != []:
            protocol_failures.append("protocol drift did not fail closed")
        if _forbidden_response_paths(protocol_response):
            protocol_failures.append("protocol response contains generated-answer fields")
        record_protocol(check_name, protocol_failures)
    selected_cases = [
        case
        for case in suite["cases"]
        if (categories is None or case.get("category") in categories)
        and (case_ids is None or case.get("case_id") in case_ids)
    ]
    if not selected_cases:
        raise ValueError("query selection is empty")
    results: list[dict[str, Any]] = []
    for case in selected_cases:
        request = {
            "schema_version": "jimuyun.knowledge-locator-request.v1",
            "request_id": f"knowledge-query-eval:{case['case_id']}",
            "consumer": case["consumer"],
            "query": case["query"],
            "snapshot": request_snapshot,
            "policy_revision": policy_revision,
        }
        runs = [
            _run_locator(repository_root, request, catalog_path, policies_path, projections_path)
            for _ in range(repeat)
        ]
        failures: list[str] = []
        if any(code != 0 for code, _, _ in runs):
            failures.extend(f"locator exit={code}: {stderr}" for code, _, stderr in runs if code != 0)
        if any(stdout != runs[0][1] for _, stdout, _ in runs[1:]):
            failures.append("locator stdout is not byte-deterministic")
        try:
            response = json.loads(runs[0][1].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            response = {}
            failures.append(f"locator stdout is not valid UTF-8 JSON: {error}")
        if not isinstance(response, dict):
            response = {}
            failures.append("locator response is not an object")
        forbidden = _forbidden_response_paths(response)
        if forbidden:
            failures.append(f"generated-answer fields present: {', '.join(sorted(forbidden))}")
        if response.get("schema_version") != "jimuyun.knowledge-locator-result.v1":
            failures.append("unexpected locator result schema")
        if response.get("request_id") != request["request_id"]:
            failures.append("request_id binding mismatch")
        if response.get("snapshot") != request["snapshot"]:
            failures.append("snapshot binding mismatch")
        if response.get("source_snapshot_id") != snapshot.get("snapshot_id"):
            failures.append("source_snapshot_id binding mismatch")
        if response.get("policy_revision") != policy_revision:
            failures.append("policy revision binding mismatch")
        candidates = response.get("candidates")
        if not isinstance(candidates, list):
            candidates = []
            failures.append("candidates is not an array")
        expected = case["expected"]
        expected_result_status = expected.get("result_status", "matched")
        actual_result_status = response.get("status")
        if actual_result_status != expected_result_status:
            failures.append(f"expected {expected_result_status} status, got {actual_result_status}")
        rank: int | None = None
        verified_read_set = 0
        evidence_locations: dict[str, list[dict[str, Any]]] = {}
        decisions: list[dict[str, Any]] = []
        expected_module_id = expected.get("module_id")
        if expected_result_status == "insufficient_match":
            if candidates:
                failures.append("negative query returned candidates")
        else:
            ranks = {
                candidate.get("module_id"): index
                for index, candidate in enumerate(candidates, 1)
                if isinstance(candidate, dict)
            }
            rank = ranks.get(expected_module_id)
            if rank is None:
                failures.append(f"expected module missing: {expected_module_id}")
                matched_candidate: dict[str, Any] = {}
            else:
                matched_candidate = candidates[rank - 1]
                if rank > expected["max_rank"]:
                    failures.append(f"expected module rank {rank} exceeds {expected['max_rank']}")
            for field in ("kind", "status"):
                if matched_candidate.get(field) != expected[field]:
                    failures.append(f"expected {field}={expected[field]}, got {matched_candidate.get(field)}")
            if matched_candidate.get("path") != expected["path"]:
                failures.append(f"expected path={expected['path']}, got {matched_candidate.get('path')}")
            eligible = projection_by_consumer.get(case["consumer"], set())
            if expected_module_id not in eligible:
                failures.append("expected module is absent from consumer projection")
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    failures.append("candidate is not an object")
                    continue
                module_id = candidate.get("module_id")
                if module_id not in eligible:
                    failures.append(f"candidate is absent from consumer projection: {module_id}")
                if candidate.get("lifecycle") != "repository-source" or candidate.get("enforcement_level") != "E1":
                    failures.append(f"candidate exceeds repository-source E1: {module_id}")
                if candidate.get("primary_domain") not in {"toolchain", "phase", "workspace", "marketplace"}:
                    failures.append(f"candidate has an invalid primary domain: {module_id}")
                visibility = candidate.get("visibility")
                if not isinstance(visibility, dict) or set(visibility) != {"toolchain", "phase", "workspace", "marketplace"}:
                    failures.append(f"candidate has an invalid four-domain visibility map: {module_id}")
                confidence = candidate.get("rank_evidence", {}).get("confidence")
                if confidence not in {"high", "medium"}:
                    failures.append(f"matched candidate has invalid confidence: {module_id}")
                read_set = candidate.get("read_set")
                primary = read_set[0] if isinstance(read_set, list) and read_set else None
                if not isinstance(primary, dict) or primary.get("role") != "primary":
                    failures.append(f"candidate has no primary read-set binding: {module_id}")
                elif candidate.get("path") != primary.get("path") or candidate.get("source_sha256") != primary.get("source_sha256"):
                    failures.append(f"candidate primary source binding mismatch: {module_id}")
            hash_failures, verified_read_set, evidence_locations = _check_hashes_and_terms(
                repository_root,
                commit,
                [item for item in candidates if isinstance(item, dict)],
                expected_module_id,
                expected["source_terms"],
            )
            failures.extend(hash_failures)
            decisions = _consumption_decisions(
                case["case_id"],
                [item for item in candidates if isinstance(item, dict)],
                expected_module_id,
                not hash_failures,
            )
            if len(decisions) != len(candidates):
                failures.append("consumption decision coverage is incomplete")
            accepted = [decision for decision in decisions if decision["decision"] == "accepted"]
            if len(accepted) != 1 or accepted[0]["candidate"]["module_id"] != expected_module_id:
                failures.append("expected candidate was not uniquely accepted after reread")
            for decision in decisions:
                if decision["owner"] != "adapter":
                    failures.append("consumption decision owner is not adapter")
                if decision["decision"] == "accepted" and (not decision["satisfies"] or decision["rejection_reason"] is not None):
                    failures.append("accepted consumption decision is malformed")
                if decision["decision"] == "rejected" and (decision["satisfies"] or decision["rejection_reason"] not in {"wrong_domain", "insufficient_specificity", "authority_conflict", "duplicate"}):
                    failures.append("rejected consumption decision is malformed")
        results.append(
            {
                "case_id": case["case_id"],
                "category": case["category"],
                "consumer": case["consumer"],
                "query": case["query"],
                "expected_result_status": expected_result_status,
                "actual_result_status": actual_result_status,
                "expected_module_id": expected_module_id,
                "actual_rank": rank,
                "candidate_count": len(candidates),
                "verified_read_set_items": verified_read_set,
                "request_sha256": "sha256:" + hashlib.sha256((_canonical_json(request) + "\n").encode("utf-8")).hexdigest(),
                "result_sha256": "sha256:" + hashlib.sha256(runs[0][1]).hexdigest(),
                "evidence_locations": evidence_locations,
                "consumption_decisions": decisions,
                "deterministic_runs": repeat,
                "status": "passed" if not failures else "failed",
                "failures": failures,
            }
        )
    category_summary: dict[str, Any] = {}
    for category in EXPECTED_CATEGORIES:
        category_results = [item for item in results if item["category"] == category]
        if not category_results:
            continue
        passed = sum(item["status"] == "passed" for item in category_results)
        category_summary[category] = {
            "total": len(category_results),
            "passed": passed,
            "failed": len(category_results) - passed,
            "matched_cases": sum(item["expected_result_status"] == "matched" for item in category_results),
            "insufficient_match_cases": sum(item["expected_result_status"] == "insufficient_match" for item in category_results),
        }
    passed = sum(item["status"] == "passed" for item in results)
    protocol_passed = sum(item["status"] == "passed" for item in protocol_results)
    overall_passed = passed == len(results) and protocol_passed == len(protocol_results)
    return {
        "schema_version": "jimuyun.repository-knowledge-query-report.v1",
        "suite_path": suite_path.relative_to(repository_root).as_posix(),
        "snapshot": {"ref": snapshot["ref"], "commit": commit, "snapshot_id": snapshot.get("snapshot_id")},
        "policy_revision": policy_revision,
        "repeat": repeat,
        "protocol_results": protocol_results,
        "summary": {
            "status": "passed" if overall_passed else "failed",
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "protocol_total": len(protocol_results),
            "protocol_passed": protocol_passed,
            "protocol_failed": len(protocol_results) - protocol_passed,
        },
        "categories": category_summary,
        "results": results,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Evaluate real repository Knowledge Locator queries.")
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--policies", type=Path, default=DEFAULT_POLICIES)
    parser.add_argument("--projections", type=Path, default=DEFAULT_PROJECTIONS)
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--category", action="append", choices=EXPECTED_CATEGORIES)
    parser.add_argument("--case-id", action="append", help="Run one or more exact suite case IDs.")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be at least 1")
    root = args.repository_root.resolve()

    def rooted(path: Path) -> Path:
        return path if path.is_absolute() else root / path

    try:
        report = evaluate(
            root,
            rooted(args.suite),
            rooted(args.catalog),
            rooted(args.policies),
            rooted(args.projections),
            args.repeat,
            set(args.category) if args.category else None,
            set(args.case_id) if args.case_id else None,
            allow_ancestor_snapshot=True,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "blocked", "error": str(error)}, ensure_ascii=False, sort_keys=True))
        return 2
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = rooted(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded, encoding="utf-8", newline="\n")
    print(_canonical_json(report["summary"]))
    return 0 if report["summary"]["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
