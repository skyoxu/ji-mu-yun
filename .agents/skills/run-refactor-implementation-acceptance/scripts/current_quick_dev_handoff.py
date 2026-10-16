"""Read-only current Q8 handoff verification (ADR-0053 and ADR-0058)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

from acceptance_core import InputError

OWNER = Path(__file__).resolve().parents[2] / "quick-dev-tdd-adapter" / "tools"


def _file(root: Path, value: str) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute() or ".." in Path(value).parts:
        raise InputError("current Quick Dev artifact must be repository-relative")
    path = (root / value).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise InputError("current Quick Dev artifact escapes repository") from exc
    if not path.is_file():
        raise InputError("current Quick Dev artifact is missing: " + value)
    return path


def verify_current_handoff(root: Path, binding: dict[str, Any], *, allowed_changed_paths: list[str] | None = None) -> dict[str, Any]:
    required = {"semanticPlan", "receipt", "snapshotRoots", "sourceCommit", "baseCommit"}
    if not isinstance(binding, dict) or set(binding) != required:
        raise InputError("current Quick Dev handoff binding is incomplete")
    for field in ("semanticPlan", "receipt"):
        ref = binding[field]
        if not isinstance(ref, dict) or set(ref) != {"path", "sha256"}:
            raise InputError("current Quick Dev artifact binding is invalid")
        path = _file(root, ref["path"])
        if "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest() != ref["sha256"]:
            raise InputError("current Quick Dev artifact is stale: " + field)
    for field in ("sourceCommit", "baseCommit"):
        if not isinstance(binding[field], str) or not re.fullmatch(r"[0-9a-f]{40}", binding[field]):
            raise InputError("current Quick Dev commit binding is invalid")
    plan = _file(root, binding["semanticPlan"]["path"])
    receipt_path = _file(root, binding["receipt"]["path"])
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if (receipt.get("schema") != "quick-dev.implementation-complete-result.v2"
            or receipt.get("status") != "pass" or receipt.get("authorizes") != []):
        raise InputError("current Quick Dev completion is not a passed implementation result")
    previous = list(sys.path)
    try:
        sys.path.insert(0, str(OWNER))
        from coverage_predicates import publish_implementation_complete
        return publish_implementation_complete(
            workspace=root, semantic_plan=plan, predecessors=receipt["predecessors"],
            snapshot_roots=binding["snapshotRoots"], source_commit=binding["sourceCommit"],
            base_commit=binding["baseCommit"], out=receipt_path,
            profile=receipt["profile"], detached_promotion_binding=receipt.get("detached_promotion_binding"),
            verify_existing=True, allowed_changed_paths=allowed_changed_paths,
        )
    except (ValueError, KeyError, TypeError, OSError) as exc:
        raise InputError("current Quick Dev proof cannot be replayed: " + str(exc)) from exc
    finally:
        sys.path[:] = previous
