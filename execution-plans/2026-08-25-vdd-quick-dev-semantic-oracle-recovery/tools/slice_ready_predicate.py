"""Validate the current run has completed a locally closed slice lifecycle."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--slice", required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    del args.repository_root, args.plan_dir
    required = (args.run_root / "observations" / "green-observed.json", args.run_root / "observations" / "refactor-observed.json")
    status = "pass" if all(path.is_file() for path in required) else "blocked"
    result = {"status": status, "predicate": "slice-ready", "slice_id": args.slice, "run_id": args.run_root.name}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, sort_keys=True))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
