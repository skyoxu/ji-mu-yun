from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PLAN_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLAN_ROOT.parents[1]


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def refresh_contract() -> None:
    path = PLAN_ROOT / "implementation-contract.v1.json"
    contract = read_json(path)
    source_hashes = contract["authority"]["source_hashes"]
    for relative in source_hashes:
        source_hashes[relative] = sha256_file((PLAN_ROOT / relative).resolve())
    write_json(path, contract)


def refresh_deltas() -> None:
    path = PLAN_ROOT / "schemas" / "spec-deltas.v1.json"
    document = read_json(path)
    contract_hash = sha256_file(PLAN_ROOT / "implementation-contract.v1.json")
    for delta in document["deltas"]:
        delta["proposed_contract_hash"] = contract_hash
    write_json(path, document)


def refresh_quality() -> None:
    path = PLAN_ROOT / "schemas" / "requirement-quality.v1.json"
    document = read_json(path)
    document["requirements_hash"] = sha256_file(PLAN_ROOT / "schemas" / "requirements.v1.json")
    document["acceptance_contracts_hash"] = sha256_file(
        PLAN_ROOT / "schemas" / "acceptance-contracts.v1.json"
    )
    document["validator_version"] = "rmap-plan-validator.v2"
    document["generated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    write_json(path, document)


def refresh_coverage() -> None:
    path = PLAN_ROOT / "schemas" / "source-coverage.v1.json"
    document = read_json(path)
    for source in document["sources"]:
        source["sha256"] = sha256_file((PLAN_ROOT / source["path"]).resolve())
    write_json(path, document)


def refresh_authority_manifest() -> None:
    path = PLAN_ROOT / "schemas" / "authority-manifest.v1.json"
    manifest = read_json(path)
    for entries in manifest["categories"].values():
        for entry in entries:
            entry["sha256"] = sha256_file(REPOSITORY_ROOT / entry["path"])
    write_json(path, manifest)


def refresh_clarification() -> None:
    path = PLAN_ROOT / "schemas" / "clarification-decisions.v1.json"
    document = read_json(path)
    run_id = "clarification-20260717T090544Z"
    state_path = REPOSITORY_ROOT / "logs" / "vdd-clarifications" / "2026-07-15-repository-maintenance-tdd-adapter-f6d1143a" / run_id / "state.json"
    source = next(item for item in document["sources"] if item["run_id"] == run_id)
    source["state_sha256"] = sha256_file(state_path)
    write_json(path, document)


def main() -> int:
    refresh_clarification()
    refresh_contract()
    refresh_coverage()
    refresh_deltas()
    refresh_quality()
    refresh_authority_manifest()
    print("Refreshed repository-maintenance plan projections")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
