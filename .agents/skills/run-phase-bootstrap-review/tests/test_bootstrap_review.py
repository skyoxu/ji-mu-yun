from __future__ import annotations

import importlib.util
import concurrent.futures
import json
import math
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap_review.py"
REPOSITORY_ROOT = MODULE_PATH.parents[4]
PLAN_ROOT = REPOSITORY_ROOT / "execution-plans" / "2026-07-12-llm-review-evidence-gate-hardening"
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
        repair_closure_args = []
        if 1 < review_round <= bootstrap.REVIEW_CYCLE_POLICY["hardFullReviewRoundLimit"] and predecessor_run is not None:
            repository_root = self.repo.resolve()
            _, artifacts = bootstrap.collect_scope(
                repository_root, ["upstream-plan"], self.run_dir
            )
            artifact_names = [item["artifact"] for item in artifacts]
            context_mapping = {
                name: artifact_names for name in profile_contract["requiredContextClasses"]
            }
            plan_checks = (
                [{"checkId": "implementation-proof", "authorityArtifacts": artifact_names}]
                if profile_contract["planBoundCheckPolicy"]["required"] else []
            )
            predecessor_manifest = json.loads(
                (predecessor_run / "review-input.json").read_text(encoding="utf-8")
            )
            predecessor_result = json.loads(
                (predecessor_run / "review-gate-result.json").read_text(encoding="utf-8")
            )
            finding_ids = bootstrap.canonical_predecessor_finding_ids(
                predecessor_run, predecessor_result
            )
            dependency_closure = sorted(
                {item for values in context_mapping.values() for item in values}
                | {item for check in plan_checks for item in check["authorityArtifacts"]}
            )
            closure_path = self.repo / f"repair-closure-round-{review_round}.json"
            closure = {
                "schemaVersion": "bootstrap-repair-closure.v1",
                "predecessorRun": predecessor_run.relative_to(self.repo).as_posix(),
                "predecessorInputHash": predecessor_manifest["inputHash"],
                "predecessorResultHash": bootstrap.file_hash(predecessor_run / "review-gate-result.json"),
                "findingIds": finding_ids,
                "items": [
                    {
                        "findingId": finding_id,
                        "disposition": "fixed",
                        "risk": "normal",
                        "proofFamily": "regression",
                        "reason": "Targeted regression evidence closes the predecessor finding",
                        "fixRefs": ["upstream-plan/plan.md:3"],
                        "validationCommands": ["test-command repair-closure"],
                        "evidence": [
                            {
                                "path": self.target.relative_to(self.repo).as_posix(),
                                "sha256": bootstrap.file_hash(self.target),
                            }
                        ],
                    }
                    for finding_id in finding_ids
                ],
                "currentBindings": bootstrap.repair_binding_hashes(
                    artifacts, context_mapping, plan_checks
                ),
                "gitIndexHash": bootstrap.git_index_hash(self.repo),
                "writeSetHash": bootstrap.value_hash([]),
                "executionReadSetHash": bootstrap.value_hash(artifact_names),
                "dependencyClosureHash": bootstrap.value_hash(dependency_closure),
            }
            closure_path.write_text(
                json.dumps(closure, indent=2) + "\n", encoding="utf-8", newline="\n"
            )
            repair_closure_args = ["--repair-closure", str(closure_path)]
        result = bootstrap.main(
            [
                "prepare",
                "--repository-root", str(self.repo),
                "--review-id", review_id,
                "--change-id", change_id,
                "--review-round", str(review_round),
                *predecessor_args,
                *repair_closure_args,
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
        manifest = self.read_json("review-input.json")
        if manifest["executionMode"] == "codex-exec" and not (self.run_dir / "access-proof.json").is_file():
            self.complete_access_proof(manifest)
        args = ["authorize-launch", "--run-dir", str(self.run_dir)]
        if acknowledge_high_cost:
            args.append("--ack-high-cost")
        self.assertEqual(0, bootstrap.main(args))

    def complete_access_proof(self, manifest: dict) -> None:
        attempt_dir = self.run_dir / "attempts" / "test-access-probe"
        attempt_dir.mkdir(parents=True, exist_ok=True)
        handshake_path = attempt_dir / "access-handshake.json"
        handshake = bootstrap.access_handshake_payload(self.run_dir, manifest, "model_probe")
        self.write_json("attempts/test-access-probe/access-handshake.json", handshake)
        _child_environment, environment_evidence = bootstrap.child_environment()
        proof = {
            "schemaVersion": "bootstrap-access-proof.v1",
            "reviewId": manifest["reviewId"],
            "inputHash": manifest["inputHash"],
            "artifactViewManifestHash": manifest["artifactView"]["manifestHash"],
            "model": manifest["codexExecPolicy"]["preferredModel"],
            "reasoningEffort": manifest["codexExecPolicy"]["reasoningEffortByRole"]["blind_hunter"],
            "sandbox": "workspace-write",
            "workspaceRootClass": "attempt-directory-only",
            "shell": False,
            "commandIdentity": bootstrap.value_hash("test-codex-command"),
            "environmentAllowlist": list(bootstrap.ENVIRONMENT_ALLOWLIST),
            "environmentEvidenceHash": bootstrap.value_hash(environment_evidence),
            "userIdentity": bootstrap.getpass.getuser(),
            "platform": bootstrap.os.name,
            "highCostAcknowledged": manifest["reviewCostEstimate"]["highCost"],
            "handshakePath": handshake_path.relative_to(self.run_dir).as_posix(),
            "handshakeFileHash": bootstrap.file_hash(handshake_path),
            "accessHandshakeHash": handshake["handshakeHash"],
            "provenAt": bootstrap.utc_now(),
        }
        self.write_json("access-proof.json", proof)

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

    def complete_process_lease(self, operation_id: str, role: str) -> None:
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        self.addCleanup(lambda: child.poll() is None and child.kill())
        self.assertEqual(
            0,
            bootstrap.main(
                [
                    "process-lease",
                    "--run-dir",
                    str(self.run_dir),
                    "--action",
                    "acquire",
                    "--operation-id",
                    operation_id,
                    "--role",
                    role,
                    "--pid",
                    str(child.pid),
                ]
            ),
        )
        child.terminate()
        child.wait(timeout=10)
        self.assertEqual(
            0,
            bootstrap.main(
                [
                    "process-lease",
                    "--run-dir",
                    str(self.run_dir),
                    "--action",
                    "release",
                    "--operation-id",
                    operation_id,
                    "--pid",
                    str(child.pid),
                    "--state",
                    "completed",
                ]
            ),
        )

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
        self.assertIn(
            f"validate-layer --run-dir {self.run_dir.resolve()} --layer acceptance_auditor",
            prompt,
        )
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

    def test_operator_guide_matches_reviewer_owned_template_fields(self) -> None:
        guide = (PLAN_ROOT / "09-bootstrap-review-operator-guide.md").read_text(encoding="utf-8")
        self.assertIn("Preserve the manifest-bound routeVersion", guide)
        self.assertIn("update the template status to completed or failed", guide)
        self.assertIn("process-events.jsonl` 是执行事实权威", guide)
        self.assertNotIn("do not add routeversion, status", guide.lower())

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
            "references/review-profiles.v1.json",
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

    def test_gate_rejects_placeholder_accountability_fields(self) -> None:
        for field_name, value in (
            ("severityRationale", "T.B.D."),
            ("authorityOwner", "TODO"),
            ("consumer", "N/A"),
            ("validatorRef", "unknown"),
        ):
            with self.subTest(field_name=field_name):
                self.run_dir = self.repo / f"bootstrap-{field_name}"
                self.prepare(
                    review_id=f"placeholder-{field_name.lower()}",
                    change_id=f"placeholder-change-{field_name.lower()}",
                )
                candidate = self.candidate()
                candidate[field_name] = value
                self.complete_layers({"blind_hunter": [candidate]})
                self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
                rejection = self.read_json("review-rejections.json")["rejections"][0]
                self.assertEqual("schema_invalid", rejection["reasonCode"])
                self.assertIn(field_name, rejection["reason"])
                self.assertIn("placeholder-equivalent", rejection["reason"])

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

    def test_gate_keeps_same_evidence_with_distinct_failure_tuple(self) -> None:
        self.prepare()
        p2 = self.candidate("BOOT-CANDIDATE-P2", "P2")
        p1 = self.candidate("BOOT-CANDIDATE-P1", "P1")
        p1["triggerInput"] = "A differently worded trigger reaches the same evidence root"
        p1["requiredState"] = "The same code span remains authoritative"
        p1["badOutcome"] = "A blocker is hidden behind an earlier advisory"
        self.complete_layers({"blind_hunter": [p2], "acceptance_auditor": [p1]})
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        findings = self.read_json("review-candidates.json")["findings"]
        self.assertEqual(2, len(findings))
        self.assertEqual({"P1", "P2"}, {item["proposedSeverity"] for item in findings})
        self.assertEqual("awaiting_verification", self.read_json("review-gate-result.json")["status"])
        self.assertEqual([], self.read_json("review-rejections.json")["rejections"])

    def test_gate_keeps_same_evidence_and_failure_tuple_with_distinct_dimension(self) -> None:
        self.prepare()
        plan = self.candidate("BOOT-CANDIDATE-PLAN", "P2")
        acceptance = self.candidate("BOOT-CANDIDATE-ACCEPTANCE", "P2")
        acceptance["dimension"] = "acceptance"
        self.complete_layers({"blind_hunter": [plan], "acceptance_auditor": [acceptance]})
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        findings = self.read_json("review-candidates.json")["findings"]
        self.assertEqual(2, len(findings))
        self.assertEqual({"plan", "acceptance"}, {item["dimension"] for item in findings})
        self.assertEqual([], self.read_json("review-rejections.json")["rejections"])

    def test_gate_true_duplicate_retains_highest_severity(self) -> None:
        self.prepare()
        p2 = self.candidate("BOOT-CANDIDATE-P2", "P2")
        p1 = self.candidate("BOOT-CANDIDATE-P1", "P1")
        p1["triggerInput"] = "  AN IMPLEMENTER follows---the plan! "
        self.complete_layers({"blind_hunter": [p2], "acceptance_auditor": [p1]})
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        findings = self.read_json("review-candidates.json")["findings"]
        self.assertEqual(1, len(findings))
        self.assertEqual("P1", findings[0]["proposedSeverity"])
        self.assertEqual(["acceptance_auditor", "blind_hunter"], findings[0]["sourceReviewers"])
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

    def test_validate_layer_rejects_pending_output(self) -> None:
        self.prepare()
        self.complete_preflight()
        self.authorize_launch()

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

    def test_validate_finalized_run_emits_non_authorizing_envelope(self) -> None:
        self.prepare()
        self.complete_layers()
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        self.assertEqual(0, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        output = self.repo / "finalized-validation.json"

        self.assertEqual(
            0,
            bootstrap.main(
                [
                    "validate-finalized-run",
                    "--run-dir",
                    str(self.run_dir),
                    "--output",
                    str(output),
                ]
            ),
        )

        envelope = json.loads(output.read_text(encoding="utf-8"))
        manifest = self.read_json("review-input.json")
        self.assertEqual("bootstrap-finalized-run-validation.v1", envelope["schemaVersion"])
        self.assertEqual("passed", envelope["validationStatus"])
        self.assertEqual("clean", envelope["finalStatus"])
        self.assertEqual([], envelope["authorizes"])
        self.assertIn("plan-acceptance", envelope["doesNotAuthorize"])
        self.assertIn("protected-handoff", envelope["doesNotAuthorize"])
        self.assertEqual(manifest["controlPlaneRevision"], envelope["controlPlaneRevision"])
        self.assertEqual(
            bootstrap.value_hash(bootstrap.load_profile(manifest["profileName"])),
            envelope["profileHash"],
        )
        self.assertEqual(
            bootstrap.file_hash(self.run_dir / "review-gate-result.json"),
            envelope["artifactHashes"]["finalResult"],
        )

    def test_validate_finalized_run_rejects_stale_metrics(self) -> None:
        self.prepare()
        self.complete_layers()
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        self.assertEqual(0, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        metrics = self.read_json("review-metrics.json")
        metrics["acceptedUniqueCount"] = 99
        self.write_json("review-metrics.json", metrics)
        output = self.repo / "finalized-validation.json"

        self.assertEqual(
            1,
            bootstrap.main(
                [
                    "validate-finalized-run",
                    "--run-dir",
                    str(self.run_dir),
                    "--output",
                    str(output),
                ]
            ),
        )
        self.assertFalse(output.exists())

    def test_validate_finalized_run_rejects_stale_profile_projection(self) -> None:
        self.prepare()
        self.complete_layers()
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        self.assertEqual(0, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        manifest = self.read_json("review-input.json")
        manifest["controlPlaneRevision"] = "bootstrap-control-plane.stale"
        unhashed = dict(manifest)
        unhashed.pop("inputHash", None)
        manifest["inputHash"] = bootstrap.value_hash(unhashed)
        self.write_json("review-input.json", manifest)

        self.assertEqual(
            1,
            bootstrap.main(
                [
                    "validate-finalized-run",
                    "--run-dir",
                    str(self.run_dir),
                    "--output",
                    str(self.repo / "finalized-validation.json"),
                ]
            ),
        )

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

    def test_high_cost_access_probe_requires_ack_before_model_launch(self) -> None:
        for index in range(48):
            (self.scope / f"probe-extra-{index:02d}.md").write_text(
                f"# Probe Extra {index}\n", encoding="utf-8", newline="\n"
            )
        self.prepare(execution_mode="codex-exec")
        self.complete_preflight()
        self.assertTrue(self.read_json("review-input.json")["reviewCostEstimate"]["highCost"])
        self.assertEqual(
            1,
            bootstrap.main([
                "prove-access", "--run-dir", str(self.run_dir),
                "--codex-command", "missing-codex-command",
            ]),
        )
        self.assertFalse((self.run_dir / "attempts").exists())

    def test_process_lease_rejects_duplicate_live_pid_live_release_and_dead_acquire(self) -> None:
        self.prepare()
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        self.addCleanup(lambda: child.poll() is None and child.kill())
        base = [
            "process-lease", "--run-dir", str(self.run_dir), "--action", "acquire",
            "--operation-id", "preflight:targeted-tests", "--role", "preflight",
        ]
        self.assertEqual(0, bootstrap.main([*base, "--pid", str(child.pid)]))
        self.assertEqual(1, bootstrap.main([*base, "--pid", str(child.pid)]))
        release = [
            "process-lease", "--run-dir", str(self.run_dir), "--action", "release",
            "--operation-id", "preflight:targeted-tests", "--pid", str(child.pid),
            "--state", "completed",
        ]
        self.assertEqual(1, bootstrap.main(release))
        self.assertEqual("acquired", self.read_json("process-leases.json")["leases"][-1]["state"])
        child.terminate()
        child.wait(timeout=10)
        self.assertEqual(
            0,
            bootstrap.main(release),
        )
        dead_operation = [
            "process-lease", "--run-dir", str(self.run_dir), "--action", "acquire",
            "--operation-id", "model-probe:blind", "--role", "model_probe",
        ]
        before = self.read_json("process-leases.json")
        self.assertEqual(1, bootstrap.main([*dead_operation, "--pid", "99999999"]))
        self.assertEqual(before, self.read_json("process-leases.json"))
        self.assertEqual(0, bootstrap.main([*dead_operation, "--pid", str(os.getpid())]))
        leases = self.read_json("process-leases.json")["leases"]
        states = [item["state"] for item in leases if item["operationId"] == "model-probe:blind"]
        self.assertEqual(["acquired"], states)
        self.assertTrue(leases[-1]["processIdentity"])

    def test_dead_event_backed_lease_appends_stale_event_and_unblocks_write_set(self) -> None:
        self.prepare(execution_mode="codex-exec")
        self.complete_preflight()
        self.authorize_launch()
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        identity = bootstrap.process_creation_identity(child.pid)
        self.assertIsNotNone(identity)
        formal_write_set = [
            (self.run_dir / "reviewer-outputs" / "blind_hunter.json")
            .relative_to(self.repo)
            .as_posix()
        ]
        bootstrap.append_process_event(
            self.run_dir,
            {
                "eventType": "attempt-started",
                "timestamp": bootstrap.utc_now(),
                "attemptId": "interrupted-reviewer",
                "operationId": "reviewer:blind_hunter",
                "role": "blind_hunter",
                "pid": child.pid,
                "processIdentity": identity,
                "writeSet": formal_write_set,
            },
        )
        bootstrap.rebuild_process_leases_from_events(
            self.run_dir, self.read_json("review-input.json")
        )
        child.terminate()
        child.wait(timeout=10)

        self.assertEqual(
            0,
            bootstrap.main(
                [
                    "process-lease",
                    "--run-dir",
                    str(self.run_dir),
                    "--action",
                    "inspect",
                ]
            ),
        )

        events = bootstrap.read_process_events(self.run_dir)
        self.assertEqual("attempt-stale", events[-1]["eventType"])
        self.assertEqual("interrupted-reviewer", events[-1]["attemptId"])
        self.assertNotIn("interrupted-reviewer", bootstrap.active_attempts(events))
        lease = next(
            item
            for item in self.read_json("process-leases.json")["leases"]
            if item["operationId"] == "reviewer:blind_hunter"
        )
        self.assertEqual("stale", lease["state"])

    def test_process_event_append_recovers_dead_and_incomplete_owner_locks(self) -> None:
        self.prepare()
        lock = self.run_dir / ".process-events.lock"
        lock.write_text(
            json.dumps(
                {
                    "pid": 99999999,
                    "processIdentity": "windows-filetime:1",
                    "token": "dead-owner-token",
                    "createdAt": bootstrap.utc_now(),
                }
            ),
            encoding="utf-8",
            newline="\n",
        )
        event = {
            "eventType": "attempt-failed",
            "timestamp": bootstrap.utc_now(),
            "attemptId": "recovered-dead-lock",
            "operationId": "model-probe:dead-lock",
            "role": "model_probe",
            "pid": os.getpid(),
            "processIdentity": bootstrap.process_creation_identity(os.getpid()),
            "writeSet": [],
        }

        bootstrap.append_process_event(self.run_dir, event)

        self.assertFalse(lock.exists())
        self.assertEqual("recovered-dead-lock", bootstrap.read_process_events(self.run_dir)[-1]["attemptId"])

        lock.write_text("", encoding="utf-8")
        stale_time = bootstrap.time.time() - 2
        os.utime(lock, (stale_time, stale_time))
        event["attemptId"] = "recovered-incomplete-lock"
        bootstrap.append_process_event(self.run_dir, event)
        self.assertFalse(lock.exists())
        self.assertEqual(
            "recovered-incomplete-lock",
            bootstrap.read_process_events(self.run_dir)[-1]["attemptId"],
        )

        lock.write_text(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "processIdentity": bootstrap.process_creation_identity(os.getpid()),
                    "token": "committed-owner-token",
                    "createdAt": bootstrap.utc_now(),
                    "phase": "committed",
                }
            ),
            encoding="utf-8",
            newline="\n",
        )
        event["attemptId"] = "recovered-committed-lock"
        bootstrap.append_process_event(self.run_dir, event)
        self.assertFalse(lock.exists())
        self.assertEqual(
            "recovered-committed-lock",
            bootstrap.read_process_events(self.run_dir)[-1]["attemptId"],
        )

    def test_process_lease_can_release_a_normally_exited_child(self) -> None:
        self.prepare()
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        self.addCleanup(lambda: child.poll() is None and child.kill())
        self.assertEqual(0, bootstrap.main([
            "process-lease", "--run-dir", str(self.run_dir), "--action", "acquire",
            "--operation-id", "model-probe:exited", "--role", "model_probe",
            "--pid", str(child.pid),
        ]))
        child.terminate()
        child.wait(timeout=10)
        self.assertEqual(
            0,
            bootstrap.main(
                [
                    "process-lease", "--run-dir", str(self.run_dir), "--action", "release",
                    "--operation-id", "model-probe:exited", "--pid", str(child.pid),
                    "--state", "completed",
                ]
            ),
        )
        leases = self.read_json("process-leases.json")["leases"]
        self.assertEqual("completed", leases[-1]["state"])

    def test_process_lease_release_requires_owner_pid_and_matching_live_identity(self) -> None:
        self.prepare()
        acquire = [
            "process-lease", "--run-dir", str(self.run_dir), "--action", "acquire",
            "--operation-id", "model-probe:identity", "--role", "model_probe",
            "--pid", str(os.getpid()),
        ]
        self.assertEqual(0, bootstrap.main(acquire))
        release = [
            "process-lease", "--run-dir", str(self.run_dir), "--action", "release",
            "--operation-id", "model-probe:identity", "--state", "completed",
        ]
        self.assertEqual(1, bootstrap.main(release))
        self.assertEqual(1, bootstrap.main([*release, "--pid", str(os.getpid() + 1)]))
        state = self.read_json("process-leases.json")
        state["leases"][-1]["processIdentity"] = "forged-process-identity"
        self.write_json("process-leases.json", state)
        self.assertEqual(1, bootstrap.main([*release, "--pid", str(os.getpid())]))
        self.assertEqual("acquired", self.read_json("process-leases.json")["leases"][-1]["state"])

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
            results = list(executor.map(
                lambda operation: acquire(operation, os.getpid()),
                ["model-probe:parallel-a", "model-probe:parallel-b"],
            ))
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
            self.complete_process_lease(operation, layer)
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
            self.complete_process_lease(operation, layer)
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
        self.complete_process_lease("verifier", "independent_verifier")
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

    def test_abandoned_incomplete_codex_run_can_be_replaced_same_round(self) -> None:
        self.prepare(execution_mode="codex-exec")
        self.complete_preflight()
        self.authorize_launch()
        manifest = self.read_json("review-input.json")
        identity = bootstrap.process_creation_identity(os.getpid())
        self.assertIsNotNone(identity)
        bootstrap.append_process_event(
            self.run_dir,
            {
                "eventType": "attempt-started",
                "timestamp": bootstrap.utc_now(),
                "attemptId": "failed-reviewer",
                "operationId": "reviewer:blind_hunter",
                "role": "blind_hunter",
                "pid": os.getpid(),
                "processIdentity": identity,
                "writeSet": [],
            },
        )
        bootstrap.append_process_event(
            self.run_dir,
            {
                "eventType": "attempt-failed",
                "timestamp": bootstrap.utc_now(),
                "attemptId": "failed-reviewer",
                "operationId": "reviewer:blind_hunter",
                "role": "blind_hunter",
                "pid": os.getpid(),
                "processIdentity": identity,
                "writeSet": [],
                "note": "controller protocol failure",
            },
        )
        self.assertEqual(
            0,
            bootstrap.main(
                [
                    "seal-run",
                    "--run-dir",
                    str(self.run_dir),
                    "--state",
                    "abandoned",
                    "--reason",
                    "controller-protocol-failure",
                ]
            ),
        )
        abandoned = self.run_dir
        self.run_dir = self.repo / "bootstrap-run-replacement"

        self.prepare(
            execution_mode="codex-exec",
            review_id="upstream-manual-replacement",
            change_id=manifest["changeId"],
        )

        self.assertTrue((abandoned / "run-seal.json").is_file())
        self.assertTrue((self.run_dir / "review-input.json").is_file())

    def test_inspect_run_routes_passed_codex_preflight_to_access_proof(self) -> None:
        self.prepare(execution_mode="codex-exec")
        self.complete_preflight()
        classification = bootstrap.classify_run(
            self.run_dir, self.read_json("review-input.json")
        )
        self.assertEqual("prove-access", classification["nextAction"])

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
                    "--pid", str(os.getpid()),
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


    def test_codex_prepare_creates_artifact_view_and_fresh_replacement(self) -> None:
        self.prepare(execution_mode="codex-exec")
        manifest = self.read_json("review-input.json")
        view = self.read_json("artifact-view/manifest.json")
        self.assertEqual("artifact-view.v1", view["schemaVersion"])
        self.assertEqual(len(manifest["artifacts"]), len(view["entries"]))
        first = view["entries"][0]
        self.assertEqual(first["originalSha256"], first["snapshotSha256"])
        self.assertEqual(
            (self.repo / first["originalPath"]).read_bytes(),
            (self.run_dir / first["snapshotPath"]).read_bytes(),
        )
        self.target.write_text("# Plan\n\nFresh authority rule.\n", encoding="utf-8", newline="\n")
        stale_out = self.run_dir / "attempts" / "stale" / "access.json"
        self.assertEqual(
            1,
            bootstrap.main([
                "access-handshake", "--run-dir", str(self.run_dir), "--role", "blind_hunter",
                "--out", str(stale_out),
            ]),
        )
        self.run_dir = self.repo / "bootstrap-run-fresh"
        self.prepare(execution_mode="codex-exec", review_id="upstream-manual-fresh")
        fresh = self.read_json("review-input.json")
        self.assertNotEqual(manifest["inputHash"], fresh["inputHash"])
        fresh_out = self.run_dir / "attempts" / "fresh" / "access.json"
        self.assertEqual(
            0,
            bootstrap.main([
                "access-handshake", "--run-dir", str(self.run_dir), "--role", "blind_hunter",
                "--out", str(fresh_out),
            ]),
        )

    def test_run_local_access_handshake_helper_does_not_depend_on_repository_skill_path(self) -> None:
        self.prepare(execution_mode="codex-exec")
        manifest = self.read_json("review-input.json")
        attempt_dir = self.run_dir / "attempts" / "standalone-handshake"
        attempt_dir.mkdir(parents=True)
        helper_path, request_path, output_path = bootstrap.materialize_access_handshake_helper(
            self.run_dir, manifest, "blind_hunter", attempt_dir
        )

        result = subprocess.run(
            [sys.executable, str(helper_path), "--request", str(request_path), "--out", str(output_path)],
            cwd=self.repo,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(output_path.is_file())
        self.assertTrue(helper_path.is_relative_to(attempt_dir.resolve()))
        handshake = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(handshake["handshakeHash"], result.stdout.strip())
        self.assertEqual(
            handshake["handshakeHash"],
            bootstrap.validate_access_handshake_payload(
                self.run_dir, manifest, "blind_hunter", handshake
            ),
        )

    def test_codex_runner_prompt_routes_reads_through_artifact_view(self) -> None:
        self.prepare(execution_mode="codex-exec")
        manifest = self.read_json("review-input.json")
        attempt_dir = self.run_dir / "attempts" / "prompt-contract"
        attempt_dir.mkdir(parents=True)
        helper_path, request_path, output_path = bootstrap.materialize_access_handshake_helper(
            self.run_dir, manifest, "blind_hunter", attempt_dir
        )

        prompt = bootstrap.runner_prompt(
            self.run_dir,
            manifest,
            "blind_hunter",
            "prompt-contract",
            helper_path,
            request_path,
            output_path,
        )

        self.assertIn(f"Assigned run directory: {self.run_dir}", prompt)
        self.assertIn(str(self.run_dir / manifest["artifactView"]["manifestPath"]), prompt)
        self.assertIn("Read every artifact from its Artifact View snapshotPath", prompt)
        self.assertIn("Resolve every relative snapshotPath against the assigned run directory", prompt)
        self.assertIn("Do not edit formal output files", prompt)
        self.assertNotIn("fill\n`reviewer-outputs/blind_hunter.json`", prompt)

    def test_parent_rejects_forged_run_local_access_handshake(self) -> None:
        self.prepare(execution_mode="codex-exec")
        manifest = self.read_json("review-input.json")
        handshake = bootstrap.access_handshake_payload(self.run_dir, manifest, "model_probe")
        handshake["checkedArtifacts"] = []
        handshake["handshakeHash"] = bootstrap.value_hash(
            {key: value for key, value in handshake.items() if key not in {"checkedAt", "handshakeHash"}}
        )

        with self.assertRaises(bootstrap.BootstrapError):
            bootstrap.validate_access_handshake_payload(
                self.run_dir, manifest, "model_probe", handshake
            )

    def test_failed_codex_payload_preserves_failure_reason_in_formal_output(self) -> None:
        self.prepare(execution_mode="codex-exec")
        self.complete_preflight()
        self.authorize_launch()
        manifest = self.read_json("review-input.json")
        attempt_dir = self.run_dir / "attempts" / "failed-payload"
        attempt_dir.mkdir(parents=True)
        handshake = bootstrap.access_handshake_payload(self.run_dir, manifest, "blind_hunter")
        self.write_json("attempts/failed-payload/access-handshake.json", handshake)
        process_identity = bootstrap.process_creation_identity(os.getpid())
        self.assertIsNotNone(process_identity)
        self.write_json(
            "attempts/failed-payload/process-result.json",
            {
                "schemaVersion": "bootstrap-process-result.v1",
                "attemptId": "failed-payload",
                "pid": os.getpid(),
                "exitCode": 0,
                "completedAt": bootstrap.utc_now(),
            },
        )
        bootstrap.append_process_event(
            self.run_dir,
            {
                "eventType": "attempt-started",
                "timestamp": bootstrap.utc_now(),
                "attemptId": "failed-payload",
                "operationId": "reviewer:blind_hunter",
                "role": "blind_hunter",
                "pid": os.getpid(),
                "processIdentity": process_identity,
                "writeSet": [
                    (self.run_dir / "reviewer-outputs" / "blind_hunter.json")
                    .relative_to(self.repo)
                    .as_posix()
                ],
            },
        )
        candidate = {
            "schemaVersion": "bootstrap-layer-candidate.v1",
            "attemptId": "failed-payload",
            "role": "blind_hunter",
            "inputHash": manifest["inputHash"],
            "accessHandshakeHash": handshake["handshakeHash"],
            "payload": {
                "status": "failed",
                "failureReason": "Assigned context is unavailable",
                "coverage": {
                    "requiredArtifacts": [item["artifact"] for item in manifest["artifacts"]],
                    "readArtifacts": [],
                    "missingArtifacts": [item["artifact"] for item in manifest["artifacts"]],
                },
                "candidates": [],
            },
        }

        with mock.patch.object(bootstrap, "run_codex_attempt", return_value=(candidate, attempt_dir)):
            self.assertEqual(
                1,
                bootstrap.main(
                    [
                        "run-layer",
                        "--run-dir",
                        str(self.run_dir),
                        "--role",
                        "blind_hunter",
                        "--codex-command",
                        "test-codex-command",
                        "--model",
                        manifest["codexExecPolicy"]["preferredModel"],
                    ]
                ),
            )
        self.assertEqual(
            "Assigned context is unavailable",
            self.read_json("reviewer-outputs/blind_hunter.json")["failureReason"],
        )

    def test_git_index_drift_blocks_launch_authorization(self) -> None:
        self.prepare()
        self.complete_preflight()
        drift = self.repo / "index-drift.txt"
        drift.write_text("drift\n", encoding="utf-8", newline="\n")
        subprocess.run(["git", "add", "index-drift.txt"], cwd=self.repo, check=True)
        self.assertEqual(1, bootstrap.main(["authorize-launch", "--run-dir", str(self.run_dir)]))

    def test_cost_estimate_marks_round_three_scale_as_high_cost(self) -> None:
        profile = bootstrap.load_profile("bootstrap-skill-route")
        artifacts = [
            {
                "artifact": f"scope/item-{index}.md", "sha256": "sha256:" + "a" * 64,
                "sizeBytes": 10925, "textEncoding": "utf-8", "lineCount": 100,
            }
            for index in range(49)
        ]
        estimate = bootstrap.review_cost_estimate(profile, artifacts)
        self.assertTrue(estimate["highCost"])
        self.assertGreaterEqual(estimate["estimatedTotalTokens"]["p90"], 500000)
        self.assertEqual(17, estimate["basisSampleCount"])
        self.assertEqual("low", estimate["confidence"])

    def test_p2_requires_disposition_and_rejects_high_risk_deferral(self) -> None:
        self.prepare()
        self.complete_layers({"blind_hunter": [self.candidate(severity="P2")]})
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        finding_id = self.read_json("review-candidates.json")["findings"][0]["findingId"]
        self.assertEqual(1, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        manifest = self.read_json("review-input.json")
        p2 = {
            "schemaVersion": "bootstrap-p2-dispositions.v1", "reviewId": manifest["reviewId"],
            "inputHash": manifest["inputHash"], "findingIds": [finding_id],
            "dispositions": [{
                "findingId": finding_id, "status": "deferred", "risk": "high",
                "reason": "Deferred for later", "owner": "owner",
                "expiry": "2099-01-01T00:00:00Z", "closureTest": "test-command",
            }],
        }
        self.write_json("p2-dispositions.json", p2)
        self.assertEqual(1, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        p2["dispositions"][0]["risk"] = "normal"
        p2["dispositions"][0]["expiry"] = "2020-01-01T00:00:00Z"
        self.write_json("p2-dispositions.json", p2)
        self.assertEqual(1, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        p2["dispositions"][0] = {
            "findingId": finding_id, "status": "fixed", "risk": "normal",
            "reason": "Targeted validation proves closure",
        }
        self.write_json("p2-dispositions.json", p2)
        self.assertEqual(0, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        self.assertEqual("clean", self.read_json("review-gate-result.json")["status"])

    def test_list_inspect_and_seal_are_additive_lifecycle_views(self) -> None:
        self.prepare()
        classified = bootstrap.classify_run(self.run_dir, self.read_json("review-input.json"))
        self.assertEqual("prepared", classified["runExecutionState"])
        index_path = self.repo / "logs" / "ci" / "bootstrap-index.json"
        self.assertEqual(
            0,
            bootstrap.main([
                "list-runs", "--repository-root", str(self.repo), "--out", str(index_path),
            ]),
        )
        self.assertEqual(1, json.loads(index_path.read_text(encoding="utf-8"))["runCount"])
        self.assertEqual(
            0,
            bootstrap.main([
                "seal-run", "--run-dir", str(self.run_dir), "--state", "abandoned",
                "--reason", "operator-replaced-run",
            ]),
        )
        self.assertEqual("abandoned", self.read_json("run-seal.json")["state"])
        self.assertTrue((self.run_dir / "run-summary.json").is_file())
        self.assertEqual(
            1,
            bootstrap.main([
                "seal-run", "--run-dir", str(self.run_dir), "--state", "abandoned",
                "--reason", "cannot-overwrite",
            ]),
        )

    def test_control_plane_command_and_environment_are_typed_and_allowlisted(self) -> None:
        command = bootstrap.render_codex_command(
            "codex", "gpt-5.6-terra", "high", "workspace-write",
            (self.repo / "candidate.json").resolve(),
        )
        self.assertEqual("codex", command[0])
        self.assertIn("model_reasoning_effort=high", command)
        self.assertIn("-C", command)
        self.assertIn("--skip-git-repo-check", command)
        self.assertIn(str(self.repo.resolve()), command)
        child, evidence = bootstrap.child_environment()
        self.assertTrue(set(child).issubset(set(bootstrap.ENVIRONMENT_ALLOWLIST)))
        self.assertEqual(set(child), set(evidence))
        self.assertFalse(bootstrap.CONTROL_PLANE_POLICY["shell"])
        self.assertEqual("none", bootstrap.CONTROL_PLANE_POLICY["providerDispatch"])

    def test_atomic_write_uses_short_temp_name_for_deep_windows_paths(self) -> None:
        target = (
            self.repo / "logs" / "ci" / "2026-07-16" / "review-gateway-bootstrap-control-plane"
            / "artifact-view" / "tree" / "execution-plans"
            / "2026-07-12-llm-review-evidence-gate-hardening" / "schemas"
            / "bootstrap-review-launch-authorization.v1.schema.json"
        )
        bootstrap.atomic_write_json(target, {"status": "passed"})
        self.assertEqual({"status": "passed"}, json.loads(target.read_text(encoding="utf-8")))

    def test_same_role_concurrent_launch_reservation_allows_only_one_popen(self) -> None:
        self.prepare(execution_mode="codex-exec")
        manifest = self.read_json("review-input.json")
        formal_path = self.run_dir / "reviewer-outputs" / "blind_hunter.json"
        formal_before = formal_path.read_bytes()
        launched = threading.Event()
        release = threading.Event()
        popen_calls: list[list[str]] = []

        class BlockingProcess:
            pid = os.getpid()
            returncode: int | None = None

            def communicate(self, _prompt: str) -> tuple[str, str]:
                if not release.wait(timeout=5):
                    raise AssertionError("Timed out waiting to release fake Codex process")
                self.returncode = 1
                return "", "simulated child failure"

            def kill(self) -> None:
                self.returncode = -9
                release.set()

        def fake_popen(argv: list[str], **_kwargs: object) -> BlockingProcess:
            popen_calls.append(argv)
            launched.set()
            return BlockingProcess()

        model = manifest["codexExecPolicy"]["preferredModel"]
        with mock.patch.object(bootstrap.subprocess, "Popen", side_effect=fake_popen):
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                first = executor.submit(
                    bootstrap.run_codex_attempt,
                    self.run_dir,
                    manifest,
                    "blind_hunter",
                    "codex",
                    model,
                )
                self.assertTrue(launched.wait(timeout=5))
                second = executor.submit(
                    bootstrap.run_codex_attempt,
                    self.run_dir,
                    manifest,
                    "blind_hunter",
                    "codex",
                    model,
                )
                with self.assertRaises(bootstrap.BootstrapError):
                    second.result(timeout=5)
                active_lease = next(
                    item
                    for item in self.read_json("process-leases.json")["leases"]
                    if item["operationId"] == "reviewer:blind_hunter"
                )
                self.assertEqual("acquired", active_lease["state"])
                release.set()
                with self.assertRaises(bootstrap.BootstrapError):
                    first.result(timeout=5)

        self.assertEqual(1, len(popen_calls))
        self.assertEqual(formal_before, formal_path.read_bytes())
        rejected = [
            event
            for event in bootstrap.read_process_events(self.run_dir)
            if event.get("eventType") == "attempt-rejected"
        ]
        self.assertEqual(1, len(rejected))
        rejected_result = self.read_json(f"attempts/{rejected[0]['attemptId']}/process-result.json")
        self.assertIn("Concurrent write-set overlap", rejected_result["launchError"])

    def test_different_role_reservations_can_launch_concurrently(self) -> None:
        self.prepare(execution_mode="codex-exec")
        manifest = self.read_json("review-input.json")
        two_launched = threading.Event()
        release = threading.Event()
        popen_calls: list[list[str]] = []

        class BlockingProcess:
            pid = os.getpid()
            returncode: int | None = None

            def communicate(self, _prompt: str) -> tuple[str, str]:
                if not release.wait(timeout=5):
                    raise AssertionError("Timed out waiting to release fake Codex process")
                self.returncode = 1
                return "", "simulated child failure"

            def kill(self) -> None:
                self.returncode = -9
                release.set()

        def fake_popen(argv: list[str], **_kwargs: object) -> BlockingProcess:
            popen_calls.append(argv)
            if len(popen_calls) == 2:
                two_launched.set()
            return BlockingProcess()

        model = manifest["codexExecPolicy"]["preferredModel"]
        with mock.patch.object(bootstrap.subprocess, "Popen", side_effect=fake_popen):
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(
                        bootstrap.run_codex_attempt,
                        self.run_dir,
                        manifest,
                        role,
                        "codex",
                        model,
                    )
                    for role in ("blind_hunter", "edge_case_hunter")
                ]
                self.assertTrue(two_launched.wait(timeout=5))
                release.set()
                for future in futures:
                    with self.assertRaises(bootstrap.BootstrapError):
                        future.result(timeout=5)

        self.assertEqual(2, len(popen_calls))
        reserved_roles = {
            event["role"]
            for event in bootstrap.read_process_events(self.run_dir)
            if event.get("eventType") == "attempt-reserved"
        }
        self.assertEqual({"blind_hunter", "edge_case_hunter"}, reserved_roles)

    def test_completed_formal_role_output_blocks_rerun_without_overwrite(self) -> None:
        self.prepare(execution_mode="codex-exec")
        manifest = self.read_json("review-input.json")
        formal_path = self.run_dir / "reviewer-outputs" / "blind_hunter.json"
        formal = self.read_json("reviewer-outputs/blind_hunter.json")
        formal["status"] = "completed"
        formal["coverage"]["readArtifacts"] = formal["coverage"]["requiredArtifacts"]
        formal["coverage"]["missingArtifacts"] = []
        self.write_json("reviewer-outputs/blind_hunter.json", formal)
        formal_before = formal_path.read_bytes()

        with mock.patch.object(bootstrap.subprocess, "Popen") as popen:
            with self.assertRaises(bootstrap.BootstrapError):
                bootstrap.run_codex_attempt(
                    self.run_dir,
                    manifest,
                    "blind_hunter",
                    "codex",
                    manifest["codexExecPolicy"]["preferredModel"],
                )

        popen.assert_not_called()
        self.assertEqual(formal_before, formal_path.read_bytes())
        rejected = [
            event
            for event in bootstrap.read_process_events(self.run_dir)
            if event.get("eventType") == "attempt-rejected"
        ]
        self.assertEqual(1, len(rejected))
        self.assertIn("already completed", rejected[0]["note"])

    def test_completed_operation_event_blocks_rerun_before_popen(self) -> None:
        self.prepare(execution_mode="codex-exec")
        manifest = self.read_json("review-input.json")
        formal = (
            self.run_dir / "reviewer-outputs" / "blind_hunter.json"
        ).relative_to(self.repo).as_posix()
        identity = bootstrap.process_creation_identity(os.getpid())
        self.assertIsNotNone(identity)
        bootstrap.append_process_event(
            self.run_dir,
            {
                "eventType": "attempt-completed",
                "timestamp": bootstrap.utc_now(),
                "attemptId": "completed-blind-hunter",
                "operationId": "reviewer:blind_hunter",
                "role": "blind_hunter",
                "pid": os.getpid(),
                "processIdentity": identity,
                "writeSet": [formal],
            },
        )

        with mock.patch.object(bootstrap.subprocess, "Popen") as popen:
            with self.assertRaises(bootstrap.BootstrapError):
                bootstrap.run_codex_attempt(
                    self.run_dir,
                    manifest,
                    "blind_hunter",
                    "codex",
                    manifest["codexExecPolicy"]["preferredModel"],
                )

        popen.assert_not_called()

    def test_dead_reserved_controller_is_marked_stale_by_lease_inspection(self) -> None:
        self.prepare(execution_mode="codex-exec")
        manifest = self.read_json("review-input.json")
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        self.addCleanup(lambda: child.poll() is None and child.kill())
        identity = bootstrap.process_creation_identity(child.pid)
        self.assertIsNotNone(identity)
        formal = (
            self.run_dir / "reviewer-outputs" / "blind_hunter.json"
        ).relative_to(self.repo).as_posix()
        bootstrap.append_process_event(
            self.run_dir,
            {
                "eventType": "attempt-reserved",
                "timestamp": bootstrap.utc_now(),
                "attemptId": "reserved-blind-hunter",
                "operationId": "reviewer:blind_hunter",
                "role": "blind_hunter",
                "pid": child.pid,
                "processIdentity": identity,
                "writeSet": [formal],
            },
        )
        bootstrap.rebuild_process_leases_from_events(self.run_dir, manifest)
        child.terminate()
        child.wait(timeout=10)

        self.assertEqual(
            0,
            bootstrap.main(
                ["process-lease", "--run-dir", str(self.run_dir), "--action", "inspect"]
            ),
        )

        events = bootstrap.read_process_events(self.run_dir)
        self.assertEqual("attempt-stale", events[-1]["eventType"])
        self.assertEqual("reserved-blind-hunter", events[-1]["attemptId"])
        self.assertNotIn("reserved-blind-hunter", bootstrap.active_attempts(events))
        lease = next(
            item
            for item in self.read_json("process-leases.json")["leases"]
            if item["operationId"] == "reviewer:blind_hunter"
        )
        self.assertEqual("stale", lease["state"])

    def test_active_attempt_blocks_only_overlapping_formal_write_set(self) -> None:
        self.prepare(execution_mode="codex-exec")
        self.complete_preflight()
        self.complete_access_proof(self.read_json("review-input.json"))
        proof = self.read_json("access-proof.json")
        proof["commandIdentity"] = bootstrap.value_hash("missing-codex-command")
        self.write_json("access-proof.json", proof)
        self.assertEqual(0, bootstrap.main(["authorize-launch", "--run-dir", str(self.run_dir)]))
        formal = (self.run_dir / "reviewer-outputs" / "blind_hunter.json").relative_to(self.repo).as_posix()
        bootstrap.append_process_event(
            self.run_dir,
            {
                "eventType": "attempt-started", "timestamp": bootstrap.utc_now(),
                "attemptId": "existing-attempt", "operationId": "reviewer:blind_hunter",
                "role": "blind_hunter", "pid": os.getpid(),
                "processIdentity": bootstrap.process_creation_identity(os.getpid()),
                "writeSet": [formal],
            },
        )
        self.assertEqual(
            1,
            bootstrap.main([
                "run-layer", "--run-dir", str(self.run_dir), "--role", "blind_hunter",
                "--codex-command", "missing-codex-command",
            ]),
        )


if __name__ == "__main__":
    unittest.main()
