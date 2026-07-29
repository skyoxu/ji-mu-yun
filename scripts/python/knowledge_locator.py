from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from _knowledge_locator_core import (
    bind_result_to_request,
    catalog_source_snapshot,
    locate,
    require_fresh_catalog,
    verify_current_publication,
)


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _current_main_commit(repository_root: Path) -> str | None:
    current = subprocess.run(
        ["git", "-C", str(repository_root), "rev-parse", "refs/heads/main"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if current.returncode:
        return None
    commit = current.stdout.strip()
    return commit if len(commit) == 40 else None


def _main_source_hashes(
    repository_root: Path,
    catalog: dict[str, Any],
    current_commit: str | None = None,
) -> dict[str, str]:
    snapshot = catalog_source_snapshot(catalog)
    if snapshot is None:
        return {}
    current_commit = current_commit or _current_main_commit(repository_root)
    if current_commit is None:
        return {}
    ancestry = subprocess.run(
        ["git", "-C", str(repository_root), "merge-base", "--is-ancestor", snapshot["commit"], current_commit],
        capture_output=True,
        check=False,
    )
    if ancestry.returncode:
        return {}
    paths = [item.get("path") for item in snapshot["sources"] if isinstance(item, dict) and isinstance(item.get("path"), str)]
    if not paths:
        return {}
    request_bytes = "".join(f"{current_commit}:{path}\n" for path in paths).encode("utf-8")
    completed = subprocess.run(
        ["git", "-C", str(repository_root), "cat-file", "--batch"],
        input=request_bytes,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        return {}
    output = completed.stdout
    offset = 0
    hashes: dict[str, str] = {}
    for path in paths:
        newline = output.find(b"\n", offset)
        if newline < 0:
            return {}
        header = output[offset:newline].decode("ascii", errors="replace")
        offset = newline + 1
        parts = header.rsplit(" ", 2)
        if len(parts) != 3 or parts[1] != "blob" or not parts[2].isdigit():
            return {}
        size = int(parts[2])
        blob = output[offset : offset + size]
        offset += size
        if output[offset : offset + 1] != b"\n":
            return {}
        offset += 1
        hashes[path] = hashlib.sha256(blob).hexdigest()
    return hashes


def _policy_for(request: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any] | None:
    if request.get("policy_revision") != registry.get("policy_revision"):
        return None
    consumer = request.get("consumer")
    return next((item for item in registry.get("policies", []) if isinstance(item, dict) and item.get("consumer") == consumer), None)


def _projection_for(
    request: dict[str, Any],
    catalog: dict[str, Any],
    policies: dict[str, Any],
    projections: dict[str, Any] | None,
) -> set[str] | None:
    if not isinstance(catalog.get("modules"), list):
        return None
    if projections is None:
        raise ValueError("consumer_projection_missing")
    snapshot = catalog_source_snapshot(catalog)
    if (
        snapshot is None
        or projections.get("source_snapshot_id") != snapshot.get("snapshot_id")
        or projections.get("catalog_sha256") != _canonical_hash(catalog)
        or projections.get("policy_revision") != policies.get("policy_revision")
        or projections.get("policy_sha256") != _canonical_hash(policies)
    ):
        raise ValueError("consumer_projection_stale")
    projection = next(
        (
            item
            for item in projections.get("projections", [])
            if isinstance(item, dict) and item.get("consumer") == request.get("consumer")
        ),
        None,
    )
    if projection is None or not isinstance(projection.get("eligible_module_ids"), list):
        raise ValueError("consumer_projection_missing")
    return set(projection["eligible_module_ids"])


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=Path("knowledge/catalogs/repository-knowledge-catalog.v2.json"))
    parser.add_argument("--policies", type=Path)
    parser.add_argument("--projections", type=Path, default=Path("knowledge/projections/consumer-projections.v1.json"))
    parser.add_argument("--max-candidates", type=int, default=12)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--allow-unpublished-inputs", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    request = json.load(sys.stdin)
    repository_root = args.repository_root.resolve()

    def rooted(path: Path) -> Path:
        return path if path.is_absolute() else repository_root / path

    catalog_path = rooted(args.catalog)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    policy_path = args.policies
    if policy_path is None:
        revision = request.get("policy_revision")
        filename = "consumer-policies.v1.json" if revision == "knowledge-consumer-policies.v1" else "consumer-policies.v2.json"
        policy_path = Path("knowledge/policies") / filename
    policies = json.loads(rooted(policy_path).read_text(encoding="utf-8"))
    projection_document = None
    if isinstance(catalog.get("modules"), list):
        projection_document = json.loads(rooted(args.projections).read_text(encoding="utf-8"))
    snapshot = catalog_source_snapshot(catalog)
    current_main_commit = _current_main_commit(repository_root)
    fresh = require_fresh_catalog(catalog, _main_source_hashes(repository_root, catalog, current_main_commit))
    policy = _policy_for(request, policies)
    canonical_paths = (
        catalog_path == repository_root / "knowledge" / "catalogs" / "repository-knowledge-catalog.v2.json"
        and rooted(policy_path) == repository_root / "knowledge" / "policies" / "consumer-policies.v2.json"
        and rooted(args.projections) == repository_root / "knowledge" / "projections" / "consumer-projections.v1.json"
    )
    publication_valid = (
        args.allow_unpublished_inputs
        or not canonical_paths
        or verify_current_publication(
            repository_root,
            catalog_path=catalog_path,
            policy_path=rooted(policy_path),
            projections_path=rooted(args.projections),
        )
    )
    try:
        eligible_module_ids = _projection_for(request, catalog, policies, projection_document)
    except ValueError:
        eligible_module_ids = None
        projection_valid = False
    else:
        projection_valid = True
    if (
        snapshot is None
        # ADR-0050 permits a generation source commit to precede main only
        # while the complete source read-set still matches current main.
        # A published derived catalog is committed after its source snapshot.
        # Freshness is established by the complete read-set above, so require
        # the caller to bind that catalog snapshot rather than the later HEAD.
        or request.get("snapshot") != {"ref": snapshot["ref"], "commit": snapshot["commit"]}
        or fresh["status"] != "current"
        or policy is None
        or not projection_valid
        or not publication_valid
    ):
        core_result = {"status": "blocked", "candidates": []}
    else:
        policy_max = policy.get("max_candidates", args.max_candidates)
        maximum = min(args.max_candidates, policy_max) if isinstance(policy_max, int) else args.max_candidates
        core_result = locate(
            request,
            catalog,
            max_candidates=maximum,
            policy=policy,
            eligible_module_ids=eligible_module_ids,
        )
    result = bind_result_to_request(request, core_result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
