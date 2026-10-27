from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import _knowledge_locator_core as core


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
    parser.add_argument("--allow-stale-catalog", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    request = json.load(sys.stdin)
    result = core.query_with_diagnostics(
        request, args.repository_root, catalog_path=args.catalog,
        policies_path=args.policies, projections_path=args.projections,
        max_candidates=args.max_candidates,
        allow_unpublished_inputs=args.allow_unpublished_inputs,
        allow_stale_catalog=args.allow_stale_catalog,
    )["result"]
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
