#!/usr/bin/env python3
"""Freeze a hash-bound baseline manifest for clarification control assets."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--closure", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    root = Path(args.repository_root).resolve()
    closure = json.loads(Path(args.closure).read_text(encoding="utf-8"))
    verifier = closure.get("verifier", closure)
    if closure.get("status") not in {None, "PASS"} or verifier.get("schema_version") != "vdd.clarification-closure-verifier.v1":
        raise SystemExit("VDD-CLARIFICATION-BASELINE-CLOSURE")
    entries = []
    for item in verifier["observations"]:
        identity = item.get("identity")
        if not item.get("exists") or not isinstance(identity, dict):
            raise SystemExit("VDD-CLARIFICATION-BASELINE-IDENTITY")
        entries.append({"owner_path": item["path"], **identity})
    manifest = {
        "schema_version": "vdd.clarification-baseline.v2",
        "closure_hash": "sha256:" + hashlib.sha256(
            json.dumps(verifier, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "entries": entries,
    }
    manifest["manifest_hash"] = "sha256:" + hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    Path(args.out).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
