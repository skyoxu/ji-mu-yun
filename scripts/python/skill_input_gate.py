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
    # ADR-0060: live consumers cannot opt into historical v1 by filename.
    if receipt_path.name != "current.v1.json":
        raise ValueError("live consumer requires a v2 current pointer; v1 is historical only")
    from skill_input_v2 import require_current
    from skill_input_retention import register_consumer_use
    result = require_current(repository_root, receipt_path, consumer=consumer,
                             operation=operation, contract_path=contract_path)
    # Persist protection before returning control to any downstream producer.
    use = register_consumer_use(receipt_path.parent, repository_root,
                               consumer=consumer, operation=operation, generation_id=result["generation_id"])
    return {**result, "generation_id": use["generation_id"],
            "retention_reference": use["reference_id"]}
