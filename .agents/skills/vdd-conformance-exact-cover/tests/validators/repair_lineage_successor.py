"""Regression coverage for deterministic VDD repair-lineage successors."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[5]
PLAN = ROOT / "execution-plans/2026-08-13-vdd-conformance-exact-cover"
GOVERNANCE = PLAN / "governance"
sys.path.insert(0, str(ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts"))
from conformance import validate_conformance  # noqa: E402
from vdd_repair_lineage import LineageError, semantic_fingerprint, successor  # noqa: E402


def args_for(output: Path) -> argparse.Namespace:
    return argparse.Namespace(
        repository_root=ROOT,
        spec=ROOT / "_bmad-output/specs/spec-vdd-conformance-exact-cover/SPEC.md",
        target_root="execution-plans/2026-08-13-vdd-conformance-exact-cover",
        predecessor_freeze=GOVERNANCE / "source-freeze-20260820.v1.json",
        predecessor_mapping=GOVERNANCE / "requirements-acceptance-slice-command-20260820-reviewed.v2.json",
        predecessor_review=GOVERNANCE / "semantic-review-run-20260820.v2.json",
        predecessor_repair_input=GOVERNANCE / "vdd-repair-input-20260820-v2.v1.json",
        predecessor_conformance=GOVERNANCE / "conformance-result-20260820-review-v2.v1.json",
        policy=ROOT / ".agents/skills/vdd-conformance-exact-cover/references/runtime-policy-registry.v1.json",
        out_dir=output,
    )


def main() -> int:
    output = GOVERNANCE / ".repair-lineage-successor-test"
    shutil.rmtree(output, ignore_errors=True)
    try:
        first = successor(args_for(output))
        pointer = output / "repair-lineage-current.v1.json"
        first_bytes = pointer.read_bytes()
        second = successor(args_for(output))
        if first["status"] != "conformant" or second != first or pointer.read_bytes() != first_bytes:
            return 2
        current = json.loads(pointer.read_text(encoding="utf-8"))
        freeze = ROOT / current["source_freeze"]["path"]
        mapping = ROOT / current["reviewed_mapping"]["path"]
        result = validate_conformance(ROOT, freeze, mapping)
        if result.get("status") != "conformant":
            return 2
        lineage = json.loads((ROOT / current["repair_lineage_successor"]["path"]).read_text(encoding="utf-8"))
        if lineage["validation_envelope"]["validator"]["sha256"] != result["validator_identity"]:
            return 2
        obligations = json.loads(mapping.read_text(encoding="utf-8"))["obligations"]
        deferred = next(item for item in obligations if item["obligation_id"] in json.loads(
            (ROOT / current["repair_input"]["path"]).read_text(encoding="utf-8")
        )["ambiguity_ids"])
        changed = json.loads(json.dumps(deferred))
        changed["anchor"]["quote"] += " changed"
        if semantic_fingerprint(deferred) == semantic_fingerprint(changed):
            return 2
        # The predecessor receipt pins the historic validator identity. A
        # hand-edited repair input cannot silently replace that custody link.
        tampered_repair = output / "tampered-repair.json"
        repair = json.loads((GOVERNANCE / "vdd-repair-input-20260820-v2.v1.json").read_text(encoding="utf-8"))
        repair["validator"]["sha256"] = "sha256:" + "0" * 64
        tampered_repair.write_text(json.dumps(repair, separators=(",", ":")), encoding="utf-8", newline="\n")
        tampered = args_for(output)
        tampered.predecessor_repair_input = tampered_repair
        try:
            successor(tampered)
        except LineageError as exc:
            if str(exc) != "predecessor_chain_invalid":
                return 2
        else:
            return 2
        malformed = args_for(output)
        malformed.predecessor_repair_input = output / "missing-repair.json"
        try:
            successor(malformed)
        except LineageError as exc:
            return 0 if str(exc) == "predecessor_chain_invalid" else 2
        return 2
    finally:
        shutil.rmtree(output, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
