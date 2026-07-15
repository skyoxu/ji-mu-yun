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

    def test_pass_clarification_fixture_is_valid(self) -> None:
        fixture = SKILL_ROOT / "scripts" / "fixtures" / "clarification-state-pass.json"
        result = self.validator.validate_clarification_fixture(SKILL_ROOT, fixture)
        self.assertTrue(result["ok"], result)

    def test_clarification_mutation_cases_are_valid(self) -> None:
        fixture = SKILL_ROOT / "scripts" / "fixtures" / "clarification-cases.json"
        result = self.validator.validate_clarification_cases(SKILL_ROOT, fixture)
        self.assertTrue(result["ok"], result)

    def test_missing_clarification_state_field_is_rejected(self) -> None:
        source = SKILL_ROOT / "scripts" / "fixtures" / "clarification-state-pass.json"
        data = json.loads(source.read_text(encoding="utf-8"))
        del data["write_disposition"]
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "missing-write-disposition.json"
            fixture.write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n"
            )
            result = self.validator.validate_clarification_fixture(SKILL_ROOT, fixture)
        self.assertFalse(result["ok"])
        self.assertIn(
            "VDD-CLARIFICATION-FIELD",
            {item["rule_id"] for item in result["findings"]},
        )

    def test_missing_clarification_case_is_rejected(self) -> None:
        source = SKILL_ROOT / "scripts" / "fixtures" / "clarification-cases.json"
        data = json.loads(source.read_text(encoding="utf-8"))
        data["cases"] = [case for case in data["cases"] if case["id"] != "headless-close"]
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "clarification-cases.json"
            base_source = SKILL_ROOT / "scripts" / "fixtures" / "clarification-state-pass.json"
            shutil.copy2(base_source, Path(tmp) / "clarification-state-pass.json")
            fixture.write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n"
            )
            result = self.validator.validate_clarification_cases(SKILL_ROOT, fixture)
        self.assertFalse(result["ok"])
        self.assertIn(
            "VDD-CLARIFICATION-CASE-COVERAGE",
            {item["rule_id"] for item in result["findings"]},
        )

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
            "authorizes": [{}],
            "does_not_authorize": [[]],
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

    def test_pass_result_cannot_escalate_predicate_authority(self) -> None:
        source = SKILL_ROOT / "scripts" / "fixtures" / "validation-result-pass.json"
        mutations = {
            "release-authority": {
                "authorizes": ["release-ready"],
                "does_not_authorize": ["unrelated"],
            },
            "missing-higher-boundaries": {
                "authorizes": ["plan-ready"],
                "does_not_authorize": ["release-ready"],
            },
            "overlapping-authority": {
                "authorizes": ["plan-ready"],
                "does_not_authorize": [
                    "plan-ready",
                    "phase-authorized",
                    "implementation-accepted",
                    "release-ready",
                ],
            },
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
            self.assertIn(
                "VDD-RESULT-AUTHORITY", {item["rule_id"] for item in result["findings"]}
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

    def test_write_before_clarification_trace_is_rejected(self) -> None:
        fixture = (
            SKILL_ROOT
            / "scripts"
            / "fixtures"
            / "compliance-trace-write-before-clarification.jsonl"
        )
        result = self.validator.validate_trace(SKILL_ROOT, fixture)
        self.assertFalse(result["ok"])
        self.assertIn("VDD-COMPLIANCE-ORDER", {item["rule_id"] for item in result["findings"]})

    def test_clarification_state_cli_lifecycle(self) -> None:
        script = SKILL_ROOT / "scripts" / "clarification_state.py"
        authority_hash = "sha256:" + "a" * 64
        target_hash = "sha256:" + "b" * 64
        response_hash = "sha256:" + "c" * 64
        pass_fixture = json.loads(
            (SKILL_ROOT / "scripts" / "fixtures" / "clarification-state-pass.json").read_text(
                encoding="utf-8"
            )
        )
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            initialized = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "init",
                    "--project-root",
                    str(project_root),
                    "--target",
                    "execution-plans/example",
                    "--mode",
                    "create",
                    "--interaction-mode",
                    "interactive",
                    "--run-id",
                    "clarification-test-001",
                    "--authority-hash",
                    authority_hash,
                    "--target-hash",
                    target_hash,
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(0, initialized.returncode, initialized.stdout + initialized.stderr)
            state_path = Path(json.loads(initialized.stdout)["state"])
            status = subprocess.run(
                [sys.executable, str(script), "status", "--state", str(state_path)],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(0, status.returncode, status.stdout + status.stderr)
            self.assertEqual("clarification_required", json.loads(status.stdout)["status"])

            round_payload = {
                "round_id": "CR-001",
                "questions": pass_fixture["questions"],
                "same_level_exhausted": False,
                "same_level_exhausted_reason": None,
                "confidence": 96,
                "dimension_scores": pass_fixture["rounds"][0]["dimension_scores"],
                "dimension_evidence": pass_fixture["rounds"][0]["dimension_evidence"],
                "recommend_exit": True,
                "analysis": "All five boundary dimensions are grounded.",
                "user_turn_id": "user-turn-001",
                "confirmed_boundaries": ["The target boundary is confirmed."],
                "non_goals": ["No implementation is accepted by clarification."],
                "conflicts": [],
                "open_items": [],
            }
            round_file = Path(tmp) / "round.json"
            round_file.write_text(
                json.dumps(round_payload, indent=2) + "\n", encoding="utf-8", newline="\n"
            )
            recorded = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "record-round",
                    "--state",
                    str(state_path),
                    "--round-file",
                    str(round_file),
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(0, recorded.returncode, recorded.stdout + recorded.stderr)

            exit_payload = {
                "actor": "user",
                "explicit_no_more_clarification": True,
                "explicit_write_permission": True,
                "user_response_hash": response_hash,
                "user_turn_id": "user-turn-002",
                "summary": "No further clarification is needed and writing may begin.",
                "confidence": 96,
                "current_authority_hash": authority_hash,
                "current_target_hash": target_hash,
            }
            exit_file = Path(tmp) / "exit.json"
            exit_file.write_text(
                json.dumps(exit_payload, indent=2) + "\n", encoding="utf-8", newline="\n"
            )
            closed = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "close",
                    "--state",
                    str(state_path),
                    "--exit-file",
                    str(exit_file),
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(0, closed.returncode, closed.stdout + closed.stderr)
            self.assertEqual("normal", json.loads(closed.stdout)["write_disposition"])

            validated = subprocess.run(
                [sys.executable, str(script), "validate", "--state", str(state_path)],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(0, validated.returncode, validated.stdout + validated.stderr)
            self.assertTrue(json.loads(validated.stdout)["ok"])

            new_authority_hash = "sha256:" + "d" * 64
            new_target_hash = "sha256:" + "e" * 64
            invalidated = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "invalidate",
                    "--state",
                    str(state_path),
                    "--reason",
                    "Relevant authority changed.",
                    "--current-authority-hash",
                    new_authority_hash,
                    "--current-target-hash",
                    new_target_hash,
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(0, invalidated.returncode, invalidated.stdout + invalidated.stderr)
            reopened = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "reopen",
                    "--state",
                    str(state_path),
                    "--question-id",
                    "CQ-001",
                    "--reason",
                    "Reconfirm the affected goal boundary.",
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(0, reopened.returncode, reopened.stdout + reopened.stderr)
            reopened_state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual("active", reopened_state["status"])
            self.assertEqual(new_authority_hash, reopened_state["authority_hash"])
            self.assertEqual("reopened", reopened_state["questions"][0]["status"])
            events = (state_path.parent / "events.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(5, len(events))
            self.assertEqual(
                [
                    "initialized",
                    "round_recorded",
                    "clarification_exit_attested",
                    "invalidated",
                    "reopened",
                ],
                [json.loads(line)["event"] for line in events],
            )

    def test_superseded_clarification_run_cannot_be_invalidated(self) -> None:
        script = SKILL_ROOT / "scripts" / "clarification_state.py"
        fixture = json.loads(
            (SKILL_ROOT / "scripts" / "fixtures" / "clarification-state-pass.json").read_text(
                encoding="utf-8"
            )
        )
        with tempfile.TemporaryDirectory() as tmp:
            state_path = (
                Path(tmp)
                / "logs"
                / "vdd-clarifications"
                / fixture["target_slug"]
                / "run-a"
                / "state.json"
            )
            state_path.parent.mkdir(parents=True)
            fixture.update(
                {
                    "run_id": "run-a",
                    "status": "superseded",
                    "exit_attestation": None,
                    "write_disposition": "blocked",
                }
            )
            state_path.write_text(
                json.dumps(fixture, indent=2) + "\n", encoding="utf-8", newline="\n"
            )

            rejected = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "invalidate",
                    "--state",
                    str(state_path),
                    "--reason",
                    "Relevant authority changed.",
                    "--current-authority-hash",
                    "sha256:" + "d" * 64,
                    "--current-target-hash",
                    "sha256:" + "e" * 64,
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(1, rejected.returncode, rejected.stdout + rejected.stderr)
            rejected_payload = json.loads(rejected.stdout)
            self.assertEqual(
                "VDD-CLARIFICATION-STATE-TRANSITION", rejected_payload["rule_id"]
            )
            self.assertIn("only active, closed runs", rejected_payload["error"])
            self.assertEqual(
                "superseded", json.loads(state_path.read_text(encoding="utf-8"))["status"]
            )

    def test_invalidated_run_cannot_reopen_while_sibling_is_active(self) -> None:
        script = SKILL_ROOT / "scripts" / "clarification_state.py"
        fixture = json.loads(
            (SKILL_ROOT / "scripts" / "fixtures" / "clarification-state-pass.json").read_text(
                encoding="utf-8"
            )
        )
        with tempfile.TemporaryDirectory() as tmp:
            target_root = (
                Path(tmp) / "logs" / "vdd-clarifications" / fixture["target_slug"]
            )
            invalidated_path = target_root / "run-a" / "state.json"
            active_path = target_root / "run-b" / "state.json"
            invalidated_path.parent.mkdir(parents=True)
            active_path.parent.mkdir(parents=True)

            invalidated = json.loads(json.dumps(fixture))
            invalidated.update(
                {
                    "run_id": "run-a",
                    "status": "invalidated",
                    "exit_attestation": None,
                    "write_disposition": "blocked",
                }
            )
            active = json.loads(json.dumps(fixture))
            active.update(
                {
                    "run_id": "run-b",
                    "status": "active",
                    "exit_attestation": None,
                    "write_disposition": "blocked",
                }
            )
            invalidated_path.write_text(
                json.dumps(invalidated, indent=2) + "\n", encoding="utf-8", newline="\n"
            )
            active_path.write_text(
                json.dumps(active, indent=2) + "\n", encoding="utf-8", newline="\n"
            )

            rejected = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "reopen",
                    "--state",
                    str(invalidated_path),
                    "--question-id",
                    "CQ-001",
                    "--reason",
                    "Reconfirm the affected goal boundary.",
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(1, rejected.returncode, rejected.stdout + rejected.stderr)
            rejected_payload = json.loads(rejected.stdout)
            self.assertEqual("VDD-CLARIFICATION-ACTIVE-RUN", rejected_payload["rule_id"])
            self.assertIn("another run is active", rejected_payload["error"])
            self.assertEqual(
                "invalidated",
                json.loads(invalidated_path.read_text(encoding="utf-8"))["status"],
            )
            self.assertEqual("active", json.loads(active_path.read_text(encoding="utf-8"))["status"])

    def test_clarification_state_cli_rejects_sensitive_round_payload(self) -> None:
        script = SKILL_ROOT / "scripts" / "clarification_state.py"
        hash_value = "sha256:" + "a" * 64
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            initialized = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "init",
                    "--project-root",
                    str(project_root),
                    "--target",
                    "execution-plans/example",
                    "--mode",
                    "create",
                    "--interaction-mode",
                    "interactive",
                    "--run-id",
                    "clarification-test-sensitive",
                    "--authority-hash",
                    hash_value,
                    "--target-hash",
                    hash_value,
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(0, initialized.returncode, initialized.stdout + initialized.stderr)
            state_path = Path(json.loads(initialized.stdout)["state"])
            payload = Path(tmp) / "sensitive.json"
            payload.write_text(
                json.dumps({"round_id": "CR-001", "questions": [], "api_key": "redacted"}) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            rejected = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "record-round",
                    "--state",
                    str(state_path),
                    "--round-file",
                    str(payload),
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(1, rejected.returncode)
            self.assertIn("prohibited sensitive data", json.loads(rejected.stdout)["error"])

    def test_clarification_init_rejects_path_escape(self) -> None:
        script = SKILL_ROOT / "scripts" / "clarification_state.py"
        hash_value = "sha256:" + "a" * 64
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            base = [
                sys.executable,
                str(script),
                "init",
                "--project-root",
                str(project_root),
                "--mode",
                "create",
                "--interaction-mode",
                "interactive",
                "--authority-hash",
                hash_value,
                "--target-hash",
                hash_value,
            ]
            cases = [
                (["--target", "../outside", "--run-id", "safe-run"], None),
                (["--target", "execution-plans/example", "--run-id", "../escape"], None),
                (
                    [
                        "--target",
                        "execution-plans/example",
                        "--run-id",
                        "safe-run",
                        "--evidence-root",
                        "execution-plans/example",
                    ],
                    "VDD-CLARIFICATION-EVIDENCE-OVERLAP",
                ),
                (
                    [
                        "--target",
                        "logs/vdd-clarifications",
                        "--run-id",
                        "safe-run-default-contained",
                    ],
                    "VDD-CLARIFICATION-EVIDENCE-OVERLAP",
                ),
                (
                    [
                        "--target",
                        "evidence/plans/example",
                        "--run-id",
                        "safe-run-custom-contained",
                        "--evidence-root",
                        "evidence",
                    ],
                    "VDD-CLARIFICATION-EVIDENCE-OVERLAP",
                ),
            ]
            for extra, expected_rule in cases:
                with self.subTest(extra=extra):
                    rejected = subprocess.run(
                        base + extra,
                        check=False,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                    )
                    self.assertEqual(1, rejected.returncode, rejected.stdout + rejected.stderr)
                    if expected_rule is not None:
                        self.assertEqual(expected_rule, json.loads(rejected.stdout)["rule_id"])

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

    def test_clarification_contract_drift_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mutated = Path(tmp) / "skill"
            shutil.copytree(SKILL_ROOT, mutated)
            target = mutated / "scripts" / "skill-contract.json"
            contract = json.loads(target.read_text(encoding="utf-8"))
            contract["clarification"]["minimum_questions_per_round"] = 4
            target.write_text(
                json.dumps(contract, indent=2) + "\n", encoding="utf-8", newline="\n"
            )
            result = self.validator.validate_skill(mutated)
        self.assertFalse(result["ok"])
        self.assertIn(
            "VDD-CLARIFICATION-CONTRACT-DRIFT",
            {item["rule_id"] for item in result["findings"]},
        )

    def test_invalid_clarification_script_returns_structured_finding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mutated = Path(tmp) / "skill"
            shutil.copytree(SKILL_ROOT, mutated)
            target = mutated / "scripts" / "clarification_state.py"
            target.write_text("this is not valid python\n", encoding="utf-8", newline="\n")
            result = self.validator.validate_skill(mutated)
        self.assertFalse(result["ok"])
        self.assertIn(
            "VDD-CLARIFICATION-CONTRACT-DRIFT",
            {item["rule_id"] for item in result["findings"]},
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
