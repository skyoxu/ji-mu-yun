from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    args = parser.parse_args()
    root, plan = args.repository_root.resolve(), args.plan_dir.resolve()
    round_dir = plan / "repair" / "round-1"
    required = [
        "finding-set.v1.json", "repair-state.v1.json", "historical-artifact-disposition.v1.json",
        "baseline-manifest.2050ec68.v1.json", "bootstrap-preexisting-delta.v1.json",
        "repair-candidate-manifest.v1.json", "repair-changed-set.v1.json",
        "plan-validation-receipt.v2.json", "authorization-predecessor.2050ec68.v1.json",
    ]
    missing = [name for name in required if not (round_dir / name).is_file()]
    validation = round_dir / "plan-validation-receipt.v2.json"
    value = json.loads(validation.read_text(encoding="utf-8")) if validation.is_file() else {}
    if missing or value.get("status") != "pass" or value.get("authorizes") != []:
        raise ValueError("repair round is not ready for closure")
    refs = {name.removesuffix(".v1.json"): {"path": f"repair/round-1/{name}", "sha256": sha(round_dir / name)} for name in required}
    closure = {"schema_version": "toolchain-workflow-repair.repair-closure.v1", "plan_id": "toolchain-workflow-repair", "status": "pass", "failures": [], "bindings": refs, "requires": ["plan-validation-pass", "pre-existing-delta", "authorization-predecessor"], "authorizes": [], "lifecycle_transition": "none"}
    write(round_dir / "repair-closure.v1.json", closure)
    entry = {"schema_version": "toolchain-workflow-repair.quick-dev-entry.v1", "predicate": "quick-dev-entry-ready", "status": "fail", "failures": ["slice-receipts-not-complete"], "next_action": "run-slice", "slice_id": "W0", "closure_sha256": sha(round_dir / "repair-closure.v1.json"), "authorizes": [], "lifecycle_transition": "none"}
    write(round_dir / "quick-dev-entry-receipt.v1.json", entry)
    print(json.dumps({"status": "pass", "closure": "repair/round-1/repair-closure.v1.json", "authorizes": []}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
