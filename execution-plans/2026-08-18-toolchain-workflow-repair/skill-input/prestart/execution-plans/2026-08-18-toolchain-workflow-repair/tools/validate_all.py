"""Plan-local, deterministic candidate identity for Quick Dev entry."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


PLAN_ID = "toolchain-workflow-repair"
SLICES = {f"W{index}" for index in range(7)}


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def current_candidate_identity(slice_id: str) -> dict[str, str]:
    if slice_id not in SLICES:
        raise ValueError("unknown slice")
    plan = Path(__file__).resolve().parents[1]
    contract = plan / "implementation-contract.v1.json"
    registry = plan / "command-registry.v1.json"
    authority = plan / "authority-manifest.v1.json"
    for path in (contract, registry, authority):
        if not path.is_file() or path.is_symlink():
            raise ValueError("candidate identity input is missing or unsafe")
    selected = json.loads(contract.read_text(encoding="utf-8"))
    slice_contract = next((item for item in selected["slices"] if item["slice_id"] == slice_id), None)
    if slice_contract is None:
        raise ValueError("slice is missing")
    validator = Path(__file__)
    projection = {
        "slice_id": slice_id,
        "contract": _sha(contract.read_bytes()),
        "registry": _sha(registry.read_bytes()),
        "authority": _sha(authority.read_bytes()),
        "slice": slice_contract,
        "validator": _sha(validator.read_bytes()),
    }
    return {
        "candidate_hash": _sha(_canonical(projection)),
        "validator_hash": projection["validator"],
        "contract_hash": projection["contract"],
        "command_registry_hash": projection["registry"],
        "authority_manifest_hash": projection["authority"],
    }
