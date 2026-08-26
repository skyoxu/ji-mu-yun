from __future__ import annotations

import argparse
import base64
import fnmatch
import hashlib
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _legacy_predecessor(repository_root: Path, red: dict[str, Any]) -> dict[str, str] | None:
    """Validate the immutable failed RED that permits a legacy replay."""
    mode = red.get("mode", "red")
    if mode == "red":
        return None
    if mode not in {"legacy-regression", "prior-red-successor"}:
        raise ValueError("RED mode is invalid")
    field = "legacy_predecessor" if mode == "legacy-regression" else "prior_red"
    predecessor = red.get(field)
    if not isinstance(predecessor, dict) or set(predecessor) != {"path", "sha256"}:
        raise ValueError("RED successor requires a bound prior RED")
    path, expected = predecessor["path"], predecessor["sha256"]
    if not isinstance(path, str) or not isinstance(expected, str) or not expected.startswith("sha256:"):
        raise ValueError("legacy regression predecessor is invalid")
    root = repository_root.resolve()
    evidence = (root / path).resolve()
    try:
        evidence.relative_to(root)
    except ValueError as exc:
        raise ValueError("legacy regression predecessor escapes repository") from exc
    if not evidence.is_file() or _sha(evidence.read_bytes()) != expected:
        raise ValueError("legacy regression predecessor hash is stale")
    try:
        observed = json.loads(evidence.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("legacy regression predecessor is unreadable") from exc
    if (
        not isinstance(observed, dict)
        or observed.get("stage") != "red"
        or not isinstance(observed.get("exit_code"), int)
        or observed["exit_code"] == 0
        or not isinstance(observed.get("commands_attempted"), list)
        or red.get("command_id") not in observed.get("commands_attempted", [])
    ):
        raise ValueError("legacy regression predecessor is not a prior RED")
    return {"path": path, "sha256": expected}


def _load_candidate_identity(plan: Path, slice_id: str) -> dict[str, str]:
    helper = plan / "tools" / "validate_all.py"
    plan_tools = str(helper.parent)
    # Plan validators use repository-local, generic helper module names. Load
    # their complete sibling set in an isolated import transaction so a Skill
    # helper cannot be selected accidentally, then restore the caller's module
    # namespace before returning the identity.
    sibling_modules = (
        "validate_all", "contract_guards", "fixture_checks",
        "candidate_diff_guards", "protocol_guards", "evidence_guards",
        "isolated_test_repository", "slice_guards",
        "validation_result_guards", "slice_freshness", "rmap_checks",
    )
    original_path = list(sys.path)
    prior_modules = {name: sys.modules.get(name) for name in sibling_modules}
    try:
        sys.path.insert(0, plan_tools)
        for name in sibling_modules:
            sys.modules.pop(name, None)
        spec = importlib.util.spec_from_file_location("plan_candidate_identity", helper)
        if spec is None or spec.loader is None:
            raise RuntimeError("plan-local candidate identity helper is unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        identity = module.current_candidate_identity(slice_id)
    finally:
        sys.path[:] = original_path
        for name in sibling_modules:
            sys.modules.pop(name, None)
            if prior_modules[name] is not None:
                sys.modules[name] = prior_modules[name]
    if not isinstance(identity, dict) or not isinstance(identity.get("validator_hash"), str):
        raise ValueError("plan-local candidate identity is invalid")
    return identity


def _candidate_run_id(repository_root: Path, plan_id: str) -> str:
    candidates = sorted((repository_root / "logs" / "tdd-adapter" / plan_id / "RMAP-S6").glob("*/candidate-evidence.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for candidate in candidates:
        try:
            value = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (candidate.parent / "targeted-validation.v1.json").is_file() and os.environ.get("JIMUYUN_TDD_EXECUTION_MODE") != "targeted-validation":
            continue
        if value.get("predicate") == "implementation-candidate" and value.get("status") == "pass":
            return candidate.parent.name
    raise ValueError("current implementation candidate is unavailable")


def _expand(value: Any, *, plan_rel: str, plan_id: str, slice_id: str, run_id: str, candidate_run_id: str) -> str:
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
                       .replace("<run-id>", run_id)
                       .replace("<candidate-run-id>", candidate_run_id))
        if expanded.startswith("logs/tdd-adapter/"):
            return expanded
        if expanded.startswith("tdd-adapter/"):
            return f"logs/{expanded}"
        return f"logs/tdd-adapter/{expanded.removeprefix('logs/')}"
    if kind == "slice_id" and raw == "<slice-id>":
        return slice_id
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


def _generated_red_descriptor(slice_id: str, red: dict[str, Any], allowed_tests: list[str] | None = None) -> dict[str, Any]:
    """Compile VDD failure intent into the current Quick Dev RED invocation."""
    forbidden = {"command_id", "mode", "legacy_predecessor", "prior_red", "receipt", "run_id", "sha256"}
    if forbidden & set(red):
        raise ValueError("VDD-owned RED must not bind execution evidence or a command")
    if set(red) != {"test_selector", "expected_failure_ids"}:
        raise ValueError("VDD RED intent is invalid")
    selector = red["test_selector"]
    failure_ids = red["expected_failure_ids"]
    test_path = selector.split("::", 1)[0] if isinstance(selector, str) else ""
    if (
        not isinstance(selector, str)
        or Path(test_path).is_absolute()
        or ".." in Path(test_path).parts
        or test_path.startswith((".git/", "logs/"))
        or (allowed_tests is not None and not any(fnmatch.fnmatchcase(test_path, pattern) for pattern in allowed_tests))
        or not isinstance(failure_ids, list)
        or not failure_ids
        or any(not isinstance(item, str) or not item for item in failure_ids)
    ):
        raise ValueError("VDD RED intent is invalid")
    argv = ["-3", "-B", "-m", "pytest", selector, "-q"]
    return {
        "id": f"quick-dev-generated-red-{slice_id}",
        "executable": "py",
        "argv": argv,
        "cwd": ".",
        "timeout_seconds": 300,
        "shell": False,
    }


def _execution_fingerprint(
    repository_root: Path,
    selected: dict[str, Any],
    registry: dict[str, Any],
    red: dict[str, Any],
    green: dict[str, Any],
    refactor: list[dict[str, Any]],
    terminal: dict[str, Any],
    validator_hash: str,
) -> tuple[str, str | None]:
    """Bind RED reuse to executable semantics, not the whole contract bytes."""
    intent = selected.get("tdd", {}).get("red", {})
    selector = intent.get("test_selector") if isinstance(intent, dict) else None
    test = (repository_root / selector).resolve() if isinstance(selector, str) else None
    # Historical contracts used a descriptive selector together with a fully
    # registered RED command.  New Quick-Dev-owned RED contracts must point at
    # real test bytes, but preserving this read-only compatibility avoids
    # silently invalidating unrelated existing plans.
    if test is not None and test.is_file():
        try:
            test.relative_to(repository_root.resolve())
        except ValueError as exc:
            raise ValueError("RED test file escapes repository") from exc
        test_hash: str | None = _sha(test.read_bytes())
    elif red["id"].startswith("quick-dev-generated-red-"):
        raise ValueError("RED test file must exist before invocation preparation")
    else:
        test_hash = None
    projection = {
        "slice_id": selected.get("slice_id"),
        "behavior": selected.get("behavior"),
        "depends_on": selected.get("depends_on"),
        "allowed_changes": selected.get("allowed_changes"),
        "red": intent,
        "red_command": red,
        "green_command": green,
        "refactor_commands": refactor,
        "terminal_command": terminal,
        "validator_hash": validator_hash,
        "test_sha256": test_hash,
        "command_registry_schema": registry.get("schema_version"),
    }
    return _sha(json.dumps(projection, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")), test_hash


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
    values = {"plan_rel": plan_rel, "plan_id": contract["plan_id"], "slice_id": slice_id, "run_id": run_id, "candidate_run_id": _candidate_run_id(root, contract["plan_id"]) if slice_id == "RMAP-S7" else ""}
    commands = {item["id"]: item for item in registry["commands"]}
    tdd = selected["tdd"]
    if contract.get("red_execution_owner") == "quick-dev-tdd-adapter":
        predecessor = None
        red_mode = "red"
        allowed_tests = selected.get("allowed_changes", {}).get("tests", [])
        if not isinstance(allowed_tests, list) or any(not isinstance(path, str) for path in allowed_tests):
            raise ValueError("slice test write set is invalid")
        red = _generated_red_descriptor(slice_id, tdd["red"], allowed_tests)
    else:
        predecessor = _legacy_predecessor(root, tdd["red"])
        red_mode = tdd["red"].get("mode", "red")
        red = _descriptor(commands, tdd["red"]["command_id"], **values)
    green = _descriptor(commands, tdd["green"]["command_id"], **values)
    refactor = [_descriptor(commands, item["command_id"], **values) for item in tdd["refactor"]["invocations"]]
    terminal = _descriptor(commands, selected["post_refactor_command_id"], **values)
    preparation = [_descriptor(commands, item["command_id"], **values) for item in selected.get("pre_terminal", [])]
    identity = _load_candidate_identity(plan, slice_id)
    execution_fingerprint, test_hash = _execution_fingerprint(root, selected, registry, red, green, refactor, terminal, identity["validator_hash"])
    authority = plan / contract["authority"]["authority_manifest"]
    context = {
        "plan_id": contract["plan_id"], "slice_id": slice_id, "run_id": run_id,
        "authority_refs": [{"role": "authority-manifest", "path_type": "plan_path", "path": authority.relative_to(plan).as_posix(), "payload_base64": base64.b64encode(authority.read_bytes()).decode("ascii")}],
        "implementation_contract": {"role": "implementation-contract", "path_type": "plan_path", "path": "implementation-contract.v1.json", "payload_base64": base64.b64encode(contract_bytes).decode("ascii")},
        "requirement_ids": selected["requirement_ids"], "acceptance_ids": selected["acceptance_ids"], "source_refs": selected["source_refs"],
        "boundaries": {
            "allowed_write_set": [path for group in selected["allowed_changes"].values() for path in group],
            "stage_write_sets": {"red": [*selected["allowed_changes"].get("tests", []), *selected["allowed_changes"].get("documentation", [])], "green": list(selected["allowed_changes"].get("production", [])), "refactor": [path for group in selected["allowed_changes"].values() for path in group]},
            "forbidden_write_set": [*contract.get("forbidden_changes", []), *selected["forbidden_changes"]],
            "execution_read_set": selected["execution_read_set"],
            "dependency_closure": selected["dependency_closure"],
        },
        "target_command_ids": [red["id"], green["id"], *[item["id"] for item in refactor], terminal["id"]],
        "stage_results": {
            "red": {"schema_version": "rmap.tdd-stage-result.v1", "plan_id": contract["plan_id"], "slice_id": slice_id, "run_id": run_id, "status": "legacy-regression-observed" if red_mode == "legacy-regression" else "prior-red-imported" if red_mode == "prior-red-successor" else "red-observed", "mode": red_mode, "legacy_predecessor": predecessor if red_mode == "legacy-regression" else None, "prior_red": predecessor if red_mode == "prior-red-successor" else None, "command_id": red["id"], "test_selector": tdd["red"]["test_selector"], "test_sha256": test_hash, "expected_failure_ids": tdd["red"]["expected_failure_ids"], "execution_fingerprint": execution_fingerprint, "contract_hash": _sha(contract_bytes), "validator_hash": identity["validator_hash"], "pre_implementation_candidate": identity},
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
