"""Validate the executable RED/GREEN separation contract."""
from __future__ import annotations

import ast
import json
from pathlib import Path


def validate(plan: Path) -> tuple[bool, list[str]]:
    contract = json.loads((plan / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    errors: list[str] = []
    for item in contract.get("slices", []):
        sid = item.get("slice_id")
        red = item.get("tdd", {}).get("red", {})
        selector = red.get("test_selector")
        if not isinstance(selector, str):
            errors.append(f"{sid}:missing-red-selector")
            continue
        path = (plan.parents[1] / selector).resolve()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError):
            errors.append(f"{sid}:red-selector-unreadable")
            continue
        source = ast.unparse(tree)
        if "assert False" in source or "raise AssertionError" in source and "FAILURE_ID" not in source:
            errors.append(f"{sid}:constant-red-placeholder")
        if not any(isinstance(node, ast.Call) for node in ast.walk(tree)):
            errors.append(f"{sid}:red-has-no-behavior-call")
        green = item.get("tdd", {}).get("green", {})
        green_id = green.get("command_id")
        if not isinstance(green_id, str) or green_id == red.get("command_id"):
            errors.append(f"{sid}:green-reuses-red-command")
        if not isinstance(item.get("planned_new_files"), list) and not isinstance(item.get("allowed_changes", {}).get("production"), list):
            errors.append(f"{sid}:missing-implementation-entrypoint")
        if not item.get("allowed_changes", {}).get("production"):
            errors.append(f"{sid}:missing-success-artifact-owner")
    return not errors, errors


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-dir", type=Path, required=True)
    args = parser.parse_args()
    ok, errors = validate(args.plan_dir.resolve())
    print(json.dumps({"status": "pass" if ok else "blocked", "errors": errors}, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
