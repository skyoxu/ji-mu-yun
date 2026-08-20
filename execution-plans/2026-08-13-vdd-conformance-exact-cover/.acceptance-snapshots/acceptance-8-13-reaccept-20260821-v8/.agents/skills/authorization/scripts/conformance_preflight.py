"""Verify a current exact-cover receipt without publishing lifecycle state."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def validate(receipt: dict[str, object], manifest: Path, mapping: Path, validator: Path) -> None:
    required = {"schema_version", "status", "errors", "authorizes", "source_manifest_hash", "source_manifest_canonical_hash", "requirements_manifest_hash", "validator_identity"}
    if not required.issubset(receipt) or receipt.get("schema_version") != "vdd-conformance-result.v1":
        raise ValueError("conformance receipt schema is invalid")
    if receipt.get("status") != "conformant" or receipt.get("errors") != [] or receipt.get("authorizes") != []:
        raise ValueError("conformance receipt is not current and conformant")
    manifest_value = json.loads(manifest.read_text(encoding="utf-8"))
    expected = {
        "source_manifest_hash": digest(manifest),
        "source_manifest_canonical_hash": manifest_value.get("canonical_hash"),
        "requirements_manifest_hash": digest(mapping),
        "validator_identity": digest(validator),
    }
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise ValueError("conformance receipt bindings are stale or mismatched")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--validator", type=Path, required=True)
    args = parser.parse_args()
    try:
        validate(json.loads(args.receipt.read_text(encoding="utf-8")), args.manifest, args.mapping, args.validator)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "blocked", "family": "artifact_integrity_failure", "detail": str(exc), "authorizes": []}))
        return 2
    print(json.dumps({"status": "preflight_passed", "authorizes": []}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
