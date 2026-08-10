#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


HASH_PREFIX = "sha256:"


def canonical_bytes(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def value_hash(value):
    return HASH_PREFIX + hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_hash(path):
    return HASH_PREFIX + hashlib.sha256(path.read_bytes()).hexdigest()


def ensure_within(path, parent, label):
    resolved = path.resolve()
    try:
        resolved.relative_to(parent.resolve())
    except ValueError as exc:
        raise RuntimeError(f"{label} escaped its allowed root: {path}") from exc
    return resolved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    request_path = Path(args.request).resolve()
    attempt_dir = request_path.parent
    output = ensure_within(Path(args.out), attempt_dir, "Handshake output")
    request = json.loads(request_path.read_text(encoding="utf-8"))
    run_dir = Path(request["runDirectory"]).resolve()
    artifact_root = (run_dir / "artifact-view").resolve()
    view_path = ensure_within(
        run_dir / request["artifactViewManifestPath"], artifact_root, "Artifact View manifest"
    )
    if file_hash(view_path) != request["artifactViewManifestHash"]:
        raise RuntimeError("Artifact View manifest hash mismatch")
    view = json.loads(view_path.read_text(encoding="utf-8"))
    checked = []
    for entry in view.get("entries", []):
        snapshot = ensure_within(run_dir / entry["snapshotPath"], artifact_root, "Snapshot")
        if not snapshot.is_file() or file_hash(snapshot) != entry["snapshotSha256"]:
            raise RuntimeError(f"Access handshake failed for {entry['snapshotPath']}")
        checked.append(
            {"originalPath": entry["originalPath"], "snapshotSha256": entry["snapshotSha256"]}
        )
    payload = {
        "schemaVersion": "bootstrap-access-handshake.v1",
        "reviewId": request["reviewId"],
        "inputHash": request["inputHash"],
        "role": request["role"],
        "artifactViewManifestHash": request["artifactViewManifestHash"],
        "checkedArtifacts": checked,
        "checkedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    payload["handshakeHash"] = value_hash(
        {key: value for key, value in payload.items() if key != "checkedAt"}
    )
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    os.replace(temporary, output)
    print(payload["handshakeHash"])


if __name__ == "__main__":
    main()
