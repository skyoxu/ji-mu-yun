from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _knowledge_locator_core import bind_result_to_request, locate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=Path("knowledge/catalogs/repository-knowledge-catalog.v1.json"))
    parser.add_argument("--max-candidates", type=int, default=12)
    args = parser.parse_args()
    request = json.load(sys.stdin)
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    result = bind_result_to_request(request, locate(request, catalog, max_candidates=args.max_candidates))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
