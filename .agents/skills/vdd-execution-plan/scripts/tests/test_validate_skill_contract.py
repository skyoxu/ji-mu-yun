from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = SKILL_ROOT / "scripts" / "validate_skill_contract.py"


def load_validator():
    if not VALIDATOR_PATH.exists():
        raise AssertionError(f"validator implementation missing: {VALIDATOR_PATH}")
    spec = importlib.util.spec_from_file_location("validate_skill_contract", VALIDATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class SkillContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.validator = load_validator()

    def test_clean_skill_passes(self) -> None:
        result = self.validator.validate_skill(SKILL_ROOT)
        self.assertTrue(result["ok"], result)
        self.assertEqual([], result["findings"])

    def test_pass_result_fixture_is_valid(self) -> None:
        fixture = SKILL_ROOT / "scripts" / "fixtures" / "validation-result-pass.json"
        result = self.validator.validate_result_fixture(SKILL_ROOT, fixture)
        self.assertTrue(result["ok"], result)

    def test_compliance_scenarios_are_valid(self) -> None:
        fixture = SKILL_ROOT / "scripts" / "fixtures" / "compliance-scenarios.json"
        result = self.validator.validate_scenarios(SKILL_ROOT, fixture)
        self.assertTrue(result["ok"], result)

    def test_missing_competing_scenario_mutation_is_rejected(self) -> None:
        source = SKILL_ROOT / "scripts" / "fixtures" / "compliance-scenarios.json"
        data = json.loads(source.read_text(encoding="utf-8"))
        data["scenarios"] = [
            scenario for scenario in data["scenarios"] if scenario["level"] != "competing"
        ]
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "missing-competing.json"
            fixture.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
            result = self.validator.validate_scenarios(SKILL_ROOT, fixture)
        self.assertFalse(result["ok"])
        self.assertIn("VDD-SCENARIO-LEVEL", {item["rule_id"] for item in result["findings"]})

    def test_stale_pass_result_is_rejected(self) -> None:
        fixture = SKILL_ROOT / "scripts" / "fixtures" / "validation-result-stale.json"
        result = self.validator.validate_result_fixture(SKILL_ROOT, fixture)
        self.assertFalse(result["ok"])
        self.assertIn("VDD-RESULT-STALE", {item["rule_id"] for item in result["findings"]})

    def test_missing_result_field_mutation_is_rejected(self) -> None:
        source = SKILL_ROOT / "scripts" / "fixtures" / "validation-result-pass.json"
        data = json.loads(source.read_text(encoding="utf-8"))
        del data["authorizes"]
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "missing-authorizes.json"
            fixture.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
            result = self.validator.validate_result_fixture(SKILL_ROOT, fixture)
        self.assertFalse(result["ok"])
        self.assertIn("VDD-RESULT-FIELD", {item["rule_id"] for item in result["findings"]})

    def test_non_object_result_fixture_returns_structured_parse_finding(self) -> None:
        for value in (None, []):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as tmp:
                fixture = Path(tmp) / "non-object-result.json"
                fixture.write_text(
                    json.dumps(value) + "\n", encoding="utf-8", newline="\n"
                )
                result = self.validator.validate_result_fixture(SKILL_ROOT, fixture)
            self.assertFalse(result["ok"])
            self.assertEqual(
                ["VDD-RESULT-PARSE"],
                [item["rule_id"] for item in result["findings"]],
            )

    def test_invalid_result_authority_fields_are_rejected(self) -> None:
        source = SKILL_ROOT / "scripts" / "fixtures" / "validation-result-pass.json"
        mutations = {
            "run_id": None,
            "predicate": [],
            "validator_version": "",
            "generated_at": False,
            "authorizes": [None],
            "does_not_authorize": [None],
            "diagnostics": [None],
        }
        for field_name, invalid_value in mutations.items():
            with self.subTest(field_name=field_name), tempfile.TemporaryDirectory() as tmp:
                data = json.loads(source.read_text(encoding="utf-8"))
                data[field_name] = invalid_value
                fixture = Path(tmp) / f"invalid-{field_name}.json"
                fixture.write_text(
                    json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n"
                )
                result = self.validator.validate_result_fixture(SKILL_ROOT, fixture)
            self.assertFalse(result["ok"])
            self.assertIn(
                "VDD-RESULT-FIELD", {item["rule_id"] for item in result["findings"]}
            )

    def test_pass_check_requires_non_empty_evidence(self) -> None:
        source = SKILL_ROOT / "scripts" / "fixtures" / "validation-result-pass.json"
        data = json.loads(source.read_text(encoding="utf-8"))
        data["checks"][0]["evidence"] = []
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "empty-check-evidence.json"
            fixture.write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n"
            )
            result = self.validator.validate_result_fixture(SKILL_ROOT, fixture)
        self.assertFalse(result["ok"])
        self.assertIn("VDD-RESULT-CHECK", {item["rule_id"] for item in result["findings"]})

    def test_non_standard_json_constant_is_rejected(self) -> None:
        source = SKILL_ROOT / "scripts" / "fixtures" / "validation-result-pass.json"
        text = source.read_text(encoding="utf-8").replace(
            '"diagnostics": []', '"diagnostics": [{"value": NaN}]'
        )
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "nan-result.json"
            fixture.write_text(text, encoding="utf-8", newline="\n")
            result = self.validator.validate_result_fixture(SKILL_ROOT, fixture)
        self.assertFalse(result["ok"])
        self.assertEqual(
            ["VDD-RESULT-PARSE"], [item["rule_id"] for item in result["findings"]]
        )

    def test_result_status_authority_combinations_are_rejected(self) -> None:
        source = SKILL_ROOT / "scripts" / "fixtures" / "validation-result-pass.json"
        mutations = {
            "pass-with-diagnostic": {"diagnostics": [{"rule_id": "VDD-FAIL"}]},
            "fail-with-authorization": {"status": "fail"},
            "blocked-with-authorization": {"status": "blocked"},
            "incomplete-with-authorization": {"status": "incomplete"},
        }
        for name, values in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                data = json.loads(source.read_text(encoding="utf-8"))
                data.update(values)
                fixture = Path(tmp) / f"{name}.json"
                fixture.write_text(
                    json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n"
                )
                result = self.validator.validate_result_fixture(SKILL_ROOT, fixture)
            self.assertFalse(result["ok"])
            self.assertTrue(
                {"VDD-RESULT-STATUS", "VDD-RESULT-AUTHORITY", "VDD-RESULT-CHECK"}
                & {item["rule_id"] for item in result["findings"]}
            )

    def test_non_pass_result_with_diagnostic_and_failed_check_is_valid(self) -> None:
        source = SKILL_ROOT / "scripts" / "fixtures" / "validation-result-pass.json"
        data = json.loads(source.read_text(encoding="utf-8"))
        data.update(
            {
                "status": "fail",
                "authorizes": [],
                "diagnostics": [{"rule_id": "VDD-PLAN-001"}],
            }
        )
        data["checks"][0]["status"] = "fail"
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "valid-fail-result.json"
            fixture.write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n"
            )
            result = self.validator.validate_result_fixture(SKILL_ROOT, fixture)
        self.assertTrue(result["ok"], result)

    def test_non_object_scenario_fixture_returns_structured_parse_finding(self) -> None:
        for value in (None, []):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as tmp:
                fixture = Path(tmp) / "non-object-scenarios.json"
                fixture.write_text(
                    json.dumps(value) + "\n", encoding="utf-8", newline="\n"
                )
                result = self.validator.validate_scenarios(SKILL_ROOT, fixture)
            self.assertFalse(result["ok"])
            self.assertEqual(
                ["VDD-SCENARIO-PARSE"],
                [item["rule_id"] for item in result["findings"]],
            )

    def test_boolean_trace_sequence_is_rejected(self) -> None:
        source = SKILL_ROOT / "scripts" / "fixtures" / "compliance-trace-pass.jsonl"
        lines = source.read_text(encoding="utf-8").splitlines()
        first = json.loads(lines[0])
        first["seq"] = True
        lines[0] = json.dumps(first, separators=(",", ":"))
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "boolean-sequence.jsonl"
            fixture.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
            result = self.validator.validate_trace(SKILL_ROOT, fixture)
        self.assertFalse(result["ok"])
        self.assertIn(
            "VDD-COMPLIANCE-SEQUENCE", {item["rule_id"] for item in result["findings"]}
        )

    def test_cli_returns_structured_json_for_non_object_scenario_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "non-object-scenarios.json"
            fixture.write_text("null\n", encoding="utf-8", newline="\n")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR_PATH),
                    "--skill-root",
                    str(SKILL_ROOT),
                    "--scenario-fixture",
                    str(fixture),
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        payload = json.loads(completed.stdout)
        self.assertEqual(1, completed.returncode, completed.stderr)
        self.assertEqual("vdd.skill-validation.v1", payload["schema_version"])
        self.assertEqual("VDD-SCENARIO-PARSE", payload["findings"][0]["rule_id"])

    def test_compliant_trace_passes(self) -> None:
        fixture = SKILL_ROOT / "scripts" / "fixtures" / "compliance-trace-pass.jsonl"
        result = self.validator.validate_trace(SKILL_ROOT, fixture)
        self.assertTrue(result["ok"], result)

    def test_implementation_first_trace_is_rejected(self) -> None:
        fixture = (
            SKILL_ROOT
            / "scripts"
            / "fixtures"
            / "compliance-trace-implementation-first.jsonl"
        )
        result = self.validator.validate_trace(SKILL_ROOT, fixture)
        self.assertFalse(result["ok"])
        self.assertIn("VDD-COMPLIANCE-ORDER", {item["rule_id"] for item in result["findings"]})

    def test_missing_trace_step_mutation_is_rejected(self) -> None:
        source = SKILL_ROOT / "scripts" / "fixtures" / "compliance-trace-pass.jsonl"
        lines = [
            line
            for line in source.read_text(encoding="utf-8").splitlines()
            if '"action":"prove_validator_red"' not in line
        ]
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "missing-red-step.jsonl"
            fixture.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
            result = self.validator.validate_trace(SKILL_ROOT, fixture)
        self.assertFalse(result["ok"])
        self.assertIn("VDD-COMPLIANCE-ACTION", {item["rule_id"] for item in result["findings"]})

    def test_missing_required_file_mutation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mutated = Path(tmp) / "skill"
            shutil.copytree(SKILL_ROOT, mutated)
            (mutated / "references" / "skill-compliance-protocol.md").unlink()
            result = self.validator.validate_skill(mutated)
        self.assertIn("VDD-SKILL-FILE", {item["rule_id"] for item in result["findings"]})

    def test_missing_contract_section_returns_structured_contract_finding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mutated = Path(tmp) / "skill"
            shutil.copytree(SKILL_ROOT, mutated)
            target = mutated / "scripts" / "skill-contract.json"
            contract = json.loads(target.read_text(encoding="utf-8"))
            del contract["required_files"]
            target.write_text(
                json.dumps(contract, indent=2) + "\n", encoding="utf-8", newline="\n"
            )
            result = self.validator.validate_skill(mutated)
        self.assertFalse(result["ok"])
        self.assertEqual(
            ["VDD-SKILL-CONTRACT"], [item["rule_id"] for item in result["findings"]]
        )

    def test_missing_heading_mutation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mutated = Path(tmp) / "skill"
            shutil.copytree(SKILL_ROOT, mutated)
            target = mutated / "SKILL.md"
            text = target.read_text(encoding="utf-8")
            text = text.replace("## Maintain and evaluate this Skill", "## Maintenance")
            target.write_text(text, encoding="utf-8", newline="\n")
            result = self.validator.validate_skill(mutated)
        self.assertIn("VDD-SKILL-HEADING", {item["rule_id"] for item in result["findings"]})

    def test_missing_reference_link_mutation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mutated = Path(tmp) / "skill"
            shutil.copytree(SKILL_ROOT, mutated)
            target = mutated / "SKILL.md"
            text = target.read_text(encoding="utf-8")
            text = text.replace("references/skill-compliance-protocol.md", "")
            target.write_text(text, encoding="utf-8", newline="\n")
            result = self.validator.validate_skill(mutated)
        self.assertIn("VDD-SKILL-LINK", {item["rule_id"] for item in result["findings"]})

    def test_cli_returns_json_and_zero_for_clean_skill(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(VALIDATOR_PATH), "--skill-root", str(SKILL_ROOT)],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertTrue(payload["ok"], payload)


if __name__ == "__main__":
    unittest.main()
