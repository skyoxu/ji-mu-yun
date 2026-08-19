from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


PLAN_ID = "toolchain-workflow-repair"


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def contract_digest(plan: Path) -> str:
    return digest(plan / "implementation-contract.v1.json")


def registry_digest(plan: Path) -> str:
    return digest(plan / "command-registry.v1.json")


def publish_canonical_receipt(plan: Path, result: dict) -> Path:
    """Publish the current Quick Dev handoff without rewriting history."""
    repair = plan / "repair" / "round-1"
    repair.mkdir(parents=True, exist_ok=True)
    base = repair / "quick-dev-implementation-complete.v1.json"
    encoded = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if base.is_file():
        if base.read_text(encoding="utf-8") == encoded:
            return base
        suffix = result["contract_hash"].split(":", 1)[-1][:16]
        base = repair / f"quick-dev-implementation-complete.{suffix}.v1.json"
    if base.is_file() and base.read_text(encoding="utf-8") != encoded:
        raise RuntimeError("canonical implementation receipt successor conflicts")
    if not base.is_file():
        base.write_text(encoded, encoding="utf-8", newline="\n")
    return base


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    root, plan = args.repository_root.resolve(), args.plan_dir.resolve()
    failures = []
    for index in range(7):
        slice_id = f"W{index}"
        # The lifecycle runner's canonical slice predicate artifact is
        # `slice-ready-result.json`; `slice-receipt.json` was never produced
        # by the current adapter and would make terminal completion impossible.
        matches = sorted((root / "logs" / "tdd-adapter" / PLAN_ID / slice_id).glob("*/slice-ready-result.json"))
        if len(matches) != 1:
            failures.append(f"slice:{slice_id}:current-pass-receipt-required")
            continue
        try:
            receipt = json.loads(matches[0].read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            failures.append(f"slice:{slice_id}:receipt-invalid")
            continue
        if receipt.get("predicate") != "slice-ready" or receipt.get("status") != "pass" or receipt.get("failures", []) != [] or receipt.get("authorizes", []) != []:
            failures.append(f"slice:{slice_id}:receipt-not-current-pass")
    result = {
        "schema_version": "quick-dev-implementation-complete.v1",
        "plan_id": PLAN_ID,
        "predicate": "implementation-complete",
        "status": "pass" if not failures else "fail",
        "failures": failures,
        "contract_hash": contract_digest(plan),
        "command_registry_hash": registry_digest(plan),
        "terminal_command_id": "terminal-full",
        "validated_command_ids": [f"w{index}-terminal" for index in range(7)],
        "authorizes": ["implementation-complete"] if not failures else [],
        "lifecycle_transition": "none",
    }
    if result["status"] == "pass":
        result["canonical_receipt_path"] = publish_canonical_receipt(plan, result).relative_to(plan).as_posix()
    encoded = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(encoded, encoding="utf-8", newline="\n")
    print(encoded, end="")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
