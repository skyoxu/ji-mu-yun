from __future__ import annotations

import importlib.util
import json
import re
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

    def test_route_outcome_mutation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "skill"
            shutil.copytree(SKILL_ROOT, copied)
            path = copied / "scripts" / "skill-contract.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["input_routes"]["single-requirements-markdown"]["outcome"] = "vdd-create"
            path.write_text(json.dumps(data), encoding="utf-8", newline="\n")
            result = self.validator.validate_skill(copied)
            self.assertIn("VDD-INPUT-ROUTING", {item["rule_id"] for item in result["findings"]})

    def test_skill_route_text_mutation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "skill"
            shutil.copytree(SKILL_ROOT, copied)
            path = copied / "SKILL.md"
            text = path.read_text(encoding="utf-8").replace(
                "One standalone requirements Markdown file routes to direct implementation",
                "One standalone requirements Markdown file routes to VDD create",
            )
            path.write_text(text, encoding="utf-8", newline="\n")
            result = self.validator.validate_skill(copied)
            self.assertIn("VDD-INPUT-ROUTING", {item["rule_id"] for item in result["findings"]})

    def test_clarification_security_regression_suite_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "skill"
            shutil.copytree(SKILL_ROOT, copied)
            path = copied / "scripts" / "tests" / "test_clarification_state_review_regressions.py"
            path.unlink()
            result = self.validator.validate_skill(copied)
            self.assertIn("VDD-SKILL-FILE", {item["rule_id"] for item in result["findings"]})

    def test_legacy_fixture_cannot_reintroduce_strict_controls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "skill"
            shutil.copytree(SKILL_ROOT, copied)
            path = copied / "scripts" / "fixtures" / "clarification-legacy-v1.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["confidence"] = 95
            path.write_text(json.dumps(data), encoding="utf-8", newline="\n")
            result = self.validator.validate_skill(copied)
            self.assertIn("VDD-LEGACY-FIXTURE", {item["rule_id"] for item in result["findings"]})

    def test_obsolete_clarification_fixture_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "skill"
            shutil.copytree(SKILL_ROOT, copied)
            path = copied / "scripts" / "fixtures" / "clarification-cases.json"
            path.write_text("{}\n", encoding="utf-8", newline="\n")
            result = self.validator.validate_skill(copied)
            self.assertIn("VDD-OBSOLETE-FIXTURE", {item["rule_id"] for item in result["findings"]})

    def test_renamed_strict_clarification_fixture_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "skill"
            shutil.copytree(SKILL_ROOT, copied)
            path = copied / "scripts" / "fixtures" / "renamed-legacy-control.json"
            path.write_text(json.dumps({"exit_attestation": {"explicit_write_permission": True}}), encoding="utf-8", newline="\n")
            result = self.validator.validate_skill(copied)
            self.assertIn("VDD-OBSOLETE-FIXTURE", {item["rule_id"] for item in result["findings"]})

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

    def test_review_reentry_policy_mutation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "skill"
            shutil.copytree(SKILL_ROOT, copied)
            path = copied / "scripts" / "skill-contract.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["review_reentry_policy"]["transport_failure"] = "new-review-round"
            path.write_text(json.dumps(data), encoding="utf-8", newline="\n")
            result = self.validator.validate_skill(copied)
            self.assertIn("VDD-REVIEW-REENTRY", {item["rule_id"] for item in result["findings"]})

    def test_excluded_recovery_architecture_is_absent(self) -> None:
        sources = {
            path.relative_to(SKILL_ROOT).as_posix(): path.read_text(encoding="utf-8")
            for path in SKILL_ROOT.rglob("*")
            if path.is_file()
            and path.suffix in {".py", ".json", ".jsonl", ".yaml"}
            if "tests" not in path.parts
        }
        for forbidden in (
            r"events\.jsonl",
            r"\bprevious_hash\b",
            r"\bevent_hash\b",
            r"import\s+msvcrt",
            r"\btarget_registry\b",
            r"\bsignature\b",
            r"\bgeneration\b",
            r"\bcommitted_pointer\b",
            r"\bpromotion_transaction\b",
        ):
            with self.subTest(forbidden=forbidden):
                offenders = [relative for relative, source in sources.items() if re.search(forbidden, source)]
                self.assertEqual([], offenders)

    def test_inactive_strict_clarification_fixtures_are_absent(self) -> None:
        fixture_root = SKILL_ROOT / "scripts" / "fixtures"
        for name in (
            "clarification-cases.json",
            "clarification-state-pass.json",
            "compliance-scenarios.json",
            "compliance-trace-pass.jsonl",
            "compliance-trace-write-before-clarification.jsonl",
            "compliance-trace-implementation-first.jsonl",
        ):
            with self.subTest(name=name):
                self.assertFalse((fixture_root / name).exists())


if __name__ == "__main__":
    unittest.main()
