from __future__ import annotations

import copy
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

    def test_authorization_proof_package_golden_declares_required_execution_role(self) -> None:
        fixture = SKILL_ROOT / "scripts" / "fixtures" / "authorization-proof-package-golden.json"
        payload = json.loads(fixture.read_text(encoding="utf-8"))
        self.assertEqual("deterministic-package", payload["assurance_level"])
        self.assertIn("result-envelope", payload["roles"]["execution"])

    def test_authorization_proof_package_validator_rejects_dimension_and_lineage_mutations(self) -> None:
        script = SKILL_ROOT / "scripts" / "authorization_proof_package.py"
        fixture = SKILL_ROOT / "scripts" / "fixtures" / "authorization-proof-package-golden.json"
        for mutate in (
            lambda item: item["proofs"][0]["dimension_verdicts"].pop("immutable_identity"),
            lambda item: item["proofs"][0]["lineage"].update({"status": "supersedes", "predecessor": None}),
            lambda item: item["predicate_closures"]["plan-ready"].update({"mode": "shared-superset", "coverage_proof": False}),
        ):
            with self.subTest(mutate=mutate):
                with tempfile.TemporaryDirectory() as tmp:
                    candidate = Path(tmp) / "package.json"
                    payload = json.loads(fixture.read_text(encoding="utf-8"))
                    mutate(payload)
                    candidate.write_text(json.dumps(payload), encoding="utf-8")
                    completed = subprocess.run([sys.executable, str(script), str(candidate)], capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(1, completed.returncode, completed.stdout + completed.stderr)

    def test_authorization_proof_package_orchestrator_writes_restricted_pass_envelope(self) -> None:
        script = SKILL_ROOT / "scripts" / "authorization_proof_package.py"
        fixture = SKILL_ROOT / "scripts" / "fixtures" / "authorization-proof-package-golden.json"
        with tempfile.TemporaryDirectory() as tmp:
            result_path = Path(tmp) / "result.json"
            completed = subprocess.run([sys.executable, str(script), str(fixture), "--result", str(result_path)], capture_output=True, text=True, encoding="utf-8")
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertEqual("PASS", payload["status"])
        self.assertEqual(["deterministic-package-validation"], payload["authorizes"])
        self.assertIn("release-ready", payload["does_not_authorize"])

    def test_authorization_proof_package_integration_registry_reports_failing_validator(self) -> None:
        script = SKILL_ROOT / "scripts" / "authorization_proof_package.py"
        fixture = SKILL_ROOT / "scripts" / "fixtures" / "authorization-proof-package-golden.json"
        registry = SKILL_ROOT / "scripts" / "fixtures" / "authorization-proof-package-integration.json"
        completed = subprocess.run([sys.executable, str(script), str(fixture), "--integration-registry", str(registry)], cwd=SKILL_ROOT.parents[2], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(1, completed.returncode)
        self.assertIn("VDD-PACKAGE-INTEGRATION-EXECUTION", completed.stdout)

    def test_authorization_package_executes_registered_integration_validator(self) -> None:
        script = SKILL_ROOT / "scripts" / "authorization_proof_package.py"
        fixture = SKILL_ROOT / "scripts" / "fixtures" / "authorization-proof-package-golden.json"
        with tempfile.TemporaryDirectory() as tmp:
            registry = Path(tmp) / "integration.json"
            registry.write_text(json.dumps({
                "schema_version": "vdd.authorization-proof-package-integration.v1",
                "fixtures": [
                    {"id": "golden", "kind": "golden", "package": str(fixture), "expected_assurance": "deterministic-package"},
                    {"id": "failing-validator", "kind": "integration", "package": str(fixture), "validator": str(fixture), "arguments": [], "expected_assurance": "deterministic-package"},
                ],
            }), encoding="utf-8", newline="\n")
            completed = subprocess.run([sys.executable, str(script), str(fixture), "--integration-registry", str(registry)], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(1, completed.returncode)
        self.assertIn("VDD-PACKAGE-INTEGRATION-EXECUTION", completed.stdout)

    def test_authorization_package_rejects_zero_exit_integration_without_pass_envelope(self) -> None:
        script = SKILL_ROOT / "scripts" / "authorization_proof_package.py"
        fixture = SKILL_ROOT / "scripts" / "fixtures" / "authorization-proof-package-golden.json"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            validator = root / "validator.py"
            validator.write_text("import json\nprint(json.dumps({}))\n", encoding="utf-8", newline="\n")
            registry = root / "integration.json"
            registry.write_text(json.dumps({
                "schema_version": "vdd.authorization-proof-package-integration.v1",
                "fixtures": [
                    {"id": "golden", "kind": "golden", "package": str(fixture), "expected_assurance": "deterministic-package"},
                    {"id": "zero-exit-invalid", "kind": "integration", "package": str(fixture), "validator": str(validator), "arguments": [], "expected_assurance": "deterministic-package", "expected_result_schema": "rmap.validation-result.v1", "expected_predicate": "plan-ready", "expected_status": "pass", "required_bindings": ["candidate_hash", "current_candidate_hash"]},
                ],
            }), encoding="utf-8", newline="\n")
            completed = subprocess.run([sys.executable, str(script), str(fixture), "--integration-registry", str(registry)], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(1, completed.returncode)
        self.assertIn("VDD-PACKAGE-INTEGRATION-RESULT", completed.stdout)

    def test_authorization_package_rejects_self_registered_semantic_authority(self) -> None:
        script = SKILL_ROOT / "scripts" / "authorization_proof_package.py"
        fixture = SKILL_ROOT / "scripts" / "fixtures" / "authorization-proof-package-golden.json"
        with tempfile.TemporaryDirectory() as tmp:
            payload = json.loads(fixture.read_text(encoding="utf-8"))
            for proof in payload["proofs"]:
                proof["producer_authority"]["path"] = "forged/authority.md"
            for authority in payload["semantic_contract"]["authorities"].values():
                authority["path"] = "forged/authority.md"
            package = Path(tmp) / "package.json"
            package.write_text(json.dumps(payload), encoding="utf-8", newline="\n")
            completed = subprocess.run([sys.executable, str(script), str(package), "--orchestrate"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(1, completed.returncode)
        self.assertIn("VDD-PACKAGE-SEMANTIC-ROOT", completed.stdout)

    def test_authorization_package_recomputes_git_binary_closure_and_lineage(self) -> None:
        script = SKILL_ROOT / "scripts" / "authorization_proof_package.py"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tracked = root / "tracked.txt"
            binary = root / "runtime.bin"
            tracked.write_text("tracked\n", encoding="utf-8", newline="\n")
            binary.write_bytes(b"\x00runtime\xff")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "add", "tracked.txt"], cwd=root, check=True)
            subprocess.run(["git", "-c", "user.name=VDD", "-c", "user.email=vdd@example.invalid", "commit", "-qm", "fixture"], cwd=root, check=True)
            tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=root, text=True).strip()
            mode, _, blob, _ = subprocess.check_output(["git", "ls-tree", tree, "--", "tracked.txt"], cwd=root, text=True).split()
            binary_hash = __import__("hashlib").sha256(binary.read_bytes()).hexdigest()
            payload = json.loads((SKILL_ROOT / "scripts/fixtures/authorization-proof-package-golden.json").read_text(encoding="utf-8"))
            members = ["tracked", "runtime"]
            closure_root = "sha256:" + __import__("hashlib").sha256(json.dumps(sorted(members), separators=(",", ":")).encode("utf-8")).hexdigest()
            payload["predicate_closures"] = {"plan-ready": {"producer": "manifest-discovery", "verifier": "consumer-trace", "producer_discovery": {"id": "builtin:in-closure-proofs"}, "verifier_discovery": {"id": "builtin:typed-proofs"}, "mode": "exact", "producer_members": members, "verifier_members": members, "members": members, "closure_root": closure_root}}
            payload["baseline"] = {"records": {"tracked": blob}}
            static = dict(payload["proofs"][0])
            runtime = dict(payload["proofs"][1])
            static.update({"id": "tracked", "identity": {"kind": "git-tracked", "tree": tree, "path": "tracked.txt", "mode": mode, "blob": blob}, "lineage": {"status": "unchanged", "predecessor": blob}})
            runtime.update({"id": "runtime", "content_path": "runtime.bin", "identity": {"kind": "binary", "sha256": binary_hash, "byte_length": len(binary.read_bytes())}, "lineage": {"status": "new", "predecessor": None}})
            payload["proofs"] = [static, runtime]
            package = root / "package.json"
            package.write_text(json.dumps(payload), encoding="utf-8", newline="\n")
            completed = subprocess.run([sys.executable, str(script), str(package), "--repository-root", str(root)], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            payload["predicate_closures"]["plan-ready"]["closure_root"] = "sha256:stale"
            payload["proofs"][1]["identity"]["sha256"] = "0" * 64
            package.write_text(json.dumps(payload), encoding="utf-8", newline="\n")
            refreshed = subprocess.run([sys.executable, str(script), str(package), "--repository-root", str(root), "--refresh", "--orchestrate"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, refreshed.returncode, refreshed.stdout + refreshed.stderr)

    def test_authorization_package_rejects_each_dimension_in_isolation(self) -> None:
        script = SKILL_ROOT / "scripts" / "authorization_proof_package.py"
        source = SKILL_ROOT / "scripts/fixtures/authorization-proof-package-golden.json"
        dimensions = ("schema_producer_authority", "immutable_identity", "source_of_truth_derivation", "independent_recomputation", "staleness_propagation", "recovery_supersession", "consumer_authorization_boundary")
        for dimension in dimensions:
            with self.subTest(dimension=dimension), tempfile.TemporaryDirectory() as tmp:
                payload = json.loads(source.read_text(encoding="utf-8"))
                payload["proofs"][0]["dimension_verdicts"][dimension] = "NON-AUTHORITATIVE"
                package = Path(tmp) / "package.json"
                package.write_text(json.dumps(payload), encoding="utf-8")
                completed = subprocess.run([sys.executable, str(script), str(package)], capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(1, completed.returncode)
                self.assertIn("VDD-PACKAGE-DIMENSION:" + dimension, completed.stdout)

    def test_authorization_package_rejects_unknown_producer_authority(self) -> None:
        script = SKILL_ROOT / "scripts" / "authorization_proof_package.py"
        source = SKILL_ROOT / "scripts/fixtures/authorization-proof-package-golden.json"
        with tempfile.TemporaryDirectory() as tmp:
            payload = json.loads(source.read_text(encoding="utf-8"))
            payload["proofs"][0]["producer_authority"]["id"] = "forged-producer"
            package = Path(tmp) / "package.json"
            package.write_text(json.dumps(payload), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(script), str(package)],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        self.assertEqual(1, completed.returncode)
        self.assertIn("VDD-PACKAGE-DIMENSION:schema_producer_authority", completed.stdout)

    def test_authorization_package_rejects_shared_closure_discovery_callable(self) -> None:
        script = SKILL_ROOT / "scripts" / "authorization_proof_package.py"
        source = SKILL_ROOT / "scripts" / "fixtures" / "authorization-proof-package-golden.json"
        with tempfile.TemporaryDirectory() as tmp:
            payload = json.loads(source.read_text(encoding="utf-8"))
            closure = payload["predicate_closures"]["plan-ready"]
            closure["verifier_discovery"] = dict(closure["producer_discovery"])
            package = Path(tmp) / "package.json"
            package.write_text(json.dumps(payload), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(script), str(package)],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        self.assertEqual(1, completed.returncode)
        self.assertIn("VDD-PACKAGE-CLOSURE:plan-ready", completed.stdout)

    def test_authorization_package_recomputes_generated_text_identity(self) -> None:
        script = SKILL_ROOT / "scripts" / "authorization_proof_package.py"
        source = SKILL_ROOT / "scripts" / "fixtures" / "authorization-proof-package-golden.json"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text_path = root / "generated.txt"
            text_path.write_bytes(b"line one\r\nline two\r\n")
            payload = json.loads(source.read_text(encoding="utf-8"))
            identity = {
                "kind": "generated-text",
                "canonicalization_rule": "utf8-lf-v1",
                "normalized_sha256": "sha256:" + __import__("hashlib").sha256(b"line one\nline two\n").hexdigest(),
                "raw_sha256": "sha256:" + __import__("hashlib").sha256(text_path.read_bytes()).hexdigest(),
            }
            for proof in payload["proofs"]:
                proof["content_path"] = "generated.txt"
                proof["identity"] = dict(identity)
            package = root / "package.json"
            package.write_text(json.dumps(payload), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(script), str(package), "--repository-root", str(root)],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)

    def test_authorization_package_rejects_unregistered_external_validation_envelope(self) -> None:
        script = SKILL_ROOT / "scripts" / "authorization_proof_package.py"
        fixture = SKILL_ROOT / "scripts" / "fixtures" / "authorization-proof-package-golden.json"
        with tempfile.TemporaryDirectory() as tmp:
            envelope = Path(tmp) / "external-envelope.json"
            envelope.write_text(json.dumps({"root_id": "forged", "signer": "forged"}), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(script), str(fixture), "--external-envelope", str(envelope)],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        self.assertEqual(1, completed.returncode)

    def test_authorization_package_rejects_unsigned_registered_external_envelope(self) -> None:
        script = SKILL_ROOT / "scripts" / "authorization_proof_package.py"
        fixture = SKILL_ROOT / "scripts" / "fixtures" / "authorization-proof-package-golden.json"
        with tempfile.TemporaryDirectory() as tmp:
            envelope = Path(tmp) / "external-envelope.json"
            envelope.write_text(json.dumps({
                "schema_version": "vdd.external-validation-envelope.v1",
                "root_id": "vdd-local-deterministic",
                "signer": "repository-local-deterministic-runner",
                "validator_identity": "vdd.authorization_proof_package.validate.v1",
                "package_sha256": "sha256:" + __import__("hashlib").sha256(fixture.read_bytes()).hexdigest(),
            }), encoding="utf-8", newline="\n")
            completed = subprocess.run([sys.executable, str(script), str(fixture), "--external-envelope", str(envelope)], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(1, completed.returncode)
        self.assertIn("VDD-PACKAGE-EXTERNAL-ENVELOPE", completed.stdout)
        self.assertIn("VDD-PACKAGE-EXTERNAL-ENVELOPE", completed.stdout)

    def test_authorization_package_orchestrator_reports_seven_mutation_checks(self) -> None:
        script = SKILL_ROOT / "scripts" / "authorization_proof_package.py"
        fixture = SKILL_ROOT / "scripts/fixtures/authorization-proof-package-golden.json"
        completed = subprocess.run([sys.executable, str(script), str(fixture), "--orchestrate"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(7, len(payload["mutation_checks"]))
        self.assertTrue(all(item["status"] == "rejected" for item in payload["mutation_checks"]))

    def test_authorization_package_result_binds_current_inputs_and_rule_checks(self) -> None:
        script = SKILL_ROOT / "scripts" / "authorization_proof_package.py"
        fixture = SKILL_ROOT / "scripts/fixtures/authorization-proof-package-golden.json"
        completed = subprocess.run(
            [sys.executable, str(script), str(fixture), "--orchestrate"],
            capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        payload = json.loads(completed.stdout)
        bindings = json.loads(fixture.read_text(encoding="utf-8"))["bindings"]
        self.assertEqual(bindings["candidate_hash"], payload["candidate_hash"])
        self.assertEqual(bindings["source_hash"], payload["source_hash"])
        self.assertEqual(bindings["validator_root"], payload["validator_root"])
        self.assertEqual(bindings["authority_root"], payload["authority_root"])
        self.assertEqual(bindings["closure_definition_hash"], payload["closure_definition_hash"])
        self.assertEqual(
            {"VDD-PACKAGE-DIMENSION:" + dimension for dimension in (
                "schema_producer_authority", "immutable_identity", "source_of_truth_derivation",
                "independent_recomputation", "staleness_propagation", "recovery_supersession",
                "consumer_authorization_boundary",
            )},
            {item["rule_id"] for item in payload["checks"]},
        )

    def test_authorization_package_result_uses_bootstrap_mutation_contract(self) -> None:
        script = SKILL_ROOT / "scripts" / "authorization_proof_package.py"
        fixture = SKILL_ROOT / "scripts/fixtures/authorization-proof-package-golden.json"
        completed = subprocess.run(
            [sys.executable, str(script), str(fixture), "--orchestrate"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(
            {"dimension", "expected_rule_id", "status"},
            set(payload["mutation_checks"][0]),
        )
        self.assertEqual("rejected", payload["mutation_checks"][0]["status"])

    def test_clean_skill_passes(self) -> None:
        result = self.validator.validate_skill(SKILL_ROOT)
        self.assertTrue(result["ok"], result)
        self.assertEqual([], result["findings"])

    def test_authorization_proof_package_mutations_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mutated = Path(tmp) / "skill"
            shutil.copytree(SKILL_ROOT, mutated)
            golden = mutated / "scripts/fixtures/authorization-proof-package-golden.json"
            payload = json.loads(golden.read_text(encoding="utf-8"))
            payload["roles"]["execution"].remove("result-envelope")
            golden.write_text(json.dumps(payload), encoding="utf-8")
            result = self.validator.validate_skill(mutated)
        self.assertIn("VDD-SKILL-CONTRACT", {item["rule_id"] for item in result["findings"]})

    def test_authorization_package_schema_rejects_missing_runtime_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mutated = Path(tmp) / "skill"
            shutil.copytree(SKILL_ROOT, mutated)
            schema = mutated / "scripts/fixtures/authorization-proof-package-schema.json"
            payload = json.loads(schema.read_text(encoding="utf-8"))
            del payload["runtime_proof_required_fields"]
            schema.write_text(json.dumps(payload), encoding="utf-8")
            result = self.validator.validate_skill(mutated)
        self.assertIn("VDD-SKILL-CONTRACT", {item["rule_id"] for item in result["findings"]})

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

    def test_pass_result_requires_deterministic_package_assurance(self) -> None:
        fixture = SKILL_ROOT / "scripts" / "fixtures" / "validation-result-pass.json"
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "result.json"
            payload = json.loads(fixture.read_text(encoding="utf-8"))
            payload["assurance_level"] = "fresh-context-observed"
            candidate.write_text(
                json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n"
            )
            result = self.validator.validate_result_fixture(SKILL_ROOT, candidate)
        self.assertIn("VDD-RESULT-ASSURANCE", {item["rule_id"] for item in result["findings"]})

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

    def test_authorization_proof_package_identity_mutation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mutated = Path(tmp) / "skill"
            shutil.copytree(SKILL_ROOT, mutated)
            target = mutated / "scripts" / "skill-contract.json"
            contract = json.loads(target.read_text(encoding="utf-8"))
            golden = mutated / "scripts/fixtures/authorization-proof-package-golden.json"
            payload = json.loads(golden.read_text(encoding="utf-8"))
            payload["identity_policy"]["binary"] = ["raw-sha256"]
            golden.write_text(json.dumps(payload), encoding="utf-8")
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
