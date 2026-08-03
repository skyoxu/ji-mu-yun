#!/usr/bin/env python3
"""Publish only the plan-local implementation-complete lifecycle transition."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict[str, object]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def contract_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def completion_mode(status: object) -> str:
    if status == "implementation-authorized":
        return "initial"
    if status == "implementation-complete":
        return "repair"
    raise RuntimeError("implementation completion requires an authorized or completed state")


def canonical_hash(value: object) -> str:
    payload = json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.repository_root.resolve()
    plan = args.plan_dir.resolve()
    contract_path = plan / "implementation-contract.v1.json"
    contract = load_json(contract_path)
    state_path = plan / "plan-state.v1.json"
    state = load_json(state_path)
    mode = completion_mode(state.get("status"))
    current_hash = contract_hash(contract_path)
    evidence_root = root / "logs" / "tdd-adapter" / str(contract["plan_id"])
    evidence_bindings: list[dict[str, str]] = []
    for slice_item in contract.get("slices", []):
        if not isinstance(slice_item, dict) or not isinstance(slice_item.get("slice_id"), str):
            raise RuntimeError("implementation contract has an invalid slice")
        slice_id = slice_item["slice_id"]
        results = sorted((evidence_root / slice_id).glob("*/slice-ready-result.json"))
        current_results = [
            path
            for path in results
            if (result := load_json(path)).get("predicate") == "slice-ready"
            and result.get("status") == "pass"
            and result.get("contract_hash") == current_hash
            and result.get("slice_id") == slice_id
            and result.get("authorizes") == []
        ]
        if not current_results:
            raise RuntimeError(f"implementation completion is missing current slice evidence: {slice_id}")
        selected = current_results[-1]
        evidence_bindings.append(
            {
                "slice_id": slice_id,
                "path": selected.relative_to(root).as_posix(),
                "sha256": "sha256:" + hashlib.sha256(selected.read_bytes()).hexdigest(),
            }
        )
    repair_binding = canonical_hash(evidence_bindings)
    readiness = subprocess.run(
        [sys.executable, "-B", str(plan / "tools/check_e2_readiness.py")],
        cwd=root,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    if readiness.returncode:
        raise RuntimeError("implementation completion cannot compute E2 readiness")
    if not json.loads(readiness.stdout).get("ready"):
        raise RuntimeError("implementation completion requires current E2 readiness")
    composition = subprocess.run(
        [sys.executable, "-B", str(plan / "tools/validate_whole_directory.py")],
        cwd=root,
        check=False,
    )
    if composition.returncode:
        raise RuntimeError("implementation completion requires whole-directory validation")
    history = state.setdefault("status_history", [])
    if not isinstance(history, list):
        raise RuntimeError("plan state history is invalid")
    index_path = plan / "00-index.md"
    index = index_path.read_text(encoding="utf-8")
    if mode == "initial":
        state["status"] = "implementation-complete"
        state["authorizes"] = ["plan-ready", "implementation-authorized", "implementation-complete"]
        history.append(
            {
                "status": "implementation-complete",
                "reason": "Quick Dev adapter observed current TDD evidence for K0-K14 and the plan-local completion predicate passed.",
                "evidence": [
                    "logs/tdd-adapter/jimuyun-four-domain-knowledge-context.v1/",
                    "tools/check_e2_readiness.py",
                    "tools/validate_whole_directory.py",
                ],
            }
        )
        write_json(state_path, state)
        expected = "- Status: implementation-authorized"
        if index.count(expected) != 1:
            raise RuntimeError("plan index status is not uniquely implementation-authorized")
        index_path.write_text(index.replace(expected, "- Status: implementation-complete"), encoding="utf-8", newline="\n")
    else:
        if index.count("- Status: implementation-complete") != 1:
            raise RuntimeError("repair completion requires a uniquely completed plan index")
        marker = f"repair-binding:{repair_binding}"
        if not any(marker in str(item.get("reason", "")) for item in history if isinstance(item, dict)):
            history.append(
                {
                    "status": "implementation-complete",
                    "reason": f"Quick Dev adapter revalidated K0-K14 after repair ({marker}).",
                    "evidence": [
                        "logs/tdd-adapter/jimuyun-four-domain-knowledge-context.v1/",
                        "tools/check_e2_readiness.py",
                        "tools/validate_whole_directory.py",
                    ],
                }
            )
            write_json(state_path, state)
    report = plan / "95-implementation-evolution-and-completion-report.md"
    report_text = report.read_text(encoding="utf-8")
    if mode == "repair" and repair_binding in report_text:
        print(json.dumps({"status": "implementation-complete", "disposition": "existing", "authorizes": ["implementation-complete"]}, sort_keys=True))
        return 0
    timestamp = datetime.now(timezone.utc).isoformat()
    with report.open("a", encoding="utf-8", newline="\n") as stream:
        heading = "Implementation completion" if mode == "initial" else "Implementation repair completion"
        stream.write(f"\n## {heading}\n\n")
        stream.write(f"- Observed at: `{timestamp}`\n")
        stream.write("- Publisher: `tools/publish_implementation_complete.py` through the Quick Dev adapter bridge.\n")
        if mode == "repair":
            stream.write(f"- Repair binding: `{repair_binding}`\n")
        stream.write("- Result: `implementation-complete`; this does not authorize acceptance, deployment, handoff, release, or archive.\n")
    print(json.dumps({"status": "implementation-complete", "disposition": "published", "authorizes": ["implementation-complete"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
