from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
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
        "validator-input-manifest.v1.json", "plan-validation-receipt.v2.json",
        "authorization-predecessor.2050ec68.v1.json", "root-cause-callsite-inventory.v1.json",
        "producer-consumer-composition-receipt.v1.json", "sibling-8-17-manifest.v1.json",
        "sibling-original-8-18-manifest.v1.json",
    ]
    missing = [name for name in required if not (round_dir / name).is_file()]
    validation = round_dir / "plan-validation-receipt.v2.json"
    value = json.loads(validation.read_text(encoding="utf-8")) if validation.is_file() else {}
    test_receipts = sorted((round_dir / "test-receipts").glob("*.v1.json"))
    ready_input = sorted((plan / "skill-input").glob("*-receipt.json"))
    selected_input = next((item for item in reversed(ready_input) if item.name.startswith("prestart-") and json.loads(item.read_text(encoding="utf-8")).get("ready") is True), None)
    if missing or not test_receipts or selected_input is None or value.get("status") != "pass" or value.get("authorizes") != []:
        raise ValueError("repair round is not ready for closure")
    refs = {name.removesuffix(".v1.json"): {"path": f"repair/round-1/{name}", "sha256": sha(round_dir / name)} for name in required}
    for receipt in test_receipts:
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        if payload.get("status") != "pass" or payload.get("authorizes") != []:
            raise ValueError("repair test receipt is not a non-authorizing pass")
        refs[f"test:{receipt.stem}"] = {"path": receipt.relative_to(plan).as_posix(), "sha256": sha(receipt)}
    refs["skill_input_ready"] = {"path": selected_input.relative_to(plan).as_posix(), "sha256": sha(selected_input)}
    refs["knowledge_context"] = {"path": "knowledge-context.v1.json", "sha256": sha(plan / "knowledge-context.v1.json")}
    refs["knowledge_freeze"] = {"path": "knowledge-context.freeze.v1.json", "sha256": sha(plan / "knowledge-context.freeze.v1.json")}
    closure = {"schema_version": "toolchain-workflow-repair.repair-closure.v1", "plan_id": "toolchain-workflow-repair", "status": "pass", "failures": [], "bindings": refs, "requires": ["plan-validation-pass", "pre-existing-delta", "authorization-predecessor", "current-skill-input", "knowledge-preflight"], "authorizes": [], "lifecycle_transition": "none"}
    write(round_dir / "repair-closure.v1.json", closure)
    print(json.dumps({"status": "pass", "closure": "repair/round-1/repair-closure.v1.json", "authorizes": []}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
