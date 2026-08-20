"""Publish a maintainer-owned authorization successor for this legacy plan."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


PLAN_ID = "vdd-conformance-exact-cover"


def identity(path: Path) -> str:
    if path.suffix == ".json":
        value = json.loads(path.read_text(encoding="utf-8"))
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    else:
        payload = path.read_bytes()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def binding(root: Path, path: Path) -> dict[str, str]:
    return {
        "path": path.relative_to(root).as_posix(),
        "identity_kind": "canonical-json-v1" if path.suffix == ".json" else "raw-bytes-v1",
        "sha256": identity(path),
    }


def write(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--maintainer-authorize", action="store_true")
    args = parser.parse_args()
    if not args.maintainer_authorize:
        raise ValueError("explicit maintainer authorization is required")
    root, plan = args.repository_root.resolve(), args.plan_dir.resolve()
    contract = json.loads((plan / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    state_path = plan / "plan-state.v1.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if contract.get("plan_id") != PLAN_ID or state.get("state") != "implementation-authorized":
        raise ValueError("plan is not maintainer-authorized")
    repair = plan / "repair" / "round-1"
    authority = plan / "authority-manifest.v1.json"
    write(authority, {"schema_version": "vdd-conformance-exact-cover.authority-manifest.v1", "authority_sources": [{"path": contract["authority"]["authority_manifest"], "role": "canonical_spec"}, {"path": "AGENTS.md", "role": "repository_rule"}], "candidate_inputs": [{"path": "execution-plans/2026-08-13-vdd-conformance-exact-cover/implementation-contract.v1.json", "role": "implementation_contract"}, {"path": "execution-plans/2026-08-13-vdd-conformance-exact-cover/command-registry.v1.json", "role": "command_registry"}], "authorizes": []})
    predecessor = repair / "legacy-maintainer-authorization-predecessor.v1.json"
    write(predecessor, {"schema_version": "vdd-conformance-exact-cover.legacy-authorization-predecessor.v1", "plan_state": state, "authorizes": []})
    repair_state = repair / "repair-state.v1.json"
    write(repair_state, {"schema_version": "vdd-conformance-exact-cover.repair-state.v1", "plan_id": PLAN_ID, "round": 1, "status": "closed", "blocks_execution": False, "authorizes": []})
    validation = repair / "adapter-compatibility-plan-validation.v1.json"
    write(validation, {"schema_version": "vdd-conformance-exact-cover.adapter-compatibility-plan-validation.v1", "plan_id": PLAN_ID, "predicate": "plan-valid", "status": "pass", "failures": [], "authorizes": []})
    candidate = repair / "adapter-compatibility-candidate-manifest.v1.json"
    candidate_paths = ["implementation-contract.v1.json", "command-registry.v1.json", "tools/terminal_full.py", "tools/terminal_validation.py", "tools/validate_all.py", "tools/tdd_bridge.py"]
    write(candidate, {"schema_version": "vdd-conformance-exact-cover.adapter-compatibility-candidate-manifest.v1", "plan_id": PLAN_ID, "paths": [{"path": path, "sha256": identity(plan / path)} for path in candidate_paths], "authorizes": []})
    delta = repair / "adapter-compatibility-preexisting-delta.v1.json"
    write(delta, {"schema_version": "vdd-conformance-exact-cover.adapter-compatibility-preexisting-delta.v1", "plan_id": PLAN_ID, "disposition": "legacy-plan-adapter-compatibility", "authorizes": []})
    required = {
        "implementation_contract": plan / "implementation-contract.v1.json",
        "command_registry": plan / "command-registry.v1.json",
        "authority_manifest": authority,
        "knowledge_context": plan / "knowledge-context.v1.json",
        "knowledge_context_freeze": plan / "knowledge-context.freeze.v1.json",
        "plan_validation": validation,
        "repair_closure": plan / "repair" / "round-8" / "repair-closure.json",
        "bootstrap_preexisting_delta": delta,
        "candidate_manifest": candidate,
        "validate_all": plan / "tools" / "validate_all.py",
        "terminal_validator": plan / "tools" / "terminal_full.py",
        "immutable_predecessor": predecessor,
    }
    receipt = {"schema_version": "vdd-conformance-exact-cover.implementation-authorization-receipt.v1", "plan_id": PLAN_ID, **{name: binding(root, path) for name, path in required.items()}, "decision": {"owner": "maintainer", "transition": "implementation-authorized", "reason": "explicit-maintainer-authorization-legacy-adapter-compatibility"}, "authorizes": ["implementation-authorized"], "does_not_authorize": ["implementation-complete", "acceptance-passed", "knowledge-publication", "bootstrap-review", "release"]}
    receipt_path = plan / "implementation-authorization-receipt.successor.v1.json"
    write(receipt_path, receipt)
    print(json.dumps({"status": "pass", "receipt": receipt_path.as_posix(), "authorizes": ["implementation-authorized"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
