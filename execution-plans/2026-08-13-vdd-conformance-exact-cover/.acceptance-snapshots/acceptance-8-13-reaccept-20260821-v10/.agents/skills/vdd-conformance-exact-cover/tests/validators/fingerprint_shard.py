from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts"))
from conformance import aggregate_fingerprint, shard_id, shard_reuse_fingerprint  # noqa: E402


def main() -> int:
    policy = (ROOT / "_bmad-output/specs/spec-vdd-conformance-exact-cover/execution-policy.md").read_text(encoding="utf-8")
    contracts = (ROOT / "_bmad-output/specs/spec-vdd-conformance-exact-cover/authority-and-data-contracts.md").read_text(encoding="utf-8")
    if "vcec-shard-v1" not in policy or "source_manifest_hash" not in contracts or "shard_reuse_fingerprint" not in contracts:
        return 2
    payload = {"source_manifest_hash":"sha256:" + "a" * 64,"requirements_manifest_hash":"sha256:" + "b" * 64,"validator_identity":"v1","prompt_identity":"p1","policy_identity":"policy1","authoritative_companions":["a"]}
    shard_payload = {"shard_identity": shard_id("manifest.md", "sha256:" + "c" * 64, 0, 1), "source_segments":[[0,1]], "roles":["canonical"], "relationships":[], "requirements_manifest_hash":payload["requirements_manifest_hash"], "validator_identity":"v1","prompt_identity":"p1","policy_identity":"policy1"}
    return 0 if aggregate_fingerprint(payload).startswith("sha256:") and shard_reuse_fingerprint(shard_payload).startswith("sha256:") else 2


if __name__ == "__main__":
    raise SystemExit(main())
