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
        review.write_text('{"schema_version":"vdd-review-run.v1","status":"accepted","authorizes":[]}\n', encoding="utf-8", newline="\n")
        result = validate_conformance(ROOT, manifest, prior)
        if result["status"] != "requirement_semantic_review_required":
            return 2
        repair = build_repair_input(
            ROOT, result, manifest, prior, review, repaired,
            ROOT / ".agents/skills/vdd-conformance-exact-cover/references/runtime-policy-registry.v1.json",
            "semantic-handoff-repair", ["repair/round-5/requirements-acceptance-slice-command.v1.json"],
        )
        required = {
            "schema_version", "repair_id", "target_root", "frozen_authority", "review_run",
            "prior_requirements_manifest", "repaired_requirements_manifest", "validator", "policy",
            "ambiguity_ids", "affected_requirement_ids", "ambiguity", "allowed_repair_scope", "authorizes",
        }
        return 0 if set(repair) == required and repair["ambiguity_ids"] == [deferred["obligation_id"]] and repair["affected_requirement_ids"] == ["VCEC-001"] and repair["ambiguity"] and repair["authorizes"] == [] else 2


if __name__ == "__main__":
    raise SystemExit(main())
