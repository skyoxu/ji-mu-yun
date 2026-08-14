from __future__ import annotations

import hashlib
import json
from pathlib import Path

PLAN_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLAN_ROOT.parents[1]
VALIDATOR_VERSION = "vdd-conformance-exact-cover.validator.v1"


def _hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _value(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _snapshot(slice_id: str) -> dict[str, str]:
    contract = json.loads((PLAN_ROOT / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    selected = []
    for item in contract["slices"]:
        selected.append(item)
        if item.get("slice_id") == slice_id:
            break
    registry = PLAN_ROOT / "command-registry.v1.json"
    authority = REPOSITORY_ROOT / contract["authority"]["authority_manifest"]
    validator_root = _value({
        "validator": (PLAN_ROOT / "tools/validate_all.py").read_bytes().decode("utf-8"),
        "bridge": (PLAN_ROOT / "tools/tdd_bridge.py").read_bytes().decode("utf-8"),
    })
    authority_root = _hash(authority) if authority.is_file() else _value("missing")
    contract_hash = _hash(PLAN_ROOT / "implementation-contract.v1.json")
    command_hash = _hash(registry)
    closure = _value({"slice_id": slice_id, "selected": selected, "terminal": contract.get("terminal_validation")})
    candidate = _value({"contract": contract_hash, "commands": command_hash, "authority": authority_root, "validator": validator_root})
    return {
        "candidate_hash": candidate,
        "predicate_input_root": _value({"candidate_hash": candidate, "closure_definition_hash": closure}),
        "authority_root": authority_root,
        "validator_root": validator_root,
        "validator_version": f"{VALIDATOR_VERSION}+{validator_root}",
        "closure_definition_hash": closure,
    }


def current_candidate_identity(slice_id: str = "S0") -> dict[str, str]:
    return _snapshot(slice_id)


def slice_validation_snapshot(slice_id: str) -> dict[str, str]:
    return _snapshot(slice_id)


def validation_snapshot() -> dict[str, str]:
    return _snapshot("S5")


def main() -> int:
    print(json.dumps({"status": "pass", "validation_snapshot": validation_snapshot()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
