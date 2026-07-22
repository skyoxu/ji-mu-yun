from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _load_candidate_identity(plan: Path, slice_id: str) -> dict[str, str]:
    helper = plan / "tools" / "validate_all.py"
    if str(helper.parent) not in sys.path:
        sys.path.insert(0, str(helper.parent))
    spec = importlib.util.spec_from_file_location("plan_candidate_identity", helper)
    if spec is None or spec.loader is None:
        raise RuntimeError("plan-local candidate identity helper is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    identity = module.current_candidate_identity(slice_id)
    if not isinstance(identity, dict) or not isinstance(identity.get("validator_hash"), str):
        raise ValueError("plan-local candidate identity is invalid")
    return identity


def _expand(value: Any, *, plan_rel: str, plan_id: str, slice_id: str, run_id: str) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict) or set(value) != {"type", "value"}:
        raise ValueError("command argument is invalid")
    kind, raw = value["type"], value["value"]
    if not isinstance(raw, str):
        raise ValueError("command placeholder value is invalid")
    if kind == "plan_path":
        return f"{plan_rel}/{raw}"
    if kind == "repo_path":
        return raw
    if kind == "run_path":
        expanded = (raw.replace("<plan-id>", plan_id)
                       .replace("<slice-id>", slice_id)
                       .replace("<run-id>", run_id))
        return expanded if expanded.startswith("logs/") else f"logs/{expanded}"
    raise ValueError("unsupported command placeholder")


def _descriptor(commands: dict[str, dict[str, Any]], command_id: str, **values: str) -> dict[str, Any]:
    item = commands.get(command_id)
    if item is None:
        raise ValueError(f"command is not registered: {command_id}")
    if item.get("cwd", {}).get("value") != ".":
        raise ValueError("non-root command cwd is unsupported")
    return {
        "id": command_id,
        "executable": item["executable"],
        "argv": [_expand(value, **values) for value in item["argv"]],
        "cwd": ".",
        "timeout_seconds": item["timeout_seconds"],
        "shell": False,
    }


def build(repository_root: Path, plan_dir: Path, slice_id: str, run_id: str) -> dict[str, Any]:
    root, plan = repository_root.resolve(), plan_dir.resolve()
    try:
        plan.relative_to((root / "execution-plans").resolve())
    except ValueError as exc:
        raise ValueError("plan directory must stay under execution-plans") from exc
    contract_bytes = (plan / "implementation-contract.v1.json").read_bytes()
    contract = json.loads(contract_bytes.decode("utf-8"))
    registry = json.loads((plan / contract["command_registry"]).read_text(encoding="utf-8"))
    selected = next((item for item in contract["slices"] if item.get("slice_id") == slice_id), None)
    if selected is None:
        raise ValueError("slice is missing")
    plan_rel = plan.relative_to(root).as_posix()
    values = {"plan_rel": plan_rel, "plan_id": contract["plan_id"], "slice_id": slice_id, "run_id": run_id}
    commands = {item["id"]: item for item in registry["commands"]}
    tdd = selected["tdd"]
    red = _descriptor(commands, tdd["red"]["command_id"], **values)
    green = _descriptor(commands, tdd["green"]["command_id"], **values)
    refactor = [_descriptor(commands, item["command_id"], **values) for item in tdd["refactor"]["invocations"]]
    terminal = _descriptor(commands, selected["post_refactor_command_id"], **values)
    preparation = [_descriptor(commands, item["command_id"], **values) for item in selected.get("pre_terminal", [])]
    identity = _load_candidate_identity(plan, slice_id)
    authority = plan / contract["authority"]["authority_manifest"]
    context = {
        "plan_id": contract["plan_id"], "slice_id": slice_id, "run_id": run_id,
        "authority_refs": [{"role": "authority-manifest", "path_type": "plan_path", "path": authority.relative_to(plan).as_posix(), "payload_base64": base64.b64encode(authority.read_bytes()).decode("ascii")}],
        "implementation_contract": {"role": "implementation-contract", "path_type": "plan_path", "path": "implementation-contract.v1.json", "payload_base64": base64.b64encode(contract_bytes).decode("ascii")},
        "requirement_ids": selected["requirement_ids"], "acceptance_ids": selected["acceptance_ids"], "source_refs": selected["source_refs"],
        "boundaries": {"allowed_write_set": [path for group in selected["allowed_changes"].values() for path in group], "forbidden_write_set": selected["forbidden_changes"], "execution_read_set": selected["execution_read_set"], "dependency_closure": selected["dependency_closure"]},
        "target_command_ids": [red["id"], green["id"], *[item["id"] for item in refactor], terminal["id"]],
        "stage_results": {
            "red": {"schema_version": "rmap.tdd-stage-result.v1", "plan_id": contract["plan_id"], "slice_id": slice_id, "run_id": run_id, "status": "red-observed", "command_id": red["id"], "test_selector": tdd["red"]["test_selector"], "expected_failure_ids": tdd["red"]["expected_failure_ids"], "contract_hash": _sha(contract_bytes), "validator_hash": identity["validator_hash"]},
            "green": {"schema_version": "rmap.tdd-stage-result.v1", "plan_id": contract["plan_id"], "slice_id": slice_id, "run_id": run_id, "status": "green-observed", "command_id": green["id"], "contract_hash": _sha(contract_bytes), "validator_hash": identity["validator_hash"]},
            "refactor": {"schema_version": "rmap.tdd-stage-result.v1", "plan_id": contract["plan_id"], "slice_id": slice_id, "run_id": run_id, "status": "refactor-verified", "command_id": refactor[0]["id"], "command_ids": [item["id"] for item in refactor], "contract_hash": _sha(contract_bytes), "validator_hash": identity["validator_hash"]},
        },
    }
    return {"run_context": context, "red": red, "green": green, "refactor": refactor, "preparation": preparation, "terminal": terminal}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--slice-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    output = build(args.repository_root, args.plan_dir, args.slice_id, args.run_id)
    args.out_dir.mkdir(parents=True, exist_ok=False)
    files = {"run-context.json": output["run_context"], "red-command.json": output["red"], "green-command.json": output["green"], "refactor-commands.json": output["refactor"], "preparation-commands.json": output["preparation"], "terminal-command.json": output["terminal"]}
    for name, value in files.items():
        (args.out_dir / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"run_id": args.run_id, "created_at": datetime.now(timezone.utc).isoformat(), "authorizes": []}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
