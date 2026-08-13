"""Run the controlled knowledge producer-to-consumer composition check."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PLAN = ROOT / "execution-plans/2026-08-13-vdd-conformance-exact-cover"
PRODUCER = ROOT / ".agents/skills/vdd-execution-plan/scripts/prepare_knowledge_context.py"
CONSUMER = ROOT / ".agents/skills/vdd-execution-plan/scripts/vdd_knowledge_preflight.py"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, default=PLAN / "repair/round-3/composition-receipt.v1.json")
    args = parser.parse_args()
    receipt_path = args.receipt if args.receipt.is_absolute() else ROOT / args.receipt
    runs_root = PLAN / "repair/round-3/composition-runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    run_numbers = [int(path.name.removeprefix("run-")) for path in runs_root.glob("run-*") if path.name.removeprefix("run-").isdigit()]
    run_root = runs_root / f"run-{(max(run_numbers, default=0) + 1):03d}"
    output = run_root / "knowledge-context.v1.json"
    target = PLAN.relative_to(ROOT)
    run_root.mkdir(parents=True, exist_ok=False)
    try:
        command = [
            sys.executable,
            str(PRODUCER),
            "--repository-root", str(ROOT),
            "--request-id", "vdd-conformance-exact-cover-2026-08-13",
            "--query", "VDD self-hosted execution plan Canonical Spec Package exact-cover conformance repository rules lifecycle authority",
            "--target-plan", str(target),
            "--output", str(output),
            "--allow-stale-catalog",
            "--required-module", "repository-rules",
            "--required-module", "adr.ADR-0044",
            "--required-module", "adr.ADR-0048",
            "--accept", "AGENTS.md=repository-rules,adr.ADR-0044,adr.ADR-0048",
        ]
        produced = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
        if produced.returncode:
            print(produced.stderr or produced.stdout or "composition producer failed")
            return 2
        context = output
        freeze = output.with_name("knowledge-context.freeze.v1.json")
        payload = json.loads(context.read_text(encoding="utf-8"))
        spec = importlib.util.spec_from_file_location("vdd_preflight_consumer", CONSUMER)
        if spec is None or spec.loader is None:
            raise RuntimeError("composition consumer unavailable")
        module = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(ROOT / "scripts/python"))
        spec.loader.exec_module(module)
        consumed_payload = module.evaluate_preflight(payload, repository_root=ROOT)
        if consumed_payload.get("status") != "ready":
            print(json.dumps(consumed_payload, ensure_ascii=False))
            return 2
        payload = {
            "schema_version": "vdd-repair-composition-receipt.v1",
            "round": 3,
            "command_id": "composition",
            "status": "passed",
            "producer": {"path": str(PRODUCER.relative_to(ROOT)).replace("\\", "/"), "sha256": digest(PRODUCER)},
            "consumer": {"path": str(CONSUMER.relative_to(ROOT)).replace("\\", "/"), "sha256": digest(CONSUMER)},
            "controlled_command": {"path": str(Path(__file__).relative_to(ROOT)).replace("\\", "/"), "sha256": digest(Path(__file__))},
            "execution_outputs": [
                {"path": str(context.relative_to(ROOT)).replace("\\", "/"), "sha256": digest(context)},
                {"path": str(freeze.relative_to(ROOT)).replace("\\", "/"), "sha256": digest(freeze)},
            ],
            "producer_exit_code": produced.returncode,
            "consumer_exit_code": 0,
            "validation_reference": "execution-plans/2026-08-13-vdd-conformance-exact-cover/repair/round-3/composition.py",
            "authorizes": [],
        }
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("composition=passed")
        return 0
    except (OSError, json.JSONDecodeError, RuntimeError, ImportError) as exc:
        print(f"composition=blocked reason={exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
