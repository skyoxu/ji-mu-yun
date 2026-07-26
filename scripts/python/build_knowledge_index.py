from __future__ import annotations

import argparse
import json
from pathlib import Path

from _knowledge_locator_core import publish_index_generation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--index-root", type=Path, default=Path("knowledge/indexes"))
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--policy-revision", required=True)
    args = parser.parse_args()
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    print(json.dumps(publish_index_generation(args.index_root, catalog, args.snapshot_id, args.policy_revision), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
