"""Static anti-fabrication guard for a planned/actual RED selector.

The initial Chapter 4/5/6 execution envelope is Windows + pytest/Python.  Before
any public RED process launch, require the bound Python test to import and call at
least one declared Python production owner.  This is intentionally conservative:
an unsupported/dynamic binding is a VDD/RED-contract repair, never an assumed
expected RED.
"""
from __future__ import annotations

import ast
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from runtime_evidence import safe_relative

_FORBIDDEN_EVIDENCE_TOKENS = (
    "semantic-plan-bundle.v1.json",
    "compiler-state.v1.json",
    "implementation-complete",
    "slice-ready.json",
    "canonical-evidence/",
    "logs/tdd-adapter/",
)


def _slice(bundle: Mapping[str, Any], slice_id: str) -> Mapping[str, Any]:
    values = bundle.get("slices")
    if not isinstance(values, list):
        raise ValueError("semantic plan slices missing")
    matches = [item for item in values if isinstance(item, Mapping) and item.get("slice_id") == slice_id]
    if len(matches) != 1:
        raise ValueError("slice identity missing or ambiguous")
    return matches[0]


def _module_for_owner(path: str) -> str | None:
    relative = safe_relative(path)
    if not relative.endswith(".py"):
        return None
    module = relative[:-3].replace("/", ".")
    if module.endswith(".__init__"):
        module = module[: -len(".__init__")]
    return module or None


def _root_name(node: ast.AST) -> str | None:
    current = node
    while isinstance(current, ast.Attribute):
        current = current.value
    return current.id if isinstance(current, ast.Name) else None


def _constant_failure(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert) and isinstance(node.test, ast.Constant) and node.test.value is False:
            return True
    return False


def _self_judging_source(source: str) -> str | None:
    lowered = source.lower().replace("\\", "/")
    for token in _FORBIDDEN_EVIDENCE_TOKENS:
        if token in lowered:
            return token
    return None


def _owner_called(tree: ast.AST, module: str) -> bool:
    direct_aliases: set[str] = set()
    module_roots: set[str] = set()
    module_leaf_aliases: set[str] = set()
    parent, _, leaf = module.rpartition(".")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == module or alias.name.startswith(module + "."):
                    module_roots.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            imported_from = node.module or ""
            if imported_from == module:
                for alias in node.names:
                    if alias.name != "*":
                        direct_aliases.add(alias.asname or alias.name)
            elif parent and imported_from == parent:
                for alias in node.names:
                    if alias.name == leaf:
                        module_leaf_aliases.add(alias.asname or alias.name)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id in direct_aliases:
            return True
        root = _root_name(node.func)
        if root and (root in module_roots or root in module_leaf_aliases):
            return True
    return False


def validate_red_production_entry(
    *,
    workspace: Path,
    bundle: Mapping[str, Any],
    slice_id: str,
    descriptor: Mapping[str, Any],
) -> dict[str, Any]:
    if descriptor.get("stage") != "red":
        raise ValueError("production-entry guard only accepts RED descriptor")
    if descriptor.get("slice_id") != slice_id or descriptor.get("plan_id") != bundle.get("plan_id"):
        raise ValueError("RED descriptor plan/slice identity mismatch")

    selected = _slice(bundle, slice_id)
    owners = [str(item) for item in selected.get("production_owners", []) if isinstance(item, str) and item]
    python_owners = [(owner, module) for owner in owners if (module := _module_for_owner(owner))]
    if not python_owners:
        raise ValueError("RED production-entry guard has no supported Python production owner")

    candidate_refs: list[str] = []
    for raw in [*descriptor.get("target_refs", []), *selected.get("execution_snapshot_paths", [])]:
        if not isinstance(raw, str):
            continue
        ref = safe_relative(raw)
        if ref.endswith(".py") and ref not in owners and ref not in candidate_refs:
            candidate_refs.append(ref)
    if not candidate_refs:
        raise ValueError("RED production-entry guard found no bound Python test source")

    root = workspace.resolve()
    parsed: list[tuple[str, str, ast.AST]] = []
    for ref in candidate_refs:
        path = (root / ref).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError("RED test path escapes repository") from exc
        if not path.is_file() or path.is_symlink():
            continue
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=ref)
        except SyntaxError as exc:
            raise ValueError(f"RED test source is not valid Python: {ref}") from exc
        if _constant_failure(tree):
            raise ValueError(f"RED test contains unconditional assert False: {ref}")
        self_judging = _self_judging_source(source)
        if self_judging:
            raise ValueError(f"RED test reads plan/evidence completion bytes: {ref}:{self_judging}")
        parsed.append((ref, source, tree))

    if not parsed:
        raise ValueError("RED test source is missing; run author-red first")

    bindings: list[dict[str, str]] = []
    for owner, module in python_owners:
        for ref, _source, tree in parsed:
            if _owner_called(tree, module):
                bindings.append({"production_owner": owner, "module": module, "test_ref": ref})
    if not bindings:
        raise ValueError("RED test does not import and call any declared production owner")

    return {
        "schema": "quick-dev.red-production-entry-guard.v1",
        "status": "pass",
        "slice_id": slice_id,
        "bindings": bindings,
        "test_refs": [item[0] for item in parsed],
        "fixed_failure_detected": False,
        "self_judging_detected": False,
        "model_called": False,
        "tests_executed": False,
        "writes_performed": False,
        "authorizes": [],
    }
