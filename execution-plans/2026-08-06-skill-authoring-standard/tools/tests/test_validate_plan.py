from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("validate_plan", ROOT / "tools" / "validate_plan.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class ValidatePlanTests(unittest.TestCase):
    def test_draft_plan_has_no_structural_errors(self) -> None:
        errors = MODULE.validate(allow_draft=True)
        self.assertNotIn("plan-id-mismatch", errors)
        self.assertNotIn("slice-order-mismatch", errors)

    def test_forbidden_path_is_rejected(self) -> None:
        contract_path = ROOT / "implementation-contract.v1.json"
        original = contract_path.read_text(encoding="utf-8")
        try:
            changed = original.replace("docs/architecture/ADR_INDEX_PHASE.md", ".agents/skills/run-phase-bootstrap-review/**", 1)
            contract_path.write_text(changed, encoding="utf-8", newline="\n")
            self.assertTrue(any(item.startswith("forbidden-write:") for item in MODULE.validate(allow_draft=True)))
        finally:
            contract_path.write_text(original, encoding="utf-8", newline="\n")

    def test_command_registry_is_shell_free(self) -> None:
        registry = json.loads((ROOT / "command-registry.v1.json").read_text(encoding="utf-8"))
        self.assertTrue(registry["commands"])
        self.assertTrue(all(item["shell"] is False for item in registry["commands"]))

    def test_resume_state_must_match_plan_state(self) -> None:
        path = ROOT / "resume-state.v1.json"
        original = path.read_text(encoding="utf-8")
        try:
            value = json.loads(original)
            value["state"] = "implementation-complete"
            path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")
            self.assertIn("resume-state-plan-state-mismatch", MODULE.validate(allow_draft=True))
        finally:
            path.write_text(original, encoding="utf-8", newline="\n")

    def test_forbidden_path_checks_windows_case_and_traversal(self) -> None:
        contract_path = ROOT / "implementation-contract.v1.json"
        original = contract_path.read_text(encoding="utf-8")
        try:
            changed = original.replace(
                "docs/architecture/ADR_INDEX_PHASE.md",
                "phasea.platform/Program.cs",
                1,
            )
            contract_path.write_text(changed, encoding="utf-8", newline="\n")
            self.assertTrue(any(item.startswith("forbidden-write:") for item in MODULE.validate(allow_draft=True)))

            changed = original.replace(
                "docs/architecture/ADR_INDEX_PHASE.md",
                "../PhaseA.Platform/Program.cs",
                1,
            )
            contract_path.write_text(changed, encoding="utf-8", newline="\n")
            self.assertTrue(any(item.startswith("forbidden-write:") for item in MODULE.validate(allow_draft=True)))

            changed = original.replace(
                "docs/architecture/ADR_INDEX_PHASE.md",
                ".agents/skills/vdd-execution-plan/SKILL.md",
                1,
            )
            contract_path.write_text(changed, encoding="utf-8", newline="\n")
            self.assertTrue(any(item.startswith("forbidden-write:") for item in MODULE.validate(allow_draft=True)))
        finally:
            contract_path.write_text(original, encoding="utf-8", newline="\n")

    def test_repository_root_write_scope_is_rejected(self) -> None:
        contract_path = ROOT / "implementation-contract.v1.json"
        original = contract_path.read_text(encoding="utf-8")
        try:
            value = json.loads(original)
            value["slices"][0]["allowed_changes"]["production"][0] = "."
            contract_path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")
            self.assertTrue(any(item.startswith("forbidden-write:") for item in MODULE.validate(allow_draft=True)))
        finally:
            contract_path.write_text(original, encoding="utf-8", newline="\n")

    def test_external_validator_bindings_are_present_and_current(self) -> None:
        authority_path = ROOT / "authority-manifest.v1.json"
        original = authority_path.read_text(encoding="utf-8")
        try:
            value = json.loads(original)
            value["validator_bindings"][0]["sha256"] = "sha256:" + "0" * 64
            authority_path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")
            self.assertIn(
                "validator-binding-drift:.agents/skills/vdd-execution-plan/scripts/vdd_knowledge_preflight.py",
                MODULE.validate(allow_draft=True),
            )
        finally:
            authority_path.write_text(original, encoding="utf-8", newline="\n")

    def test_authority_source_set_cannot_drop_required_entry(self) -> None:
        authority_path = ROOT / "authority-manifest.v1.json"
        original = authority_path.read_text(encoding="utf-8")
        try:
            value = json.loads(original)
            value["source_files"].pop()
            authority_path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")
            self.assertIn("authority-source-set-mismatch", MODULE.validate(allow_draft=True))
        finally:
            authority_path.write_text(original, encoding="utf-8", newline="\n")

    def test_baseline_untracked_manifest_requires_exact_declared_set(self) -> None:
        baseline_path = ROOT / "baseline-and-scope.v1.json"
        original = baseline_path.read_text(encoding="utf-8")
        try:
            value = json.loads(original)
            value["scope"]["untracked_paths"] = []
            baseline_path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")
            self.assertIn("baseline-untracked-set-mismatch", MODULE.validate(allow_draft=True))
        finally:
            baseline_path.write_text(original, encoding="utf-8", newline="\n")

    def test_contract_requires_authority_and_forbidden_change_bindings(self) -> None:
        contract_path = ROOT / "implementation-contract.v1.json"
        original = contract_path.read_text(encoding="utf-8")
        try:
            value = json.loads(original)
            value.pop("authority", None)
            value["slices"][0].pop("forbidden_changes", None)
            contract_path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")
            errors = MODULE.validate(allow_draft=True)
            self.assertIn("authority-manifest-binding-mismatch", errors)
            self.assertIn("slice-forbidden-changes-missing:SAS-S0", errors)
        finally:
            contract_path.write_text(original, encoding="utf-8", newline="\n")

    def test_authority_source_rejects_absolute_and_traversal_paths(self) -> None:
        authority_path = ROOT / "authority-manifest.v1.json"
        original = authority_path.read_text(encoding="utf-8")
        try:
            value = json.loads(original)
            value["source_files"][0]["path"] = str((ROOT / "00-index.md").resolve())
            authority_path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")
            self.assertIn("authority-source-drift:" + value["source_files"][0]["path"], MODULE.validate(allow_draft=True))

            value = json.loads(original)
            value["source_files"][0]["path"] = "../AGENTS.md"
            authority_path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")
            self.assertIn("authority-source-drift:../AGENTS.md", MODULE.validate(allow_draft=True))
        finally:
            authority_path.write_text(original, encoding="utf-8", newline="\n")

    def test_composition_receipt_output_rejects_path_escape(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.receipt_output_path("../outside.json")
        with self.assertRaises(ValueError):
            MODULE.receipt_output_path(str((ROOT / "outside.json").resolve()))


if __name__ == "__main__":
    unittest.main()
