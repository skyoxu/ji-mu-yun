from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from _knowledge_locator_core import bind_result_to_request, catalog_source_snapshot, locate, require_fresh_catalog


def _main_source_hashes(repository_root: Path, catalog: dict) -> dict[str, str]:
    paths = {
        entry.get("source_path") or entry.get("path")
        for entry in catalog.get("entries", [])
        if isinstance(entry, dict)
    }
    hashes: dict[str, str] = {}
    for path in paths:
        if not isinstance(path, str) or not path:
            continue
        result = subprocess.run(
            ["git", "-C", str(repository_root), "show", f"refs/heads/main:{path}"],
            capture_output=True, check=False,
        )
        if result.returncode == 0:
            hashes[path] = hashlib.sha256(result.stdout).hexdigest()
    return hashes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=Path("knowledge/catalogs/repository-knowledge-catalog.v1.json"))
    parser.add_argument("--max-candidates", type=int, default=12)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    request = json.load(sys.stdin)
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    snapshot = catalog_source_snapshot(catalog)
    fresh = require_fresh_catalog(catalog, _main_source_hashes(args.repository_root.resolve(), catalog))
    if snapshot is None or request.get("snapshot") != {"ref": snapshot["ref"], "commit": snapshot["commit"]} or fresh["status"] != "current":
        core_result = {"status": "blocked", "candidates": []}
    else:
        core_result = locate(request, catalog, max_candidates=args.max_candidates)
    result = bind_result_to_request(request, core_result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
