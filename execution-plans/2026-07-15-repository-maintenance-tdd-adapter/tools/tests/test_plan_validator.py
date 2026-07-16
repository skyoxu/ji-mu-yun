from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
import uuid
import hashlib
from unittest.mock import patch
from pathlib import Path


PLAN_ROOT = Path(__file__).resolve().parents[2]
TOOLS = PLAN_ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from fixture_checks import apply_mutations, evaluate_fixture  # noqa: E402
from contract_guards import junction_escape_is_rejected, schema_error, typed_path_is_safe  # noqa: E402
from evidence_guards import validate_candidate_review_documents  # noqa: E402
from rmap_checks import (  # noqa: E402
    PREDICATE_AUTHORITY,
    load_machine,
    validate_commands,
    validate_contract,
    validate_coverage,
    validate_deltas,
    validate_plan_state,
    validate_requirements,
    validate_static,
)
from validate_all import validator_identity  # noqa: E402
from rmap_checks import candidate_hash, sha256_file  # noqa: E402


class PlanValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data, cls.load_findings = load_machine(PLAN_ROOT)

    def test_machine_documents_load(self) -> None:
        self.assertEqual([], self.load_findings)

    def test_static_plan_is_valid(self) -> None:
        _, findings, _ = validate_static(PLAN_ROOT)
        self.assertEqual([], findings)

    def test_every_declared_fixture_has_exact_result(self) -> None:
        for case in self.data["fixtures"]["cases"]:
            with self.subTest(case=case["id"]):
                rules = [item["rule_id"] for item in evaluate_fixture(PLAN_ROOT, case["id"], self.data)]
                expected = [] if case["expected_valid"] else [case["expected_rule"]]
                self.assertEqual(expected, rules)

    def test_predicate_authority_is_exact(self) -> None:
        self.assertEqual([], validate_plan_state(self.data["state"]))
        for name, (authorizes, excludes) in PREDICATE_AUTHORITY.items():
            self.assertEqual(authorizes, self.data["state"]["predicates"][name]["authorizes"])
            self.assertEqual(excludes, self.data["state"]["predicates"][name]["does_not_authorize"])

    def test_release_escalation_is_rejected(self) -> None:
        state = copy.deepcopy(self.data["state"])
        state["predicates"]["plan-ready"]["authorizes"].append("release-ready")
        self.assertEqual(["RMAP-AUTH-PREDICATE"], [item["rule_id"] for item in validate_plan_state(state)])

    def test_shell_and_raw_command_are_rejected(self) -> None:
        commands = copy.deepcopy(self.data["commands"])
        commands["shell"] = True
        self.assertEqual(["RMAP-CMD-SHELL"], [item["rule_id"] for item in validate_commands(commands)])
        commands = copy.deepcopy(self.data["commands"])
        commands["commands"][0]["command"] = "py -3 unsafe.py"
        self.assertEqual(["RMAP-CMD-RAW"], [item["rule_id"] for item in validate_commands(commands)])

    def test_contract_schema_required_field_is_enforced(self) -> None:
        contract = copy.deepcopy(self.data["contract"])
        del contract["plan_id"]
        rules = [item["rule_id"] for item in validate_contract(PLAN_ROOT, contract, self.data["requirements"], self.data["commands"])]
        self.assertEqual(["RMAP-STRUCT-SCHEMA"], rules)

    def test_typed_command_path_cannot_escape_plan_root(self) -> None:
        commands = copy.deepcopy(self.data["commands"])
        commands["commands"][0]["argv"][1]["value"] = "../../outside.py"
        rules = [item["rule_id"] for item in validate_commands(commands)]
        self.assertEqual(["RMAP-CMD-PATH-CONTAINMENT"], rules)

    def test_typed_repo_path_rejects_junction_escape(self) -> None:
        with patch.object(tempfile, "TemporaryDirectory", side_effect=PermissionError("default and nested temp denied")):
            self.assertTrue(junction_escape_is_rejected(PLAN_ROOT))
        commands = copy.deepcopy(self.data["commands"])
        commands["commands"][0]["cwd"]["value"] = "C:\\outside"
        rules = [item["rule_id"] for item in validate_commands(commands)]
        self.assertEqual(["RMAP-CMD-PATH-CONTAINMENT"], rules)

    def test_unknown_schema_keyword_fails_closed(self) -> None:
        schema = {"type": "object", "unknownKeyword": True}
        self.assertIn("unsupported schema keywords", schema_error({}, schema) or "")

    def test_validator_identity_binds_all_authorizing_helpers(self) -> None:
        digest = __import__("hashlib").sha256()
        names = ("validate_all.py", "rmap_checks.py", "contract_guards.py", "evidence_guards.py", "shadow_guards.py", "source_guards.py", "slice_guards.py", "fixture_checks.py")
        for name in names:
            path = TOOLS / name
            digest.update(path.name.encode("utf-8")); digest.update(b"\0")
            digest.update(path.read_bytes()); digest.update(b"\0")
        self.assertEqual(f"rmap-plan-validator.v1+sha256:{digest.hexdigest()}", validator_identity())

    def test_nested_write_and_forbidden_globs_overlap(self) -> None:
        contract = copy.deepcopy(self.data["contract"])
        contract["slices"][0]["allowed_changes"]["documentation"][0] = "Docs/**"
        contract["slices"][0]["forbidden_changes"][0] = "docs/standards/**"
        rules = [item["rule_id"] for item in validate_contract(PLAN_ROOT, contract, self.data["requirements"], self.data["commands"])]
        self.assertIn("RMAP-PATH-OVERLAP", rules)

    def test_authority_book_hash_must_be_concrete_and_current(self) -> None:
        contract = copy.deepcopy(self.data["contract"])
        contract["authority"]["source_hashes"]["01-intent-authority-and-non-goals.md"] = "runtime-bound"
        rules = [item["rule_id"] for item in validate_contract(PLAN_ROOT, contract, self.data["requirements"], self.data["commands"])]
        self.assertIn("RMAP-HASH-AUTHORITY", rules)

    def test_s0_exit_predicate_has_reachable_proof_command(self) -> None:
        contract = copy.deepcopy(self.data["contract"])
        contract["slices"][0]["tdd"]["green"]["command_id"] = "rmap-plan-validate"
        rules = [item["rule_id"] for item in validate_contract(PLAN_ROOT, contract, self.data["requirements"], self.data["commands"])]
        self.assertIn("RMAP-TDD-EXIT-PROOF", rules)

    def test_every_slice_exit_predicate_has_reachable_proof_command(self) -> None:
        contract = copy.deepcopy(self.data["contract"])
        contract["slices"][1]["tdd"]["green"]["command_id"] = "rmap-plan-validate"
        rules = [item["rule_id"] for item in validate_contract(PLAN_ROOT, contract, self.data["requirements"], self.data["commands"])]
        self.assertIn("RMAP-TDD-EXIT-PROOF", rules)

    def test_source_coverage_location_is_exact(self) -> None:
        coverage = copy.deepcopy(self.data["coverage"])
        coverage["sources"][0]["sections"][0]["lines"] = "1-1"
        ids = {item["id"] for item in self.data["requirements"]["requirements"]}
        rules = [item["rule_id"] for item in validate_coverage(PLAN_ROOT, coverage, ids)]
        self.assertEqual(["RMAP-REQ-COVERAGE-LOCATION"], rules)

    def test_candidate_review_identity_mismatch_is_rejected(self) -> None:
        candidate = {"candidate_commit_or_tree_hash": "tree-b", "predicate": "implementation-candidate", "status": "pass"}
        review_input = {"authorityRevision": "tree-a", "inputHash": "sha256:" + "1" * 64, "artifacts": []}
        findings = validate_candidate_review_documents(PLAN_ROOT, "logs/tdd-adapter/run/candidate-result.json", candidate, review_input, {}, {}, {}, "implementation-candidate", [], "sha256:" + "2" * 64, "sha256:" + "3" * 64, "RMAP-S6")
        self.assertIn("RMAP-REVIEW-EVIDENCE-BINDING", [item["rule_id"] for item in findings])

    def test_acceptance_rejects_open_blocker_and_undisposed_p2(self) -> None:
        candidate = {"candidate_commit_or_tree_hash": "tree-a", "predicate": "implementation-candidate", "status": "pass"}
        review_input = {"authorityRevision": "tree-a", "inputHash": "sha256:" + "1" * 64, "artifacts": []}
        result = {"status": "blocked", "findings": [{"findingId": "P1-X", "proposedSeverity": "P1", "status": "confirmed"}]}
        findings = validate_candidate_review_documents(PLAN_ROOT, "logs/tdd-adapter/run/candidate-result.json", candidate, review_input, {}, result, {}, "implementation-accepted", [], "sha256:" + "2" * 64, "sha256:" + "3" * 64, "RMAP-S7")
        self.assertIn("RMAP-REVIEW-P0-P1-OPEN", [item["rule_id"] for item in findings])

    def test_current_candidate_and_clean_review_binding_passes(self) -> None:
        repository_root = PLAN_ROOT.parents[1]
        candidate_path = repository_root / "logs" / "tdd-adapter" / f"binding-{uuid.uuid4().hex}.json"
        candidate_path.parent.mkdir(parents=True, exist_ok=True)
        candidate = {
            "schema_version": "jimuyun.tdd-result.v1", "predicate": "implementation-candidate", "status": "pass",
            "plan_hash": candidate_hash(PLAN_ROOT), "source_hash": sha256_file(repository_root / "agentbuild.txt"),
            "slice_id": "RMAP-S6", "authority_revision": "tree-a", "candidate_commit_or_tree_hash": "tree-a",
            "authorizes": ["bootstrap-review"], "does_not_authorize": ["implementation-accepted", "protected-handoff", "release-ready"],
        }
        candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
        relative = candidate_path.relative_to(repository_root).as_posix()
        digest = "sha256:" + hashlib.sha256(candidate_path.read_bytes()).hexdigest()
        identity = {"reviewId": "review-a", "routeVersion": "route-a", "policyRevision": "sha256:" + "4" * 64, "authorityRevision": "tree-a", "inputHash": "sha256:" + "5" * 64}
        review_input = {**identity, "artifacts": [{"artifact": relative, "sha256": digest}], "deterministicPreflightPolicy": {"requiredChecks": ["plan-check"]}, "planBoundRequiredChecks": []}
        preflight = {**identity, "status": "passed", "checks": [{"checkId": "plan-check", "status": "passed"}]}
        review_result = {**identity, "status": "clean", "findings": []}
        dispositions = {**identity, "dispositions": []}
        try:
            findings = validate_candidate_review_documents(PLAN_ROOT, relative, candidate, review_input, preflight, review_result, dispositions, "implementation-candidate", [], candidate_hash(PLAN_ROOT), sha256_file(repository_root / "agentbuild.txt"), "RMAP-S6")
            self.assertEqual([], findings)
            accepted = validate_candidate_review_documents(PLAN_ROOT, relative, candidate, review_input, preflight, review_result, dispositions, "implementation-accepted", [], candidate_hash(PLAN_ROOT), sha256_file(repository_root / "agentbuild.txt"), "RMAP-S6")
            self.assertEqual([], accepted)
        finally:
            candidate_path.unlink(missing_ok=True)

    def test_backend_commit_authority_is_rejected(self) -> None:
        contract = copy.deepcopy(self.data["contract"])
        contract["backend"]["authorities"].append("commit")
        rules = [item["rule_id"] for item in validate_contract(PLAN_ROOT, contract, self.data["requirements"], self.data["commands"])]
        self.assertEqual(["RMAP-BACKEND-AUTHORITY"], rules)

    def test_successor_cannot_start_stale(self) -> None:
        contract = copy.deepcopy(self.data["contract"])
        contract["recovery"]["successor_initial_state"] = "stale"
        rules = [item["rule_id"] for item in validate_contract(PLAN_ROOT, contract, self.data["requirements"], self.data["commands"])]
        self.assertEqual(["RMAP-RECOVERY-NEW-RUN-STATE"], rules)

    def test_requirements_are_exact_and_quality_checked(self) -> None:
        self.assertEqual([], validate_requirements(PLAN_ROOT, self.data["requirements"], self.data["quality"]))

    def test_each_requirement_maps_to_one_delta(self) -> None:
        ids = {item["id"] for item in self.data["requirements"]["requirements"]}
        self.assertEqual([], validate_deltas(self.data["deltas"], ids))

    def test_mutation_helper_supports_list_append(self) -> None:
        mutated = apply_mutations({"items": []}, [{"op": "add", "path": "/items/-", "value": "x"}])
        self.assertEqual({"items": ["x"]}, mutated)

    def test_mutation_helper_supports_remove(self) -> None:
        mutated = apply_mutations({"value": "x"}, [{"op": "remove", "path": "/value"}])
        self.assertEqual({}, mutated)


if __name__ == "__main__":
    unittest.main()
