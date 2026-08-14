from __future__ import annotations

import json
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
PLAN = ROOT / "execution-plans/2026-08-13-vdd-conformance-exact-cover"
sys.path.insert(0, str(ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts"))
from conformance import build_obligation_inventory  # noqa: E402


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def complete_mapping(manifest: dict[str, object]) -> dict[str, object]:
    mapping = json.loads((PLAN / "repair/round-5/requirements-acceptance-slice-command.v1.json").read_text(encoding="utf-8"))
    inventory = build_obligation_inventory(ROOT, manifest)
    requirements = {item["id"]: item for item in mapping["requirements"]}
    for requirement in requirements.values():
        requirement["obligation_ids"] = []
    for obligation in inventory:
        requirement_id = obligation["obligation_id"] if obligation["obligation_id"] in requirements else "VCEC-001"
        obligation["requirement_ids"] = [requirement_id]
        requirements[requirement_id]["obligation_ids"].append(obligation["obligation_id"])
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
        manifest = Path(raw) / "source-freeze-manifest.v1.json"
        mapping = Path(raw) / "requirements-mapping.v1.json"
        initial_receipt = Path(raw) / "initial-conformance-receipt.json"
        repair_input = Path(raw) / "vdd-repair-input.v1.json"
        repaired_manifest = Path(raw) / "repaired-source-freeze-manifest.v1.json"
        repaired_receipt = Path(raw) / "repaired-conformance-receipt.json"
        freeze = subprocess.run([
            sys.executable, str(ROOT / ".agents/skills/vdd-execution-plan/scripts/source_freeze.py"),
            "--repository-root", str(ROOT), "--spec", str(ROOT / "_bmad-output/specs/spec-vdd-conformance-exact-cover/SPEC.md"),
            "--target-root", "execution-plans/2026-08-13-vdd-conformance-exact-cover", "--run-id", "dogfood", "--out", str(manifest),
        ], cwd=ROOT, check=False)
        if freeze.returncode:
            return 2
        frozen = json.loads(manifest.read_text(encoding="utf-8"))
        mapping.write_text(json.dumps(complete_mapping(frozen)), encoding="utf-8", newline="\n")
        exact = subprocess.run([
            sys.executable, str(ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts/validate_conformance.py"),
            "--repository-root", str(ROOT), "--manifest", str(manifest), "--mapping", str(mapping),
        ], cwd=ROOT, check=False, capture_output=True, text=True)
        if exact.returncode or '"status":"conformant"' not in exact.stdout:
            return 2
        initial_receipt.write_text(exact.stdout, encoding="utf-8", newline="\n")
        # Optional semantic review is explicitly not requested for this structurally complete run.
        (Path(raw) / "optional-review.v1.json").write_text('{"status":"not-requested","authorizes":[]}\n', encoding="utf-8", newline="\n")
        repair_input.write_text(json.dumps({
            "schema_version": "vdd-repair-input.v1",
            "repair_id": "dogfood-repair",
            "target_root": "execution-plans/2026-08-13-vdd-conformance-exact-cover",
            "prior_source_manifest_hash": digest(manifest),
            "authorizes": [],
        }), encoding="utf-8", newline="\n")
        repair = subprocess.run([
            sys.executable, str(ROOT / ".agents/skills/vdd-execution-plan/scripts/source_freeze.py"),
            "--repository-root", str(ROOT), "--spec", str(ROOT / "_bmad-output/specs/spec-vdd-conformance-exact-cover/SPEC.md"),
            "--target-root", "execution-plans/2026-08-13-vdd-conformance-exact-cover", "--run-id", "dogfood-repair", "--repair-input", str(repair_input), "--out", str(repaired_manifest),
        ], cwd=ROOT, check=False)
        if repair.returncode:
            return 2
        rerun = subprocess.run([
            sys.executable, str(ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts/validate_conformance.py"),
            "--repository-root", str(ROOT), "--manifest", str(repaired_manifest), "--mapping", str(mapping),
        ], cwd=ROOT, check=False, capture_output=True, text=True)
        if rerun.returncode or '"status":"conformant"' not in rerun.stdout:
            return 2
        repaired_receipt.write_text(rerun.stdout, encoding="utf-8", newline="\n")
        preflight = subprocess.run([
            sys.executable, str(ROOT / ".agents/skills/authorization/scripts/conformance_preflight.py"),
            "--receipt", str(repaired_receipt), "--manifest", str(repaired_manifest), "--mapping", str(mapping),
            "--validator", str(ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts/conformance.py"),
        ], cwd=ROOT, check=False)
        return 0 if preflight.returncode == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
