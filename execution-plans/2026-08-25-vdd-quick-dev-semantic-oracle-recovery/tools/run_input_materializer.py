"""Materialize only declared run-local owner inputs from one explicit manifest."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


INPUTS = {
    "S1": ("semantic-intent-input.v1.json", "active-acceptance-manifest.v1.json", "semantic-verification-input.v1.json"),
    "S2": ("descriptor-input.v1.json", "semantic-artifacts.v1.json"),
    "S3": ("execution-input.v1.json", "execution-descriptor.v1.json"),
    "S4": ("coverage-input.v1.json", "process-receipt.v1.json"),
    "S5": ("false-green-fixture-input.v1.json", "acceptance-coverage.v1.json"),
}


def materialize(run_root: Path, slice_id: str) -> None:
    source = run_root / "run-inputs.v1.json"
    value = json.loads(source.read_text(encoding="utf-8"))
    entries = value.get("inputs") if isinstance(value, dict) else None
    expected = set(INPUTS.get(slice_id, ()))
    if (
        value.get("schema_version") != "quick-dev-tdd-adapter.run-inputs.v1"
        or value.get("slice_id") != slice_id or value.get("run_id") != run_root.name
        or not isinstance(entries, dict) or set(entries) != expected
    ):
        raise ValueError("run input manifest does not exactly match slice inputs")
    for name, payload in entries.items():
        if not isinstance(payload, dict):
            raise ValueError("run input payload is invalid")
        (run_root / name).write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--run-root", type=Path, required=True); parser.add_argument("--slice", required=True)
    args = parser.parse_args(); materialize(args.run_root, args.slice)
