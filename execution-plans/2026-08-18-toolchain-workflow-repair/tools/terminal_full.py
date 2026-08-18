from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = {
        "schema_version": "toolchain-workflow-repair.terminal-result.v1",
        "plan_id": "toolchain-workflow-repair",
        "predicate": "implementation-complete",
        "status": "fail",
        "failures": ["maintainer-implementation-authorization-required"],
        "authorizes": [],
        "lifecycle_transition": "none",
    }
    encoded = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(encoded, encoding="utf-8", newline="\n")
    print(encoded, end="")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
