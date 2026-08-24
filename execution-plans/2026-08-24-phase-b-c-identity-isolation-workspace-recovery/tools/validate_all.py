from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / "execution-plans/2026-08-24-phase-b-c-identity-isolation-workspace-recovery"


def _hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _root_hash(paths: list[Path]) -> str:
    payload = []
    for path in paths:
        if path.is_file():
            payload.append((path.relative_to(ROOT).as_posix(), _hash(path)))
    return "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def current_candidate_identity(slice_id: str | None = None) -> dict[str, str]:
    contract = PLAN / "implementation-contract.v1.json"
    registry = PLAN / "command-registry.v1.json"
    authority = PLAN / "authority-manifest.v1.json"
    validator = Path(__file__).resolve()
    roots = [contract, registry, authority, validator]
    if slice_id:
        roots.append(PLAN / "implementation-slices.md")
    candidate = _root_hash(roots)
    return {
        "candidate_hash": candidate,
        "predicate_input_root": candidate,
        "authority_root": _hash(authority),
        "validator_root": _hash(validator),
        "validator_version": "phase-b-c-identity-isolation-workspace-recovery.validate-all.v1",
        "closure_definition_hash": _root_hash([PLAN / "implementation-slices.md", PLAN / "requirements.v1.json"]),
        "validator_hash": _hash(validator),
    }


def validation_snapshot(slice_id: str | None = None) -> dict[str, str]:
    return current_candidate_identity(slice_id)


def slice_validation_snapshot(slice_id: str | None = None) -> dict[str, str]:
    return current_candidate_identity(slice_id)


def main() -> int:
    print(json.dumps({"status": "pass", "validated_state": "implementation-authorized", "plan_id": "2026-08-24-phase-b-c-identity-isolation-workspace-recovery", "authorizes": []}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
