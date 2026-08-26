from __future__ import annotations

import argparse
import json
from pathlib import Path
import importlib.util


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--slice", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=False)
    args = parser.parse_args()
    validator_path = args.plan_dir / "tools" / "validate_all.py"
    spec = importlib.util.spec_from_file_location("plan_validate_all", validator_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("plan aggregate validator is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if args.run_root is None:
        raise RuntimeError("terminal run root is required")
    # The terminal predicate is a reader.  It must never manufacture slice
    # evidence, acceptance coverage, or a replay report to satisfy itself.
    result = module.validate_terminal(args.plan_dir, args.run_root)
    result.update({
        "slice_id": args.slice,
        "run_id": args.run_root.name if args.run_root else None,
        "plan_id": "vdd-quick-dev-semantic-oracle-recovery",
        "producer": "terminal-validator",
    })
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
