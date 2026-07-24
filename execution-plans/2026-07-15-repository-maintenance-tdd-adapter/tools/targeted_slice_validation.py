from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def _loop_runner(repository_root: Path):
    path = repository_root / ".agents" / "skills" / "quick-dev-tdd-adapter" / "tools" / "loop_plan_directory.py"
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("rmap_targeted_loop_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("targeted lifecycle runner is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    args = parser.parse_args()
    root, plan = args.repository_root.resolve(), args.plan_dir.resolve()
    contract = json.loads((plan / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    policy = contract["execution_replay_policy"]["targeted_validation"]
    runner = _loop_runner(root)
    previous_mode = os.environ.get("JIMUYUN_TDD_EXECUTION_MODE")
    os.environ["JIMUYUN_TDD_EXECUTION_MODE"] = "targeted-validation"
    try:
        for slice_id in policy["allowed_slices"]:
            selected = next(item for item in contract["slices"] if item["slice_id"] == slice_id)
            runner._run_slice(root, plan, slice_id, selected["execution_snapshot_paths"])
            evidence_root = root / "logs" / "tdd-adapter" / contract["plan_id"] / slice_id
            run_dir = max((path for path in evidence_root.iterdir() if path.is_dir()), key=lambda path: path.stat().st_mtime)
            marker = {"schema_version": "jimuyun.targeted-validation.v1", "mode": "targeted-validation", "slice_id": slice_id, "generated_at": datetime.now(timezone.utc).isoformat(), "authorizes": [], "does_not_authorize": policy["does_not_authorize"]}
            (run_dir / policy["evidence_marker"]).write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8", newline="\n")
    finally:
        if previous_mode is None:
            os.environ.pop("JIMUYUN_TDD_EXECUTION_MODE", None)
        else:
            os.environ["JIMUYUN_TDD_EXECUTION_MODE"] = previous_mode
    print(json.dumps({"mode": "targeted-validation", "slices": policy["allowed_slices"], "authorizes": []}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
