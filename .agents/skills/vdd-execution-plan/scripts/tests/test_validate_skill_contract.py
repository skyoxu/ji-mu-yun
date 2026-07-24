from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = SKILL_ROOT / "scripts" / "validate_skill_contract.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("vdd_validator", VALIDATOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SkillContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.validator = load_validator()

    def test_package_is_valid(self) -> None:
        self.assertTrue(self.validator.validate_skill(SKILL_ROOT)["ok"])

    def test_profiles_are_progressive(self) -> None:
        contract = self.validator.load_contract(SKILL_ROOT)
        standard = set(contract["profiles"]["standard"])
        resumable = set(contract["profiles"]["resumable"])
        hosted = set(contract["profiles"]["self-hosted"])
        self.assertTrue(standard < resumable < hosted)
        self.assertNotIn("implementation_report", standard)

    def test_missing_profile_case_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "skill"
            shutil.copytree(SKILL_ROOT, copied)
            path = copied / "scripts" / "fixtures" / "profile-cases.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["cases"].pop()
            path.write_text(json.dumps(data), encoding="utf-8", newline="\n")
            result = self.validator.validate_skill(copied)
            self.assertIn("VDD-PROFILE-CASES-COVERAGE", {item["rule_id"] for item in result["findings"]})

    def test_live_plan_hardcoding_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "skill"
            shutil.copytree(SKILL_ROOT, copied)
            path = copied / "SKILL.md"
            hardcoded_plan = "execution-plans/" + "2026" + "-01-01-example"
            path.write_text(path.read_text(encoding="utf-8") + f"\n{hardcoded_plan}\n", encoding="utf-8", newline="\n")
            result = self.validator.validate_skill(copied)
            self.assertIn("VDD-GENERIC-HARDCODING", {item["rule_id"] for item in result["findings"]})

    def test_live_plan_hardcoding_in_a_fixture_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "skill"
            shutil.copytree(SKILL_ROOT, copied)
            path = copied / "scripts" / "fixtures" / "profile-cases.json"
            hardcoded_plan = "execution-plans/" + "2026" + "-01-01-example"
            path.write_text(
                path.read_text(encoding="utf-8") + f"\n{hardcoded_plan}\n",
                encoding="utf-8",
                newline="\n",
            )
            result = self.validator.validate_skill(copied)
            self.assertIn("VDD-GENERIC-HARDCODING", {item["rule_id"] for item in result["findings"]})

    def test_lifecycle_owner_mutation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "skill"
            shutil.copytree(SKILL_ROOT, copied)
            path = copied / "references" / "lifecycle-state-contract.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["transitions"][2]["owner"] = "vdd-execution-plan"
            path.write_text(json.dumps(data), encoding="utf-8", newline="\n")
            result = self.validator.validate_skill(copied)
            self.assertIn("VDD-LIFECYCLE-OWNERS", {item["rule_id"] for item in result["findings"]})

    def test_lifecycle_endpoint_and_legacy_output_mutations_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "skill"
            shutil.copytree(SKILL_ROOT, copied)
            path = copied / "references" / "lifecycle-state-contract.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["transitions"][0]["to"] = "archived"
            data["compatibility_adapter"]["emits_legacy_output"] = True
            path.write_text(json.dumps(data), encoding="utf-8", newline="\n")
            result = self.validator.validate_skill(copied)
            rules = {item["rule_id"] for item in result["findings"]}
            self.assertIn("VDD-LIFECYCLE-OWNERS", rules)
            self.assertIn("VDD-LIFECYCLE-COMPATIBILITY", rules)

    def test_profile_fixture_cannot_omit_required_control(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "skill"
            shutil.copytree(SKILL_ROOT, copied)
            path = copied / "scripts" / "fixtures" / "profile-cases.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            case = next(item for item in data["cases"] if item["id"] == "resumable-interrupted")
            case["required"].pop()
            path.write_text(json.dumps(data), encoding="utf-8", newline="\n")
            result = self.validator.validate_skill(copied)
            self.assertIn("VDD-PROFILE-CASES-REQUIRED", {item["rule_id"] for item in result["findings"]})

    def test_slice_local_replay_rule_mutation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "skill"
            shutil.copytree(SKILL_ROOT, copied)
            path = copied / "scripts" / "fixtures" / "profile-cases.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            case = next(item for item in data["cases"] if item["id"] == "slice-local-stale")
            case["expected_invalidation"] = "full-replay"
            path.write_text(json.dumps(data), encoding="utf-8", newline="\n")
            result = self.validator.validate_skill(copied)
            self.assertIn("VDD-PROFILE-CASES-BEHAVIOR", {item["rule_id"] for item in result["findings"]})


if __name__ == "__main__":
    unittest.main()
