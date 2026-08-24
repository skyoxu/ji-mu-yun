from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


PLAN_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = PLAN_ROOT / "tools" / "validate_implementation.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("tc_d1_validate_implementation", VALIDATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("validator import failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ValidateImplementationTests(unittest.TestCase):
    def test_s3_missing_downstream_receipt_has_terminal_failure_family(self) -> None:
        module = load_validator()
        self.assertEqual(
            "terminal-consumer-replay-incomplete",
            module.failure_family_for_errors(
                [
                    "required implementation artifact is missing: execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/downstream-replay-receipt.v1.json"
                ],
                "RMAP-S3",
            ),
        )
    def test_historical_candidate_matches_the_frozen_baseline(self) -> None:
        module = load_validator()
        errors: list[str] = []
        module.check_historical_tree(errors)
        self.assertEqual([], errors)

    def test_mutable_authority_hashes_cover_both_consumers(self) -> None:
        module = load_validator()
        hashes = module.current_mutable_authority_hashes()
        self.assertEqual(2, len(hashes))
        self.assertIn(".agents/skills/vdd-execution-plan/SKILL.md", hashes)
        self.assertIn(".agents/skills/run-refactor-implementation-acceptance/SKILL.md", hashes)

    def test_historical_replay_rejects_unbound_minimal_artifacts(self) -> None:
        module = load_validator()
        errors: list[str] = []
        module.validate_historical_replay(
            {"historical_portability": "machine-bound", "authorizes": []},
            {"status": "pass", "exit_code": 0, "authorizes": []},
            errors,
        )
        self.assertTrue(any("historical validator" in error for error in errors), errors)
        self.assertTrue(any("current wrapper" in error for error in errors), errors)

    def test_historical_replay_accepts_complete_byte_bindings(self) -> None:
        module = load_validator()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            validator = root / module.HISTORICAL_VALIDATOR_PATH
            command_evidence = root / module.HISTORICAL_COMMAND_EVIDENCE_PATH
            receipt_path = root / module.CURRENT_REPLAY_RECEIPT_PATH
            target_root = root / module.CURRENT_REPLAY_TARGET
            capability = root / module.CURRENT_REPLAY_CAPABILITY
            for path, content in (
                (validator, "print('historical')\n"),
                (command_evidence, "terminal result: pass\n"),
                (target_root / "SKILL.md", "# Target\n"),
                (capability, "{}\n"),
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8", newline="\n")
            validator_binding = {
                "path": module.HISTORICAL_VALIDATOR_PATH,
                "sha256": module.file_sha256(validator),
            }
            command_binding = {
                "path": module.HISTORICAL_COMMAND_EVIDENCE_PATH,
                "sha256": module.file_sha256(command_evidence),
                "command": module.HISTORICAL_COMMAND,
                "recorded_result": "pass",
            }
            receipt = {
                "status": "pass",
                "exit_code": 0,
                "historical_validator": validator_binding,
                "historical_command_evidence": command_binding,
                "current_wrapper_replay": {
                    "entrypoint": module.CURRENT_REPLAY_ENTRYPOINT,
                    "command": module.CURRENT_REPLAY_COMMAND,
                    "status": "pass",
                    "exit_code": 0,
                    "target_package": {
                        "path": module.CURRENT_REPLAY_TARGET,
                        "manifest_sha256": module.directory_manifest_sha256(target_root),
                    },
                    "capability": {
                        "path": module.CURRENT_REPLAY_CAPABILITY,
                        "sha256": module.file_sha256(capability),
                    },
                    "resolved_validator": {
                        "path": "C:/installed/quick_validate.py",
                        "version": "1.0",
                        "sha256": "sha256:" + "a" * 64,
                        "package_identity": "skill-creator-v1",
                    },
                    "probes": [
                        {"probe_id": "detached-positive", "status": "pass", "exit_code": 0},
                        {"probe_id": "detached-negative", "status": "expected-failure", "exit_code": 1},
                    ],
                },
                "authorizes": [],
            }
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8", newline="\n")
            record = {
                "historical_portability": "machine-bound",
                "historical_validator": validator_binding,
                "historical_command_evidence": command_binding,
                "current_wrapper_replay": {
                    "entrypoint": module.CURRENT_REPLAY_ENTRYPOINT,
                    "receipt_path": module.CURRENT_REPLAY_RECEIPT_PATH,
                    "receipt_sha256": module.file_sha256(receipt_path),
                },
                "authorizes": [],
            }
            errors: list[str] = []
            module.validate_historical_replay(record, receipt, errors, repository_root=root)
            self.assertEqual([], errors)

    def test_historical_replay_rejects_wrong_target_or_incomplete_command(self) -> None:
        module = load_validator()
        errors: list[str] = []
        module.validate_historical_replay(
            {"historical_portability": "machine-bound", "authorizes": []},
            {
                "status": "pass",
                "exit_code": 0,
                "current_wrapper_replay": {
                    "entrypoint": module.CURRENT_REPLAY_ENTRYPOINT,
                    "command": ["py", "-3", "-B", module.CURRENT_REPLAY_ENTRYPOINT],
                    "status": "pass",
                    "exit_code": 0,
                    "target_package": {"path": ".agents/skills/wrong", "manifest_sha256": "sha256:" + "0" * 64},
                },
                "authorizes": [],
            },
            errors,
        )
        self.assertTrue(any("passing current wrapper replay" in error for error in errors), errors)
        self.assertTrue(any("intended target package" in error for error in errors), errors)

    def test_evaluation_artifacts_require_native_evidence_and_six_cases(self) -> None:
        module = load_validator()
        seeds = {
            "baseline_status": "non-authorizing-candidates",
            "seeds": [
                {"failure_family": family, "candidate_class": expectation[0], "native_evidence": []}
                for family, expectation in module.SEED_EXPECTATIONS.items()
            ],
            "authorizes": [],
        }
        matrix = {
            "cases": [{"case_id": "positive", "category": "positive", "validation_surface": "probe"}],
            "authorizes": [],
        }
        errors: list[str] = []
        module.validate_evaluation_artifacts(seeds, matrix, errors)
        self.assertTrue(any("requires native evidence" in error for error in errors), errors)
        self.assertTrue(any("expected observation" in error for error in errors), errors)
        self.assertTrue(any("each frozen category exactly once" in error for error in errors), errors)

    def test_evaluation_matrix_invalid_category_fails_closed(self) -> None:
        module = load_validator()
        errors: list[str] = []
        module.validate_evaluation_artifacts(
            {"baseline_status": "non-authorizing-candidates", "seeds": [], "authorizes": []},
            {
                "cases": [
                    {
                        "case_id": "invalid-category",
                        "category": ["positive"],
                        "validation_surface": "probe",
                        "expected_observation": "pass",
                    }
                ],
                "authorizes": [],
            },
            errors,
        )
        self.assertTrue(any("invalid category" in error for error in errors), errors)

    def test_evaluation_artifacts_accept_complete_native_evidence_and_matrix(self) -> None:
        module = load_validator()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            seed_items = []
            for family, (candidate_class, evidence_path) in module.SEED_EXPECTATIONS.items():
                source = root / evidence_path
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text(family + "\n", encoding="utf-8", newline="\n")
                seed_items.append(
                    {
                        "failure_family": family,
                        "candidate_class": candidate_class,
                        "native_evidence": [{"path": evidence_path, "sha256": module.file_sha256(source)}],
                    }
                )
            seeds = {
                "baseline_status": "non-authorizing-candidates",
                "seeds": seed_items,
                "authorizes": [],
            }
            matrix = {
                "cases": [
                    {
                        "case_id": f"case-{category}",
                        "category": category,
                        "validation_surface": f"surface-{category}",
                        "expected_observation": f"observe-{category}",
                    }
                    for category in module.MATRIX_CATEGORIES
                ],
                "authorizes": [],
            }
            errors: list[str] = []
            module.validate_evaluation_artifacts(seeds, matrix, errors, repository_root=root)
            self.assertEqual([], errors)

            matrix_path = root / module.MATRIX_PATH
            matrix_path.parent.mkdir(parents=True, exist_ok=True)
            matrix_path.write_text(json.dumps(matrix), encoding="utf-8", newline="\n")
            case_results = []
            for case in matrix["cases"]:
                evidence = root / "evidence" / f"{case['case_id']}.json"
                evidence.parent.mkdir(parents=True, exist_ok=True)
                evidence.write_text(json.dumps({"status": "pass"}), encoding="utf-8", newline="\n")
                case_results.append(
                    {
                        "case_id": case["case_id"],
                        "category": case["category"],
                        "validation_surface": case["validation_surface"],
                        "status": "pass",
                        "observed_result": case["expected_observation"],
                        "evidence": [
                            {
                                "path": evidence.relative_to(root).as_posix(),
                                "sha256": module.file_sha256(evidence),
                            }
                        ],
                    }
                )
            receipt = {
                "status": "pass",
                "exit_code": 0,
                "runner_entrypoint": module.CURRENT_REPLAY_ENTRYPOINT,
                "command": module.MATRIX_REPLAY_COMMAND,
                "matrix_path": module.MATRIX_PATH,
                "matrix_sha256": module.file_sha256(matrix_path),
                "case_results": case_results,
                "authorizes": [],
            }
            receipt_errors: list[str] = []
            module.validate_matrix_receipt(matrix, receipt, receipt_errors, repository_root=root)
            self.assertEqual([], receipt_errors)

    def test_matrix_receipt_rejects_unexecuted_declared_cases(self) -> None:
        module = load_validator()
        matrix = {
            "cases": [
                {
                    "case_id": f"case-{category}",
                    "category": category,
                    "validation_surface": category,
                    "expected_observation": "pass",
                }
                for category in module.MATRIX_CATEGORIES
            ],
            "authorizes": [],
        }
        errors: list[str] = []
        module.validate_matrix_receipt(matrix, {"status": "pass", "authorizes": []}, errors)
        self.assertTrue(any("one result per case" in error for error in errors), errors)

    def test_matrix_receipt_rejects_observation_mismatch(self) -> None:
        module = load_validator()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            matrix = {
                "cases": [
                    {
                        "case_id": f"case-{category}",
                        "category": category,
                        "validation_surface": category,
                        "expected_observation": "expected",
                    }
                    for category in module.MATRIX_CATEGORIES
                ],
                "authorizes": [],
            }
            matrix_path = root / module.MATRIX_PATH
            matrix_path.parent.mkdir(parents=True, exist_ok=True)
            matrix_path.write_text(json.dumps(matrix), encoding="utf-8", newline="\n")
            evidence = root / "evidence.json"
            evidence.write_text("{}\n", encoding="utf-8", newline="\n")
            receipt = {
                "status": "pass",
                "exit_code": 0,
                "runner_entrypoint": module.CURRENT_REPLAY_ENTRYPOINT,
                "command": module.MATRIX_REPLAY_COMMAND,
                "matrix_path": module.MATRIX_PATH,
                "matrix_sha256": module.file_sha256(matrix_path),
                "case_results": [
                    {
                        "case_id": case["case_id"],
                        "category": case["category"],
                        "validation_surface": case["validation_surface"],
                        "status": "pass",
                        "observed_result": "unexpected",
                        "evidence": [{"path": "evidence.json", "sha256": module.file_sha256(evidence)}],
                    }
                    for case in matrix["cases"]
                ],
                "authorizes": [],
            }
            errors: list[str] = []
            module.validate_matrix_receipt(matrix, receipt, errors, repository_root=root)
            self.assertTrue(any("expected observations" in error for error in errors), errors)

    def test_terminal_command_stdout_must_equal_saved_receipt(self) -> None:
        module = load_validator()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            receipt_path = root / "receipt.json"
            receipt = {"status": "pass", "authorizes": []}
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8", newline="\n")
            original_root = module.REPOSITORY_ROOT
            module.REPOSITORY_ROOT = root
            try:
                result = module.run_json_receipt(
                    [sys.executable, "-c", "import json; print(json.dumps({'status':'pass','authorizes':[]}))"],
                    receipt_path,
                    30,
                )
                mismatch = module.run_json_receipt(
                    [sys.executable, "-c", "import json; print(json.dumps({'status':'fail','authorizes':[]}))"],
                    receipt_path,
                    30,
                )
            finally:
                module.REPOSITORY_ROOT = original_root
            self.assertTrue(result["receipt_match"])
            self.assertFalse(mismatch["receipt_match"])

    def test_core_skill_routes_require_exact_repository_wrapper_commands(self) -> None:
        module = load_validator()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            vdd = root / ".agents/skills/vdd-execution-plan/SKILL.md"
            acceptance = root / ".agents/skills/run-refactor-implementation-acceptance/SKILL.md"
            vdd.parent.mkdir(parents=True, exist_ok=True)
            acceptance.parent.mkdir(parents=True, exist_ok=True)
            vdd.write_text("# VDD\n", encoding="utf-8", newline="\n")
            acceptance.write_text("# Acceptance\n", encoding="utf-8", newline="\n")
            original_root = module.REPOSITORY_ROOT
            module.REPOSITORY_ROOT = root
            try:
                missing_errors: list[str] = []
                module.check_skill_routes(missing_errors)
                vdd.write_text(
                    "## Repository-Owned Package Validation\n\nUse this repository-owned command for Skill package validation:\n\n```text\npy -3 -B scripts/sc/skill_package_replay.py validate-package --target .agents/skills/vdd-execution-plan --capability scripts/sc/config/skill-package-validator-capability.v1.json\n```\n",
                    encoding="utf-8",
                    newline="\n",
                )
                acceptance.write_text(
                    "## Repository-Owned Package Validation\n\nUse this repository-owned command for Skill package validation:\n\n```text\npy -3 -B scripts/sc/skill_package_replay.py validate-package --target .agents/skills/run-refactor-implementation-acceptance --capability scripts/sc/config/skill-package-validator-capability.v1.json\n```\n",
                    encoding="utf-8",
                    newline="\n",
                )
                routed_errors: list[str] = []
                module.check_skill_routes(routed_errors)
            finally:
                module.REPOSITORY_ROOT = original_root
            self.assertEqual(2, len(missing_errors))
            self.assertEqual([], routed_errors)


if __name__ == "__main__":
    unittest.main()
