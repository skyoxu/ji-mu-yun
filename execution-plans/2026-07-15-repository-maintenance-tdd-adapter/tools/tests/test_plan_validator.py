from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch


PLAN_ROOT = Path(__file__).resolve().parents[2]
TOOLS = PLAN_ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from authority_guards import validate_acceptance_contracts, validate_authority_manifest, validate_clarification_projection  # noqa: E402
from contract_guards import junction_escape_is_rejected, schema_error  # noqa: E402
from evidence_guards import validate_candidate_document, validate_candidate_review_documents  # noqa: E402
from fixture_checks import apply_mutations, evaluate_fixture  # noqa: E402
from protocol_guards import value_hash  # noqa: E402
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
from validate_all import current_candidate_identity, run_predicate, validator_identity  # noqa: E402
from slice_guards import validate_slice_outputs  # noqa: E402


class PlanValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data, cls.load_findings = load_machine(PLAN_ROOT)

    def _candidate(self, current: dict[str, str], authority_revision: str | None = None) -> dict[str, object]:
        identity = {key: current[key] for key in (
            "head", "index_tree", "tracked_diff_hash", "untracked_manifest_hash", "contract_hash",
            "command_registry_hash", "validator_hash", "authority_manifest_hash", "candidate_worktree_hash",
        )}
        identity.update({
            "changed_file_manifest_hash": "sha256:" + "1" * 64,
            "test_diff_hash": "sha256:" + "2" * 64,
            "red_run_id": "red-a", "green_run_id": "green-a", "refactor_run_id": "refactor-a",
            "final_context_manifest_hash": "sha256:" + "3" * 64,
            "final_capsule_hash": "sha256:" + "4" * 64,
            "accepted_attempt_id": "ATTEMPT-001",
            "accepted_attempt_decision_hash": "sha256:" + "5" * 64,
        })
        return {
            "schema_version": "jimuyun.tdd-result.v1", "predicate": "implementation-candidate", "status": "pass",
            "plan_hash": current["plan_hash"], "source_hash": current["source_hash"], "slice_id": "RMAP-S6",
            "authority_revision": authority_revision or current["head"], "candidate_identity": identity,
            "authorizes": ["bootstrap-review"],
            "does_not_authorize": ["implementation-accepted", "protected-handoff", "release-ready"],
        }

    def _stage_run(self, current: dict[str, str]) -> tuple[Path, list[dict[str, object]], dict[str, str]]:
        repository_root = PLAN_ROOT.parents[1]
        run_dir = repository_root / "logs" / "tdd-adapter" / f"test-{uuid.uuid4().hex}"
        run_dir.mkdir(parents=True)
        contract_slice = next(item for item in self.data["contract"]["slices"] if item["slice_id"] == "RMAP-S6")
        stages: list[dict[str, object]] = []
        paths: dict[str, str] = {"run_dir": run_dir.relative_to(repository_root).as_posix()}
        predecessor = None
        for index, (stage, status) in enumerate((("red", "red-observed"), ("green", "green-observed"), ("refactor", "refactor-verified"))):
            tdd = contract_slice["tdd"]
            document: dict[str, object] = {
                "schema_version": "rmap.tdd-stage-result.v1", "plan_id": "repository-maintenance-tdd-adapter",
                "slice_id": "RMAP-S6", "run_id": "run-a", "stage": stage, "status": status,
                "command_id": tdd[stage]["command_id"] if stage != "refactor" else "refactor-composite",
                "exit_code": 1 if stage == "red" else 0, "contract_hash": current["contract_hash"],
                "validator_hash": current["validator_hash"], "observed_at": f"2026-07-16T00:00:0{index}Z",
                "predecessor_stage_hash": predecessor,
            }
            if stage == "red":
                document.update({"test_selector": tdd["red"]["test_selector"], "expected_failure_ids": tdd["red"]["expected_failure_ids"]})
            if stage == "refactor":
                document["command_ids"] = [item["command_id"] for item in tdd["refactor"]["invocations"]]
            path = run_dir / f"{stage}-result.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            predecessor = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
            stages.append(document); paths[f"{stage}_result"] = path.relative_to(repository_root).as_posix()
        recovery = {"schema_version": "rmap.recovery-state.v1", "run_id": "run-a", "state": "complete", "contract_hash": current["contract_hash"], "validator_hash": current["validator_hash"], "predecessor_run_id": None, "supersedes_run_id": None}
        (run_dir / "recovery-state.json").write_text(json.dumps(recovery), encoding="utf-8")
        self._write_protocol_run(run_dir)
        return run_dir, stages, paths

    def _write_protocol_run(self, run_dir: Path) -> None:
        bundle = copy.deepcopy(self.data["protocol_fixtures"]["valid_bundle"])
        context, capsule = bundle["context_manifest"], bundle["slice_capsule"]
        for document in (context, capsule):
            document["slice_id"] = "RMAP-S6"; document["run_id"] = "run-a"
        context["stage"] = "finalize-candidate"; capsule["stage"] = "finalize-candidate"
        capsule["exit_predicate"] = "implementation-candidate"
        attempt = bundle["attempts"][0]
        for document in attempt.values():
            document["slice_id"] = "RMAP-S6"; document["run_id"] = "run-a"; document["stage"] = "refactor"
        request, response, diff, decision = (attempt[key] for key in ("backend_request", "backend_response", "diff_manifest", "adapter_decision"))
        request["goal"] = "preserve-green-refactor"
        capsule_hash = value_hash(capsule)
        context["capsule_ref"]["sha256"] = capsule_hash
        context["context_hash"] = value_hash({"capsule_hash": capsule_hash, "artifact_refs": context["artifact_refs"]})
        request["capsule_ref"]["sha256"] = capsule_hash
        request["request_payload_hash"] = value_hash({"capsule_hash": capsule_hash, "goal": request["goal"], "allowed_command_ids": request["allowed_command_ids"]})
        diff["actual_diff_hash"] = value_hash(diff["files"])
        decision["input_context_hash"] = context["context_hash"]
        decision["backend_request_hash"] = value_hash(request); decision["backend_response_hash"] = value_hash(response)
        decision["actual_diff_hash"] = diff["actual_diff_hash"]; decision["next_allowed_state"] = "refactor-verified"
        previous = None
        for event in bundle["events"]:
            event["slice_id"] = "RMAP-S6"; event["run_id"] = "run-a"; event["stage"] = "refactor"; event["previous_event_hash"] = previous
            previous = value_hash(event)
        context_dir = run_dir / "context" / capsule["capsule_id"]; context_dir.mkdir(parents=True)
        (context_dir / "context-manifest.v1.json").write_text(json.dumps(context), encoding="utf-8")
        (context_dir / "slice-capsule.v1.json").write_text(json.dumps(capsule), encoding="utf-8")
        attempt_dir = run_dir / "attempts" / request["attempt_id"]; attempt_dir.mkdir(parents=True)
        for key, name in (("backend_request", "backend-request.v1.json"), ("backend_response", "backend-response.v1.json"), ("diff_manifest", "diff-manifest.v1.json"), ("adapter_decision", "adapter-decision.v1.json")):
            (attempt_dir / name).write_text(json.dumps(attempt[key]), encoding="utf-8")
        (run_dir / "run-events.jsonl").write_text("\n".join(json.dumps(event) for event in bundle["events"]) + "\n", encoding="utf-8")

    def _candidate_run(self, current: dict[str, str]) -> tuple[Path, dict[str, object], list[dict[str, object]], dict[str, str]]:
        run_dir, stages, paths = self._stage_run(current)
        changed = run_dir / "changed-files.json"; changed.write_text(json.dumps({"schema_version": "rmap.changed-files.v1", "files": []}), encoding="utf-8")
        test_diff = run_dir / "test-diff.patch"; test_diff.write_text("", encoding="utf-8")
        candidate = self._candidate(current)
        identity = candidate["candidate_identity"]
        identity["changed_file_manifest_hash"] = "sha256:" + hashlib.sha256(changed.read_bytes()).hexdigest()
        identity["test_diff_hash"] = "sha256:" + hashlib.sha256(test_diff.read_bytes()).hexdigest()
        for stage in ("red", "green", "refactor"):
            identity[f"{stage}_run_id"] = "run-a"
        context_dir = run_dir / "context" / "CAP-001"
        identity["final_context_manifest_hash"] = "sha256:" + hashlib.sha256((context_dir / "context-manifest.v1.json").read_bytes()).hexdigest()
        identity["final_capsule_hash"] = "sha256:" + hashlib.sha256((context_dir / "slice-capsule.v1.json").read_bytes()).hexdigest()
        identity["accepted_attempt_id"] = "ATTEMPT-001"
        identity["accepted_attempt_decision_hash"] = "sha256:" + hashlib.sha256((run_dir / "attempts" / "ATTEMPT-001" / "adapter-decision.v1.json").read_bytes()).hexdigest()
        path = run_dir / "candidate-result.json"; path.write_text(json.dumps(candidate), encoding="utf-8")
        return path, candidate, stages, paths

    def test_machine_documents_load(self) -> None:
        self.assertEqual([], self.load_findings)

    def test_static_plan_is_valid(self) -> None:
        _, findings, _ = validate_static(PLAN_ROOT)
        self.assertEqual([], findings)

    def test_repair_predicate_passes_without_higher_authority(self) -> None:
        with patch("validate_all.run_unit_tests", return_value=({"rule_id": "RMAP-UNIT-TESTS", "status": "pass", "evidence": ["mocked"]}, [])):
            result, exit_code = run_predicate("plan-repair-verified")
        self.assertEqual(0, exit_code)
        self.assertEqual("pass", result["status"])
        self.assertEqual(["plan-repair-verified"], result["authorizes"])

    def test_manual_pause_blocks_plan_ready(self) -> None:
        with patch("validate_all.run_unit_tests", return_value=({"rule_id": "RMAP-UNIT-TESTS", "status": "pass", "evidence": ["mocked"]}, [])):
            result, exit_code = run_predicate("plan-ready")
        self.assertEqual(1, exit_code)
        self.assertEqual("blocked", result["status"])
        self.assertEqual([], result["authorizes"])
        self.assertIn("RMAP-REVIEW-MANUAL-PAUSE", {item["rule_id"] for item in result["diagnostics"]})

    def test_manual_pause_blocks_slice_and_candidate_predicates(self) -> None:
        for predicate in ("slice-ready", "implementation-candidate", "implementation-accepted"):
            with self.subTest(predicate=predicate):
                with patch("validate_all.run_unit_tests", return_value=({"rule_id": "RMAP-UNIT-TESTS", "status": "pass", "evidence": ["mocked"]}, [])):
                    result, exit_code = run_predicate(predicate)
                self.assertEqual(1, exit_code)
                self.assertEqual("blocked", result["status"])

    def test_every_declared_fixture_has_exact_rule(self) -> None:
        for case in self.data["fixtures"]["cases"]:
            with self.subTest(case=case["id"]):
                rules = sorted({item["rule_id"] for item in evaluate_fixture(PLAN_ROOT, case["id"], self.data)})
                expected = [] if case["expected_valid"] else [case["expected_rule"]]
                self.assertEqual(expected, rules)

    def test_predicate_authority_is_exact(self) -> None:
        self.assertEqual([], validate_plan_state(self.data["state"], self.data["review_blocker"]))
        for name, (authorizes, excludes) in PREDICATE_AUTHORITY.items():
            self.assertEqual(authorizes, self.data["state"]["predicates"][name]["authorizes"])
            self.assertEqual(excludes, self.data["state"]["predicates"][name]["does_not_authorize"])

    def test_round_four_authorization_is_rejected(self) -> None:
        blocker = copy.deepcopy(self.data["review_blocker"])
        blocker["round_4_authorized"] = True
        rules = {item["rule_id"] for item in validate_plan_state(self.data["state"], blocker)}
        self.assertEqual({"RMAP-REVIEW-MANUAL-PAUSE"}, rules)

    def test_blocker_projection_requires_full_authority_binding(self) -> None:
        blocker = copy.deepcopy(self.data["review_blocker"]); blocker["policy_revision"] = "garbage"
        self.assertIn("RMAP-REVIEW-MANUAL-PAUSE", {item["rule_id"] for item in validate_plan_state(self.data["state"], blocker)})

    def test_release_escalation_is_rejected(self) -> None:
        state = copy.deepcopy(self.data["state"])
        state["predicates"]["plan-repair-verified"]["authorizes"].append("release-ready")
        rules = {item["rule_id"] for item in validate_plan_state(state, self.data["review_blocker"])}
        self.assertEqual({"RMAP-AUTH-PREDICATE"}, rules)

    def test_shell_and_raw_command_are_rejected(self) -> None:
        commands = copy.deepcopy(self.data["commands"]); commands["shell"] = True
        self.assertEqual({"RMAP-CMD-SHELL"}, {item["rule_id"] for item in validate_commands(commands)})
        commands = copy.deepcopy(self.data["commands"]); commands["commands"][0]["command"] = "py -3 unsafe.py"
        self.assertEqual({"RMAP-CMD-RAW"}, {item["rule_id"] for item in validate_commands(commands)})
        commands = copy.deepcopy(self.data["commands"]); commands["commands"][0]["executable"] = "powershell"
        self.assertIn("RMAP-CMD-EXECUTABLE", {item["rule_id"] for item in validate_commands(commands)})

    def test_command_descriptors_do_not_own_stage_exit(self) -> None:
        self.assertTrue(all("expected_exit" not in item and "expected_failure_ids" not in item for item in self.data["commands"]["commands"]))

    def test_slice_command_requires_explicit_stage_arguments(self) -> None:
        commands = copy.deepcopy(self.data["commands"]); command = next(item for item in commands["commands"] if item["id"] == "rmap-s6-candidate-validate")
        command["argv"].remove("--candidate-result")
        self.assertIn("RMAP-CMD-STAGE-PROTOCOL", {item["rule_id"] for item in validate_commands(commands)})

    def test_red_stage_requires_nonzero_and_selector(self) -> None:
        contract = copy.deepcopy(self.data["contract"])
        contract["slices"][2]["tdd"]["red"]["expected_exit"] = "zero"
        rules = {item["rule_id"] for item in validate_contract(PLAN_ROOT, contract, self.data["requirements"], self.data["commands"])}
        self.assertIn("RMAP-TDD-STAGE-EXPECTATION", rules)

    def test_contract_schema_required_field_is_enforced(self) -> None:
        contract = copy.deepcopy(self.data["contract"]); del contract["plan_id"]
        self.assertEqual(["RMAP-STRUCT-SCHEMA"], [item["rule_id"] for item in validate_contract(PLAN_ROOT, contract, self.data["requirements"], self.data["commands"])])

    def test_nested_schema_object_rejects_unknown_field(self) -> None:
        contract = copy.deepcopy(self.data["contract"]); contract["recovery"]["unknown"] = True
        self.assertEqual(["RMAP-STRUCT-SCHEMA"], [item["rule_id"] for item in validate_contract(PLAN_ROOT, contract, self.data["requirements"], self.data["commands"])])

    def test_unknown_schema_keyword_fails_closed(self) -> None:
        self.assertIn("unsupported schema keywords", schema_error({}, {"type": "object", "unknownKeyword": True}) or "")

    def test_typed_command_path_cannot_escape_plan_root(self) -> None:
        commands = copy.deepcopy(self.data["commands"]); commands["commands"][0]["argv"][1]["value"] = "../../outside.py"
        self.assertEqual({"RMAP-CMD-PATH-CONTAINMENT"}, {item["rule_id"] for item in validate_commands(commands)})

    def test_typed_repo_path_rejects_junction_escape(self) -> None:
        result = junction_escape_is_rejected(PLAN_ROOT)
        if result is None:
            self.skipTest("junction creation is unavailable for this Windows token")
        self.assertTrue(result)

    def test_validator_identity_binds_all_authorizing_helpers(self) -> None:
        digest = hashlib.sha256()
        names = ("validate_all.py", "rmap_checks.py", "contract_guards.py", "authority_guards.py", "evidence_guards.py", "shadow_guards.py", "source_guards.py", "slice_guards.py", "fixture_checks.py", "protocol_guards.py")
        for name in names:
            path = TOOLS / name
            digest.update(path.name.encode("utf-8")); digest.update(b"\0"); digest.update(path.read_bytes()); digest.update(b"\0")
        self.assertEqual(f"rmap-plan-validator.v2+sha256:{digest.hexdigest()}", validator_identity())

    def test_nested_write_and_forbidden_globs_overlap(self) -> None:
        contract = copy.deepcopy(self.data["contract"])
        contract["slices"][0]["allowed_changes"]["documentation"][0] = "Docs/**"
        contract["slices"][0]["forbidden_changes"][0] = "docs/standards/**"
        self.assertIn("RMAP-PATH-OVERLAP", {item["rule_id"] for item in validate_contract(PLAN_ROOT, contract, self.data["requirements"], self.data["commands"])})

    def test_authority_book_hash_must_be_concrete_and_current(self) -> None:
        contract = copy.deepcopy(self.data["contract"])
        contract["authority"]["source_hashes"]["01-intent-authority-and-non-goals.md"] = "runtime-bound"
        self.assertIn("RMAP-HASH-AUTHORITY", {item["rule_id"] for item in validate_contract(PLAN_ROOT, contract, self.data["requirements"], self.data["commands"])})

    def test_authority_manifest_is_complete_and_current(self) -> None:
        self.assertEqual([], validate_authority_manifest(PLAN_ROOT, self.data["authority_manifest"]))
        manifest = copy.deepcopy(self.data["authority_manifest"]); manifest["categories"]["machine_owners"].pop()
        self.assertIn("RMAP-HASH-AUTHORITY-MANIFEST", {item["rule_id"] for item in validate_authority_manifest(PLAN_ROOT, manifest)})

    def test_authority_manifest_rejects_ignored_log_source(self) -> None:
        manifest = copy.deepcopy(self.data["authority_manifest"])
        manifest["categories"]["repository_rules"][0]["path"] = "logs/runtime.json"
        self.assertIn("RMAP-HASH-AUTHORITY-MANIFEST", {item["rule_id"] for item in validate_authority_manifest(PLAN_ROOT, manifest)})

    def test_clarification_projection_is_durable(self) -> None:
        self.assertEqual([], validate_clarification_projection(self.data["clarification"], self.data["state"]))
        self.assertNotIn("logs/", json.dumps(self.data["clarification"]["sources"]))

    def test_static_validation_does_not_require_log_files(self) -> None:
        original = Path.is_file
        def without_logs(path: Path) -> bool:
            return False if "logs" in {part.lower() for part in path.parts} else original(path)
        with patch.object(Path, "is_file", new=without_logs):
            _, findings, _ = validate_static(PLAN_ROOT)
        self.assertEqual([], findings)

    def test_source_coverage_location_is_exact(self) -> None:
        coverage = copy.deepcopy(self.data["coverage"]); coverage["sources"][0]["sections"][0]["lines"] = "1-1"
        ids = {item["id"] for item in self.data["requirements"]["requirements"]}
        self.assertEqual({"RMAP-REQ-COVERAGE-LOCATION"}, {item["rule_id"] for item in validate_coverage(PLAN_ROOT, coverage, ids)})

    def test_requirements_quality_and_acceptance_are_current(self) -> None:
        self.assertEqual([], validate_requirements(PLAN_ROOT, self.data["requirements"], self.data["quality"], self.data["acceptance"]))
        self.assertEqual([], validate_acceptance_contracts(self.data["acceptance"], self.data["requirements"], self.data["contract"], self.data["commands"], self.data["fixtures"], self.data["protocol_fixtures"]))
        acceptance = copy.deepcopy(self.data["acceptance"]); acceptance["acceptances"][0]["expected_failure_ids"] = ["NOT-A-RULE"]
        self.assertIn("RMAP-REQ-ACCEPTANCE-CONTRACT", {item["rule_id"] for item in validate_acceptance_contracts(acceptance, self.data["requirements"], self.data["contract"], self.data["commands"], self.data["fixtures"], self.data["protocol_fixtures"])})

    def test_earliest_slice_phase_mismatch_is_rejected(self) -> None:
        contract = copy.deepcopy(self.data["contract"]); contract["slices"][2]["phase_id"] = "P2"
        self.assertIn("RMAP-TDD-PHASE", {item["rule_id"] for item in validate_contract(PLAN_ROOT, contract, self.data["requirements"], self.data["commands"])})

    def test_candidate_sequence_is_s2_slice_s6_candidate_s7_acceptance(self) -> None:
        predicates = {item["slice_id"]: item["exit_predicate"] for item in self.data["contract"]["slices"]}
        self.assertEqual("slice-ready", predicates["RMAP-S2"])
        self.assertEqual("implementation-candidate", predicates["RMAP-S6"])
        self.assertEqual("implementation-accepted", predicates["RMAP-S7"])

    def test_candidate_identity_incomplete_is_rejected(self) -> None:
        current = current_candidate_identity()
        for field in ("test_diff_hash", "accepted_attempt_decision_hash"):
            with self.subTest(field=field):
                candidate = self._candidate(current); del candidate["candidate_identity"][field]
                self.assertIn("RMAP-HASH-CANDIDATE-IDENTITY", {item["rule_id"] for item in validate_candidate_document(PLAN_ROOT, "logs/tdd-adapter/run/candidate-result.json", candidate, current)})

    def test_unrelated_untracked_file_does_not_change_candidate_identity(self) -> None:
        repository_root = PLAN_ROOT.parents[1]; path = repository_root / f"rmap-unrelated-{uuid.uuid4().hex}.txt"
        before = current_candidate_identity(); path.write_text("unrelated", encoding="utf-8")
        try:
            self.assertEqual(before, current_candidate_identity())
        finally:
            path.unlink(missing_ok=True)

    def test_validation_drift_prevents_repair_pass(self) -> None:
        before = {"candidate_hash": "sha256:" + "1" * 64, "source_hash": "sha256:" + "2" * 64, "validator_version": "validator-a"}
        after = {**before, "candidate_hash": "sha256:" + "3" * 64}
        with patch("validate_all.validation_snapshot", side_effect=[before, after]), patch("validate_all.run_unit_tests", return_value=({"rule_id": "RMAP-UNIT-TESTS", "status": "pass", "evidence": ["mocked"]}, [])):
            result, exit_code = run_predicate("plan-repair-verified")
        self.assertEqual(1, exit_code); self.assertEqual("fail", result["status"])
        self.assertIn("RMAP-HASH-VALIDATION-DRIFT", {item["rule_id"] for item in result["diagnostics"]})

    def test_stage_evidence_binds_hashes_order_and_recovery(self) -> None:
        current = current_candidate_identity(); run_dir, _, paths = self._stage_run(current)
        contract_slice = next(item for item in self.data["contract"]["slices"] if item["slice_id"] == "RMAP-S6")
        try:
            _, findings = validate_slice_outputs(PLAN_ROOT.parents[1], "RMAP-S6", self.data["shadow"], paths, contract_slice, current)
            self.assertEqual([], findings)
            red = json.loads((run_dir / "red-result.json").read_text(encoding="utf-8")); red["validator_hash"] = "sha256:" + "0" * 64
            (run_dir / "red-result.json").write_text(json.dumps(red), encoding="utf-8")
            _, findings = validate_slice_outputs(PLAN_ROOT.parents[1], "RMAP-S6", self.data["shadow"], paths, contract_slice, current)
            self.assertIn("RMAP-HASH-CANDIDATE-IDENTITY", {item["rule_id"] for item in findings})
        finally:
            shutil.rmtree(run_dir)

    def test_candidate_and_clean_review_binding_passes(self) -> None:
        repository_root = PLAN_ROOT.parents[1]
        current = current_candidate_identity(); candidate_path, candidate, stages, _ = self._candidate_run(current)
        relative = candidate_path.relative_to(repository_root).as_posix()
        digest = "sha256:" + hashlib.sha256(candidate_path.read_bytes()).hexdigest()
        review_dir = repository_root / "logs" / "ci" / f"synthetic-{uuid.uuid4().hex}"; review_dir.mkdir(parents=True)
        evidence_path = review_dir / "preflight" / "plan-check.txt"; evidence_path.parent.mkdir(); evidence_path.write_text("pass", encoding="utf-8")
        pointer = json.loads((repository_root / "execution-plans/2026-07-12-llm-review-evidence-gate-hardening/bootstrap/review-profiles.v1.json").read_text(encoding="utf-8"))
        profiles = json.loads((repository_root / pointer["authority"]).read_text(encoding="utf-8"))["profiles"]
        profile = profiles["bootstrap-implementation-conformance"]
        review_input = {"schemaVersion": "bootstrap-review-input.v1", "authorityClass": "supplemental_bootstrap", "profileName": "bootstrap-implementation-conformance", "reviewId": "review-a", "authorityRevision": current["head"], "artifacts": [{"artifact": relative, "sha256": digest}], "deterministicPreflightPolicy": {"requiredChecks": ["plan-check"]}, "planBoundRequiredChecks": []}
        for field in ("reviewProfile", "policyRevision", "routeVersion", "requiredLayers", "codexExecPolicy", "requiredContextClasses", "completenessPolicy"):
            review_input[field] = profile[field]
        review_input["inputHash"] = "sha256:" + hashlib.sha256(json.dumps(review_input, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        identity = {key: review_input[key] for key in ("reviewId", "routeVersion", "policyRevision", "authorityRevision", "inputHash")}
        preflight = {**identity, "schemaVersion": "bootstrap-preflight-result.v1", "status": "passed", "checks": [{"checkId": "plan-check", "status": "passed", "exitCode": 0, "evidence": [{"path": "preflight/plan-check.txt", "sha256": "sha256:" + hashlib.sha256(evidence_path.read_bytes()).hexdigest()}]}]}
        review_result = {**identity, "schemaVersion": "review-result.v1", "authorityClass": "supplemental_bootstrap", "reviewProfile": review_input["reviewProfile"], "requiredLayers": review_input["requiredLayers"], "completedLayers": review_input["requiredLayers"], "failedLayers": [], "skippedLayers": [], "status": "clean", "findings": []}
        dispositions = {**identity, "schemaVersion": "bootstrap-review-dispositions.v1", "authorityClass": "supplemental_bootstrap", "dispositions": []}
        try:
            self.assertEqual([], validate_candidate_document(PLAN_ROOT, relative, candidate, current, stages))
            self.assertEqual([], validate_candidate_review_documents(PLAN_ROOT, relative, candidate, review_input, preflight, review_result, dispositions, [], current, stages, review_dir))
        finally:
            shutil.rmtree(candidate_path.parent); shutil.rmtree(review_dir)

    def test_acceptance_rejects_open_p1(self) -> None:
        repository_root = PLAN_ROOT.parents[1]
        current = current_candidate_identity(); candidate = self._candidate(current)
        path = repository_root / "logs" / "tdd-adapter" / f"blocked-{uuid.uuid4().hex}.json"
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(candidate), encoding="utf-8")
        relative = path.relative_to(repository_root).as_posix(); digest = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        identity = {"reviewId": "r", "routeVersion": "v", "policyRevision": "sha256:" + "4" * 64, "authorityRevision": "tree-a", "inputHash": "sha256:" + "5" * 64}
        review_input = {**identity, "artifacts": [{"artifact": relative, "sha256": digest}], "deterministicPreflightPolicy": {"requiredChecks": ["c"]}, "planBoundRequiredChecks": []}
        preflight = {**identity, "status": "passed", "checks": [{"checkId": "c", "status": "passed"}]}
        result = {**identity, "status": "blocked", "findings": [{"findingId": "P1-X", "proposedSeverity": "P1", "status": "confirmed"}]}
        dispositions = {**identity, "dispositions": [{"findingId": "P1-X"}]}
        try:
            rules = {item["rule_id"] for item in validate_candidate_review_documents(PLAN_ROOT, relative, candidate, review_input, preflight, result, dispositions, [], current)}
            self.assertIn("RMAP-REVIEW-P0-P1-OPEN", rules)
        finally:
            path.unlink(missing_ok=True)

    def test_each_requirement_maps_to_one_complete_delta(self) -> None:
        ids = {item["id"] for item in self.data["requirements"]["requirements"]}
        self.assertEqual([], validate_deltas(PLAN_ROOT, self.data["deltas"], ids))

    def test_mutation_helper_supports_list_append_and_remove(self) -> None:
        self.assertEqual({"items": ["x"]}, apply_mutations({"items": []}, [{"op": "add", "path": "/items/-", "value": "x"}]))
        self.assertEqual({}, apply_mutations({"value": "x"}, [{"op": "remove", "path": "/value"}]))

if __name__ == "__main__":
    unittest.main()
