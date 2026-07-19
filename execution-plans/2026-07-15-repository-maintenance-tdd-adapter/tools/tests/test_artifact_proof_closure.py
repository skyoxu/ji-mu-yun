from __future__ import annotations

import copy
import ast
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

PLAN_ROOT = Path(__file__).resolve().parents[2]
TOOLS = PLAN_ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from fixture_checks import evaluate_protected_boundary_takeover_fixture, evaluate_synchronized_trust_root_fixture  # noqa: E402
import artifact_proof_guards  # noqa: E402
import artifact_proof_projection_support  # noqa: E402
from validate_all import run_unit_tests  # noqa: E402


REPOSITORY_ROOT = PLAN_ROOT.parents[1]
DIMENSIONS = {
    "schema_producer_authority": "RMAP-ARTIFACT-PROOF-PRODUCER",
    "immutable_identity": "RMAP-ARTIFACT-PROOF-IDENTITY",
    "source_of_truth_derivation": "RMAP-ARTIFACT-PROOF-DERIVATION",
    "independent_recomputation": "RMAP-ARTIFACT-PROOF-RULE",
    "staleness_propagation": "RMAP-ARTIFACT-PROOF-STALENESS",
    "recovery_supersession": "RMAP-ARTIFACT-PROOF-LINEAGE",
    "consumer_authorization_boundary": "RMAP-ARTIFACT-PROOF-CONSUMER",
}


def load_json(relative: str) -> dict:
    return json.loads((PLAN_ROOT / relative).read_text(encoding="utf-8"))


def manifest_maps() -> tuple[dict[str, str], dict[str, str]]:
    manifest = load_json("schemas/authority-manifest.v1.json")
    hashes: dict[str, str] = {}
    categories: dict[str, str] = {}
    for category, entries in manifest["categories"].items():
        for entry in entries:
            hashes[entry["path"]] = entry["sha256"]
            categories[entry["path"]] = category
    return hashes, categories


def production_consumer_paths() -> set[str]:
    plan_prefix = PLAN_ROOT.relative_to(REPOSITORY_ROOT).as_posix()
    validate_tree = ast.parse((TOOLS / "validate_all.py").read_text(encoding="utf-8"))
    validator_names: set[str] = set()
    for node in ast.walk(validate_tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "validator_identity":
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "names" for target in child.targets
            ) and isinstance(child.value, ast.List):
                validator_names = {
                    item.value for item in child.value.elts
                    if isinstance(item, ast.Constant) and isinstance(item.value, str)
                }
    self_tests = {
        f"{plan_prefix}/tools/tests/{path.name}"
        for path in (TOOLS / "tests").glob("test_*.py")
    }
    validator_paths = {f"{plan_prefix}/tools/{name}" for name in validator_names}

    rmap_tree = ast.parse((TOOLS / "rmap_checks.py").read_text(encoding="utf-8"))
    machine_inputs: set[str] = set()
    for node in ast.walk(rmap_tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "load_machine":
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "names" for target in child.targets
            ) and isinstance(child.value, ast.Dict):
                machine_inputs = {
                    f"{plan_prefix}/{item.value}"
                    for item in child.value.values
                    if isinstance(item, ast.Constant) and isinstance(item.value, str)
                }
    manifest = load_json("schemas/authority-manifest.v1.json")
    manifest_inputs = {
        item["path"] for entries in manifest["categories"].values() for item in entries
    }
    return validator_paths | self_tests | machine_inputs | manifest_inputs


def git_baseline_hash(relative: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"HEAD:{relative}"],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    import hashlib

    return "sha256:" + hashlib.sha256(result.stdout).hexdigest()


class ArtifactProofClosureTests(unittest.TestCase):
    def test_every_closure_member_maps_to_an_executable_type_contract(self) -> None:
        closure = load_json("schemas/predicate-artifact-closure.v1.json")
        contracts = closure["type_contracts"]
        for artifact in closure["artifacts"]:
            with self.subTest(path=artifact["path"]):
                contract_id = artifact["type_contract_id"]
                self.assertIn(contract_id, contracts)
                contract = contracts[contract_id]
                self.assertEqual(set(DIMENSIONS), set(contract["dimension_rules"]))
                self.assertEqual(
                    set(DIMENSIONS),
                    set(contract["dimension_verdicts"]),
                )
                self.assertTrue(contract["validator_path"])
                self.assertTrue(contract["validator_callable"])

    def test_closure_verifier_does_not_call_the_projection_builder(self) -> None:
        closure = load_json("schemas/predicate-artifact-closure.v1.json")
        with mock.patch.object(
            artifact_proof_projection_support,
            "build_predicate_artifact_closure",
            side_effect=AssertionError("producer cannot be the verifier oracle"),
        ):
            self.assertEqual(
                [],
                artifact_proof_projection_support.validate_predicate_artifact_closure(
                    REPOSITORY_ROOT, closure
                ),
            )

    def test_candidate_identity_covers_the_complete_authorizing_closure(self) -> None:
        closure = load_json("schemas/predicate-artifact-closure.v1.json")
        members = {item["path"] for item in closure["artifacts"]}
        self.assertEqual(members, set(closure["candidate_hash_scope"]["members"]))
        self.assertEqual("repository", closure["candidate_hash_scope"]["root"])

    def test_validation_result_is_a_formal_authorizing_runtime_type(self) -> None:
        authority = load_json("schemas/artifact-proof-authority.v1.json")
        inventory = load_json("schemas/artifact-proof-required.v1.json")
        runtime = load_json("schemas/runtime-artifact-type-proof.v1.json")
        type_id = "validation-result-instance"
        self.assertIn(type_id, inventory["runtime_types"])
        rule = next(item for item in authority["runtime_types"] if item["type_id"] == type_id)
        proof = next(item for item in runtime["proofs"] if item["type_id"] == type_id)
        self.assertEqual("validation-result", rule["consumer_authorization_boundary"]["predicate"])
        self.assertEqual([], rule["consumer_authorization_boundary"]["authorizes"])
        self.assertEqual(rule, {key: proof[key] for key in rule})

    def test_predicate_closure_covers_real_consumers(self) -> None:
        closure = load_json("schemas/predicate-artifact-closure.v1.json")
        validator = getattr(artifact_proof_guards, "validate_predicate_artifact_closure", None)
        self.assertTrue(callable(validator), "predicate closure validator must be independently callable")
        self.assertEqual([], validator(REPOSITORY_ROOT, closure))
        classified = {item["path"] for item in closure["artifacts"] + closure["excluded"]}
        self.assertLessEqual(production_consumer_paths(), classified)

    def test_authorizing_derivation_cannot_self_reference(self) -> None:
        registry = load_json("schemas/artifact-proof-registry.v1.json")
        closure = load_json("schemas/predicate-artifact-closure.v1.json")
        members = {item["path"] for item in closure["artifacts"]}
        for proof in registry["proofs"]:
            if proof["artifact_path"] not in members:
                continue
            for rule in proof["source_of_truth_derivation"]["rules"]:
                with self.subTest(path=proof["artifact_path"]):
                    self.assertNotEqual(
                        (proof["artifact_path"], "authoritative-bytes"),
                        (rule["source"], rule["derivation"]),
                    )

    def test_lineage_does_not_use_current_hash_as_fake_predecessor(self) -> None:
        authority = load_json("schemas/artifact-proof-authority.v1.json")
        registry = load_json("schemas/artifact-proof-registry.v1.json")
        rules = {item["path"]: item for item in authority["artifacts"]}
        for proof in registry["proofs"]:
            path = proof["artifact_path"]
            lineage = proof["recovery_supersession"]
            baseline = rules[path].get("predecessor_sha256") or git_baseline_hash(path)
            current = "sha256:" + __import__("hashlib").sha256(
                (REPOSITORY_ROOT / path).read_bytes()
            ).hexdigest()
            with self.subTest(path=path):
                if baseline is None:
                    self.assertEqual(("new", None), (lineage["lifecycle_status"], lineage["predecessor_sha256"]))
                elif baseline == current:
                    self.assertEqual(("unchanged", current), (lineage["lifecycle_status"], lineage["predecessor_sha256"]))
                else:
                    self.assertEqual(("supersedes", baseline), (lineage["lifecycle_status"], lineage["predecessor_sha256"]))

    def test_non_authoritative_requires_machine_exclusion(self) -> None:
        closure = load_json("schemas/predicate-artifact-closure.v1.json")
        by_path = {item["path"]: item for item in closure["excluded"]}
        for predicate_id, predicate in closure["predicates"].items():
            members = set(predicate["members"])
            for path in predicate["excluded"]:
                item = by_path[path]
                with self.subTest(predicate=predicate_id, path=path):
                    self.assertNotIn(item["path"], members)
                    self.assertEqual("OUT-OF-CLOSURE", item["classification"])
                    self.assertEqual([], item["authorizes"])
                    self.assertEqual(
                        {"not-read-by-validator", "not-in-predicate-hash", "authorizes-none"},
                        set(item["machine_checks"]),
                    )

    def test_composite_test_runner_has_bounded_fail_closed_execution(self) -> None:
        completed = subprocess.CompletedProcess([], 0, "", "")
        with mock.patch("validate_all.subprocess.run", return_value=completed) as invoked:
            run_unit_tests()
        child_env = invoked.call_args.kwargs["env"]
        self.assertEqual((os.environ.get("TEMP"), os.environ.get("TMP")), (child_env.get("TEMP"), child_env.get("TMP")))
        self.assertGreaterEqual(invoked.call_args.kwargs["timeout"], 300)

        timeout = subprocess.TimeoutExpired([sys.executable, "-m", "unittest"], 300)
        with mock.patch("validate_all.subprocess.run", side_effect=timeout):
            check, findings = run_unit_tests()
        self.assertEqual("fail", check["status"])
        self.assertEqual(["RMAP-UNIT-TESTS"], [item["rule_id"] for item in findings])
        self.assertIn("timeout", findings[0]["message"])

    def test_every_formal_artifact_uses_the_uniform_proof_inventory(self) -> None:
        inventory = load_json("schemas/artifact-proof-required.v1.json")
        authority = load_json("schemas/artifact-proof-authority.v1.json")
        registry = load_json("schemas/artifact-proof-registry.v1.json")
        formal_paths = set(inventory["contract_artifacts"])
        self.assertNotIn("provisional_diagnostic_artifacts", inventory)
        self.assertIn(
            ".agents/skills/run-phase-bootstrap-review/references/artifact-proof-authority-root.v1.json",
            formal_paths,
        )
        self.assertIn(
            ".agents/skills/run-phase-bootstrap-review/scripts/artifact_proof_root_guards.py",
            formal_paths,
        )
        self.assertEqual(formal_paths, {item["path"] for item in authority["artifacts"]})
        self.assertEqual(formal_paths, {item["artifact_path"] for item in registry["proofs"]})

    def test_manifest_boundaries_keep_their_real_artifact_semantics(self) -> None:
        authority = load_json("schemas/artifact-proof-authority.v1.json")
        classes = authority["classes"]
        by_path = {item["path"]: item for item in authority["artifacts"]}
        expected = {
            ".agents/skills/run-phase-bootstrap-review/references/artifact-proof-authority-root.v1.json": (
                "manifest-bound-authority-root",
                "normative",
            ),
            ".agents/skills/run-phase-bootstrap-review/scripts/artifact_proof_root_guards.py": (
                "manifest-bound-validator",
                "validator",
            ),
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/runtime_artifact_proof_guards.py": (
                "manifest-bound-validator",
                "validator",
            ),
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/artifact_proof_projection_support.py": (
                "manifest-bound-validator",
                "validator",
            ),
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/artifact_proof_inventory_support.py": (
                "manifest-bound-validator",
                "validator",
            ),
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/validation_result_guards.py": (
                "manifest-bound-validator",
                "validator",
            ),
        }
        for path, (class_id, artifact_kind) in expected.items():
            with self.subTest(path=path):
                self.assertEqual(class_id, by_path[path]["class_id"])
                self.assertIsNone(by_path[path]["sha256"])
                self.assertEqual(artifact_kind, classes[class_id]["artifact_kind"])
                self.assertEqual("manual-authority", classes[class_id]["producer_authority"]["producer_kind"])
                self.assertEqual("derived-projection", classes[class_id]["identity_mode"])
                self.assertEqual("authoritative-bytes", classes[class_id]["derivation"])

    def test_current_reentry_artifacts_are_authorization_participating(self) -> None:
        registry = load_json("schemas/artifact-proof-registry.v1.json")
        by_path = {item["artifact_path"]: item for item in registry["proofs"]}
        expected = {
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/reentry-successor-20260718/successor-authority.json": [],
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/reentry-successor-20260718/authorization-event.json": [],
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/reentry-successor-20260718/policy-decision.json": [],
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/review-policy-reentry.v1.json": ["manual-pause-reentry"],
        }
        for path, authorizes in expected.items():
            with self.subTest(path=path):
                proof = by_path[path]
                self.assertEqual("authorization-participating", proof["proof_scope"])
                self.assertEqual(authorizes, proof["consumer_authorization_boundary"]["authorizes"])
                self.assertEqual(
                    {"PASS"},
                    {verdict["status"] for verdict in proof["dimension_verdicts"].values()},
                )

    def test_runtime_type_contracts_have_executable_seven_dimension_semantics(self) -> None:
        authority = load_json("schemas/artifact-proof-authority.v1.json")
        runtime = load_json("schemas/runtime-artifact-type-proof.v1.json")
        hashes, categories = manifest_maps()
        validator = getattr(artifact_proof_guards, "validate_runtime_type_proof", None)
        self.assertTrue(callable(validator), "runtime proof validator must be independently callable")
        rules = {item["type_id"]: item for item in authority["runtime_types"]}
        proofs = {item["type_id"]: item for item in runtime["proofs"]}
        inventory = load_json("schemas/artifact-proof-required.v1.json")
        self.assertEqual(set(rules), set(proofs))
        for type_id, rule in rules.items():
            with self.subTest(type_id=type_id):
                self.assertEqual(
                    [],
                    validator(
                        REPOSITORY_ROOT,
                        proofs[type_id],
                        rule,
                        hashes,
                        categories,
                        inventory["predicate_authority"],
                        inventory["registered_consumers"],
                    ),
                )

    def test_each_runtime_dimension_has_an_isolated_fail_closed_mutation(self) -> None:
        authority = load_json("schemas/artifact-proof-authority.v1.json")
        runtime = load_json("schemas/runtime-artifact-type-proof.v1.json")
        inventory = load_json("schemas/artifact-proof-required.v1.json")
        hashes, categories = manifest_maps()
        validator = getattr(artifact_proof_guards, "validate_runtime_type_proof", None)
        self.assertTrue(callable(validator), "runtime proof validator must be independently callable")
        rule = authority["runtime_types"][0]
        base = next(item for item in runtime["proofs"] if item["type_id"] == rule["type_id"])
        mutations = {
            "schema_producer_authority": lambda item: item["schema_producer_authority"].update(
                authority_sha256="sha256:" + "0" * 64
            ),
            "immutable_identity": lambda item: item["immutable_identity"].update(
                schema_sha256="sha256:" + "0" * 64
            ),
            "source_of_truth_derivation": lambda item: item["source_of_truth_derivation"].update(rules=[]),
            "independent_recomputation": lambda item: item["independent_recomputation"].update(
                negative_test_sha256="sha256:" + "0" * 64
            ),
            "staleness_propagation": lambda item: item["staleness_propagation"].update(invalidates=[]),
            "recovery_supersession": lambda item: item["recovery_supersession"].update(lineage_fields=[]),
            "consumer_authorization_boundary": lambda item: item["consumer_authorization_boundary"].update(
                consumers=["unregistered consumer"]
            ),
        }
        for dimension, mutate in mutations.items():
            with self.subTest(dimension=dimension):
                candidate = copy.deepcopy(base)
                mutate(candidate)
                findings = validator(
                    REPOSITORY_ROOT,
                    candidate,
                    rule,
                    hashes,
                    categories,
                    inventory["predicate_authority"],
                    inventory["registered_consumers"],
                )
                self.assertEqual([DIMENSIONS[dimension]], [item["rule_id"] for item in findings])

    def test_full_stack_candidate_takeover_is_rejected_by_external_boundary(self) -> None:
        findings = evaluate_protected_boundary_takeover_fixture(PLAN_ROOT)
        self.assertEqual(
            {"RMAP-ARTIFACT-PROOF-PROTECTED-ROOT"},
            {item["rule_id"] for item in findings},
        )

    def test_synchronized_trust_root_attacks_are_isolated(self) -> None:
        cases = {
            "artifact-proof-synchronized-lattice-escalation": "RMAP-ARTIFACT-PROOF-CONSUMER",
            "artifact-proof-synchronized-staleness-truncation": "RMAP-ARTIFACT-PROOF-PRODUCER",
            "artifact-proof-synchronized-lineage-forgery": "RMAP-ARTIFACT-PROOF-PRODUCER",
            "artifact-proof-synchronized-producer-source": "RMAP-ARTIFACT-PROOF-PRODUCER",
        }
        for fixture_id, expected_rule in cases.items():
            with self.subTest(fixture_id=fixture_id):
                findings = evaluate_synchronized_trust_root_fixture(PLAN_ROOT, fixture_id)
                self.assertEqual([expected_rule], [item["rule_id"] for item in findings])
