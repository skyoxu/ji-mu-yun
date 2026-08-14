from __future__ import annotations

import json
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
PLAN = ROOT / "execution-plans/2026-08-13-vdd-conformance-exact-cover"
sys.path.insert(0, str(ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts"))
from conformance import build_obligation_inventory, semantic_handoff_hash  # noqa: E402


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def complete_mapping(manifest: dict[str, object]) -> dict[str, object]:
    mapping = json.loads((PLAN / "repair/round-5/requirements-acceptance-slice-command.v1.json").read_text(encoding="utf-8"))
    inventory = build_obligation_inventory(ROOT, manifest)
    requirements = {item["id"]: item for item in mapping["requirements"]}
    for requirement in requirements.values():
        requirement["obligation_ids"] = []
    for obligation in inventory:
        if obligation["status"] == "active":
            requirement_ids = sorted(set(re.findall(r"`(VCEC-\d{3})`", obligation["anchor"]["quote"])))
            if not requirement_ids or any(item not in requirements for item in requirement_ids):
                raise ValueError("active dogfood obligation lacks a canonical requirement ID")
            obligation["requirement_ids"] = requirement_ids
            obligation["acceptance_ids"] = sorted({acceptance_id for requirement_id in requirement_ids for acceptance_id in requirements[requirement_id]["acceptance_ids"]})
            obligation["mapping_kind"] = "identity"
            obligation["merge_reason"] = "Canonical VCEC requirement identifier is present in the source anchor."
            for requirement_id in requirement_ids:
                requirements[requirement_id]["obligation_ids"].append(obligation["obligation_id"])
        else:
            obligation["requirement_ids"] = []
            obligation["acceptance_ids"] = []
            obligation["mapping_kind"] = "disposition"
            obligation["merge_reason"] = obligation["disposition"]["reason"]
    mapping["obligations"] = inventory
    mapping["semantic_review"] = []
    return mapping


def main() -> int:
    pointer = ROOT / "_bmad-output/specs/canonical-spec-package-selections/current/SPEC-vdd-conformance-exact-cover.json"
    if not pointer.is_file():
        return 2
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=artifacts) as raw:
        plan = Path(raw) / "requirements-plan"
        shutil.copytree(PLAN, plan)
        target_root = plan.relative_to(ROOT).as_posix()
        manifest = Path(raw) / "source-freeze-manifest.v1.json"
        mapping = plan / "repair/round-5/requirements-acceptance-slice-command.v1.json"
        repaired_mapping = plan / "repair/round-5/requirements-acceptance-slice-command.repaired.v1.json"
        initial_receipt = Path(raw) / "initial-conformance-receipt.json"
        repair_input = Path(raw) / "vdd-repair-input.v1.json"
        repaired_manifest = Path(raw) / "repaired-source-freeze-manifest.v1.json"
        repaired_receipt = Path(raw) / "repaired-conformance-receipt.json"
        authority_manifest = Path(raw) / "authority-source-freeze-manifest.v1.json"
        freeze = subprocess.run([
            sys.executable, str(ROOT / ".agents/skills/vdd-execution-plan/scripts/source_freeze.py"),
            "--repository-root", str(ROOT), "--spec", str(ROOT / "_bmad-output/specs/spec-vdd-conformance-exact-cover/SPEC.md"),
            "--target-root", target_root, "--run-id", "dogfood-authority", "--out", str(authority_manifest),
        ], cwd=ROOT, check=False)
        if freeze.returncode:
            return 2
        frozen = json.loads(authority_manifest.read_text(encoding="utf-8"))
        valid_mapping = complete_mapping(frozen)
        mapping.write_text(json.dumps(valid_mapping), encoding="utf-8", newline="\n")
        freeze = subprocess.run([
            sys.executable, str(ROOT / ".agents/skills/vdd-execution-plan/scripts/source_freeze.py"),
            "--repository-root", str(ROOT), "--spec", str(ROOT / "_bmad-output/specs/spec-vdd-conformance-exact-cover/SPEC.md"),
            "--target-root", target_root, "--run-id", "dogfood", "--requirements-manifest", str(mapping), "--out", str(manifest),
        ], cwd=ROOT, check=False)
        if freeze.returncode:
            return 2
        frozen = json.loads(manifest.read_text(encoding="utf-8"))
        exact = subprocess.run([
            sys.executable, str(ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts/validate_conformance.py"),
            "--repository-root", str(ROOT), "--manifest", str(manifest), "--mapping", str(mapping),
        ], cwd=ROOT, check=False, capture_output=True, text=True)
        if exact.returncode == 0 or '"status":"requirement_semantic_review_required"' not in exact.stdout:
            return 2
        initial_receipt.write_text(exact.stdout, encoding="utf-8", newline="\n")
        initial = json.loads(exact.stdout)
        handoff_value = initial.get("semantic_handoff")
        if not isinstance(handoff_value, dict):
            return 2
        review_run = Path(raw) / "deterministic-repair-review.v1.json"
        review_run.write_text(json.dumps({
            "schema_version": "vdd-review-run.v1",
            "status": "accepted",
            "semantic_handoff_hash": semantic_handoff_hash(handoff_value),
            "source_manifest_hash": handoff_value["frozen_authority"]["source_manifest_hash"],
            "requirements_manifest_hash": handoff_value["requirements_manifest_hash"],
            "profile": handoff_value["profile"],
            "ambiguity_ids": handoff_value["affected_obligation_ids"],
            "affected_requirement_ids": handoff_value["affected_requirement_ids"],
            "decision": "accepted",
            "authorizes": [],
        }), encoding="utf-8", newline="\n")
        reviewed = json.loads(json.dumps(valid_mapping))
        reviewed["approved_semantic_dispositions"] = [{
            "obligation_ids": handoff_value["affected_obligation_ids"],
            "decision": "not_applicable",
            "review_run": {"path": review_run.relative_to(ROOT).as_posix(), "sha256": digest(review_run)},
            "prior_requirements_manifest": {"path": mapping.relative_to(ROOT).as_posix(), "sha256": digest(mapping)},
            "semantic_handoff": handoff_value,
            "semantic_handoff_hash": semantic_handoff_hash(handoff_value),
        }]
        approved = set(handoff_value["affected_obligation_ids"])
        for obligation in reviewed["obligations"]:
            if obligation["obligation_id"] in approved:
                obligation["status"] = "not_applicable"
        repaired_mapping.write_text(json.dumps(reviewed), encoding="utf-8", newline="\n")
        handoff = subprocess.run([
            sys.executable, str(ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts/validate_conformance.py"),
            "--repository-root", str(ROOT), "--manifest", str(manifest), "--mapping", str(mapping),
            "--repair-input-out", str(repair_input), "--repair-id", "dogfood-repair",
            "--review-run", str(review_run), "--repaired-requirements-manifest", str(repaired_mapping),
            "--policy", str(ROOT / ".agents/skills/vdd-conformance-exact-cover/references/runtime-policy-registry.v1.json"),
            "--allowed-repair-scope", "repair/round-5/requirements-acceptance-slice-command.v1.json",
        ], cwd=ROOT, check=False)
        if handoff.returncode:
            return 2
        repair = subprocess.run([
            sys.executable, str(ROOT / ".agents/skills/vdd-execution-plan/scripts/source_freeze.py"),
            "--repository-root", str(ROOT), "--spec", str(ROOT / "_bmad-output/specs/spec-vdd-conformance-exact-cover/SPEC.md"),
            "--target-root", target_root, "--run-id", "dogfood-repair", "--repair-input", str(repair_input), "--requirements-manifest", str(repaired_mapping), "--out", str(repaired_manifest),
        ], cwd=ROOT, check=False)
        if repair.returncode:
            return 2
        rerun = subprocess.run([
            sys.executable, str(ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts/validate_conformance.py"),
            "--repository-root", str(ROOT), "--manifest", str(repaired_manifest), "--mapping", str(mapping),
        ], cwd=ROOT, check=False, capture_output=True, text=True)
        if rerun.returncode == 0 or '"requirements_identity_mismatch"' not in rerun.stdout:
            return 2
        rerun = subprocess.run([
            sys.executable, str(ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts/validate_conformance.py"),
            "--repository-root", str(ROOT), "--manifest", str(repaired_manifest), "--mapping", str(repaired_mapping),
        ], cwd=ROOT, check=False, capture_output=True, text=True)
        if rerun.returncode or '"status":"conformant"' not in rerun.stdout:
            return 2
        repaired_receipt.write_text(rerun.stdout, encoding="utf-8", newline="\n")
        preflight = subprocess.run([
            sys.executable, str(ROOT / ".agents/skills/authorization/scripts/conformance_preflight.py"),
            "--receipt", str(repaired_receipt), "--manifest", str(repaired_manifest), "--mapping", str(repaired_mapping),
            "--validator", str(ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts/conformance.py"),
        ], cwd=ROOT, check=False)
        if preflight.returncode:
            return 2
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
