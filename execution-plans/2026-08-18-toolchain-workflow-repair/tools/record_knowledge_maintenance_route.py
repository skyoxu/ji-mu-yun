"""Record a non-authorizing route when required Knowledge modules are absent."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    args = parser.parse_args()
    root, plan = args.repository_root.resolve(), args.plan_dir.resolve()
    main_commit = subprocess.run(
        ["git", "rev-parse", "refs/heads/main"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    request = {
        "schema_version": "jimuyun.knowledge-locator-request.v1",
        "request_id": "TWR-20260819-prestart",
        "consumer": "vdd",
        "query": "skill-input-execution knowledge-execution-gates toolchain workflow repair typed skill input selection immutable generation current pointer retention",
        "snapshot": {"ref": "refs/heads/main", "commit": main_commit},
        "policy_revision": "knowledge-consumer-policies.v2",
        "allow_stale_catalog": True,
    }
    result = subprocess.run(["python", "scripts/python/knowledge_locator.py", "--repository-root", str(root), "--max-candidates", "100"], cwd=root, input=json.dumps(request), text=True, capture_output=True, check=False)
    try:
        locator = json.loads(result.stdout)
    except json.JSONDecodeError:
        locator = {"status": "invalid-locator-output"}
    required = {"skill-input-execution", "knowledge-execution-gates"}
    found = {item.get("module_id") for item in locator.get("candidates", []) if isinstance(item, dict)}
    payload = {
        "schema_version": "jimuyun.acceptance-knowledge-maintenance-route.v1",
        "status": "blocked",
        "failure_code": "catalog_stale",
        "target_plan": plan.relative_to(root).as_posix(),
        "requires_explicit_maintainer_confirmation": True,
        "route_output": "",
        "locator_request": request,
        "locator_result": locator,
        "required_modules": sorted(required),
        "missing_modules": sorted(required - found),
        "next_action": "knowledge-maintenance-required",
        "automatic_publication_allowed": False,
        "authorizes": [],
    }
    filename_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
    output = plan / "knowledge-context-routes" / (filename_hash + ".json")
    payload["route_output"] = output.relative_to(root).as_posix()
    route_body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    route_sha256 = hashlib.sha256(route_body).hexdigest()
    payload["route_sha256"] = "sha256:" + route_sha256
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": "blocked", "missing_modules": payload["missing_modules"], "authorizes": []}))
    return 2 if payload["missing_modules"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
