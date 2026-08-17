#!/usr/bin/env python3
"""Classify Quick Dev inputs before selecting an implementation backend."""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
REPOSITORY_ROOT = SCRIPT_PATH.parents[4]
SC_ROOT = REPOSITORY_ROOT / "scripts" / "sc"
if str(SCRIPT_PATH.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT_PATH.parent))
if str(SC_ROOT) not in sys.path:
    sys.path.insert(0, str(SC_ROOT))

import workflow_model_routing as model_routing
from _schema_runtime import schema_errors


class InputRoutingError(ValueError):
    """Raised when an explicit Quick Dev input is unsafe or incomplete."""


CALLER_LANES = {
    "bmad-quick-dev": "standalone_requirement",
    "quick-dev-tdd-adapter": "strict_tdd_plan",
    "direct-plan-implementation": "verified_compact_vdd",
}


def enforce_caller_lane(route: dict[str, Any], caller: str) -> None:
    """Prevent a workflow implementation backend from consuming another lane."""
    expected_lane = CALLER_LANES.get(caller)
    if expected_lane is None:
        raise InputRoutingError("Quick Dev caller is unknown")
    if route.get("lane") != expected_lane:
        raise InputRoutingError(
            f"{caller} cannot consume {route.get('lane')}; "
            f"handoff required to {route.get('backend')}"
        )


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InputRoutingError(f"{label} is unreadable or invalid JSON") from exc
    if not isinstance(value, dict):
        raise InputRoutingError(f"{label} must be a JSON object")
    return value


def _within(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise InputRoutingError(f"{label} escapes the repository") from exc
    return resolved


def _strict_contract_lane(target: Path, contract_path: Path) -> dict[str, Any]:
    contract = _read_json(contract_path, "implementation contract")
    schema_version = contract.get("schema_version")
    canonical_version = "jimuyun.implementation-contract.v1"
    plan_owned_version = re.compile(
        r"^[a-z0-9][a-z0-9.-]*\.implementation-contract\.(v1|v2)$"
    )
    if schema_version == canonical_version:
        schema_name = "implementation-contract.v1.schema.json"
    elif isinstance(schema_version, str) and plan_owned_version.fullmatch(schema_version):
        version = schema_version.rsplit(".", 1)[-1]
        schema_name = f"plan-owned-implementation-contract.{version}.schema.json"
    else:
        raise InputRoutingError(
            "implementation contract is schema-invalid: unsupported schema_version"
        )
    schema_path = (
        REPOSITORY_ROOT
        / ".agents/skills/quick-dev-tdd-adapter/schemas"
        / schema_name
    )
    schema = _read_json(schema_path, "implementation contract schema")
    errors = schema_errors(schema, contract)
    if errors:
        raise InputRoutingError(
            "implementation contract is schema-invalid: " + "; ".join(errors[:5])
        )
    plan_id = contract.get("plan_id")
    slices = contract.get("slices")
    if (
        not isinstance(plan_id, str)
        or not plan_id
        or not isinstance(slices, list)
        or any(
            not isinstance(item, dict)
            or not isinstance(item.get("slice_id"), str)
            or not item["slice_id"]
            for item in slices
        )
    ):
        raise InputRoutingError("implementation contract is structurally invalid")
    return {
        "lane": "strict_tdd_plan",
        "backend": "quick-dev-tdd-adapter",
        "planId": plan_id,
        "input": target.relative_to(REPOSITORY_ROOT).as_posix(),
    }


def _compact_lane(target: Path) -> dict[str, Any]:
    required = {
        "index": target / "00-index.md",
        "state": target / "plan-state.v1.json",
        "requirements": target / "requirements.v1.json",
        "baseline": target / "baseline-and-scope.v1.json",
        "planValidator": target / "tools" / "validate_plan.py",
        "implementationValidator": target / "tools" / "validate_implementation.py",
        "completionReport": target / "95-implementation-evolution-and-completion-report.md",
    }
    missing = sorted(name for name, path in required.items() if not path.is_file())
    if missing:
        raise InputRoutingError(
            "contract-free plan is not a verified compact VDD input: " + ", ".join(missing)
        )
    state = _read_json(required["state"], "compact VDD state")
    requirements = _read_json(required["requirements"], "compact VDD requirements")
    baseline = _read_json(required["baseline"], "compact VDD baseline")
    plan_ids = {state.get("plan_id"), requirements.get("plan_id"), baseline.get("plan_id")}
    if len(plan_ids) != 1 or not isinstance(next(iter(plan_ids)), str):
        raise InputRoutingError("compact VDD plan identity bindings do not match")
    plan_id = next(iter(plan_ids))
    slices = state.get("slices")
    requirement_rows = requirements.get("requirements")
    acceptance_rows = requirements.get("acceptance")
    plan_slices = requirements.get("slices")
    git_binding = baseline.get("git")
    if (
        state.get("schema_version") != "vdd.plan-state.v1"
        or state.get("state_owner") != "terminal-validator"
        or state.get("state") not in {
            "plan-ready", "implementation-authorized", "implementation-complete",
            "acceptance-passed",
        }
        or state.get("profile") != "self-hosted"
        or state.get("authorizes") != [state.get("state")]
        or not isinstance(slices, list)
        or not slices
        or any(not isinstance(item, dict) or not item.get("id") for item in slices)
        or not all(isinstance(value, list) and value for value in (requirement_rows, acceptance_rows, plan_slices))
        or requirements.get("schema_version") is None
        or requirements.get("profile") != "self-hosted"
        or requirements.get("authorizes") != []
        or baseline.get("schema_version") is None
        or baseline.get("authorizes") != []
        or not isinstance(git_binding, dict)
        or not isinstance(git_binding.get("head"), str)
        or len(git_binding["head"]) != 40
        or not isinstance(baseline.get("scope_roots"), list)
        or not baseline["scope_roots"]
    ):
        raise InputRoutingError("compact VDD state or authorization boundary is invalid")
    if state["state"] == "implementation-complete" and any(
        item.get("status") != "completed" for item in slices
    ):
        raise InputRoutingError("compact VDD completed state has incomplete slices")
    for label in ("planValidator", "implementationValidator"):
        try:
            tree = ast.parse(required[label].read_text(encoding="utf-8"))
        except (OSError, UnicodeError, SyntaxError) as exc:
            raise InputRoutingError(f"compact VDD {label} is unreadable or invalid") from exc
        functions = {
            node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        if not {"main"}.issubset(functions) or (
            label == "planValidator" and "validate" not in functions
        ):
            raise InputRoutingError(f"compact VDD {label} lacks its terminal validation entrypoint")
    if state["state"] != "implementation-complete":
        completed = subprocess.run(
            [sys.executable, str(required["planValidator"])],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=120,
        )
        try:
            validation = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise InputRoutingError("compact VDD plan validator returned invalid JSON") from exc
        if (
            completed.returncode != 0
            or not isinstance(validation, dict)
            or validation.get("status") != "pass"
            or validation.get("validated_state") != state["state"]
            or validation.get("plan_id", plan_id) != plan_id
        ):
            raise InputRoutingError("compact VDD plan validator did not verify current state")
    return {
        "lane": "verified_compact_vdd",
        "backend": "direct-plan-implementation",
        "planId": plan_id,
        "input": target.relative_to(REPOSITORY_ROOT).as_posix(),
        "requiredValidation": [
            required["planValidator"].relative_to(REPOSITORY_ROOT).as_posix(),
            required["implementationValidator"].relative_to(REPOSITORY_ROOT).as_posix(),
        ],
    }


def route_input(
    repository_root: Path,
    input_path: Path,
    facts: dict[str, Any],
    *,
    requested_class: str | None = None,
) -> dict[str, Any]:
    global REPOSITORY_ROOT
    REPOSITORY_ROOT = repository_root.resolve()
    target = _within(input_path, REPOSITORY_ROOT, "Quick Dev input")
    execution_root = (REPOSITORY_ROOT / "execution-plans").resolve()
    if target.is_file():
        try:
            target.relative_to(execution_root)
        except ValueError:
            pass
        else:
            raise InputRoutingError("a standalone requirement cannot be inside execution-plans")
        if target.suffix.lower() != ".md":
            raise InputRoutingError("standalone Quick Dev input must be Markdown")
        try:
            requirement_text = target.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise InputRoutingError("standalone Quick Dev input must be readable UTF-8") from exc
        if not requirement_text.strip():
            raise InputRoutingError("standalone Quick Dev input must not be empty")
        lane = {
            "lane": "standalone_requirement",
            "backend": "ordinary-quick-dev",
            "planId": None,
            "input": target.relative_to(REPOSITORY_ROOT).as_posix(),
        }
    elif target.is_dir():
        try:
            target.relative_to(execution_root)
        except ValueError as exc:
            raise InputRoutingError("plan directory must stay under execution-plans") from exc
        contract_path = target / "implementation-contract.v1.json"
        lane = (
            _strict_contract_lane(target, contract_path)
            if contract_path.exists()
            else _compact_lane(target)
        )
    else:
        raise InputRoutingError("Quick Dev input does not exist")
    try:
        decision = model_routing.quick_dev_decision(
            facts, requested_class=requested_class
        )
    except model_routing.RoutingError as exc:
        raise InputRoutingError(str(exc)) from exc
    return {
        "schemaVersion": "jimuyun.quick-dev-input-route.v1",
        **lane,
        "modelDecision": decision,
        "authorizes": [],
        "doesNotAuthorize": [
            "implementation-acceptance", "protected-handoff", "release", "commit", "done"
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", default=str(REPOSITORY_ROOT))
    parser.add_argument("--input", required=True)
    parser.add_argument("--facts", required=True)
    parser.add_argument("--requested-class")
    parser.add_argument("--caller", choices=sorted(CALLER_LANES), required=True)
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    try:
        facts = _read_json(Path(args.facts), "Quick Dev facts")
        result = route_input(
            Path(args.repository_root),
            Path(args.input),
            facts,
            requested_class=args.requested_class,
        )
        if args.caller:
            enforce_caller_lane(result, args.caller)
    except InputRoutingError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8", newline="\n")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
