from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.repository_root.resolve()
    plan = args.plan_dir.resolve()
    validation_path = plan / "repair" / "plan-validation-receipt.v1.json"
    state_path = plan / "plan-state.v1.json"
    resume_path = plan / "resume-state.v1.json"
    report_path = plan / "95-implementation-evolution-and-completion-report.md"
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    state = json.loads(state_path.read_text(encoding="utf-8"))
    resume = json.loads(resume_path.read_text(encoding="utf-8"))
    if validation.get("predicate") != "plan-valid" or validation.get("status") != "pass" or validation.get("authorizes") != []:
        raise ValueError("plan validation is not a valid non-authorizing pass")
    if state.get("status") not in {"draft", "plan-ready"}:
        raise ValueError("plan state cannot be published from this lifecycle state")
    if state.get("status") == "draft":
        state["status"] = "plan-ready"
        state["authorizes"] = ["plan-ready"]
        state["owner"] = "vdd"
        write_json(state_path, state)
        resume["status"] = "plan-ready"
        resume["next_action"] = "awaiting-maintainer-implementation-authorization"
        write_json(resume_path, resume)
        with report_path.open("a", encoding="utf-8", newline="\n") as report:
            report.write("\n## Plan-Ready Publication\n\n")
            report.write("VDD published `plan-ready` after controlled plan validation. This does not authorize implementation, Knowledge publication, Bootstrap, or acceptance.\n")
    receipt = {
        "schema_version": "toolchain-workflow-repair.plan-ready-publication.v1",
        "plan_id": "toolchain-workflow-repair",
        "owner": "vdd",
        "validation": {"path": "repair/plan-validation-receipt.v1.json", "sha256": sha256(validation_path)},
        "plan_state": {"path": "plan-state.v1.json", "sha256": sha256(state_path)},
        "resume_state": {"path": "resume-state.v1.json", "sha256": sha256(resume_path)},
        "authorizes": ["plan-ready"],
        "does_not_authorize": ["implementation-authorized", "implementation-complete", "acceptance-passed", "knowledge-publication", "bootstrap-review"],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.out, receipt)
    print(json.dumps({"status": "pass", "receipt": args.out.as_posix(), "authorizes": ["plan-ready"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
