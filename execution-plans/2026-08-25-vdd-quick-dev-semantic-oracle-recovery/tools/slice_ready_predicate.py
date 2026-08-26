"""Validate the current run has completed a locally closed slice lifecycle."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def validate_slice_ready(repository_root: Path, run_root: Path, slice_id: str) -> dict[str, object]:
    """Require genuine adapter observations and a RED-bound successor."""
    observations = run_root / "observations"
    for stage in ("green", "refactor"):
        path = observations / f"{stage}-observed.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {"status": "blocked", "reason": f"{stage}-observation-missing-or-invalid"}
        if value.get("stage") != stage or value.get("exit_code") != 0:
            return {"status": "blocked", "reason": f"{stage}-observation-not-successful"}
    import sys
    tools = repository_root / ".agents" / "skills" / "quick-dev-tdd-adapter" / "tools"
    sys.path.insert(0, str(tools))
    from stage_lifecycle_runner import validate_implementation_successor
    if not validate_implementation_successor(run_root):
        return {"status": "blocked", "reason": "implementation-successor-invalid"}
    plan = repository_root / "execution-plans" / "2026-08-25-vdd-quick-dev-semantic-oracle-recovery"
    try:
        contract = json.loads((plan / "implementation-contract.v1.json").read_text(encoding="utf-8"))
        selected = next(item for item in contract["slices"] if item.get("slice_id") == slice_id)
        missing = [path for path in selected.get("planned_new_files", []) if not (repository_root / path).is_file()]
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, StopIteration, TypeError):
        return {"status": "blocked", "reason": "planned-file-contract-invalid"}
    if missing:
        return {"status": "blocked", "reason": "planned-files-missing", "missing": missing}
    return {"status": "pass", "predicate": "slice-ready", "slice_id": slice_id, "run_id": run_root.name}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--slice", required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    del args.plan_dir
    result = validate_slice_ready(args.repository_root, args.run_root, args.slice)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
