"""Publish current conformance and external semantic-review input artifacts."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / "execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery"
GOV = PLAN / "governance"
sys.path.insert(0, str(ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts"))
from conformance import semantic_handoff_hash  # noqa: E402


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def ref(path: Path) -> dict[str, str]:
    return {"path": path.resolve().relative_to(ROOT.resolve()).as_posix(), "sha256": sha(path)}


def require_head_bytes(path: Path) -> None:
    """Refuse to bind HEAD to dirty or differently normalized candidate bytes."""
    root = ROOT.resolve()
    target = path.resolve()
    try:
        relative = target.relative_to(root).as_posix()
    except ValueError as exc:
        raise RuntimeError(f"candidate input escapes repository: {path}") from exc
    committed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", f"HEAD:{relative}"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
    )
    normalized = subprocess.run(
        ["git", "-C", str(root), "hash-object", "--path", relative, str(target)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
    )
    if committed.returncode != 0 or normalized.returncode != 0 or committed.stdout.strip() != normalized.stdout.strip():
        raise RuntimeError(f"candidate input must match HEAD exactly: {relative}")


def write_new(path: Path, value: object) -> None:
    encoded = (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != encoded:
            raise FileExistsError(f"refusing to replace existing artifact: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(encoded)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--mapping", type=Path, default=GOV / "requirements-acceptance-mapping.v1.reviewed.json")
    parser.add_argument("--manifest", type=Path, default=GOV / "vdd-source-freeze-manifest.v1.external-bd210cef-successor.json")
    parser.add_argument("--skill-input-receipt", type=Path, default=PLAN / "skill-input/repair-round-4/receipt.v1.json")
    args = parser.parse_args()
    mapping = args.mapping.resolve()
    manifest = args.manifest.resolve()
    current_receipt = args.skill_input_receipt.resolve()
    for candidate_input in (
        PLAN / "implementation-contract.v1.json",
        PLAN / "command-registry.v1.json",
        manifest,
        mapping,
        current_receipt,
    ):
        require_head_bytes(candidate_input)
    conformance = GOV / f"vdd-conformance-result.v1.{args.tag}.json"
    review_input = GOV / f"external-semantic-review-input.v1.{args.tag}.json"
    validator = ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts/validate_conformance.py"
    result = subprocess.run(
        ["python", str(validator), "--repository-root", str(ROOT), "--manifest", str(manifest), "--mapping", str(mapping)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False,
    )
    if not result.stdout.strip():
        raise RuntimeError(result.stderr)
    conformance_value = json.loads(result.stdout)
    write_new(conformance, conformance_value)
    handoff = conformance_value.get("semantic_handoff") or {}
    frozen_authority = handoff.get("frozen_authority", {})
    source_manifest_hash = frozen_authority.get("source_manifest_hash", conformance_value.get("source_manifest_hash"))
    ambiguity_ids = handoff.get("affected_obligation_ids", [])
    affected_requirement_ids = handoff.get("affected_requirement_ids", [])
    package = {
        "schema_version": "vdd-external-semantic-review-input.v1",
        "plan_id": "vdd-quick-dev-semantic-oracle-recovery",
        "profile": handoff.get("profile", "bootstrap-upstream-plan"),
        "selection_hash": json.loads(manifest.read_text(encoding="utf-8"))["selection_hash"],
        "candidate": {
            "head_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip(),
            "implementation_contract": ref(PLAN / "implementation-contract.v1.json"),
            "command_registry": ref(PLAN / "command-registry.v1.json"),
        },
        "source_freeze": ref(manifest),
        "requirements_mapping": ref(mapping),
        "conformance_result": ref(conformance),
        "skill_input_receipt": ref(current_receipt),
        "required_review_bindings": {
            "semantic_handoff_hash": semantic_handoff_hash(handoff) if handoff else None,
            "source_manifest_hash": source_manifest_hash,
            "requirements_manifest_hash": ref(mapping)["sha256"],
            "ambiguity_ids": ambiguity_ids,
            "affected_requirement_ids": affected_requirement_ids,
        },
        "review_scope": "Rebind the reviewed semantic dispositions and source evidence to this exact candidate; do not authorize implementation.",
        "required_output": "vdd-review-run.v1",
        "authorizes": [],
    }
    write_new(review_input, package)
    print(json.dumps({"conformance": ref(conformance), "review_input": ref(review_input), "status": conformance_value["status"], "errors": conformance_value["errors"], "authorizes": []}, ensure_ascii=False, sort_keys=True))
if __name__ == "__main__":
    main()
