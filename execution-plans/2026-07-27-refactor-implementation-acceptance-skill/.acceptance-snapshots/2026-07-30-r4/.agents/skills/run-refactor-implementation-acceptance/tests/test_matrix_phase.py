from __future__ import annotations

import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))
import acceptance_core
import matrix_phase


class MatrixPhaseTests(unittest.TestCase):
    def _verified_row(self) -> dict:
        return {
            "check_id": "A", "source_clause_ids": ["CLAUSE-A"], "canonical_source_ref": "source.md:1", "source_refs": ["source.md:1"], "requirement": "A requirement", "phase_id": "P1", "requirement_refs": ["requirement:A"], "policy_check_refs": [], "applicability": {"status": "applicable", "activation_predicate": "always", "authority_refs": ["source.md"], "evidence_ids": []}, "implementation_owner": "developer", "verification_owner": "tester", "approval_owner": "owner", "implementation_refs": ["code.py"], "test_definition_refs": ["test.py"], "test_run_evidence_ids": ["EVID-1"], "runtime_evidence_ids": [], "evidence_requirements": {"required_kinds": ["test_run"], "minimum_by_kind": {"test_run": 1}, "freshness_policy": "exact_candidate", "waiver_allowed": False, "source_refs": ["CLAUSE-A"]}, "disposition": "verified", "evaluation_state": "evaluated", "deterministic_gate_state": "eligible", "deterministic_blocking_predecessors": [], "gap": "",
        }

    def test_phase_graph_rejects_cycle(self) -> None:
        with self.assertRaises(acceptance_core.InputError):
            matrix_phase.validate_phase_graph({"schemaVersion": "phase-graph.v1", "authorizes": [], "phases": [{"phaseId": "A", "dependsOn": ["B"]}, {"phaseId": "B", "dependsOn": ["A"]}]})

    def test_phase_graph_requires_schema_and_non_authorizing_boundary(self) -> None:
        with self.assertRaisesRegex(acceptance_core.InputError, "schema"):
            matrix_phase.validate_phase_graph({"phases": [{"phaseId": "A", "dependsOn": []}]})

    def test_phase_node_rejects_unknown_fields(self) -> None:
        graph = {"schemaVersion": "phase-graph.v1", "authorizes": [], "phases": [{"phaseId": "A", "dependsOn": [], "untrusted": True}]}
        with self.assertRaisesRegex(acceptance_core.InputError, "node fields"):
            matrix_phase.validate_phase_graph(graph)

    def test_join_phase_waits_for_all_predecessors(self) -> None:
        graph = {"schemaVersion": "phase-graph.v1", "authorizes": [], "phases": [{"phaseId": "A", "dependsOn": []}, {"phaseId": "B", "dependsOn": []}, {"phaseId": "C", "dependsOn": ["A", "B"], "joinPolicy": "all"}]}
        result = matrix_phase.evaluate_phase_readiness(graph, {"A"})
        self.assertEqual("blocked", result["C"])

    def test_three_dod_levels_remain_distinct(self) -> None:
        result = matrix_phase.three_level_dod("passed", "passed", "blocked")
        self.assertEqual("blocked", result["program_dod"])

    def test_base_matrix_requires_exact_check_ids_and_evidence_for_verified_rows(self) -> None:
        valid = [self._verified_row()]
        matrix_phase.validate_base_matrix(valid, {"A"})
        with self.assertRaises(acceptance_core.InputError):
            matrix_phase.validate_base_matrix(valid + valid, {"A"})

    def test_undetermined_applicability_cannot_claim_verified_or_eligible(self) -> None:
        row = self._verified_row()
        row["applicability"] = {"status": "undetermined", "activation_predicate": "unknown", "authority_refs": ["source.md"], "evidence_ids": []}
        with self.assertRaises(acceptance_core.InputError):
            matrix_phase.validate_base_matrix([row], {"A"})

    def test_program_dod_requires_typed_passed_protected_gate(self) -> None:
        gate = {"gateId": "BH-HANDOFF", "gateClass": "protected", "resultPath": "logs/gate.json", "resultHash": "sha256:" + "a" * 64, "schemaPath": "schemas/gate.json", "schemaHash": "sha256:" + "b" * 64, "authorityRef": "ADR-0041", "authorizationScopes": ["program_dod"], "status": "blocked"}
        result = matrix_phase.evaluate_three_level_dod(first_slice_checks={"A"}, phase_checks={"A"}, program_checks={"A"}, eligible_checks={"A"}, required_gate_scopes={"program_dod": {"program_dod"}}, gates=[gate])
        self.assertEqual("passed", result["phase_exit"]["status"])
        self.assertEqual("blocked", result["program_dod"]["status"])
        gate["status"] = "passed"
        result = matrix_phase.evaluate_three_level_dod(first_slice_checks={"A"}, phase_checks={"A"}, program_checks={"A"}, eligible_checks={"A"}, required_gate_scopes={"program_dod": {"program_dod"}}, gates=[gate])
        self.assertEqual("passed", result["program_dod"]["status"])

    def test_impact_projection_blocks_only_the_phase_consuming_candidate_partition(self) -> None:
        row = self._verified_row()
        projection = matrix_phase.project_acceptance_impact(base_rows=[row], required_check_ids={"A"}, partitions=[{"partitionId": "P1", "baseCompleteness": "candidate", "effectiveCompleteness": "candidate", "status": "current"}, {"partitionId": "P2", "baseCompleteness": "deterministic_complete", "effectiveCompleteness": "deterministic_complete", "status": "current"}], phase_consumed_partitions={"phase:P1": ["P1"]}, gates=[], base_matrix_hash="sha256:" + "a" * 64, code_review_policy_binding_hash="sha256:" + "a" * 64, phase_policy_result_hashes={"taskChecklistClosure": "sha256:" + "b" * 64, "diffCoverage": "sha256:" + "b" * 64, "staticAnalysis": "sha256:" + "b" * 64, "securityScan": "sha256:" + "b" * 64}, phase_graph_hash="sha256:" + "c" * 64)
        self.assertEqual("blocked", projection["checkImpacts"][0]["effectiveGateState"])
        self.assertEqual("candidate", projection["scopeCompleteness"][0]["scopeEffectiveCompleteness"])
        self.assertEqual([], projection["authorizes"])

    def test_cli_exposes_append_only_impact_projection(self) -> None:
        import acceptance_cli
        self.assertTrue(callable(acceptance_cli.project_acceptance_impact_command))

    def test_candidate_and_final_results_use_distinct_append_only_paths(self) -> None:
        import tempfile
        import matrix_phase

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / "phase-candidate.json"
            final = root / "phase-final.json"
            value = {"phaseId": "P1", "status": "candidate"}
            candidate_result = matrix_phase.publish_candidate_result(candidate, value, "sha256:" + "a" * 64)
            self.assertEqual([], __import__("json").loads(candidate.read_text(encoding="utf-8"))["authorizes"])
            matrix_phase.publish_final_result(final, value, candidate, candidate_result["candidateHash"], "sha256:" + "b" * 64)
            with self.assertRaisesRegex(matrix_phase.InputError, "distinct"):
                matrix_phase.publish_final_result(candidate, value, candidate, candidate_result["candidateHash"], "sha256:" + "b" * 64)

    def test_impact_projection_requires_all_phase_policy_result_hashes(self) -> None:
        row = self._verified_row()
        with self.assertRaisesRegex(acceptance_core.InputError, "result hash"):
            matrix_phase.project_acceptance_impact(base_rows=[row], required_check_ids={"A"}, partitions=[], phase_consumed_partitions={}, gates=[], base_matrix_hash="sha256:" + "a" * 64, code_review_policy_binding_hash="sha256:" + "a" * 64, phase_policy_result_hashes={}, phase_graph_hash="sha256:" + "c" * 64)


if __name__ == "__main__":
    unittest.main()
