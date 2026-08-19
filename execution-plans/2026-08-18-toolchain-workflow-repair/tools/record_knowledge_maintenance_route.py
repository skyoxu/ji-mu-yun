"""Record a non-authorizing route when required Knowledge modules are absent."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    args = parser.parse_args()
    root, plan = args.repository_root.resolve(), args.plan_dir.resolve()
    request = {
        "schema_version": "jimuyun.knowledge-locator-request.v1",
        "request_id": "TWR-20260819-prestart",
        "consumer": "vdd",
        "query": "toolchain workflow repair typed skill input selection immutable generation current pointer retention knowledge gates",
        "snapshot": {"ref": "refs/heads/main", "commit": "2050ec682bab8cdc11770bf9823549b264a9e339"},
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
        "schema_version": "toolchain-workflow-repair.knowledge-maintenance-route.v1",
        "locator_request": request,
        "locator_result": locator,
        "required_modules": sorted(required),
        "missing_modules": sorted(required - found),
        "next_action": "knowledge-maintenance-required",
        "automatic_publication_allowed": False,
        "authorizes": [],
    }
    output = plan / "repair" / "round-1" / "knowledge-maintenance-route.v1.json"
    output.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": "blocked", "missing_modules": payload["missing_modules"], "authorizes": []}))
    return 2 if payload["missing_modules"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
