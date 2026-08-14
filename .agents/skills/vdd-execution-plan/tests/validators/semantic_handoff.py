from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[5]
PLAN = ROOT / "execution-plans/2026-08-13-vdd-conformance-exact-cover"
sys.path.insert(0, str(ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts"))
from conformance import build_repair_input, validate_conformance  # noqa: E402


def main() -> int:
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=artifacts) as raw:
        directory = Path(raw)
        manifest = directory / "source-freeze-manifest.v1.json"
        source = PLAN / "repair/round-5/requirements-acceptance-slice-command.v1.json"
        prior = directory / "prior-requirements.v1.json"
        repaired = directory / "repaired-requirements.v1.json"
        review = directory / "review-run.v1.json"
        freeze = subprocess.run([
            sys.executable, str(ROOT / ".agents/skills/vdd-execution-plan/scripts/source_freeze.py"),
            "--repository-root", str(ROOT), "--spec", str(ROOT / "_bmad-output/specs/spec-vdd-conformance-exact-cover/SPEC.md"),
            "--target-root", "execution-plans/2026-08-13-vdd-conformance-exact-cover", "--run-id", "semantic-handoff", "--out", str(manifest),
        ], cwd=ROOT, check=False, capture_output=True)
        if freeze.returncode:
            return 2
        mapping = json.loads(source.read_text(encoding="utf-8"))
        deferred = next((item for item in mapping["obligations"] if item["status"] == "deferred"), None)
        if deferred is None:
            return 2
        mapping["semantic_review"] = [{
            "obligation_ids": [deferred["obligation_id"]],
            "requirement_ids": ["VCEC-001"],
            "reason": "The deferred source clause needs an upstream equivalence decision.",
            "scope": "Review source-to-requirement applicability before VDD repair.",
            "profile": "bootstrap-upstream-plan",
            "target_plan": "execution-plans/2026-08-13-vdd-conformance-exact-cover",
        }]
        prior.write_text(json.dumps(mapping), encoding="utf-8", newline="\n")
        repaired_mapping = json.loads(json.dumps(mapping))
        repaired_mapping["semantic_review"] = []
        repaired.write_text(json.dumps(repaired_mapping), encoding="utf-8", newline="\n")
        result = validate_conformance(ROOT, manifest, prior)
        if result["status"] != "requirement_semantic_review_required":
            return 2
        handoff = result.get("semantic_handoff")
        if not isinstance(handoff, dict):
            return 2
        from conformance import semantic_handoff_hash  # noqa: E402
        review.write_text(json.dumps({
            "schema_version": "vdd-review-run.v1",
            "status": "accepted",
            "semantic_handoff_hash": semantic_handoff_hash(handoff),
            "source_manifest_hash": handoff["frozen_authority"]["source_manifest_hash"],
            "requirements_manifest_hash": handoff["requirements_manifest_hash"],
            "profile": handoff["profile"],
            "ambiguity_ids": handoff["affected_obligation_ids"],
            "affected_requirement_ids": handoff["affected_requirement_ids"],
            "decision": "accepted",
            "authorizes": [],
        }), encoding="utf-8", newline="\n")
        stale_review = directory / "stale-review-run.v1.json"
        stale_value = json.loads(review.read_text(encoding="utf-8"))
        stale_value["requirements_manifest_hash"] = "sha256:" + "0" * 64
        stale_review.write_text(json.dumps(stale_value), encoding="utf-8", newline="\n")
        try:
            build_repair_input(
                ROOT, result, manifest, prior, stale_review, repaired,
                ROOT / ".agents/skills/vdd-conformance-exact-cover/references/runtime-policy-registry.v1.json",
                "semantic-handoff-stale-review", ["repair/round-5/requirements-acceptance-slice-command.v1.json"],
            )
        except ValueError:
            pass
        else:
            return 2
        repair = build_repair_input(
            ROOT, result, manifest, prior, review, repaired,
            ROOT / ".agents/skills/vdd-conformance-exact-cover/references/runtime-policy-registry.v1.json",
            "semantic-handoff-repair", ["repair/round-5/requirements-acceptance-slice-command.v1.json"],
        )
        required = {
            "schema_version", "repair_id", "target_root", "frozen_authority", "semantic_handoff", "semantic_handoff_hash", "review_run",
            "prior_requirements_manifest", "repaired_requirements_manifest", "validator", "policy",
            "ambiguity_ids", "affected_requirement_ids", "ambiguity", "allowed_repair_scope", "authorizes",
        }
        return 0 if set(repair) == required and deferred["obligation_id"] in repair["ambiguity_ids"] and "VCEC-001" in repair["affected_requirement_ids"] and repair["ambiguity"] and repair["authorizes"] == [] else 2


if __name__ == "__main__":
    raise SystemExit(main())
