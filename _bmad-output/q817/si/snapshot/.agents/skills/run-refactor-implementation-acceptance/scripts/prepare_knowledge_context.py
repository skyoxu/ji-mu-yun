"""Create a publication-bound Refactor Acceptance knowledge context."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
PYTHON_ROOT = REPOSITORY_ROOT / "scripts" / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from knowledge_context_validation import (  # noqa: E402
    canonical_hash,
    refresh_context_read_set,
    validate_catalog_freshness,
    validate_context,
    validate_worktree_sources,
)


def _accepted(values: list[str]) -> dict[str, list[str]]:
    accepted: dict[str, list[str]] = {}
    for value in values:
        path, separator, modules = value.partition("=")
        selected = [item for item in modules.split(",") if item]
        if not separator or not path or not selected:
            raise ValueError("--accept must be candidate-path=module[,module]")
        accepted[path] = selected
    return accepted


def _policy_revision(root: Path) -> str:
    policy = json.loads((root / "knowledge/policies/consumer-policies.v2.json").read_text(encoding="utf-8"))
    revision = policy.get("policy_revision")
    if not isinstance(revision, str) or not revision:
        raise SystemExit("canonical consumer policy revision is invalid")
    return revision


def _target_plan_path(root: Path, raw: Path) -> Path:
    if raw.is_absolute() or ".." in raw.parts:
        raise ValueError("target plan must be repository-relative")
    target = (root / raw).resolve()
    relative = target.relative_to(root)
    if len(relative.parts) != 2 or relative.parts[0] != "execution-plans":
        raise ValueError("target plan must name one direct execution-plans directory")
    return target


def _output_path(root: Path, raw: Path, target_plan: Path) -> Path:
    if raw.is_absolute() or ".." in raw.parts:
        raise ValueError("knowledge context output must be repository-relative")
    output = (root / raw).resolve()
    try:
        output.relative_to(target_plan)
    except ValueError as exc:
        raise ValueError("knowledge context output must stay inside the target execution-plan") from exc
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--max-candidates", type=int, default=12)
    parser.add_argument("--required-module", action="append", default=[])
    parser.add_argument("--accept", action="append", default=[])
    parser.add_argument("--target-plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.max_candidates <= 12:
        raise SystemExit("--max-candidates must be between 1 and 12")
    root = args.repository_root.resolve()
    try:
        target_plan = _target_plan_path(root, args.target_plan)
        output = _output_path(root, args.output, target_plan)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    catalog_path = root / "knowledge" / "catalogs" / "repository-knowledge-catalog.v2.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    snapshot = catalog.get("source_snapshot", {})
    request = {
        "schema_version": "jimuyun.knowledge-locator-request.v1",
        "request_id": args.request_id,
        "consumer": "refactor-acceptance",
        "query": args.query,
        "max_candidates": args.max_candidates,
        "snapshot": {"ref": snapshot.get("ref"), "commit": snapshot.get("commit")},
        "policy_revision": _policy_revision(root),
        # Catalog freshness affects retrieval coverage, not the integrity of a
        # Locator result whose complete source/read-set is independently bound.
        "allow_stale_catalog": True,
    }
    completed = subprocess.run(
        [
            sys.executable, "-B",
            str(root / "scripts" / "python" / "knowledge_locator.py"),
            "--repository-root", str(root),
            "--max-candidates", str(args.max_candidates),
            "--allow-stale-catalog",
        ],
        input=json.dumps(request, ensure_ascii=False),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise SystemExit(completed.stderr or "knowledge locator failed")
    result = json.loads(completed.stdout)
    accepted = _accepted(args.accept)
    returned_paths = {item.get("path") for item in result.get("candidates", []) if isinstance(item, dict)}
    if set(accepted) - returned_paths:
        raise SystemExit("--accept names a path absent from the Locator result")
    decisions = [
        {
            "owner": "adapter",
            "candidate": {"path": item.get("path"), "source_sha256": item.get("source_sha256")},
            "decision": "accepted" if item.get("path") in accepted else "rejected",
            "satisfies": accepted.get(item.get("path"), []),
            "rejection_reason": None if item.get("path") in accepted else "insufficient_specificity",
        }
        for item in result.get("candidates", [])
        if isinstance(item, dict)
    ]
    payload = {
        "schema_version": "jimuyun.knowledge-consumer-context.v1",
        "consumer": "refactor-acceptance",
        "locator_request": request,
        "locator_result": result,
        "required_modules": args.required_module,
        "decisions": decisions,
        "request_sha256": canonical_hash(request),
        "result_sha256": canonical_hash(result),
    }
    catalog_failure_code = validate_catalog_freshness(root)
    failure_code = validate_context(
        payload,
        repository_root=root,
        verify_catalog=True,
        verify_sources=True,
        expected_consumer="refactor-acceptance",
        require_selection=True,
    )
    if failure_code is None:
        failure_code = validate_worktree_sources(payload, root)
    if failure_code == "candidate_worktree_source_hash_mismatch":
        try:
            payload = refresh_context_read_set(payload, root)
        except (OSError, ValueError):
            # The original mismatch is the stable, fail-closed diagnosis when
            # the selected read-set cannot be safely refreshed.
            pass
        else:
            failure_code = validate_context(
                payload,
                repository_root=root,
                verify_catalog=True,
                verify_sources=True,
                expected_consumer="refactor-acceptance",
                require_selection=True,
            )
            if failure_code is None:
                failure_code = validate_worktree_sources(payload, root)
    knowledge_freshness = "degraded" if catalog_failure_code == "catalog_stale" else "current"
    payload["preflight"] = {
        "status": "blocked" if failure_code else "ready",
        "failure_code": failure_code,
        "knowledge_freshness": knowledge_freshness,
        "catalog_failure_code": "catalog_stale" if knowledge_freshness == "degraded" else None,
        "source_freshness": "refreshed" if payload.get("source_refresh") else "catalog_bound",
        "context_sha256": canonical_hash(payload),
    }
    if failure_code is not None:
        route = {
            "schema_version": "jimuyun.acceptance-knowledge-maintenance-route.v1",
            "status": "blocked",
            "failure_code": failure_code,
            "next_action": "knowledge-context-repair-required",
            "target_plan": target_plan.relative_to(root).as_posix(),
            "snapshot": request["snapshot"],
            "request_sha256": payload["request_sha256"],
            "result_sha256": payload["result_sha256"],
            "automatic_publication_allowed": False,
            "requires_explicit_maintainer_confirmation": False,
            "authorizes": [],
        }
        route_seed = canonical_hash(route).removeprefix("sha256:")
        route_output = target_plan / "knowledge-context-routes" / f"{route_seed}.json"
        route["route_output"] = route_output.relative_to(root).as_posix()
        route["route_sha256"] = canonical_hash(route)
        route_output.parent.mkdir(parents=True, exist_ok=True)
        try:
            with route_output.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(route, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        except FileExistsError:
            if json.loads(route_output.read_text(encoding="utf-8")) != route:
                raise SystemExit("knowledge maintenance route output is append-only")
        print(json.dumps(route, sort_keys=True))
        return 2
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    except FileExistsError as exc:
        raise SystemExit("knowledge context output is append-only") from exc
    print(json.dumps({"status": payload["preflight"]["status"], "output": str(output), "authorizes": []}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
