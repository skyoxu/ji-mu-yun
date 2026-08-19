from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "python"))
from skill_input_consumption import artifact_identity_hash


PLAN_ID = "toolchain-workflow-repair"


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256(path: Path) -> str:
    return artifact_identity_hash(path)


def write_json(path: Path, value: dict) -> None:
    path.write_bytes((json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8"))


def exclusive_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = source.read_bytes()
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
    except Exception:
        try:
            destination.unlink()
        except OSError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--refresh-authorized-successor", action="store_true")
    parser.add_argument("--skill-input-receipt", type=Path, required=True)
    args = parser.parse_args()
    root = args.repository_root.resolve()
    plan = args.plan_dir.resolve()
    expected_out = plan / "implementation-authorization-receipt.successor.v1.json"
    contract_path = plan / "implementation-contract.v1.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract.get("plan_id") != PLAN_ID or args.out.resolve() != expected_out:
        raise ValueError("authorization output path is not canonical for this plan")

    state_path = plan / "plan-state.v1.json"
    resume_path = plan / "resume-state.v1.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    resume = json.loads(resume_path.read_text(encoding="utf-8"))
    refreshing = state.get("status") == "implementation-authorized"
    predecessor = None
    predecessor_path = None
    if refreshing:
        if not args.refresh_authorized_successor or state.get("authorizes") != ["plan-ready", "implementation-authorized"] or not expected_out.is_file():
            raise ValueError("authorized successor refresh requires explicit maintainer flag and predecessor receipt")
        previous_hash = hashlib.sha256(expected_out.read_bytes()).hexdigest()
        predecessor_path = plan / "repair" / "round-1" / f"authorization-predecessor.{previous_hash[:16]}.v1.json"
        if not predecessor_path.exists():
            exclusive_copy(expected_out, predecessor_path)
        predecessor = {"path": predecessor_path.relative_to(root).as_posix(), "sha256": sha256(predecessor_path)}
    elif state.get("plan_id") != PLAN_ID or state.get("status") != "plan-ready" or state.get("authorizes") != ["plan-ready"]:
        raise ValueError("plan is not currently plan-ready")
    relative = plan.relative_to(root).as_posix()
    bindings = {
        "implementation_contract": "implementation-contract.v1.json",
        "command_registry": "command-registry.v1.json",
        "authority_manifest": "authority-manifest.v1.json",
        "knowledge_context": "knowledge-context.v1.json",
        "knowledge_context_freeze": "knowledge-context.freeze.v1.json",
        "plan_validation": "repair/round-1/plan-validation-receipt.v4.json",
        "repair_closure": "repair/round-1/repair-closure.v1.json",
        "bootstrap_preexisting_delta": "repair/round-1/bootstrap-preexisting-delta.v1.json",
        "candidate_manifest": "repair/round-1/repair-candidate-manifest.v1.json",
        "validate_all": "tools/validate_all.py",
        "terminal_validator": "tools/terminal_full.py",
        "immutable_predecessor": predecessor_path.relative_to(plan).as_posix() if predecessor_path else "repair/round-1/authorization-predecessor.2050ec68.v1.json",
    }
    skill_input = args.skill_input_receipt.resolve()
    try:
        skill_input_relative = skill_input.relative_to(plan).as_posix()
    except ValueError as exc:
        raise ValueError("skill input receipt must be inside this plan") from exc
    bindings["skill_input_receipt"] = skill_input_relative
    request = skill_input.with_name(skill_input.name.replace("-receipt.json", "-request.json"))
    if request.is_file():
        bindings["skill_input_request"] = request.relative_to(plan).as_posix()
    receipt_bindings = {
        name: {"path": f"{relative}/{path}", "sha256": sha256(plan / path)}
        for name, path in bindings.items()
    }
    # The revalidation command emits the versioned plan-validation receipt;
    # bind that exact artifact instead of requiring a second, nonexistent alias.
    candidate_binding_hash = "sha256:" + hashlib.sha256(canonical(receipt_bindings)).hexdigest()

    receipt_bindings["immutable_predecessor"] = {
        "path": f"{relative}/{bindings['immutable_predecessor']}",
        "sha256": sha256(plan / bindings["immutable_predecessor"]),
    }
    state.update({
        "status": "implementation-authorized",
        "owner": "maintainer",
        "authorizes": ["plan-ready", "implementation-authorized"],
    })
    resume.update({
        "status": "implementation-authorized",
        "next_action": "run-slice",
    })
    write_json(state_path, state)
    write_json(resume_path, resume)

    receipt = {
        "schema_version": "toolchain-workflow-repair.implementation-authorization-receipt.v1",
        "plan_id": PLAN_ID,
        **receipt_bindings,
        "candidate_binding_hash": candidate_binding_hash,
        "predecessor_authorization=<redacted>,
        "decision": {
            "owner": "maintainer",
            "transition": "implementation-authorized",
            "reason": "explicit-maintainer-authorization",
        },
        "authorizes": ["implementation-authorized"],
        "does_not_authorize": ["implementation-complete", "acceptance-passed", "knowledge-publication", "bootstrap-review", "release"],
    }
    write_json(expected_out, receipt)
    report = plan / "95-implementation-evolution-and-completion-report.md"
    with report.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write("\n## Implementation Authorization\n\n")
        handle.write("The maintainer explicitly published `implementation-authorized` after current plan-ready validation and binding verification. This does not authorize implementation completion, Acceptance, Knowledge publication, Bootstrap, or release.\n")
    print(json.dumps({"status": "pass", "receipt": expected_out.as_posix(), "authorizes": ["implementation-authorized"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
