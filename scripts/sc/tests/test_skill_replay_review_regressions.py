"""Behavioral regression checks for TC-D1 review repairs (Accepted ADR-0058)."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import os
from pathlib import Path
from unittest import mock

ENTRY = Path(__file__).resolve().parents[1] / "skill_package_replay.py"
SPEC = importlib.util.spec_from_file_location("review_replay", ENTRY)
replay = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(replay)


class ReviewRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patch = mock.patch.object(replay, "ROOT", self.root)
        self.patch.start()
        self.write("candidate/SKILL.md", "INVALID PACKAGE\n")
        self.validator = self.write("validator/check.py", "import sys\nfrom pathlib import Path\nexpected=Path(__file__).resolve().parent.parent/'candidate'\nraise SystemExit(0 if Path(sys.argv[1]).resolve()==expected else 2)\n")
        self.cap = {"allowed_root": "validator", "validator_entrypoint": "check.py", "validator_sha256": replay.digest(self.validator), "probe_args": ["{target}"], "state": "active", "authorizes": [], "validator_source": "validator/source.py", "validator_source_sha256": replay.digest(self.validator), "required_rules": []}
        self.cap["negative_probe"] = {"path": "SKILL.md", "replacement": {}, "diagnostic": "invalid-fixture"}
        self.write("validator/source.py", self.validator.read_text(encoding="utf-8"))
        self.write("capability.json", json.dumps(self.cap))

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def write(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        return path

    def test_path_only_validator_cannot_claim_effective_target_reads(self):
        with self.assertRaises((ValueError, RuntimeError)):
            replay.validate_package("candidate", "capability.json")

    def test_validator_cannot_be_its_own_independent_source(self):
        cap = dict(self.cap, validator_source="validator/check.py")
        with self.assertRaises(ValueError):
            replay.independent_validator_verification(self.validator, cap)

    def test_six_labels_and_copies_do_not_qualify_as_stable_matrix(self):
        self.validator.write_text("import sys\nfrom pathlib import Path\nraise SystemExit(0 if (Path(sys.argv[1])/'SKILL.md').is_file() else 2)\n", encoding="utf-8")
        self.cap.update(validator_sha256=replay.digest(self.validator), validator_source_sha256=replay.digest(self.validator))
        self.write("validator/source.py", self.validator.read_text(encoding="utf-8"))
        self.write("capability.json", json.dumps(self.cap))
        cases = []
        for index in range(6):
            source = self.write(f"inputs/{index}.txt", f"label-{index}\n")
            cases.append({"case_id": f"case-{index}", "target": "candidate", "stable_target": "candidate", "candidate_target": "candidate", "capability": "capability.json", "expected_exit": 0, "matrix_input": {"input_id": f"input-{index}", "source_path": f"inputs/{index}.txt", "source_sha256": replay.digest(source)}, "fixture_state_assignments": {"Stable": {"fixture_id": "missing-stable", "state_id": "prior"}, "Candidate": {"fixture_id": "missing-candidate", "state_id": "new"}}})
        self.write("matrix.json", json.dumps({"schema_version": "jimuyun.stable-candidate-replay-matrix.v2", "subject_contract": "independent-stable-candidate-v1", "cases": cases, "authorizes": []}))
        result, code = replay.replay_matrix("matrix.json")
        self.assertNotEqual(0, code)
        self.assertFalse(result["aggregate_valid"])

    def snapshot_fixture(self):
        for relative in ("scripts/sc/skill_package_replay.py", replay.PRIMARY_CAPABILITY, "execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/stable-candidate-replay-matrix.v1.json", ".agents/skills/vdd-execution-plan/SKILL.md", ".agents/skills/run-refactor-implementation-acceptance/SKILL.md", "scripts/sc/tests/test_workflow_model_routing.py"):
            self.write(relative, "fixture\n")
        return self.write(".agents/skills/vdd-execution-plan/scripts/validate_skill_contract.py", "raise SystemExit(0)\n")

    def test_consumer_executable_changes_invalidate_snapshot(self):
        entry = self.snapshot_fixture()
        before = replay.current_snapshot_binding("candidate", "capability.json", self.validator)
        entry.write_text("raise SystemExit(17)\n", encoding="utf-8")
        after = replay.current_snapshot_binding("candidate", "capability.json", self.validator)
        self.assertNotEqual(before["sha256"], after["sha256"])

    def test_failed_required_consumer_cannot_be_a_successful_replay(self):
        self.snapshot_fixture()
        receipt = {"status": "pass", "resolved_validator": {"path": "validator/check.py", "sha256": replay.digest(self.validator)}, "effective_inspected_content": {"identity": "target-id"}, "effective_read_witness": {"target_identity": "target-id"}, "probes": []}
        with mock.patch.object(replay.subprocess, "run", return_value=subprocess.CompletedProcess([], 17, "", "consumer failed")):
            with self.assertRaises((ValueError, RuntimeError)):
                replay.replay_metadata("candidate", "capability.json", receipt, {"sha256": "snapshot"}, "verdict")


class NativeRuntimeTests(unittest.TestCase):
    """Actual processes and immutable Git inputs; no mocked validation results."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patch = mock.patch.object(replay, "ROOT", self.root)
        self.patch.start()
        self.write("candidate/SKILL.md", "A supported fixture Skill package.\n")
        self.write("candidate/fixture.json", '{"valid":true}\n')
        self.write("candidate/feature.py", "def result():\n    return 1\n")
        code = "import json,sys\nfrom pathlib import Path\np=Path(sys.argv[-1])/'fixture.json'\ntry:\n valid=json.loads(p.read_text(encoding='utf-8')).get('valid') is True\nexcept (OSError,ValueError):\n valid=False\nprint(json.dumps({'findings':[] if valid else ['invalid-fixture']}))\nraise SystemExit(0 if valid else 2)\n"
        validator = self.write("validator/check.py", code)
        source = self.write("authority/source.py", code)
        self.cap = {"allowed_root": "validator", "validator_entrypoint": "check.py", "validator_sha256": replay.digest(validator), "probe_args": ["{target}"], "state": "active", "authorizes": [], "validator_source": "authority/source.py", "validator_source_sha256": replay.digest(source), "required_rules": [], "negative_probe": {"path": "fixture.json", "replacement": {"valid": False}, "diagnostic": "invalid-fixture"}}
        self.write("capability.json", json.dumps(self.cap))
        for entry in ("skill_package_replay.py", "skill_replay_runtime.py", "skill_replay_observer.py"):
            self.write("scripts/sc/" + entry, ENTRY.with_name(entry).read_text(encoding="utf-8"))
        for name, entry in replay.runtime.CONSUMERS[:2]:
            self.write(entry, code)
            target = replay.runtime.PACKAGE_ROOTS[1] if name == "vdd-execution-plan" else replay.runtime.PACKAGE_ROOTS[0]
            self.write(target + "/SKILL.md", "Consumer fixture\n")
            self.write(target + "/fixture.json", '{"valid":true}\n')
        vdd_code = code.replace("/'fixture.json'", "/'scripts'/'skill-contract.json'").replace("invalid-fixture", "VDD-SKILL-CONTRACT").replace("except (OSError,ValueError):", "except (OSError,ValueError,AttributeError):")
        self.write(replay.runtime.CONSUMERS[0][1], vdd_code)
        self.write(replay.runtime.PACKAGE_ROOTS[1] + "/scripts/skill-contract.json", '{"valid":true}\n')
        self.write("scripts/sc/terminal.json", '{"observe_only":true}\n')
        self.write(replay.runtime.CONSUMERS[2][1], "from pathlib import Path\nprint((Path(__file__).parent.parent/'terminal.json').read_text(encoding='utf-8'))\n")
        history = "execution-plans/2026-08-01-refactor-acceptance-toolchain-compact-vdd/"
        self.write(history + "tools/validate_implementation.py", "# Preserved historical validator\n")
        self.write(history + "95-implementation-evolution-and-completion-report.md", "Original machine-bound command evidence\n")
        self.git("init", "-q")
        self.git("config", "user.name", "TC-D1 test")
        self.git("config", "user.email", "tc-d1-test@example.invalid")
        self.git("config", "core.autocrlf", "false")
        self.git("add", ".")
        self.git("commit", "-qm", "Immutable existing validator and subject")
        self.commit = self.git("rev-parse", "HEAD").strip()
        self.environment = mock.patch.dict(os.environ, {"TC_D1_TRUST_COMMIT": self.commit})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.patch.stop()
        self.temp.cleanup()

    def write(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        return path

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True, encoding="utf-8", check=True).stdout

    def test_real_target_reads_and_same_location_probe_oracle(self):
        receipt = replay.validate_package("candidate", "capability.json")
        self.assertEqual("pass", receipt["status"])
        self.assertEqual(["fixture.json"], receipt["effective_read_witness"]["observed_paths"])
        self.assertNotEqual(receipt["target_observation"]["detached_positive_identity"], receipt["target_observation"]["detached_negative_identity"])
        self.assertEqual(receipt["probes"][1]["actual_target"], receipt["probes"][2]["actual_target"])
        self.assertEqual("invalid-fixture", receipt["target_observation"]["negative_diagnostic"])

    def test_path_only_validator_with_valid_immutable_trust_is_rejected(self):
        code = "import sys\nfrom pathlib import Path\nraise SystemExit(0 if Path(sys.argv[1])==Path(__file__).resolve().parent.parent/'candidate' else 2)\n"
        self.write("validator/check.py", code)
        self.write("authority/source.py", code)
        self.cap.update(validator_sha256=replay.digest(self.root / "validator/check.py"), validator_source_sha256=replay.digest(self.root / "authority/source.py"))
        self.write("capability.json", json.dumps(self.cap))
        self.git("add", ".")
        self.git("commit", "-qm", "Independent test authority pins path-only validator")
        with mock.patch.dict(os.environ, {"TC_D1_TRUST_COMMIT": self.git("rev-parse", "HEAD").strip()}):
            with self.assertRaisesRegex(ValueError, "no execution-time target reads"):
                replay.validate_package("candidate", "capability.json")

    def test_joint_validator_source_and_descriptor_drift_requires_external_approval(self):
        code = (self.root / "validator/check.py").read_text(encoding="utf-8") + "\n# Jointly changed candidate-controlled source\n"
        self.write("validator/check.py", code)
        self.write("authority/source.py", code)
        self.cap.update(validator_sha256=replay.digest(self.root / "validator/check.py"), validator_source_sha256=replay.digest(self.root / "authority/source.py"))
        self.write("capability.json", json.dumps(self.cap))
        with self.assertRaisesRegex(ValueError, "Trust Approval"):
            replay.validate_package("candidate", "capability.json")

    def test_unreached_validator_dependency_drift_is_rejected(self):
        self.write("validator/unreached-policy.json", '{"allow":true}')
        self.git("add", ".")
        self.git("commit", "-qm", "Freeze unreached policy dependency")
        commit = self.git("rev-parse", "HEAD").strip()
        self.write("validator/unreached-policy.json", '{"allow":false}')
        with mock.patch.dict(os.environ, {"TC_D1_TRUST_COMMIT": commit}):
            with self.assertRaisesRegex(ValueError, "Trust Approval"):
                replay.validate_package("candidate", "capability.json")

    def test_real_four_stage_consumer_routes_reproduce_frozen_prior(self):
        value, code = replay.replay_package("candidate", "capability.json", "disable")
        self.assertEqual(0, code)
        current = value["current_wrapper_replay"]
        calls = current["consumer_verification"]["calls"]
        self.assertEqual(20, len(calls))
        for consumer, _ in replay.runtime.CONSUMERS:
            stages = [row for row in calls if row["consumer"] == consumer]
            stages = [row for row in stages if row["fixture"] != "invalid-package"]
            self.assertEqual(["enable", "disable", "rollback", "re-enable"], [row["stage"] for row in stages])
            self.assertEqual(stages[1]["route_identity"], stages[2]["route_identity"])
            self.assertNotEqual(stages[0]["route_identity"], stages[1]["route_identity"])
        self.assertEqual("Prior Route", current["consumer_invocation"]["route"])

    def test_native_consumer_failure_blocks_replay(self):
        self.write(replay.runtime.CONSUMERS[0][1], "raise SystemExit(17)\n")
        with self.assertRaisesRegex(ValueError, "required Consumer failed"):
            replay.replay_package("candidate", "capability.json", "enable")

    def test_new_aliased_consumer_is_not_silently_omitted(self):
        self.write("scripts/sc/new_consumer.py", "from package_validation import validate_package as inspect_skill\ninspect_skill(target)\n")
        with self.assertRaisesRegex(ValueError, "undeclared real call surfaces"):
            replay.consumer_manifest()

    def test_native_six_case_comparison_has_provenance_and_real_state_changes(self):
        self.write("candidate/feature.py", "def result():\n    return 2\n")
        replay.runtime.prepare_matrix(self.root, "candidate", "capability.json", self.commit, "logs/native/matrix.json")
        result, code = replay.replay_matrix("logs/native/matrix.json")
        self.assertEqual(0, code, result)
        self.assertEqual(6, len(result["case_results"]))
        for row in result["case_results"]:
            self.assertEqual(2, len(row["subject_executions"]))
            self.assertNotEqual(row["stable_subject"]["subject_identity"], row["candidate_subject"]["subject_identity"])
            if row["category"] in {"dirty_baseline", "knowledge_read_set", "closed_policy"}:
                for subject in row["subject_executions"]:
                    state = subject["observation"]["state_observations"][0]
                    self.assertNotEqual(state["fault_identity"], state["repaired_identity"])
                    self.assertTrue(state["rejection"])

    def test_comment_change_cannot_qualify_as_candidate_behavior_change(self):
        self.write("candidate/feature.py", "def result():\n    return 1\n# label-only difference\n")
        replay.runtime.prepare_matrix(self.root, "candidate", "capability.json", self.commit, "logs/label/matrix.json")
        result, code = replay.replay_matrix("logs/label/matrix.json")
        self.assertNotEqual(0, code)
        self.assertIn("no relevant executable change", result["invalid_reasons"][0])

    def test_fresh_checkout_reconstructs_candidate_dependencies_before_replay(self):
        self.write("candidate/feature.py", "def result():\n    return 2\n")
        result, code = replay.replay_package("candidate", "capability.json", "fresh")
        self.assertEqual(0, code)
        value = result["current_wrapper_replay"]
        self.assertTrue(value["fresh_checkout"])
        self.assertEqual(value["pinned_coverage"], value["fresh_coverage"])
        reconstructed = Path(value["checkout_path"])
        self.assertEqual((self.root / "candidate/feature.py").read_bytes(), (reconstructed / "candidate/feature.py").read_bytes())
        import shutil
        shutil.rmtree(reconstructed.parent)

    def test_utf8_output_keeps_native_crlf_bytes(self):
        result = replay.runtime.execute([sys.executable, "-X", "utf8", "-I", "-S", "-c", "import sys;sys.stdout.buffer.write(b'caf\\xc3\\xa9\\r\\n')"], self.root)
        self.assertEqual("caf\u00e9\r\n", result.stdout)

    def test_environment_change_invalidates_snapshot(self):
        validator = self.root / "validator/check.py"
        before = replay.current_snapshot_binding("candidate", "capability.json", validator)
        with mock.patch.dict(os.environ, {"LANG": "TC-D1-different-locale"}):
            after = replay.current_snapshot_binding("candidate", "capability.json", validator)
        self.assertNotEqual(before["sha256"], after["sha256"])

    def test_archive_requires_native_roots_and_checks_reference_bytes(self):
        specification = importlib.util.spec_from_file_location("archive_audit", ENTRY.with_name("audit_skill_replay_archive.py"))
        audit = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(audit)
        edge = self.write("logs/old-run/canonical-evidence/regression/edge.json", '{"observed":true}\n')
        report = {"slice_id": "S1", "authorizes": [], "snapshot_manifest": {"roots": []}, "assertion_coverage": {"regression": {"A-1": [{"path": "canonical-evidence/regression/edge.json", "sha256": replay.digest(edge)}]}}}
        self.write("q7.json", json.dumps(report))
        inputs = {"snapshot_manifest": {"roots": [{"root_kind": "descriptor", "repository_relative_posix_path": "logs/old-terminal/descriptors"}]}}
        self.write("terminal-input.json", json.dumps(inputs))
        terminal = {"schema": "quick-dev.implementation-complete-result.v2", "authorizes": [], "terminal_input_ref": "terminal-input.json", "terminal_input_sha256": audit.canonical(inputs), "predecessors": [{"slice_id": "S1", "result_ref": "q7.json", "result_sha256": audit.canonical(report), "run_root": "logs/old-run"}]}
        self.write("q8.json", json.dumps(terminal))
        missing = audit.inspect(self.root, "q8.json")
        self.assertEqual("archive-incomplete", missing["status"])
        self.assertIn("logs/old-terminal/descriptors", missing["missing_paths"])
        self.write("logs/old-terminal/descriptors/terminal.json", '{}\n')
        ready = audit.inspect(self.root, "q8.json")
        self.assertEqual("archive-ready", ready["status"])
        self.assertTrue(ready["does_not_validate_current_candidate"])
        edge.write_text('{"observed":false}\n', encoding="utf-8")
        self.assertEqual("archive-incomplete", audit.inspect(self.root, "q8.json")["status"])


if __name__ == "__main__":
    unittest.main()
