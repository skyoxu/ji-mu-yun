#!/usr/bin/env python3
"""Resolve only content from a verified committed clarification generation."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


def load_promotion_module():
    path = Path(__file__).with_name("clarification_promotion.py")
    spec = importlib.util.spec_from_file_location("vdd_clarification_promotion_resolver", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("VDD-CLARIFICATION-RESOLVER-LOADER")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resolve(run_dir: Path, authority_path: str) -> tuple[bool, str, Path | None]:
    promotion = load_promotion_module()
    valid, message, manifest = promotion.resolve_committed_generation(run_dir)
    if not valid or not isinstance(manifest, dict):
        return False, message or "committed generation is unavailable", None
    matches = [item for item in manifest.get("entries", []) if item.get("path") == authority_path]
    if len(matches) != 1:
        return False, "authority path is not uniquely present in committed generation", None
    candidate = run_dir / "generations" / manifest["promotion_id"] / "files" / authority_path
    if not candidate.is_file():
        return False, "committed generation content is missing", None
    return True, "", candidate


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve a committed clarification generation path.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--authority-path", required=True)
    args = parser.parse_args()
    try:
        valid, message, path = resolve(Path(args.run_dir).resolve(), args.authority_path)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        valid, message, path = False, str(exc), None
    print(json.dumps({
        "schema_version": "vdd.clarification-authority-resolution.v1",
        "status": "PASS" if valid else "FAIL",
        "path": str(path) if path is not None else None,
        "message": message,
    }))
    return 0 if valid else 1


if __name__ == "__main__":
    sys.exit(main())
