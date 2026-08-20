"""Regression coverage for deterministic VDD repair-lineage successors."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[5]
PLAN = ROOT / "execution-plans/2026-08-13-vdd-conformance-exact-cover"
GOVERNANCE = PLAN / "governance"
sys.path.insert(0, str(ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts"))
from conformance import validate_conformance  # noqa: E402
import vdd_repair_lineage as lineage  # noqa: E402
from vdd_repair_lineage import (  # noqa: E402
    LineageError, _approved_ids, _role_graph, semantic_fingerprint, successor,
)


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


def expect_successor_failure(output: Path, expected: str, mutate_source=None, mutate_inventory=None) -> bool:
    """Inject only the recomputed current inputs and exercise successor()."""
    original_loader = lineage._load_module

    def loader(name: str, path: Path):
        module = original_loader(name, path)
        if name == "repair_lineage_source_freeze" and mutate_source is not None:
            return SimpleNamespace(
                build_manifest=lambda *args, **kwargs: mutate_source(module.build_manifest(*args, **kwargs)),
                validate_manifest=lambda *_: None,
            )
        if name == "repair_lineage_conformance" and mutate_inventory is not None:
            return SimpleNamespace(
                **{key: getattr(module, key) for key in (
                    "domain_hash", "semantic_handoff_hash", "build_repair_input",
                )},
                build_obligation_inventory=lambda *args, **kwargs: mutate_inventory(module.build_obligation_inventory(*args, **kwargs)),
            )
        return module

    lineage._load_module = loader
    try:
        try:
            lineage.successor(args_for(output))
        except LineageError as exc:
            return str(exc) == expected
        return False
    finally:
        lineage._load_module = original_loader
        shutil.rmtree(output, ignore_errors=True)


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
        if any(
            "/generations/" not in current[key]["path"]
            for key in ("repair_lineage_successor", "reviewed_mapping", "repair_input", "source_freeze", "conformance_result")
        ):
            return 2
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
        # Obligation identity/prose and authority graph are semantic inputs: a
        # successor must never treat either as a validation-envelope refresh.
        changed_id = json.loads(json.dumps(deferred))
        changed_id["obligation_id"] += "-changed"
        if semantic_fingerprint(deferred) == semantic_fingerprint(changed_id):
            return 2
        predecessor_freeze = json.loads((GOVERNANCE / "source-freeze-20260820.v1.json").read_text(encoding="utf-8"))
        drifted_freeze = json.loads(json.dumps(predecessor_freeze))
        drifted_freeze["sources"][0]["role"] = "provenance"
        if _role_graph(predecessor_freeze) == _role_graph(drifted_freeze):
            return 2
        approved = _approved_ids(json.loads(mapping.read_text(encoding="utf-8")))
        if deferred["obligation_id"] not in approved or changed_id["obligation_id"] in approved:
            return 2
        if not expect_successor_failure(
            GOVERNANCE / ".repair-lineage-selection-drift-test",
            "authority_drift",
            mutate_source=lambda freeze: {**freeze, "selection_hash": "sha256:" + "0" * 64},
        ):
            return 2
        def authority_drift(freeze):
            changed_freeze = json.loads(json.dumps(freeze))
            changed_freeze["sources"][0]["role"] = "provenance"
            return changed_freeze
        if not expect_successor_failure(
            GOVERNANCE / ".repair-lineage-authority-drift-test",
            "authority_drift",
            mutate_source=authority_drift,
        ):
            return 2
        if not expect_successor_failure(
            GOVERNANCE / ".repair-lineage-obligation-drift-test",
            "obligation_drift",
            mutate_inventory=lambda inventory: [*inventory, {**inventory[0], "obligation_id": "OBL-test-added", "status": "deferred"}],
        ):
            return 2
        # Policy drift and an unavailable predecessor validator are both
        # exercised through the real producer entry point.
        alternate_policy = output / "policy.json"
        alternate_policy.write_bytes((ROOT / ".agents/skills/vdd-conformance-exact-cover/references/runtime-policy-registry.v1.json").read_bytes())
        policy_drift = args_for(output)
        policy_drift.policy = alternate_policy
        try:
            successor(policy_drift)
        except LineageError as exc:
            if str(exc) != "review_policy_drift":
                return 2
        else:
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
        unavailable_repair = output / "unavailable-validator-repair.json"
        unavailable_value = json.loads((GOVERNANCE / "vdd-repair-input-20260820-v2.v1.json").read_text(encoding="utf-8"))
        unavailable_value["validator"]["path"] = ".agents/skills/vdd-conformance-exact-cover/scripts/missing-validator.py"
        unavailable_repair.write_text(json.dumps(unavailable_value, separators=(",", ":")), encoding="utf-8", newline="\n")
        unavailable = args_for(output)
        unavailable.predecessor_repair_input = unavailable_repair
        try:
            successor(unavailable)
        except LineageError as exc:
            if str(exc) != "predecessor_validator_unavailable":
                return 2
        else:
            return 2
        interrupted_output = GOVERNANCE / ".repair-lineage-interrupted-test"
        shutil.rmtree(interrupted_output, ignore_errors=True)
        os.environ["VDD_REPAIR_LINEAGE_TEST_INTERRUPT_BEFORE_POINTER"] = "1"
        try:
            successor(args_for(interrupted_output))
        except LineageError as exc:
            if str(exc) != "generation_interrupted_before_pointer" or (interrupted_output / "repair-lineage-current.v1.json").exists():
                return 2
        else:
            return 2
        finally:
            os.environ.pop("VDD_REPAIR_LINEAGE_TEST_INTERRUPT_BEFORE_POINTER", None)
        recovered = successor(args_for(interrupted_output))
        if recovered.get("status") != "conformant" or not (interrupted_output / "repair-lineage-current.v1.json").is_file():
            return 2
        shutil.rmtree(interrupted_output, ignore_errors=True)
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
