from __future__ import annotations

import importlib.util
import concurrent.futures
import json
import math
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "run_bootstrap_review.py"
SPEC = importlib.util.spec_from_file_location("run_bootstrap_review", MODULE_PATH)
assert SPEC and SPEC.loader
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)


class BootstrapReviewCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        self.scope = self.repo / "upstream-plan"
        self.scope.mkdir(parents=True)
        self.target = self.scope / "plan.md"
        self.target.write_text("# Plan\n\nUnsafe authority rule.\n", encoding="utf-8", newline="\n")
        self.unrelated = self.scope / "zz-unrelated.md"
        self.unrelated.write_text("# Unrelated\n", encoding="utf-8", newline="\n")
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.email", "bootstrap@example.invalid"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "Bootstrap Test"], cwd=self.repo, check=True)
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "baseline"], cwd=self.repo, check=True)
        self.run_dir = self.repo / "bootstrap-run"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def read_json(self, relative: str) -> dict:
        return json.loads((self.run_dir / relative).read_text(encoding="utf-8"))

    def write_json(self, relative: str, value: dict) -> None:
        (self.run_dir / relative).write_text(
            json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n"
        )

    def prepare(
        self,
        profile: str = "bootstrap-upstream-plan",
        *,
        execution_mode: str = "manual",
        review_id: str = "upstream-manual-001",
        change_id: str = "upstream-change-001",
        review_round: int = 1,
        predecessor_run: Path | None = None,
        expected_result: int = 0,
    ) -> None:
        profile_contract = bootstrap.load_profile(profile)
        context_args = []
        for context_class in profile_contract["requiredContextClasses"]:
            context_args.extend(["--context-class", f"{context_class}={self.scope}"])
        required_check_args = []
        if profile_contract["planBoundCheckPolicy"]["required"]:
            required_check_args = ["--required-check", f"implementation-proof={self.scope}"]
        predecessor_args = [] if predecessor_run is None else ["--predecessor-run-dir", str(predecessor_run)]
        result = bootstrap.main(
            [
                "prepare",
                "--repository-root", str(self.repo),
                "--review-id", review_id,
                "--change-id", change_id,
                "--review-round", str(review_round),
                *predecessor_args,
                "--profile", profile,
                "--scope", str(self.scope),
                *context_args,
                *required_check_args,
                "--execution-mode", execution_mode,
                "--semantic-review-exclusivity", "no-other-semantic-review-in-cycle",
                "--out-dir", str(self.run_dir),
            ]
        )
        self.assertEqual(expected_result, result)

    def skill_route_fixture_args(self) -> list[str]:
        fixture_root = self.repo / "skill-route-fixture"
        files = {
            fixture_root / "SKILL.md": "# Skill\n",
            fixture_root / "openai.yaml": "interface:\n  display_name: Review\n",
            fixture_root / "09-bootstrap-review-operator-guide.md": "# Operator\n",
            fixture_root / "tools" / "run_bootstrap_review.py": "# route\n",
            fixture_root / "bootstrap" / "review-profiles.v1.json": "{}\n",
            fixture_root / "schemas" / "fixture.schema.json": "{}\n",
            fixture_root / "tools" / "tests" / "test_run_bootstrap_review.py": "# tests\n",
            self.repo / "logs" / "ci" / "review-gateway-bootstrap-fixture" / "review-report.md": "# Evidence\n",
            self.repo / "AGENTS.md": "# Rules\n",
        }
        for path, content in files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
        scopes = [fixture_root, self.repo / "logs" / "ci" / "review-gateway-bootstrap-fixture", self.repo / "AGENTS.md"]
        args = [item for scope in scopes for item in ("--scope", str(scope))]
        assignments = {
            "skill-source": fixture_root / "SKILL.md",
            "operator-guide": fixture_root / "09-bootstrap-review-operator-guide.md",
            "route-or-cli": fixture_root / "tools" / "run_bootstrap_review.py",
            "profiles-and-config": fixture_root,
            "schemas": fixture_root / "schemas",
            "tests": fixture_root / "tools" / "tests",
            "usage-evidence": self.repo / "logs" / "ci" / "review-gateway-bootstrap-fixture",
            "repository-rules": self.repo / "AGENTS.md",
        }
        args.extend(
            item
            for name, path in assignments.items()
            for item in ("--context-class", f"{name}={path}")
        )
        return args

    def complete_layers(self, candidates_by_layer: dict[str, list[dict]] | None = None) -> None:
        self.complete_preflight()
        self.authorize_launch()
        candidates_by_layer = candidates_by_layer or {}
        for layer in bootstrap.LAYERS:
            output = self.read_json(f"reviewer-outputs/{layer}.json")
            output["status"] = "completed"
            output["coverage"]["readArtifacts"] = output["coverage"]["requiredArtifacts"]
            output["coverage"]["missingArtifacts"] = []
            output["candidates"] = candidates_by_layer.get(layer, [])
            self.write_json(f"reviewer-outputs/{layer}.json", output)

    def authorize_launch(self, *, acknowledge_high_cost: bool = False) -> None:
        args = ["authorize-launch", "--run-dir", str(self.run_dir)]
        if acknowledge_high_cost:
            args.append("--ack-high-cost")
        self.assertEqual(0, bootstrap.main(args))

    def complete_preflight(self) -> None:
        result = self.read_json("preflight-result.json")
        evidence_dir = self.run_dir / "preflight"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        for check in result["checks"]:
            evidence = evidence_dir / f"{check['checkId']}.log"
            evidence.write_text("PASS\n", encoding="utf-8", newline="\n")
            check.update(
                {
                    "status": "passed",
                    "command": f"test-command {check['checkId']}",
                    "exitCode": 0,
                    "evidencePath": f"preflight/{evidence.name}",
                    "evidenceHash": bootstrap.file_hash(evidence),
                }
            )
        result["status"] = "passed"
        self.write_json("preflight-result.json", result)

    def candidate(self, candidate_id: str = "BOOT-CANDIDATE-001", severity: str = "P1") -> dict:
        manifest = self.read_json("review-input.json")
        artifact = manifest["artifacts"][0]
        return {
            "candidateId": candidate_id,
            "artifactKind": "plan",
            "artifact": artifact["artifact"],
            "artifactHash": artifact["sha256"],
            "startLine": 3,
            "endLine": 3,
            "exactEvidence": "Unsafe authority rule.",
            "triggerInput": "An implementer follows the plan",
            "requiredState": "The quoted rule is treated as authority",
            "badOutcome": "The implementer mutates the wrong owner",
            "contextRead": ["upstream-plan/plan.md:1"],
            "existingGuardAnalysis": "No validator checks this authority assignment",
            "proposedSeverity": severity,
            "severityRationale": "The reachable workflow executes the wrong required work",
            "confidence": 0.95,
            "dimension": "plan",
            "authorityOwner": "upstream plan",
            "consumer": "implementation operator",
            "validatorRef": "manual phase exit",
        }

    def test_prepare_creates_hash_bound_manual_materials_without_mutating_scope(self) -> None:
        before = self.target.read_bytes()
        self.prepare()
        self.assertEqual(before, self.target.read_bytes())
        manifest = self.read_json("review-input.json")
        self.assertEqual("bootstrap-review-input.v1", manifest["schemaVersion"])
        self.assertEqual("supplemental_bootstrap", manifest["authorityClass"])
        self.assertEqual(list(bootstrap.LAYERS), manifest["requiredLayers"])
        profile = bootstrap.load_profile("bootstrap-upstream-plan")
        self.assertEqual(profile["codexExecPolicy"], manifest["codexExecPolicy"])
        self.assertEqual("plan-authority", manifest["reviewObjectType"])
        self.assertEqual(bootstrap.COMPLETENESS_POLICY, manifest["completenessPolicy"])
        self.assertEqual(profile["reviewerInstructionPolicy"], manifest["reviewerInstructionPolicy"])
        self.assertEqual(bootstrap.REVIEW_CYCLE_POLICY, manifest["reviewCyclePolicy"])
        self.assertEqual(
            profile["deterministicPreflightPolicy"], manifest["deterministicPreflightPolicy"]
        )
        prompt = (self.run_dir / "reviewer-prompts" / "acceptance_auditor.md").read_text(encoding="utf-8")
        self.assertIn("validate-layer --run-dir <assigned-run-directory> --layer acceptance_auditor", prompt)
        self.assertIn("`missingArtifacts=[]`", prompt)
        preflight = self.read_json("preflight-result.json")
        self.assertEqual("pending", preflight["status"])
        self.assertEqual(
            profile["deterministicPreflightPolicy"]["requiredChecks"],
            [check["checkId"] for check in preflight["checks"]],
        )
        for layer in bootstrap.LAYERS:
            self.assertTrue((self.run_dir / "reviewer-prompts" / f"{layer}.md").is_file())
            output = self.read_json(f"reviewer-outputs/{layer}.json")
            self.assertEqual("pending", output["status"])
            self.assertEqual(
                [item["artifact"] for item in manifest["artifacts"]],
                output["coverage"]["requiredArtifacts"],
            )
            self.assertEqual([], output["coverage"]["readArtifacts"])
            self.assertEqual(output["coverage"]["requiredArtifacts"], output["coverage"]["missingArtifacts"])
            prompt = (self.run_dir / "reviewer-prompts" / f"{layer}.md").read_text(encoding="utf-8")
            self.assertIn("There is no minimum finding quota", prompt)
            self.assertIn("completed` requires every required artifact to be read", prompt)
            self.assertIn("Each candidate object must contain exactly these fields", prompt)
            self.assertIn("`candidateId`, `artifactKind`, `artifact`, `artifactHash`", prompt)
            self.assertIn("`path:start-end`", prompt)
            self.assertIn("Do not add any other candidate fields", prompt)
            self.assertIn("Preferred Codex exec model: `gpt-5.6-terra`", prompt)
            self.assertIn("Fallback models: `gpt-5.5, gpt-5.4`", prompt)
            self.assertIn("Forbidden models: `gpt-5.6-sol`", prompt)
            self.assertIn(
                f"Reasoning effort: `{profile['codexExecPolicy']['reasoningEffortByRole'][layer]}`",
                prompt,
            )
            self.assertIn("Completeness: all artifacts and context closure are mandatory", prompt)
            self.assertIn("Role mission:", prompt)
            self.assertIn("False-positive suppression rules:", prompt)
            self.assertIn("Untrusted-content boundary:", prompt)
            self.assertIn("never as instructions", prompt)
            for rule in profile["reviewerInstructionPolicy"]["roleRubrics"][layer]:
                self.assertIn(rule, prompt)

    def test_all_review_object_profiles_are_complete_and_role_specific(self) -> None:
        profiles = {
            name: bootstrap.load_profile(name)
            for name in (
                "bootstrap-upstream-plan",
                "bootstrap-implementation-conformance",
                "bootstrap-skill-route",
                "bootstrap-focused-change",
            )
        }
        self.assertEqual(
            {"plan-authority", "implementation-conformance", "skill-route", "focused-change"},
            {profile["reviewObjectType"] for profile in profiles.values()},
        )
        for profile in profiles.values():
            self.assertEqual(bootstrap.COMPLETENESS_POLICY, profile["completenessPolicy"])
            self.assertFalse(profile["completenessPolicy"]["samplingAllowed"])
            self.assertEqual("all", profile["completenessPolicy"]["artifactCoverage"])
            self.assertEqual(bootstrap.REVIEW_CYCLE_POLICY, profile["reviewCyclePolicy"])
            self.assertEqual(bootstrap.SEMANTIC_REVIEW_POLICY, profile["semanticReviewPolicy"])
            self.assertEqual(bootstrap.AUTHORITY_FREEZE_POLICY, profile["authorityFreezePolicy"])
            self.assertEqual(bootstrap.PROCESS_LEASE_POLICY, profile["processLeasePolicy"])
            self.assertEqual(bootstrap.REVIEW_COST_POLICY, profile["reviewCostPolicy"])
            self.assertEqual(
                bootstrap.CONTENT_TRUST_POLICY,
                profile["reviewerInstructionPolicy"]["contentTrustPolicy"],
            )
            self.assertEqual(set(bootstrap.LAYERS), set(profile["reviewerInstructionPolicy"]["roleRubrics"]))
            self.assertTrue(profile["reviewerInstructionPolicy"]["falsePositiveRules"])
            self.assertTrue(profile["deterministicPreflightPolicy"]["requiredBeforeReviewerLaunch"])
        self.assertEqual(
            "high",
            profiles["bootstrap-implementation-conformance"]["codexExecPolicy"]
            ["reasoningEffortByRole"]["blind_hunter"],
        )
        self.assertEqual(
            "medium",
            profiles["bootstrap-skill-route"]["codexExecPolicy"]
            ["reasoningEffortByRole"]["blind_hunter"],
        )

    def test_prepare_projects_each_review_object_profile_into_manifest_and_prompts(self) -> None:
        profile_names = (
            "bootstrap-upstream-plan",
            "bootstrap-implementation-conformance",
            "bootstrap-skill-route",
            "bootstrap-focused-change",
        )
        for index, profile_name in enumerate(profile_names, start=1):
            with self.subTest(profile=profile_name):
                run_dir = self.repo / f"profile-run-{index}"
                profile_args = (
                    self.skill_route_fixture_args()
                    if profile_name == "bootstrap-skill-route"
                    else [
                        "--scope", str(self.scope),
                        *[
                            item
                            for context_class in bootstrap.load_profile(profile_name)["requiredContextClasses"]
                            for item in ("--context-class", f"{context_class}={self.scope}")
                        ],
                    ]
                )
                result = bootstrap.main(
                    [
                        "prepare",
                        "--repository-root", str(self.repo),
                        "--review-id", f"profile-manual-{index:03d}",
                        "--change-id", f"profile-change-{index:03d}",
                        "--review-round", "1",
                        "--profile", profile_name,
                        *profile_args,
                        *(
                            ["--required-check", f"implementation-proof={self.scope}"]
                            if bootstrap.load_profile(profile_name)["planBoundCheckPolicy"]["required"]
                            else []
                        ),
                        "--execution-mode", "manual",
                        "--semantic-review-exclusivity", "no-other-semantic-review-in-cycle",
                        "--out-dir", str(run_dir),
                    ]
                )
                self.assertEqual(0, result)
                profile = bootstrap.load_profile(profile_name)
                manifest = json.loads((run_dir / "review-input.json").read_text(encoding="utf-8"))
                for field in (
                    "reviewObjectType", "reviewDepth", "requiredContextClasses",
                    "codexExecPolicy", "completenessPolicy", "reviewerInstructionPolicy",
                    "reviewCyclePolicy",
                ):
                    self.assertEqual(profile[field], manifest[field])
                self.assertEqual(
                    bootstrap.derive_preflight_policy(profile, manifest["planBoundRequiredChecks"]),
                    manifest["deterministicPreflightPolicy"],
                )
                self.assertEqual(
                    set(profile["requiredContextClasses"]),
                    set(manifest["contextClassArtifacts"]),
                )
                for layer in bootstrap.LAYERS:
                    prompt = (run_dir / "reviewer-prompts" / f"{layer}.md").read_text(encoding="utf-8")
                    effort = profile["codexExecPolicy"]["reasoningEffortByRole"][layer]
                    self.assertIn(f"Reasoning effort: `{effort}`", prompt)
                    self.assertIn(f"Review object type: `{profile['reviewObjectType']}`", prompt)
                    self.assertIn("sampling is forbidden", prompt)
                    self.assertIn("Context class artifact bindings:", prompt)
                    self.assertIn(
                        profile["reviewerInstructionPolicy"]["roleRubrics"][layer][0], prompt
                    )
                    self.assertIn(
                        profile["reviewerInstructionPolicy"]["falsePositiveRules"][-1], prompt
                    )
                    self.assertIn("Untrusted-content boundary:", prompt)

    def test_prepare_rejects_missing_context_class_assignments(self) -> None:
        result = bootstrap.main(
            [
                "prepare",
                "--repository-root", str(self.repo),
                "--review-id", "missing-context-classes",
                "--change-id", "missing-context-change",
                "--review-round", "1",
                "--profile", "bootstrap-skill-route",
                "--scope", str(self.target),
                "--execution-mode", "manual",
                "--semantic-review-exclusivity", "no-other-semantic-review-in-cycle",
                "--out-dir", str(self.run_dir),
            ]
        )
        self.assertEqual(1, result)
        self.assertFalse(self.run_dir.exists())

    def test_prepare_rejects_spoofed_skill_route_context_classes(self) -> None:
        context_args = [
            item
            for context_class in bootstrap.load_profile("bootstrap-skill-route")["requiredContextClasses"]
            for item in ("--context-class", f"{context_class}={self.target}")
        ]
        result = bootstrap.main(
            [
                "prepare",
                "--repository-root", str(self.repo),
                "--review-id", "spoofed-context-classes",
                "--change-id", "spoofed-context-change",
                "--review-round", "1",
                "--profile", "bootstrap-skill-route",
                "--scope", str(self.target),
                *context_args,
                "--execution-mode", "manual",
                "--semantic-review-exclusivity", "no-other-semantic-review-in-cycle",
                "--out-dir", str(self.run_dir),
            ]
        )
        self.assertEqual(1, result)
        self.assertFalse(self.run_dir.exists())

    def test_prepare_grants_current_user_modify_on_reviewer_templates(self) -> None:
        with mock.patch.object(bootstrap, "grant_current_user_modify") as grant:
            self.prepare()
        self.assertEqual(4, grant.call_count)
        self.assertEqual(
            {
                (self.run_dir / "reviewer-outputs" / "blind_hunter.json").resolve(),
                (self.run_dir / "reviewer-outputs" / "edge_case_hunter.json").resolve(),
                (self.run_dir / "reviewer-outputs" / "acceptance_auditor.json").resolve(),
                (self.run_dir / "preflight-result.json").resolve(),
            },
            {call.args[0].resolve() for call in grant.call_args_list},
        )

    def test_prepare_records_binary_artifacts_without_decoding_them(self) -> None:
        binary = self.scope / "sample.bin"
        binary.write_bytes(b"\xff\xfe\x00\x01")
        self.prepare()
        artifacts = {item["artifact"]: item for item in self.read_json("review-input.json")["artifacts"]}
        entry = artifacts["upstream-plan/sample.bin"]
        self.assertIsNone(entry["textEncoding"])
        self.assertIsNone(entry["lineCount"])

    def test_prepare_rejects_unsafe_review_id(self) -> None:
        result = bootstrap.main(
            [
                "prepare", "--repository-root", str(self.repo), "--review-id", "../bad",
                "--change-id", "unsafe-review-change", "--review-round", "1",
                "--profile", "bootstrap-upstream-plan", "--scope", str(self.scope),
                "--execution-mode", "manual",
                "--semantic-review-exclusivity", "no-other-semantic-review-in-cycle",
                "--out-dir", str(self.run_dir),
            ]
        )
        self.assertEqual(1, result)
        self.assertFalse(self.run_dir.exists())

    def test_machine_contract_files_are_valid_json(self) -> None:
        plan_root = MODULE_PATH.parents[1]
        for relative in (
            "schemas/bootstrap-reviewer-output.v1.schema.json",
            "schemas/bootstrap-verifier-output.v1.schema.json",
            "schemas/bootstrap-review-launch-authorization.v1.schema.json",
            "schemas/bootstrap-process-leases.v1.schema.json",
            "bootstrap/review-profiles.v1.json",
        ):
            value = json.loads((plan_root / relative).read_text(encoding="utf-8"))
            self.assertIsInstance(value, dict)

    def test_prepare_rejects_scope_outside_repository_before_writing(self) -> None:
        outside = Path(self.temp.name) / "outside.md"
        outside.write_text("outside", encoding="utf-8")
        result = bootstrap.main(
            [
                "prepare", "--repository-root", str(self.repo), "--review-id", "bad",
                "--change-id", "outside-scope-change", "--review-round", "1",
                "--profile", "bootstrap-upstream-plan", "--scope", str(outside),
                "--execution-mode", "manual",
                "--semantic-review-exclusivity", "no-other-semantic-review-in-cycle",
                "--out-dir", str(self.run_dir),
            ]
        )
        self.assertEqual(1, result)
        self.assertFalse(self.run_dir.exists())

    def test_gate_allows_zero_findings_only_when_all_layers_complete(self) -> None:
        self.prepare()
        self.complete_layers()
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        manifest = self.read_json("review-input.json")
        gate = self.read_json("review-gate-result.json")
        self.assertEqual("clean", gate["status"])
        self.assertEqual([], bootstrap.schema_validation_errors(
            "bootstrap-review-gate-result.v1.schema.json", gate
        ))
        for relative in ("review-candidates.json", "review-rejections.json", "review-gate-state.json"):
            sidecar = self.read_json(relative)
            for field, value in bootstrap.bootstrap_sidecar_binding(manifest).items():
                self.assertEqual(value, sidecar[field], f"{relative} has stale {field}")
        verifier_prompt = (self.run_dir / "verification-prompt.md").read_text(encoding="utf-8")
        self.assertIn("Preferred Codex exec model: `gpt-5.6-terra`", verifier_prompt)
        self.assertIn("Fallback models: `gpt-5.5, gpt-5.4`", verifier_prompt)
        self.assertIn("Forbidden models: `gpt-5.6-sol`", verifier_prompt)
        self.assertIn("Reasoning effort: `high`", verifier_prompt)

    def test_gate_stops_before_review_when_preflight_is_pending(self) -> None:
        self.prepare()
        for layer in bootstrap.LAYERS:
            output = self.read_json(f"reviewer-outputs/{layer}.json")
            output["status"] = "completed"
            output["coverage"]["readArtifacts"] = output["coverage"]["requiredArtifacts"]
            output["coverage"]["missingArtifacts"] = []
            self.write_json(f"reviewer-outputs/{layer}.json", output)
        self.assertEqual(1, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        self.assertFalse((self.run_dir / "review-gate-result.json").exists())

    def test_gate_rejects_stale_preflight_evidence(self) -> None:
        self.prepare()
        self.complete_layers()
        first_check = self.read_json("preflight-result.json")["checks"][0]
        (self.run_dir / first_check["evidencePath"]).write_text(
            "CHANGED\n", encoding="utf-8", newline="\n"
        )
        self.assertEqual(1, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        self.assertFalse((self.run_dir / "review-gate-result.json").exists())

    def test_gate_schema_rejects_awaiting_verification_without_blocker(self) -> None:
        self.prepare()
        self.complete_layers()
        manifest = self.read_json("review-input.json")
        evaluated = bootstrap.evaluate_reviewer_outputs(self.run_dir, manifest, self.repo)
        gate = evaluated["gateState"]
        gate["status"] = "awaiting_verification"
        with self.assertRaises(bootstrap.BootstrapError):
            bootstrap.validate_gate_state(gate, manifest)

    def test_gate_grants_current_user_modify_on_verifier_template(self) -> None:
        self.prepare()
        self.complete_layers()
        with mock.patch.object(bootstrap, "grant_current_user_modify") as grant:
            self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        self.assertEqual(
            (self.run_dir / "verifier-output.json").resolve(),
            grant.call_args.args[0].resolve(),
        )
        self.assertEqual([], self.read_json("review-candidates.json")["findings"])

    def test_gate_missing_required_layer_is_incomplete(self) -> None:
        self.prepare()
        self.complete_layers()
        output = self.read_json("reviewer-outputs/acceptance_auditor.json")
        output["status"] = "pending"
        self.write_json("reviewer-outputs/acceptance_auditor.json", output)
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        gate = self.read_json("review-gate-result.json")
        self.assertEqual("incomplete", gate["status"])
        self.assertEqual(["acceptance_auditor"], gate["failedLayers"])

    def test_gate_rejects_completed_layer_with_incomplete_coverage(self) -> None:
        self.prepare()
        self.complete_layers()
        output = self.read_json("reviewer-outputs/acceptance_auditor.json")
        output["coverage"]["readArtifacts"] = []
        output["coverage"]["missingArtifacts"] = output["coverage"]["requiredArtifacts"]
        self.write_json("reviewer-outputs/acceptance_auditor.json", output)
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        gate = self.read_json("review-gate-result.json")
        self.assertEqual("incomplete", gate["status"])
        self.assertEqual(["acceptance_auditor"], gate["failedLayers"])
        self.assertIn("coverage_invalid", gate["layerFailures"][0]["reason"])

    def test_gate_accepts_completed_coverage_in_any_order(self) -> None:
        self.prepare()
        self.complete_layers()
        output = self.read_json("reviewer-outputs/acceptance_auditor.json")
        output["coverage"]["readArtifacts"] = list(reversed(output["coverage"]["readArtifacts"]))
        self.write_json("reviewer-outputs/acceptance_auditor.json", output)
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        self.assertEqual("clean", self.read_json("review-gate-result.json")["status"])

    def test_gate_maps_failed_missing_context_layer_to_incomplete(self) -> None:
        self.prepare()
        self.complete_layers()
        output = self.read_json("reviewer-outputs/acceptance_auditor.json")
        output["status"] = "failed"
        output["failureReason"] = "Required acceptance authority is absent from the prepared manifest"
        output["candidates"] = []
        self.write_json("reviewer-outputs/acceptance_auditor.json", output)
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        gate = self.read_json("review-gate-result.json")
        self.assertEqual("incomplete", gate["status"])
        self.assertEqual(["acceptance_auditor"], gate["failedLayers"])
        self.assertIn("Required acceptance authority", gate["layerFailures"][0]["reason"])

    def test_gate_rejects_stale_or_wrong_exact_evidence(self) -> None:
        self.prepare()
        candidate = self.candidate()
        candidate["exactEvidence"] = "A line that is not present."
        self.complete_layers({"blind_hunter": [candidate]})
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        rejection = self.read_json("review-rejections.json")["rejections"][0]
        self.assertEqual("stale_evidence", rejection["reasonCode"])
        self.assertEqual("clean", self.read_json("review-gate-result.json")["status"])

    def test_gate_rejects_context_outside_prepared_scope(self) -> None:
        self.prepare()
        candidate = self.candidate()
        candidate["contextRead"] = ["README.md:1"]
        self.complete_layers({"blind_hunter": [candidate]})
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        rejection = self.read_json("review-rejections.json")["rejections"][0]
        self.assertEqual("missing_context", rejection["reasonCode"])

    def test_gate_rejects_placeholder_failure_tuple(self) -> None:
        self.prepare()
        candidate = self.candidate()
        candidate["triggerInput"] = " T.B.D. "
        candidate["requiredState"] = "TODO"
        candidate["badOutcome"] = "N/A"
        self.complete_layers({"blind_hunter": [candidate]})
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        rejection = self.read_json("review-rejections.json")["rejections"][0]
        self.assertEqual("missing_failure_tuple", rejection["reasonCode"])
        self.assertIn("placeholder-equivalent", rejection["reason"])
        self.assertEqual("clean", self.read_json("review-gate-result.json")["status"])

    def test_gate_rejects_placeholder_existing_guard_analysis(self) -> None:
        self.prepare()
        candidate = self.candidate(severity="P2")
        candidate["existingGuardAnalysis"] = " N/A "
        self.complete_layers({"edge_case_hunter": [candidate]})

        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))

        rejection = self.read_json("review-rejections.json")["rejections"][0]
        self.assertEqual("missing_guard_analysis", rejection["reasonCode"])
        self.assertIn("placeholder-equivalent", rejection["reason"])
        self.assertEqual("clean", self.read_json("review-gate-result.json")["status"])

    def test_gate_rejects_non_finite_json_confidence(self) -> None:
        self.prepare()
        candidate = self.candidate()
        candidate["confidence"] = math.nan
        self.complete_layers({"blind_hunter": [candidate]})
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        gate = self.read_json("review-gate-result.json")
        self.assertEqual("incomplete", gate["status"])
        self.assertIn("Non-finite JSON number", gate["layerFailures"][0]["reason"])
        self.assertEqual([], self.read_json("review-candidates.json")["findings"])

    def test_gate_applies_reviewer_json_schema(self) -> None:
        self.prepare()
        self.complete_layers()
        output = self.read_json("reviewer-outputs/blind_hunter.json")
        output["unexpected"] = True
        self.write_json("reviewer-outputs/blind_hunter.json", output)
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        gate = self.read_json("review-gate-result.json")
        self.assertEqual("incomplete", gate["status"])
        self.assertIn("schema_invalid", gate["layerFailures"][0]["reason"])

    def test_gate_fails_closed_when_prepared_scope_changes(self) -> None:
        self.prepare()
        self.complete_layers()
        self.target.write_text("# Plan\n\nChanged after prepare.\n", encoding="utf-8", newline="\n")
        self.assertEqual(1, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))

    def test_authorize_launch_rejects_new_file_added_to_prepared_directory_scope(self) -> None:
        self.prepare()
        self.complete_preflight()
        (self.scope / "late-authority.md").write_text(
            "# Late authority\n", encoding="utf-8", newline="\n"
        )
        self.assertEqual(
            1,
            bootstrap.main(["authorize-launch", "--run-dir", str(self.run_dir)]),
        )
        self.assertFalse((self.run_dir / "review-launch-authorization.json").exists())

    def test_prepare_excludes_python_cache_artifacts_from_directory_scope(self) -> None:
        cache = self.scope / "__pycache__"
        cache.mkdir()
        (cache / "module.cpython-312.pyc").write_bytes(b"cache")
        self.prepare()
        artifacts = [item["artifact"] for item in self.read_json("review-input.json")["artifacts"]]
        self.assertFalse(any("__pycache__" in item or item.endswith(".pyc") for item in artifacts))
        self.assertFalse((self.run_dir / "review-gate-result.json").exists())

    def test_gate_deduplicates_same_evidence_and_preserves_sources(self) -> None:
        self.prepare()
        first = self.candidate("BOOT-CANDIDATE-001")
        second = self.candidate("BOOT-CANDIDATE-002")
        self.complete_layers({"blind_hunter": [first], "edge_case_hunter": [second]})
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        findings = self.read_json("review-candidates.json")["findings"]
        self.assertEqual(1, len(findings))
        self.assertEqual(["blind_hunter", "edge_case_hunter"], findings[0]["sourceReviewers"])
        self.assertEqual("duplicate", self.read_json("review-rejections.json")["rejections"][0]["reasonCode"])
        self.assertEqual("awaiting_verification", self.read_json("review-gate-result.json")["status"])

    def test_gate_merges_same_evidence_root_and_retains_highest_severity(self) -> None:
        self.prepare()
        p2 = self.candidate("BOOT-CANDIDATE-P2", "P2")
        p1 = self.candidate("BOOT-CANDIDATE-P1", "P1")
        p1["triggerInput"] = "A differently worded trigger reaches the same evidence root"
        p1["requiredState"] = "The same code span remains authoritative"
        p1["badOutcome"] = "A blocker is hidden behind an earlier advisory"
        p1["dimension"] = "acceptance"
        self.complete_layers({"blind_hunter": [p2], "acceptance_auditor": [p1]})
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        findings = self.read_json("review-candidates.json")["findings"]
        self.assertEqual(1, len(findings))
        self.assertEqual("P1", findings[0]["proposedSeverity"])
        self.assertEqual(["acceptance_auditor", "blind_hunter"], findings[0]["sourceReviewers"])
        self.assertEqual("awaiting_verification", self.read_json("review-gate-result.json")["status"])
        rejection = self.read_json("review-rejections.json")["rejections"][0]
        self.assertEqual("duplicate", rejection["reasonCode"])
        self.assertIn("retained severity P1", rejection["reason"])

    def test_gate_refuses_to_overwrite_saved_verifier_decisions(self) -> None:
        self.prepare()
        self.complete_layers({"blind_hunter": [self.candidate()]})
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        finding_id = self.read_json("review-candidates.json")["findings"][0]["findingId"]
        verifier = self.read_json("verifier-output.json")
        verifier["decisions"] = [
            {
                "findingId": finding_id,
                "decision": "confirmed",
                "reason": "Saved independent verification must survive a gate rerun",
                "evidenceChecked": ["upstream-plan/plan.md:1", "upstream-plan/plan.md:3"],
            }
        ]
        self.write_json("verifier-output.json", verifier)
        before = (self.run_dir / "verifier-output.json").read_bytes()
        self.assertEqual(1, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        self.assertEqual(before, (self.run_dir / "verifier-output.json").read_bytes())

    def test_finalize_rejects_changed_gate_sidecars(self) -> None:
        self.prepare()
        self.complete_layers()
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        candidates = self.read_json("review-candidates.json")
        candidates["findings"].append({"findingId": "INJECTED"})
        self.write_json("review-candidates.json", candidates)
        self.assertEqual(1, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))

    def test_validate_layer_rejects_completed_output_with_stale_missing_artifacts(self) -> None:
        self.prepare()
        self.complete_preflight()
        self.authorize_launch()
        output = self.read_json("reviewer-outputs/acceptance_auditor.json")
        output["status"] = "completed"
        output["coverage"]["readArtifacts"] = output["coverage"]["requiredArtifacts"]
        self.write_json("reviewer-outputs/acceptance_auditor.json", output)

        self.assertEqual(
            1,
            bootstrap.main(
                [
                    "validate-layer",
                    "--run-dir",
                    str(self.run_dir),
                    "--layer",
                    "acceptance_auditor",
                ]
            ),
        )

    def test_validate_layer_accepts_completed_output_without_writing_gate_sidecars(self) -> None:
        self.prepare()
        self.complete_preflight()
        self.authorize_launch()
        output = self.read_json("reviewer-outputs/acceptance_auditor.json")
        output["status"] = "completed"
        output["coverage"]["readArtifacts"] = output["coverage"]["requiredArtifacts"]
        output["coverage"]["missingArtifacts"] = []
        self.write_json("reviewer-outputs/acceptance_auditor.json", output)

        self.assertEqual(
            0,
            bootstrap.main(
                [
                    "validate-layer",
                    "--run-dir",
                    str(self.run_dir),
                    "--layer",
                    "acceptance_auditor",
                ]
            ),
        )
        self.assertFalse((self.run_dir / "review-gate-state.json").exists())
        self.assertFalse((self.run_dir / "review-candidates.json").exists())

    def test_finalize_rejects_preflight_changed_after_gate(self) -> None:
        self.prepare()
        self.complete_layers()
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        preflight = self.read_json("preflight-result.json")
        preflight["checks"][0]["command"] = "substituted-command"
        self.write_json("preflight-result.json", preflight)
        self.assertEqual(1, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))

    def test_finalize_rejects_reviewer_output_changed_after_gate(self) -> None:
        self.prepare()
        self.complete_layers()
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        output = self.read_json("reviewer-outputs/blind_hunter.json")
        output["candidates"] = [self.candidate()]
        self.write_json("reviewer-outputs/blind_hunter.json", output)
        self.assertEqual(1, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))

    def test_finalize_requires_exact_blocker_decisions_and_writes_sidecars(self) -> None:
        self.prepare()
        self.complete_layers({"blind_hunter": [self.candidate()]})
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        self.assertEqual(1, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        finding_id = self.read_json("review-candidates.json")["findings"][0]["findingId"]
        verifier = self.read_json("verifier-output.json")
        verifier["decisions"] = [
            {
                "findingId": finding_id,
                "decision": "confirmed",
                "reason": "The exact evidence and authority path reproduce the failure",
                "evidenceChecked": ["upstream-plan/plan.md:1", "upstream-plan/plan.md:3"],
            }
        ]
        self.write_json("verifier-output.json", verifier)
        self.assertEqual(0, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        final_result = self.read_json("review-gate-result.json")
        self.assertEqual("blocked", final_result["status"])
        self.assertEqual("supplemental_bootstrap", final_result["authorityClass"])
        self.assertEqual(
            "supplemental_bootstrap",
            self.read_json("review-dispositions.json")["authorityClass"],
        )
        manifest = self.read_json("review-input.json")
        for relative in ("review-dispositions.json", "review-metrics.json"):
            sidecar = self.read_json(relative)
            for field, value in bootstrap.bootstrap_sidecar_binding(manifest).items():
                self.assertEqual(value, sidecar[field], f"{relative} has stale {field}")
        report = (self.run_dir / "review-report.md").read_text(encoding="utf-8")
        self.assertIn(f"Route version: `{manifest['routeVersion']}`", report)
        self.assertIn(f"Input hash: `{manifest['inputHash']}`", report)
        self.assertTrue((self.run_dir / "review-dispositions.json").is_file())
        self.assertTrue((self.run_dir / "review-metrics.json").is_file())
        self.assertTrue((self.run_dir / "review-report.md").is_file())

    def test_finalize_refuses_to_reopen_finalized_result_after_verifier_changes(self) -> None:
        self.prepare()
        self.complete_layers({"blind_hunter": [self.candidate()]})
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        finding_id = self.read_json("review-candidates.json")["findings"][0]["findingId"]
        verifier = self.read_json("verifier-output.json")
        verifier["decisions"] = [
            {
                "findingId": finding_id,
                "decision": "confirmed",
                "reason": "The exact evidence and authority path reproduce the failure",
                "evidenceChecked": ["upstream-plan/plan.md:1", "upstream-plan/plan.md:3"],
            }
        ]
        self.write_json("verifier-output.json", verifier)
        self.assertEqual(0, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        final_result_before = (self.run_dir / "review-gate-result.json").read_bytes()
        verifier["decisions"][0]["decision"] = "refuted"
        verifier["decisions"][0]["reason"] = "A later edit must not reopen the finalized result"
        self.write_json("verifier-output.json", verifier)
        verifier_before = (self.run_dir / "verifier-output.json").read_bytes()

        self.assertEqual(1, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))

        self.assertEqual(final_result_before, (self.run_dir / "review-gate-result.json").read_bytes())
        self.assertEqual(verifier_before, (self.run_dir / "verifier-output.json").read_bytes())

    def test_finalize_clean_run_accepts_empty_verifier_decisions(self) -> None:
        self.prepare()
        self.complete_layers()
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        self.assertEqual(0, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        self.assertEqual("clean", self.read_json("review-gate-result.json")["status"])
        before = (self.run_dir / "review-gate-result.json").read_bytes()
        self.assertEqual(1, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        self.assertEqual(before, (self.run_dir / "review-gate-result.json").read_bytes())

    def test_gate_refuses_to_reopen_finalized_result(self) -> None:
        self.prepare()
        self.complete_layers()
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        self.assertEqual(0, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        before = (self.run_dir / "review-gate-result.json").read_bytes()
        self.assertEqual(1, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        self.assertEqual(before, (self.run_dir / "review-gate-result.json").read_bytes())

    def test_finalize_rejects_verifier_evidence_outside_scope(self) -> None:
        self.prepare()
        self.complete_layers({"blind_hunter": [self.candidate()]})
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        finding_id = self.read_json("review-candidates.json")["findings"][0]["findingId"]
        verifier = self.read_json("verifier-output.json")
        verifier["decisions"] = [
            {
                "findingId": finding_id,
                "decision": "confirmed",
                "reason": "Unsupported external evidence",
                "evidenceChecked": ["README.md:1"],
            }
        ]
        self.write_json("verifier-output.json", verifier)
        self.assertEqual(1, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))

    def test_finalize_rejects_unrelated_in_scope_verifier_evidence(self) -> None:
        self.prepare()
        self.complete_layers({"blind_hunter": [self.candidate()]})
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        finding_id = self.read_json("review-candidates.json")["findings"][0]["findingId"]
        verifier = self.read_json("verifier-output.json")
        verifier["decisions"] = [
            {
                "findingId": finding_id,
                "decision": "confirmed",
                "reason": "An unrelated in-scope reference must not confirm the blocker",
                "evidenceChecked": ["upstream-plan/zz-unrelated.md:1"],
            }
        ]
        self.write_json("verifier-output.json", verifier)
        self.assertEqual(1, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))

    def test_finalize_requires_whole_artifact_for_path_only_context(self) -> None:
        self.prepare()
        candidate = self.candidate()
        candidate["contextRead"] = ["upstream-plan/plan.md"]
        self.complete_layers({"blind_hunter": [candidate]})
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        finding_id = self.read_json("review-candidates.json")["findings"][0]["findingId"]
        verifier = self.read_json("verifier-output.json")
        verifier["decisions"] = [
            {
                "findingId": finding_id,
                "decision": "confirmed",
                "reason": "A line-scoped citation cannot prove whole-artifact context closure",
                "evidenceChecked": ["upstream-plan/plan.md:1", "upstream-plan/plan.md:3"],
            }
        ]
        self.write_json("verifier-output.json", verifier)
        self.assertEqual(1, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        verifier["decisions"][0]["evidenceChecked"] = ["upstream-plan/plan.md"]
        self.write_json("verifier-output.json", verifier)
        self.assertEqual(0, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))

    def test_implementation_profile_requires_plan_bound_check(self) -> None:
        profile = bootstrap.load_profile("bootstrap-implementation-conformance")
        context_args = [
            item
            for context_class in profile["requiredContextClasses"]
            for item in ("--context-class", f"{context_class}={self.scope}")
        ]
        result = bootstrap.main(
            [
                "prepare",
                "--repository-root", str(self.repo),
                "--review-id", "implementation-no-plan-check",
                "--change-id", "implementation-no-plan-check",
                "--review-round", "1",
                "--profile", "bootstrap-implementation-conformance",
                "--scope", str(self.scope),
                *context_args,
                "--execution-mode", "manual",
                "--semantic-review-exclusivity", "no-other-semantic-review-in-cycle",
                "--out-dir", str(self.run_dir),
            ]
        )
        self.assertEqual(1, result)
        self.assertFalse((self.run_dir / "review-input.json").exists())

    def test_authorize_launch_rejects_authority_drift_without_sidecar(self) -> None:
        self.prepare()
        self.complete_preflight()
        self.target.write_text("# Plan\n\nChanged authority rule.\n", encoding="utf-8", newline="\n")
        self.assertEqual(
            1,
            bootstrap.main(["authorize-launch", "--run-dir", str(self.run_dir)]),
        )
        self.assertFalse((self.run_dir / "review-launch-authorization.json").exists())

    def test_high_cost_review_requires_explicit_launch_acknowledgement(self) -> None:
        for index in range(48):
            (self.scope / f"extra-{index:02d}.md").write_text(
                f"# Extra {index}\n", encoding="utf-8", newline="\n"
            )
        self.prepare()
        self.complete_preflight()
        self.assertTrue(self.read_json("review-input.json")["reviewCostEstimate"]["highCost"])
        self.assertEqual(
            1,
            bootstrap.main(["authorize-launch", "--run-dir", str(self.run_dir)]),
        )
        self.assertEqual(
            0,
            bootstrap.main(
                ["authorize-launch", "--run-dir", str(self.run_dir), "--ack-high-cost"]
            ),
        )

    def test_process_lease_rejects_duplicate_live_pid_and_reuses_stale_operation(self) -> None:
        self.prepare()
        base = [
            "process-lease", "--run-dir", str(self.run_dir), "--action", "acquire",
            "--operation-id", "preflight:targeted-tests", "--role", "preflight",
        ]
        self.assertEqual(0, bootstrap.main([*base, "--pid", str(os.getpid())]))
        self.assertEqual(1, bootstrap.main([*base, "--pid", str(os.getpid())]))
        self.assertEqual(
            0,
            bootstrap.main(
                [
                    "process-lease", "--run-dir", str(self.run_dir), "--action", "release",
                    "--operation-id", "preflight:targeted-tests", "--pid", str(os.getpid()),
                    "--state", "completed",
                ]
            ),
        )
        dead_operation = [
            "process-lease", "--run-dir", str(self.run_dir), "--action", "acquire",
            "--operation-id", "model-probe:blind", "--role", "model_probe",
        ]
        self.assertEqual(0, bootstrap.main([*dead_operation, "--pid", "99999999"]))
        self.assertEqual(0, bootstrap.main([*dead_operation, "--pid", str(os.getpid())]))
        leases = self.read_json("process-leases.json")["leases"]
        states = [item["state"] for item in leases if item["operationId"] == "model-probe:blind"]
        self.assertEqual(["stale", "acquired"], states)

    def test_process_lease_can_release_a_normally_exited_child(self) -> None:
        self.prepare()
        self.assertEqual(
            0,
            bootstrap.main(
                [
                    "process-lease", "--run-dir", str(self.run_dir), "--action", "acquire",
                    "--operation-id", "model-probe:exited", "--role", "model_probe",
                    "--pid", "99999998",
                ]
            ),
        )
        self.assertEqual(
            0,
            bootstrap.main(
                [
                    "process-lease", "--run-dir", str(self.run_dir), "--action", "release",
                    "--operation-id", "model-probe:exited", "--pid", "99999998",
                    "--state", "completed",
                ]
            ),
        )
        leases = self.read_json("process-leases.json")["leases"]
        self.assertEqual("completed", leases[-1]["state"])

    def test_parallel_process_lease_updates_do_not_overwrite_each_other(self) -> None:
        self.prepare()

        def acquire(operation: str, pid: int) -> int:
            return bootstrap.main(
                [
                    "process-lease", "--run-dir", str(self.run_dir), "--action", "acquire",
                    "--operation-id", operation, "--role", "model_probe", "--pid", str(pid),
                ]
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(
                    lambda item: acquire(*item),
                    [("model-probe:parallel-a", 99999995), ("model-probe:parallel-b", 99999996)],
                )
            )
        self.assertEqual([0, 0], results)
        operations = {
            item["operationId"] for item in self.read_json("process-leases.json")["leases"]
        }
        self.assertIn("model-probe:parallel-a", operations)
        self.assertIn("model-probe:parallel-b", operations)

    def test_codex_exec_gate_requires_completed_reviewer_process_leases(self) -> None:
        self.prepare(execution_mode="codex-exec")
        self.complete_preflight()
        self.authorize_launch()
        for layer in bootstrap.LAYERS:
            output = self.read_json(f"reviewer-outputs/{layer}.json")
            output["status"] = "completed"
            output["coverage"]["readArtifacts"] = output["coverage"]["requiredArtifacts"]
            output["coverage"]["missingArtifacts"] = []
            self.write_json(f"reviewer-outputs/{layer}.json", output)
        self.assertEqual(1, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        for layer in bootstrap.LAYERS:
            operation = f"reviewer:{layer}"
            self.assertEqual(
                0,
                bootstrap.main(
                    [
                        "process-lease", "--run-dir", str(self.run_dir), "--action", "acquire",
                        "--operation-id", operation, "--role", layer, "--pid", str(os.getpid()),
                    ]
                ),
            )
            self.assertEqual(
                0,
                bootstrap.main(
                    [
                        "process-lease", "--run-dir", str(self.run_dir), "--action", "release",
                        "--operation-id", operation, "--pid", str(os.getpid()), "--state", "completed",
                    ]
                ),
            )
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))

    def test_codex_exec_finalize_requires_completed_verifier_process_lease(self) -> None:
        self.prepare(execution_mode="codex-exec")
        self.complete_preflight()
        self.authorize_launch()
        for layer in bootstrap.LAYERS:
            output = self.read_json(f"reviewer-outputs/{layer}.json")
            output["status"] = "completed"
            output["coverage"]["readArtifacts"] = output["coverage"]["requiredArtifacts"]
            output["coverage"]["missingArtifacts"] = []
            output["candidates"] = [self.candidate()] if layer == "blind_hunter" else []
            self.write_json(f"reviewer-outputs/{layer}.json", output)
            operation = f"reviewer:{layer}"
            self.assertEqual(
                0,
                bootstrap.main(
                    [
                        "process-lease", "--run-dir", str(self.run_dir), "--action", "acquire",
                        "--operation-id", operation, "--role", layer, "--pid", str(os.getpid()),
                    ]
                ),
            )
            self.assertEqual(
                0,
                bootstrap.main(
                    [
                        "process-lease", "--run-dir", str(self.run_dir), "--action", "release",
                        "--operation-id", operation, "--pid", str(os.getpid()), "--state", "completed",
                    ]
                ),
            )
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        finding = self.read_json("review-candidates.json")["findings"][0]
        verifier = self.read_json("verifier-output.json")
        verifier["decisions"] = [
            {
                "findingId": finding["findingId"],
                "decision": "confirmed",
                "reason": "The exact failure path remains reachable",
                "evidenceChecked": ["upstream-plan/plan.md:1", "upstream-plan/plan.md:3"],
            }
        ]
        self.write_json("verifier-output.json", verifier)
        self.assertEqual(1, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        self.assertEqual(
            0,
            bootstrap.main(
                [
                    "process-lease", "--run-dir", str(self.run_dir), "--action", "acquire",
                    "--operation-id", "verifier", "--role", "independent_verifier",
                    "--pid", str(os.getpid()),
                ]
            ),
        )
        self.assertEqual(
            0,
            bootstrap.main(
                [
                    "process-lease", "--run-dir", str(self.run_dir), "--action", "release",
                    "--operation-id", "verifier", "--pid", str(os.getpid()), "--state", "completed",
                ]
            ),
        )
        self.assertEqual(0, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))

    def test_review_cycle_cannot_restart_round_one_with_new_review_id(self) -> None:
        self.prepare()
        self.complete_preflight()
        self.authorize_launch()
        self.run_dir = self.repo / "bootstrap-run-restarted"
        self.prepare(
            review_id="upstream-manual-restarted",
            change_id="upstream-change-001",
            expected_result=1,
        )
        self.assertFalse((self.run_dir / "review-input.json").exists())

    def test_unlaunched_prepare_does_not_consume_review_round(self) -> None:
        self.prepare()
        self.run_dir = self.repo / "bootstrap-run-reprepared"
        self.prepare(review_id="upstream-manual-reprepared")
        self.assertTrue((self.run_dir / "review-input.json").is_file())

    def test_codex_probe_only_run_does_not_consume_review_round(self) -> None:
        self.prepare(execution_mode="codex-exec")
        self.complete_preflight()
        self.authorize_launch()
        self.assertEqual(
            0,
            bootstrap.main(
                [
                    "process-lease", "--run-dir", str(self.run_dir), "--action", "acquire",
                    "--operation-id", "model-probe:medium", "--role", "model_probe",
                    "--pid", "99999997",
                ]
            ),
        )
        first = self.run_dir
        self.run_dir = self.repo / "bootstrap-run-after-probe"
        self.prepare(
            execution_mode="codex-exec",
            review_id="upstream-manual-after-probe",
        )
        self.assertTrue(first.is_dir())
        self.assertTrue((self.run_dir / "review-input.json").is_file())

    def test_round_three_requires_blocker_or_changed_authority_context(self) -> None:
        self.prepare()
        self.complete_layers()
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        self.assertEqual(0, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        round_one = self.run_dir

        self.run_dir = self.repo / "bootstrap-run-round-2"
        self.prepare(
            review_id="upstream-manual-002",
            review_round=2,
            predecessor_run=round_one,
        )
        self.complete_layers()
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        self.assertEqual(0, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        round_two = self.run_dir

        self.run_dir = self.repo / "bootstrap-run-round-3"
        self.prepare(
            review_id="upstream-manual-003",
            review_round=3,
            predecessor_run=round_two,
            expected_result=1,
        )

    def test_review_round_four_is_always_rejected(self) -> None:
        self.prepare()
        predecessor = self.run_dir
        self.run_dir = self.repo / "bootstrap-run-round-4"
        self.prepare(
            review_id="upstream-manual-004",
            review_round=4,
            predecessor_run=predecessor,
            expected_result=1,
        )


if __name__ == "__main__":
    unittest.main()
