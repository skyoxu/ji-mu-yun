"""Write a predecessor judge freeze from a real S3 receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write(receipt: Path, output: Path) -> dict:
    if not receipt.is_file():
        raise ValueError("predecessor receipt is missing")
    value = json.loads(receipt.read_text(encoding="utf-8"))
    judge_id = value.get("receipt", {}).get("judge_id") if isinstance(value.get("receipt"), dict) else None
    run_id = value.get("run_id")
    if (value.get("producer") != "independent-judge" or value.get("slice_id") != "S3"
            or value.get("status") != "pass" or not isinstance(run_id, str)
            or not run_id.startswith("RUN-") or judge_id in {None, "sut", "candidate"}):
        raise ValueError("predecessor receipt is not an independent S3 pass")
    evidence = value.get("evidence_sha256")
    body = {key: item for key, item in value.items() if key != "evidence_sha256"}
    digest = "sha256:" + hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if evidence != digest:
        raise ValueError("predecessor receipt evidence hash is stale")
    result = {"schema_version": "predecessor-judge-freeze.v1", "producer": "independent-judge", "status": "pass", "slice_id": "S3", "run_id": run_id, "receipt_path": receipt.as_posix(), "receipt_sha256": _sha(receipt), "judge_id": judge_id}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    write(args.receipt, args.output)
