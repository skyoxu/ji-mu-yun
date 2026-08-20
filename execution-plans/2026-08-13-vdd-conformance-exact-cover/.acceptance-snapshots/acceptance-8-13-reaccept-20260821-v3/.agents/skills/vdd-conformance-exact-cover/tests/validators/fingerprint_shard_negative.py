from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts"))
from conformance import aggregate_fingerprint, shard_id  # noqa: E402


def main() -> int:
    try:
        aggregate_fingerprint({"source_manifest_hash": "sha256:" + "a" * 64})
    except ValueError:
        return 1 if shard_id("manifest", "sha256:" + "a" * 64, 0, 1) != shard_id("manifest", "sha256:" + "a" * 64, 0, 2) else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
