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


def validate_artifacts(mapping: Path) -> list[dict[str, object]]:
    """Validate every derived artifact named by the repository mapping.

    Derived artifacts are evidence only: the concrete field is ``authorizes``
    and it must be present as an empty array. Missing, malformed, or non-empty
    values fail closed instead of being normalized into an authorization set.
    """
    document = json.loads(mapping.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("artifact mapping is not an object")
    required_types = document.get("required_artifact_types")
    artifacts = document.get("artifacts")
    if not isinstance(required_types, list) or not required_types or not all(isinstance(value, str) and value for value in required_types):
        raise ValueError("artifact mapping required_artifact_types is invalid")
    if not isinstance(artifacts, list):
        raise ValueError("artifact mapping artifacts is invalid")
    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    for item in artifacts:
        if not isinstance(item, dict) or set(item) != {"artifact_type", "path"}:
            raise ValueError("artifact mapping entry is invalid")
        kind, raw_path = item["artifact_type"], item["path"]
        if not isinstance(kind, str) or not kind or kind in seen or not isinstance(raw_path, str) or not raw_path:
            raise ValueError("artifact mapping entry identity is invalid")
        seen.add(kind)
        path = Path(raw_path)
        if not path.is_file():
            raise ValueError(f"named artifact is missing or unreadable: {raw_path}")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"named artifact is malformed: {raw_path}") from exc
        if not isinstance(value, dict) or value.get("artifact_type") != kind:
            raise ValueError(f"named artifact metadata is invalid: {raw_path}")
        if value.get("authorizes") != []:
            raise ValueError(f"named artifact must expose authorizes=[] (got {value.get('authorizes')!r}): {raw_path}")
        rows.append({"artifact_type": kind, "path": raw_path, "authorizes": []})
    if set(required_types) != seen:
        missing = sorted(set(required_types) - seen)
        extra = sorted(seen - set(required_types))
        raise ValueError(f"artifact mapping coverage mismatch: missing={missing}, extra={extra}")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--validator", type=Path, required=True)
    args = parser.parse_args()
    try:
        validate(json.loads(args.receipt.read_text(encoding="utf-8")), args.manifest, args.mapping, args.validator)
        rows = validate_artifacts(args.mapping)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "blocked", "family": "artifact_integrity_failure", "detail": str(exc), "authorizes": []}))
        return 2
    print(json.dumps({"status": "preflight_passed", "artifacts": rows, "non_empty_count": 0, "authorizes": []}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
