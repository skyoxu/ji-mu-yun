from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def publish_canonical_receipt(plan: Path, result: dict[str, object]) -> Path:
    """Publish an immutable current-contract implementation handoff."""
    repair = plan / "repair" / "round-1"
    repair.mkdir(parents=True, exist_ok=True)
    base = repair / "quick-dev-implementation-complete.v1.json"
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if base.is_file() and base.read_text(encoding="utf-8") != encoded:
        suffix = str(result["contract_hash"]).split(":", 1)[-1][:16]
        base = repair / f"quick-dev-implementation-complete.{suffix}.v1.json"
    if base.is_file() and base.read_text(encoding="utf-8") != encoded:
        raise RuntimeError("canonical implementation receipt successor conflicts")
    if not base.is_file():
        base.write_text(encoded, encoding="utf-8", newline="\n")
    return base


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slice", choices=("S0", "S1", "S2"))
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--plan-dir", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    contract_path = args.repository_root / "execution-plans/2026-08-17-quick-dev-tdd-stage-recovery/implementation-contract.v1.json"
    registry_path = args.repository_root / "execution-plans/2026-08-17-quick-dev-tdd-stage-recovery/command-registry.v1.json"
    contract_hash = _sha(contract_path.read_bytes())
    target = ".agents/skills/quick-dev-tdd-adapter/tools/tests" if args.slice is None else {
        "S0": ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_stage_lifecycle.py",
        "S1": ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_stage_recovery.py",
        "S2": ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_migration_cutover.py",
    }[args.slice]
    result = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", target, "-q"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=args.repository_root,
    )
    dogfood = None if args.slice else subprocess.run(
        [sys.executable, "-B", "execution-plans/2026-08-17-quick-dev-tdd-stage-recovery/tools/dogfood_runner.py"],
        check=False,
        capture_output=True,
        cwd=args.repository_root,
    )
    status = "pass" if result.returncode == 0 and (dogfood is None or dogfood.returncode == 0) else "fail"
    payload = {"schema_version": "quick-dev-tdd-stage-recovery.terminal-result.v1", "orchestration_version": "stage-actions.v2", "status": status, "predicate": "slice-ready" if args.slice else "implementation-complete", "plan_id": "quick-dev-tdd-stage-recovery", "contract_hash": contract_hash, "command_registry_hash": _sha(registry_path.read_bytes()), "terminal_command_id": "s0-terminal" if args.slice == "S0" else "s1-terminal" if args.slice == "S1" else "s2-terminal" if args.slice == "S2" else "terminal-full", "validated_command_ids": [] if args.slice else ["adapter-tests", "dogfood-8-17"], "adapter_output_sha256": _sha((result.stdout + result.stderr).encode("utf-8")), "dogfood_output_sha256": None if dogfood is None else _sha(dogfood.stdout + dogfood.stderr), "authorizes": ["implementation-complete"] if status == "pass" and args.slice is None else []}
    if status == "pass" and args.slice is None:
        receipt = {
            "schema_version": "quick-dev-implementation-complete.v1",
            "plan_id": payload["plan_id"],
            "predicate": payload["predicate"],
            "status": payload["status"],
            "failures": [],
            "contract_hash": payload["contract_hash"],
            "command_registry_hash": payload["command_registry_hash"],
            "terminal_command_id": payload["terminal_command_id"],
            "validated_command_ids": payload["validated_command_ids"],
            "adapter_output_sha256": payload["adapter_output_sha256"],
            "dogfood_output_sha256": payload["dogfood_output_sha256"],
            "authorizes": payload["authorizes"],
            "lifecycle_transition": "none",
        }
        payload["canonical_receipt_path"] = publish_canonical_receipt(args.repository_root / "execution-plans/2026-08-17-quick-dev-tdd-stage-recovery", receipt).relative_to(args.repository_root / "execution-plans/2026-08-17-quick-dev-tdd-stage-recovery").as_posix()
    rendered = json.dumps(payload)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(rendered)
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
