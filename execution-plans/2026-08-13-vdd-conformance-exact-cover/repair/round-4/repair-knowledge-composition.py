"""Repair-only knowledge composition; executes the real consumer CLI boundary."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PLAN = ROOT / "execution-plans/2026-08-13-vdd-conformance-exact-cover"
PRODUCER = ROOT / ".agents/skills/vdd-execution-plan/scripts/prepare_knowledge_context.py"
CONSUMER = ROOT / ".agents/skills/vdd-execution-plan/scripts/vdd_knowledge_preflight.py"
RECEIPT = PLAN / "repair/round-4/composition-runs/run-001/receipt.json"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    parser.add_argument("--validate-receipt", action="store_true")
    args = parser.parse_args()
    receipt_path = args.receipt if args.receipt.is_absolute() else ROOT / args.receipt
    if args.validate_receipt:
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            if receipt.get("schema_version") != "vdd-repair-composition-receipt.v1" or receipt.get("status") != "passed":
                raise ValueError("receipt is not passed")
            for key in ("producer", "consumer"):
                item = receipt[key]
                if item["sha256"] != sha((ROOT / item["path"]).resolve()):
                    raise ValueError(f"{key} hash is stale")
            print("repair-knowledge-composition=receipt-valid")
            return 0
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            print(f"repair-knowledge-composition=blocked reason={exc}")
            return 2
    runs_root = PLAN / "repair/round-4/composition-runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    numbers = [int(p.name.removeprefix("run-")) for p in runs_root.glob("run-*") if p.name.removeprefix("run-").isdigit()]
    run_root = runs_root / f"run-{max(numbers, default=0) + 1:03d}"
    output = run_root / "knowledge-context.v1.json"
    run_root.mkdir(parents=True, exist_ok=False)
    receipt_path = run_root / "receipt.json"
    skill_root = run_root / "skill-input"
    shutil.copytree(PLAN / "in", skill_root)
    skill_receipt = skill_root / "receipt.json"
    skill_payload = json.loads(skill_receipt.read_text(encoding="utf-8"))
    sys.path.insert(0, str(ROOT / "scripts/python"))
    from skill_input_consumption import canonical_hash, repository_identity
    source_paths = [item["path"] for item in skill_payload.get("sources", [])]
    skill_payload["repository_identity"] = repository_identity(ROOT, source_paths)
    child_path = skill_root / "child.json"
    child = json.loads(child_path.read_text(encoding="utf-8"))
    child["snapshot_root"] = str((skill_root / "s").relative_to(ROOT)).replace("\\", "/")
    child["output_root"] = str((skill_root / "o").relative_to(ROOT)).replace("\\", "/")
    child_path.write_text(json.dumps(child, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    skill_payload["child_request"] = {"path": "child.json", "sha256": sha(child_path)}
    decision_path = skill_root / "o/semantic-decision.v1.json"
    context_path = skill_root / "o/skill-input-context.v1.json"
    skill_payload["semantic_decision"] = {"path": "o/semantic-decision.v1.json", "sha256": sha(decision_path), "status": "accepted"}
    skill_payload["context_artifact"] = {"path": "o/skill-input-context.v1.json", "sha256": sha(context_path)}
    skill_payload["binding_hash"] = canonical_hash({key: value for key, value in skill_payload.items() if key != "binding_hash"})
    skill_receipt.write_text(json.dumps(skill_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    command = [sys.executable, str(PRODUCER), "--repository-root", str(ROOT), "--request-id", "vdd-conformance-exact-cover-2026-08-13", "--query", "VDD self-hosted execution plan Canonical Spec Package exact-cover conformance repository rules lifecycle authority", "--target-plan", str(PLAN.relative_to(ROOT)), "--output", str(output), "--allow-stale-catalog", "--required-module", "repository-rules", "--required-module", "adr.ADR-0044", "--required-module", "adr.ADR-0048", "--accept", "AGENTS.md=repository-rules,adr.ADR-0044,adr.ADR-0048"]
    produced = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    if produced.returncode:
        print(produced.stderr or produced.stdout or "composition producer failed")
        return 2
    context = output
    freeze = output.with_name("knowledge-context.freeze.v1.json")
    consumer_command = [sys.executable, str(CONSUMER), "--input", str(context), "--repository-root", str(ROOT), "--skill-input-receipt", str(skill_receipt), "--skill-input-operation", "create"]
    consumed = subprocess.run(consumer_command, cwd=ROOT, capture_output=True, text=True, check=False)
    if consumed.returncode:
        print(consumed.stderr or consumed.stdout or "composition consumer failed")
        return 2
    payload = {"schema_version": "vdd-repair-composition-receipt.v1", "round": 4, "command_id": "repair-knowledge-composition", "status": "passed", "producer": {"path": str(PRODUCER.relative_to(ROOT)).replace("\\", "/"), "sha256": sha(PRODUCER)}, "consumer": {"path": str(CONSUMER.relative_to(ROOT)).replace("\\", "/"), "sha256": sha(CONSUMER)}, "skill_input_receipt": {"path": str(skill_receipt.relative_to(ROOT)).replace("\\", "/"), "sha256": sha(skill_receipt)}, "execution_outputs": [{"path": str(context.relative_to(ROOT)).replace("\\", "/"), "sha256": sha(context)}, {"path": str(freeze.relative_to(ROOT)).replace("\\", "/"), "sha256": sha(freeze)}], "producer_exit_code": produced.returncode, "consumer_exit_code": consumed.returncode, "validation_reference": "execution-plans/2026-08-13-vdd-conformance-exact-cover/repair/round-4/repair-knowledge-composition.py", "authorizes": []}
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("repair-knowledge-composition=passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
