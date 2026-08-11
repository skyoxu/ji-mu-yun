#!/usr/bin/env python
"""Small integration helper for Skill-owned workflow entrypoints."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from skill_input_consumption import read_json
from validate_skill_input_consumption import validate_receipt


def require_ready_skill_input(
    *,
    receipt_path: Path,
    repository_root: Path,
    contract_path: Path,
    consumer: str,
    operation: str,
) -> dict[str, Any]:
    """Fail closed unless a receipt is ready for this exact Skill operation."""
    result = validate_receipt(receipt_path.resolve(), repository_root.resolve(), contract_path.resolve(), require_ready=True)
    receipt = read_json(receipt_path.resolve())
    if receipt.get("consumer") != consumer or receipt.get("operation") != operation:
        raise ValueError("skill input receipt consumer or operation does not match route")
    context_ref = receipt["context_artifact"]
    context_path = (receipt_path.resolve().parent / context_ref["path"]).resolve()
    if not context_path.is_file():
        raise ValueError("ready Skill input context artifact is missing")
    return {
        **result,
        "context_artifact": context_path,
        "context_artifact_hash": context_ref["sha256"],
        "binding_hash": receipt["binding_hash"],
    }
