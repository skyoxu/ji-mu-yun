from __future__ import annotations

import argparse
import json
from pathlib import Path

from route_plan_directory import route


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--max-actions", type=int, default=1)
    args = parser.parse_args()
    if args.max_actions < 1:
        raise ValueError("max actions must be positive")
    result = route(args.repository_root.resolve(), args.plan_dir.resolve())
    # This loop is a scheduler only. A caller must execute run-slice through
    # LifecycleRunner; no route decision or state sidecar is acceptance proof.
    result["max_actions"] = args.max_actions
    result["authorizes"] = []
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
