#!/usr/bin/env python
"""Validate repository-controlled FastCtx A/B evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


class AbValidationError(ValueError):
    pass


def validate(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise AbValidationError("evidence must be an object")
    required = {"schema_version", "generated_at", "measurement_kind", "limitations", "iterations", "fixture", "baseline", "fastctx_contract", "delta", "high_output_summary"}
    if set(payload) != required or payload["schema_version"] != "fastctx-ab-test.v1":
        raise AbValidationError("evidence root fields or schema version are invalid")
    if payload["measurement_kind"] != "repository-controlled-transport-policy-benchmark" or not payload["limitations"]:
        raise AbValidationError("evidence measurement identity is invalid")
    if payload["iterations"] != {"reads": 5, "writes": 5}:
        raise AbValidationError("acceptance evidence must contain five reads and five writes")
    for name in ("baseline", "fastctx_contract"):
        strategy = payload[name]
        if not isinstance(strategy, dict) or not isinstance(strategy.get("operations"), list) or len(strategy["operations"]) != 5:
            raise AbValidationError(f"{name} operations are invalid")
        for operation in strategy["operations"]:
            if operation.get("write_status") != "written" or operation.get("read_status") not in {"complete", "partial"}:
                raise AbValidationError(f"{name} operation status is invalid")
            if type(operation.get("read_bytes")) is not int or type(operation.get("read_estimated_tokens")) is not int:
                raise AbValidationError(f"{name} operation metrics are invalid")
    summary = payload["high_output_summary"]
    if summary.get("status") not in {"complete", "partial"} or summary.get("summary_bytes", 0) > 12000 or summary.get("redaction_verified") is not True:
        raise AbValidationError("high-output summary evidence is invalid")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    try:
        validate(json.loads(args.evidence.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, json.JSONDecodeError, AbValidationError) as exc:
        print(f"fastctx A/B evidence validation failed: {exc}", file=sys.stderr)
        return 2
    print("fastctx-ab-test.v1: valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
