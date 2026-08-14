from __future__ import annotations

import json
from pathlib import Path
import sys
import subprocess
import tempfile
import re

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts"))
from conformance import build_obligation_inventory, exact_cover, validate_conformance  # noqa: E402
sys.path.insert(0, str(ROOT / ".agents/skills/vdd-execution-plan/scripts"))
from source_freeze import build_manifest  # noqa: E402


def main() -> int:
    path = ROOT / "execution-plans/2026-08-13-vdd-conformance-exact-cover/repair/round-5/requirements-acceptance-slice-command.v1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    requirements = data.get("requirements", [])
    acceptance = data.get("acceptance_ids", [])
    reverse = data.get("reverse_mapping", {})
    if data.get("authorizes") != [] or not requirements or len({x.get("id") for x in requirements}) != len(requirements):
        return 2
    ids = {x.get("id") for x in requirements}
    if not all(isinstance(x, str) and x.startswith("VCEC-A") for x in acceptance):
        return 2
    if set(reverse) != set(acceptance):
        return 2
    for row in requirements:
        if not isinstance(row.get("id"), str) or not row.get("acceptance_ids") or not row.get("slice") or not row.get("command"):
            return 2
        if any(item not in acceptance for item in row["acceptance_ids"]):
            return 2
        if any(row["id"] not in reverse.get(item, []) for item in row["acceptance_ids"]):
            return 2
    if any(item not in ids for values in reverse.values() for item in values):
        return 2
    result = exact_cover(requirements, acceptance, reverse)
    if result["status"] != "conformant" or result["authorizes"] != []:
        return 2
    with tempfile.TemporaryDirectory() as raw:
        manifest = Path(raw) / "source-freeze-manifest.v1.json"
        freeze = subprocess.run([
            sys.executable, str(ROOT / ".agents/skills/vdd-execution-plan/scripts/source_freeze.py"),
            "--repository-root", str(ROOT),
            "--spec", str(ROOT / "_bmad-output/specs/spec-vdd-conformance-exact-cover/SPEC.md"),
            "--target-root", "execution-plans/2026-08-13-vdd-conformance-exact-cover",
            "--run-id", "exact-cover-validator", "--out", str(manifest),
        ], cwd=ROOT, check=False, capture_output=True, text=True)
        if freeze.returncode != 0:
            return 2
        frozen = json.loads(manifest.read_text(encoding="utf-8"))
        inventory = build_obligation_inventory(ROOT, frozen)
        roles = {item["role"] for item in inventory}
        if not {"canonical", "normative_companion", "adopted_companion", "repository_authority"}.issubset(roles):
            return 2
        if any(not item["obligation_id"] or not item["source_sha256"] or not item["anchor"]["quote"] for item in inventory):
            return 2
        prepared = json.loads(json.dumps(data))
        for requirement in prepared["requirements"]:
            requirement["obligation_ids"] = []
        requirement_index = {item["id"]: item for item in prepared["requirements"]}
        for obligation in inventory:
            direct = sorted(set(re.findall(r"`(VCEC-\d{3})`", obligation["anchor"]["quote"])))
            if obligation["status"] == "active":
                if not direct:
                    return 2
                obligation["requirement_ids"] = direct
                obligation["acceptance_ids"] = sorted({aid for rid in direct for aid in requirement_index[rid]["acceptance_ids"]})
                obligation["mapping_kind"] = "identity"
                obligation["merge_reason"] = "Canonical VCEC requirement identifier is present in the source anchor."
                for requirement_id in direct:
                    requirement_index[requirement_id]["obligation_ids"].append(obligation["obligation_id"])
            else:
                obligation["requirement_ids"] = []
                obligation["acceptance_ids"] = []
                obligation["mapping_kind"] = "disposition"
                obligation["merge_reason"] = obligation["disposition"]["reason"]
        prepared["obligations"] = inventory
        mapping = Path(raw) / "complete-mapping.json"
        mapping.write_text(json.dumps(prepared), encoding="utf-8", newline="\n")
        checked = validate_conformance(ROOT, manifest, mapping)
        if checked["status"] != "requirement_semantic_review_required" or checked.get("obligation_count") != len(inventory):
            return 2
        semantic = json.loads(json.dumps(prepared))
        deferred = next(item for item in inventory if item["status"] == "deferred")
        semantic["semantic_review"] = [{
            "obligation_ids": [deferred["obligation_id"]],
            "requirement_ids": ["VCEC-001"],
            "reason": "Source-bound equivalence ambiguity requires upstream review.",
            "scope": "Validate the proposed source-to-requirement equivalence before VDD repair.",
            "profile": "bootstrap-upstream-plan",
            "target_plan": "execution-plans/2026-08-13-vdd-conformance-exact-cover",
        }]
        semantic_path = Path(raw) / "semantic-mapping.json"
        semantic_path.write_text(json.dumps(semantic), encoding="utf-8", newline="\n")
        handoff = validate_conformance(ROOT, manifest, semantic_path)
        if handoff["status"] != "requirement_semantic_review_required" or deferred["obligation_id"] not in handoff.get("semantic_handoff", {}).get("affected_obligation_ids", []) or handoff.get("semantic_handoff", {}).get("profile") != "bootstrap-upstream-plan":
            return 2
        mutated = json.loads(json.dumps(prepared))
        mutated["obligations"] = mutated["obligations"][:-1]
        reduced = Path(raw) / "reduced-mapping.json"
        reduced.write_text(json.dumps(mutated), encoding="utf-8", newline="\n")
        rejected = validate_conformance(ROOT, manifest, reduced)
        return 0 if rejected["status"] == "blocked" and any(item["code"] == "frozen_obligation_universe_mismatch" for item in rejected["errors"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
