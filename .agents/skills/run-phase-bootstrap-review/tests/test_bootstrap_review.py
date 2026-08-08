from __future__ import annotations

import copy
import importlib.util
import concurrent.futures
import hashlib
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
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
        root_relative = Path(".agents/skills/run-phase-bootstrap-review/references/authority-roots.v1.json")
        root_target = self.repo / root_relative
        root_target.parent.mkdir(parents=True, exist_ok=True)
        root_target.write_bytes(bootstrap.AUTHORITY_ROOT_PATH.read_bytes())
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

    def write_cost_attempt(
        self,
        run_dir: Path,
        attempt_id: str,
        role: str,
        tokens: int,
        *,
        input_hash: str,
        model: str = "gpt-test",
        start_minute: int = 0,
        duration_seconds: int = 60,
        terminal_type: str = "attempt-completed",
        exit_code: int = 0,
        typed_placeholders: dict[str, str] | None = None,
        operation_id: str | None = None,
        reasoning_effort: str = "high",
    ) -> list[dict]:
        attempt = run_dir / "attempts" / attempt_id
        attempt.mkdir(parents=True)
        start = datetime(2026, 7, 30, tzinfo=timezone.utc) + timedelta(minutes=start_minute)
        process_completed = start + timedelta(seconds=max(1, duration_seconds // 2))
        terminal = start + timedelta(seconds=duration_seconds)
        timestamp = lambda value: value.isoformat().replace("+00:00", "Z")
        operation_id = operation_id or (
            "verifier" if role == "independent_verifier"
            else (f"model-probe:{model}" if role == "model_probe" else f"reviewer:{role}")
        )
        pid = 1000 + start_minute
        write_set = [] if role == "model_probe" else [f"logs/cost/{attempt_id}.json"]
        helper_path = attempt / "access-handshake-helper.py"
        handshake_request_path = attempt / "access-handshake-request.json"
        helper_path.write_text("# test helper\n", encoding="utf-8", newline="\n")
        handshake_request_path.write_text("{}\n", encoding="utf-8", newline="\n")
        request = {
            "schemaVersion": "bootstrap-attempt-request.v1",
            "attemptId": attempt_id,
            "role": role,
            "inputHash": input_hash,
            "argv": [
                "codex", "exec", "--sandbox", "workspace-write", "-m", model,
                "-c", f"model_reasoning_effort={reasoning_effort}", "--json",
                "--output-last-message", "candidate-output.json", "-",
            ],
            "shell": False,
            "environmentAllowlist": list(bootstrap.ENVIRONMENT_ALLOWLIST),
            "environmentEvidence": {},
            "typedPlaceholders": (
                typed_placeholders
                if typed_placeholders is not None
                else bootstrap.TYPED_PLACEHOLDERS
            ),
            "writeSet": write_set,
            "executionReadSet": [],
            "dependencyClosure": [],
            "handshakeHelperPath": helper_path.relative_to(run_dir).as_posix(),
            "handshakeHelperHash": bootstrap.file_hash(helper_path),
            "handshakeRequestPath": handshake_request_path.relative_to(run_dir).as_posix(),
            "handshakeRequestHash": bootstrap.file_hash(handshake_request_path),
            "createdAt": timestamp(start),
        }
        if role != "model_probe":
            request.update({
                "runDirectory": str(run_dir),
                "artifactViewManifestPath": str(run_dir / "artifact-view/manifest.json"),
                "artifactViewManifestHash": "sha256:" + "f" * 64,
            })
        (attempt / "request.json").write_text(
            json.dumps(request), encoding="utf-8", newline="\n"
        )
        (attempt / "process-result.json").write_text(json.dumps({
            "schemaVersion": "bootstrap-process-result.v1",
            "attemptId": attempt_id,
            "pid": pid,
            "exitCode": exit_code,
            "completedAt": timestamp(process_completed),
        }), encoding="utf-8", newline="\n")
        (attempt / "token-usage.json").write_text(json.dumps({
            "schemaVersion": "bootstrap-token-usage.v1", "tokens": tokens,
        }), encoding="utf-8", newline="\n")
        (attempt / "stdout.log").write_text(json.dumps({
            "type": "turn.completed", "usage": {"total_tokens": tokens},
        }) + "\n", encoding="utf-8", newline="\n")
        (attempt / "stderr.log").write_text("", encoding="utf-8", newline="\n")
        if terminal_type == "attempt-completed":
            (attempt / "candidate-output.json").write_text(
                "{}\n", encoding="utf-8", newline="\n"
            )
            (attempt / "access-handshake.json").write_text(
                "{}\n", encoding="utf-8", newline="\n"
            )
        common = {
            "attemptId": attempt_id,
            "operationId": operation_id,
            "role": role,
            "pid": pid,
            "processIdentity": f"test-process:{pid}",
            "writeSet": write_set,
        }
        events = [{
            "eventType": "attempt-started",
            "timestamp": timestamp(start),
            "requestHash": bootstrap.value_hash(request),
            "selectedModel": model,
            **common,
        }]
        if exit_code == 0:
            events.append({
                "eventType": "attempt-process-completed",
                "timestamp": timestamp(process_completed),
                **common,
            })
        events.append({"eventType": terminal_type, "timestamp": timestamp(terminal), **common})
        return events

    def write_synthetic_blocked_result(
        self, finding_id: str, *, semantic_key: str | None = None
    ) -> None:
        manifest = self.read_json("review-input.json")
        finding = {
            "findingId": finding_id,
            "proposedSeverity": "P1",
            "status": "confirmed",
            "artifact": self.target.relative_to(self.repo).as_posix(),
            "dimension": "correctness",
            "triggerInput": f"trigger {semantic_key or finding_id}",
            "requiredState": "required state",
            "badOutcome": "bad outcome",
        }
        self.write_json(
            "review-gate-result.json",
            {
                "schemaVersion": "review-result.v1",
                **bootstrap.bootstrap_sidecar_binding(manifest),
                "status": "blocked",
                "findings": [finding],
            },
        )
        self.write_json(
            "review-dispositions.json",
            {
                "schemaVersion": "bootstrap-review-dispositions.v1",
                **bootstrap.bootstrap_sidecar_binding(manifest),
                "dispositions": [
                    {"findingId": finding_id, "status": "confirmed", "reason": "test blocker"}
                ],
            },
        )
        self.write_json(
            "review-candidates.json",
            {"schemaVersion": "review-candidates.v1", "findings": [finding]},
        )
        self.write_json(
            "review-metrics.json",
            {
                "schemaVersion": "bootstrap-review-metrics.v1",
                **bootstrap.bootstrap_sidecar_binding(manifest),
                "status": "blocked",
            },
        )

    def prepare(
        self,
        profile: str = "bootstrap-upstream-plan",
        *,
        execution_mode: str = "manual",
        review_id: str = "upstream-manual-001",
        change_id: str = "upstream-change-001",
        lineage_family_id: str | None = None,
        review_round: int = 1,
        predecessor_run: Path | None = None,
        round_entry_reason: str | None = None,
        high_risk_boundaries: list[str] | None = None,
        knowledge_context: Path | None = None,
        acceptance_route: Path | None = None,
        acceptance_completeness: Path | None = None,
        acceptance_run_input: Path | None = None,
        extra_scopes: list[Path] | None = None,
        finding_reentry_authorization: Path | None = None,
        hard_limit_recovery: Path | None = None,
        expected_result: int = 0,
    ) -> None:
        profile_contract = bootstrap.load_profile(profile)
        context_args = []
        for context_class in profile_contract["requiredContextClasses"]:
            context_args.extend(["--context-class", f"{context_class}={self.scope}"])
        required_check_args = []
        if profile_contract["planBoundCheckPolicy"]["required"]:
            required_check_args = ["--required-check", f"implementation-proof={self.scope}"]
        scope_policy_args = (
            ["--directory-scope-attestation", bootstrap.DIRECTORY_SCOPE_ATTESTATION]
            if profile in bootstrap.BOUNDED_SCOPE_PROFILES
            else []
        )
        predecessor_args = [] if predecessor_run is None else ["--predecessor-run-dir", str(predecessor_run)]
        effective_round_entry_reason = round_entry_reason
        effective_high_risk_boundaries = list(high_risk_boundaries or [])
        if (
            review_round == 2
            and profile != "bootstrap-focused-repair-verification"
            and effective_round_entry_reason is None
        ):
            effective_round_entry_reason = "high_risk_boundary_changed"
            effective_high_risk_boundaries = [
                self.target.relative_to(self.repo).as_posix()
            ]
        round_entry_args = [] if effective_round_entry_reason is None else [
            "--round-entry-reason", effective_round_entry_reason
        ]
        for boundary in effective_high_risk_boundaries:
            round_entry_args.extend(["--high-risk-boundary", boundary])
        knowledge_args = [] if knowledge_context is None else ["--knowledge-context", str(knowledge_context.relative_to(self.repo))]
        acceptance_args = []
        if acceptance_route is not None:
            acceptance_args.extend([
                "--acceptance-repair-route", str(acceptance_route.relative_to(self.repo))
            ])
        if acceptance_completeness is not None:
            acceptance_args.extend([
                "--acceptance-repair-completeness",
                str(acceptance_completeness.relative_to(self.repo)),
            ])
        if acceptance_run_input is not None:
            acceptance_args.extend([
                "--acceptance-run-input",
                str(acceptance_run_input.relative_to(self.repo)),
            ])
        if finding_reentry_authorization is not None:
            acceptance_args.extend([
                "--finding-mode-reentry-authorization",
                str(finding_reentry_authorization.relative_to(self.repo)),
            ])
        if hard_limit_recovery is not None:
            acceptance_args.extend([
                "--hard-limit-repair-recovery",
                str(hard_limit_recovery.relative_to(self.repo)),
            ])
        elif (
            expected_result == 0
            and review_round > 1
            and profile != "bootstrap-focused-repair-verification"
            and predecessor_run is not None
            and effective_round_entry_reason is not None
        ):
            finding_reentry_authorization = (
                self.repo / f"finding-reentry-{review_id}.json"
            )
            authorization_args = [
                "authorize-finding-mode-reentry",
                "--repository-root", str(self.repo),
                "--lineage-family-id", lineage_family_id or change_id,
                "--next-review-round", str(review_round),
                "--predecessor-run-dir", str(predecessor_run),
                "--round-entry-reason", effective_round_entry_reason,
                "--recommendation", "recommend",
                "--confidence", "0.9",
                "--rationale", "Test fixture authorizes the typed later discovery route",
                "--user-confirmed",
                "--out", str(finding_reentry_authorization),
            ]
            if acceptance_route is not None:
                authorization_args.extend([
                    "--acceptance-repair-route", str(acceptance_route)
                ])
            self.assertEqual(0, bootstrap.main(authorization_args))
            acceptance_args.extend([
                "--finding-mode-reentry-authorization",
                str(finding_reentry_authorization.relative_to(self.repo)),
            ])
        repair_closure_args = []
        if (
            1 < review_round <= bootstrap.REVIEW_CYCLE_POLICY["hardFullReviewRoundLimit"]
            and predecessor_run is not None
            and hard_limit_recovery is None
        ):
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
                "--lineage-family-id", lineage_family_id or change_id,
                "--review-round", str(review_round),
                *predecessor_args,
                *repair_closure_args,
                *acceptance_args,
                *round_entry_args,
                "--profile", profile,
                "--scope", str(self.scope),
                *[
                    item
                    for scope in (extra_scopes or [])
                    for item in ("--scope", str(scope))
                ],
                *scope_policy_args,
                *context_args,
                *knowledge_args,
                *required_check_args,
                "--execution-mode", execution_mode,
                "--semantic-review-exclusivity", "no-other-semantic-review-in-cycle",
                "--out-dir", str(self.run_dir),
            ]
        )
        self.assertEqual(expected_result, result)

    def test_broh_s0_prepare_dry_run_contract(self) -> None:
        profile = "bootstrap-upstream-plan"
        profile_contract = bootstrap.load_profile(profile)
        context_args: list[str] = []
        for context_class in profile_contract["requiredContextClasses"]:
            context_args.extend(["--context-class", f"{context_class}={self.scope}"])
        scope_policy_args = (
            ["--directory-scope-attestation", bootstrap.DIRECTORY_SCOPE_ATTESTATION]
            if profile in bootstrap.BOUNDED_SCOPE_PROFILES
            else []
        )
        argv = [
            "prepare",
            "--dry-run",
            "--repository-root", str(self.repo),
            "--review-id", "dry-run-001",
            "--change-id", "dry-run-change-001",
            "--lineage-family-id", "dry-run-change-001",
            "--review-round", "1",
            "--profile", profile,
            "--scope", str(self.scope),
            *scope_policy_args,
            *context_args,
            "--execution-mode", "manual",
            "--semantic-review-exclusivity", "no-other-semantic-review-in-cycle",
            "--out-dir", str(self.run_dir),
        ]
        with mock.patch("sys.stdout", new_callable=io.StringIO) as output:
            result = bootstrap.main(argv)
        self.assertEqual(result, 0)
        diagnostic = json.loads(output.getvalue())
        self.assertEqual(diagnostic["status"], "dry-run")
        self.assertFalse(diagnostic["runCreated"])
        self.assertEqual(diagnostic["closureBindingVersion"], "v12")
        self.assertEqual(diagnostic["authorizes"], [])
        self.assertEqual(
            diagnostic["closureBindings"],
            {
                "candidateHash": diagnostic["candidateHash"],
                "candidateBindingHash": diagnostic["candidateBindingHash"],
                "sourceHash": diagnostic["sourceHash"],
                "validatorHash": diagnostic["validatorHash"],
                "gitIndexHash": diagnostic["gitIndexHash"],
                "writeSetHash": diagnostic["writeSetHash"],
                "executionReadSetHash": diagnostic["executionReadSetHash"],
                "dependencyClosureHash": diagnostic["dependencyClosureHash"],
            },
        )
        for field in (
            "candidateHash",
            "candidateBindingHash",
            "sourceHash",
            "validatorHash",
            "gitIndexHash",
            "writeSetHash",
            "executionReadSetHash",
            "dependencyClosureHash",
        ):
            self.assertRegex(diagnostic[field], r"^sha256:[0-9a-f]{64}$")
        self.assertFalse(self.run_dir.exists())

    def test_broh_s1_context_and_planned_file_diagnostics(self) -> None:
        profile = "bootstrap-upstream-plan"
        profile_contract = bootstrap.load_profile(profile)
        context_args: list[str] = []
        for context_class in profile_contract["requiredContextClasses"]:
            context_args.extend(["--context-class", f"{context_class}={self.scope}"])
        scope_policy_args = (
            ["--directory-scope-attestation", bootstrap.DIRECTORY_SCOPE_ATTESTATION]
            if profile in bootstrap.BOUNDED_SCOPE_PROFILES
            else []
        )
        argv = [
            "prepare",
            "--dry-run",
            "--repository-root", str(self.repo),
            "--review-id", "dry-run-s1-001",
            "--change-id", "dry-run-s1-change-001",
            "--lineage-family-id", "dry-run-s1-change-001",
            "--review-round", "1",
            "--profile", profile,
            "--scope", str(self.scope),
            "--write-set", "planned/new-output.json",
            *scope_policy_args,
            *context_args,
            "--execution-mode", "manual",
            "--semantic-review-exclusivity", "no-other-semantic-review-in-cycle",
            "--out-dir", str(self.run_dir),
        ]
        with mock.patch("sys.stdout", new_callable=io.StringIO) as output:
            result = bootstrap.main(argv)
        self.assertEqual(result, 0)
        diagnostic = json.loads(output.getvalue())
        self.assertEqual(diagnostic["contextDiagnostics"]["status"], "complete")
        self.assertRegex(diagnostic["contextDiagnostics"]["acceptedScopesHash"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(
            sorted(diagnostic["contextDiagnostics"]["requiredClasses"]),
            sorted(profile_contract["requiredContextClasses"]),
        )
        self.assertEqual(
            sorted(diagnostic["contextDiagnostics"]["classes"]),
            sorted(profile_contract["requiredContextClasses"]),
        )
        self.assertEqual(
            diagnostic["contextDiagnostics"]["acceptedScopesByClass"],
            diagnostic["contextDiagnostics"]["artifacts"],
        )
        self.assertEqual(diagnostic["plannedNewFiles"], ["planned/new-output.json"])
        self.assertEqual(diagnostic["plannedNewFilesHashVersion"], "v8")
        self.assertEqual(diagnostic["freezeWindow"]["state"], "preparation")
        self.assertEqual(diagnostic["freezeWindow"]["reviewMutationPolicy"], "immutable")
        self.assertFalse(diagnostic["freezeWindow"]["mutationAllowed"])
        self.assertEqual(diagnostic["freezeWindow"]["authorizes"], [])
        self.assertFalse(self.run_dir.exists())

    def test_broh_s2_windows_transport_heartbeat_recovery(self) -> None:
        class TimedOutProcess:
            def __init__(self) -> None:
                self.killed = False
                self.calls = 0

            def communicate(self, prompt=None, timeout=None):
                self.calls += 1
                if self.calls == 1:
                    self.prompt = prompt
                    self.timeout = timeout
                    raise subprocess.TimeoutExpired(["codex", "exec"], timeout)
                return "partial stdout", "partial stderr"

            def kill(self) -> None:
                self.killed = True

        process = TimedOutProcess()
        with self.assertRaisesRegex(bootstrap.NoProgressTimeout, "no progress") as captured:
            bootstrap.communicate_with_no_progress_timeout(process, "prompt", 5)
        self.assertTrue(process.killed)
        self.assertEqual(bootstrap.HEARTBEAT_EVENT_TYPE, "attempt-heartbeat")
        self.assertEqual(bootstrap.NO_PROGRESS_TIMEOUT_EVENT_TYPE, "attempt-no-progress-timeout-v10")
        self.assertEqual(process.timeout, 5)
        self.assertEqual(captured.exception.stdout, "partial stdout")
        self.assertEqual(captured.exception.stderr, "partial stderr")
        argv = bootstrap.render_codex_command(
            "codex", "gpt-test", "high", "workspace-write", (self.repo / "out.json").resolve()
        )
        self.assertEqual(argv[-1], "-")
        self.assertNotIn("py", argv)
        self.assertNotIn("python", argv)
        self.assertEqual(
            {
                bootstrap.attempt_failure_guidance(kind)
                for kind in ("transport", "malformed-output", "stale-evidence", "semantic-blocker")
            },
            {
                "retry-same-role",
                "retry-same-role-with-preserved-rejection",
                "refresh-frozen-binding-before-retry",
                "repair-finding-before-verification",
            },
        )

        class TimedOutProbeProcess:
            def __init__(self) -> None:
                self.pid = os.getpid()
                self.returncode = None
                self.killed = False

            def communicate(self, prompt=None, timeout=None):
                if timeout is not None:
                    raise subprocess.TimeoutExpired(["codex", "exec"], timeout)
                return "partial stdout", "partial stderr"

            def kill(self) -> None:
                self.killed = True

        self.prepare(execution_mode="codex-exec")
        self.complete_preflight()
        probe = TimedOutProbeProcess()
        real_popen = subprocess.Popen

        def launch_process(argv, *args, **kwargs):
            if argv and argv[0] == "codex":
                return probe
            return real_popen(argv, *args, **kwargs)

        with (
            mock.patch.object(
                bootstrap.subprocess, "Popen", side_effect=launch_process
            ),
            mock.patch.object(
                bootstrap, "process_creation_identity", return_value="test-process-identity"
            ),
            mock.patch.object(bootstrap, "rebuild_process_leases_from_events"),
        ):
            self.assertEqual(
                1,
                bootstrap.main(
                    [
                        "prove-access",
                        "--run-dir",
                        str(self.run_dir),
                        "--codex-command",
                        "codex",
                    ]
                ),
            )
        probe_attempts = list((self.run_dir / "attempts").glob("access-probe-*"))
        self.assertEqual(len(probe_attempts), 1)
        self.assertTrue(probe.killed)
        process_result = json.loads(
            (probe_attempts[0] / "process-result.json").read_text(encoding="utf-8")
        )
        self.assertEqual(process_result["failureClass"], "transport-timeout")
        event_types = [item["eventType"] for item in bootstrap.read_process_events(self.run_dir)]
        self.assertIn(bootstrap.HEARTBEAT_EVENT_TYPE, event_types)
        self.assertIn(bootstrap.NO_PROGRESS_TIMEOUT_EVENT_TYPE, event_types)


    def test_broh_s3_read_boundary_and_exact_evidence(self) -> None:
        source = self.repo / "frozen.txt"
        source.write_bytes("one\r\ntwo\r\nthree\r\n".encode("utf-8"))
        run_dir = self.run_dir
        artifact_view = run_dir / "artifact-view" / "tree"
        artifact_view.mkdir(parents=True)
        snapshot = artifact_view / "frozen.txt"
        snapshot.write_bytes(source.read_bytes())
        manifest = {
            "artifactView": {"manifestPath": "artifact-view/manifest.json"},
            "artifacts": [{
                "artifact": "frozen.txt",
                "sha256": bootstrap.file_hash(source),
            }],
        }
        (run_dir / "artifact-view" / "manifest.json").write_text(
            json.dumps({"entries": [{
                "originalPath": "frozen.txt",
                "snapshotPath": "artifact-view/tree/frozen.txt",
                "originalSha256": bootstrap.file_hash(source),
            }]}) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        contract = bootstrap.repository_read_contract(self.repo, run_dir / "attempts" / "a1", ["frozen.txt"])
        self.assertEqual(contract["readMode"], "sandbox-global-read-only")
        self.assertEqual(contract["readContractVersion"], "v10")
        self.assertEqual(contract["repositoryReadRoot"], str(self.repo.resolve()))
        self.assertTrue(contract["attemptWriteRoot"].endswith("attempts\\a1"))
        self.assertEqual(
            bootstrap.exact_evidence_from_frozen_view(run_dir, manifest, "frozen.txt", 2, 3),
            "two\nthree",
        )
        self.assertEqual(
            bootstrap.repeated_failure_fingerprint_status(["fp", "fp"], "fp"),
            "stop-after-threshold",
        )

        source_view = json.loads(
            (run_dir / "artifact-view" / "manifest.json").read_text(encoding="utf-8")
        )
        escaped_entry = dict(source_view["entries"][0])
        escaped_entry["originalPath"] = str(source.resolve())
        escaped_entry["snapshotPath"] = str(snapshot.resolve())
        escaped_view = {
            "schemaVersion": "artifact-view.v1",
            "authorityRevision": source_view.get("authorityRevision"),
            "entries": [escaped_entry],
        }
        escaped_view["creationHash"] = bootstrap.value_hash(
            {"authorityRevision": escaped_view.get("authorityRevision"), "entries": escaped_view["entries"]}
        )
        (run_dir / "artifact-view" / "manifest.json").write_text(
            json.dumps(escaped_view) + "\n", encoding="utf-8", newline="\n"
        )
        with self.assertRaises(bootstrap.ControlPlaneError):
            bootstrap.validate_artifact_view(run_dir, self.repo, escaped_view)



    def test_broh_s6_concurrent_discovery_wave(self) -> None:
        manifest = {
            "findingMode": "discovery",
            "requiredLayers": list(bootstrap.LAYERS),
            "fullReviewRound": 1,
        }
        wave = bootstrap.discovery_wave_plan(manifest)
        self.assertEqual(list(bootstrap.LAYERS), wave["reviewerRoles"])
        self.assertTrue(wave["concurrent"])
        self.assertTrue(wave["isolated"])
        self.assertEqual("failed-role-only", wave["transportRetryPolicy"])
        self.assertFalse(wave["transportFailureConsumesSemanticRound"])
        self.assertEqual("v6", wave["waveVersion"])
        self.assertEqual([], wave["authorizes"])

        retry = bootstrap.discovery_wave_retry_plan(
            manifest,
            successful_roles=["blind_hunter", "edge_case_hunter"],
            failed_roles=["acceptance_auditor"],
        )
        self.assertEqual(["acceptance_auditor"], retry["retryRoles"])
        self.assertEqual(["blind_hunter", "edge_case_hunter"], retry["preservedRoles"])
        self.assertEqual(1, retry["semanticRound"])
        self.assertEqual(0, retry["semanticRoundsAdded"])
        self.assertFalse(retry["newLineage"])
        self.assertEqual([], retry["authorizes"])

    def test_round_one_acceptance_candidate_freezes_git_baseline_deletion(self) -> None:
        deleted = self.scope / "removed-schema.json"
        raw = b'{"type":"object"}\n'
        deleted.write_bytes(raw)
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)
        subprocess.run(
            ["git", "commit", "-qm", "add deleted fixture"],
            cwd=self.repo,
            check=True,
        )
        baseline = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.repo, check=True,
            capture_output=True, text=True, encoding="utf-8",
        ).stdout.strip()
        deleted.unlink()
        prepared = self.repo / "acceptance-prepared.json"
        prepared.write_text(
            json.dumps({"candidateCustody": {"baselineResolvedCommit": baseline}}),
            encoding="utf-8",
            newline="\n",
        )
        relative = deleted.relative_to(self.repo).as_posix()
        identity = {
            "schemaVersion": "acceptance-bootstrap-reuse-candidate.v2",
            "acceptanceRunInputPath": prepared.relative_to(self.repo).as_posix(),
            "acceptanceRunInputFileHash": bootstrap.file_hash(prepared),
            "candidateContentManifestPath": "candidate.json",
            "candidateContentManifestFileHash": "sha256:" + "1" * 64,
            "candidateContentManifestHash": "sha256:" + "2" * 64,
            "candidateCustodyHash": "sha256:" + "3" * 64,
            "changedPaths": [relative],
            "changedPathBindings": [{
                "path": relative,
                "state": "deleted",
                "sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
            }],
            "knowledgeArtifacts": [{
                "path": ".agents/skills/run-phase-bootstrap-review/references/authority-roots.v1.json",
                "sha256": bootstrap.file_hash(
                    self.repo / ".agents/skills/run-phase-bootstrap-review/references/authority-roots.v1.json"
                ),
            }],
            "authorizes": [],
        }
        identity["identityHash"] = bootstrap.value_hash(identity)
        with mock.patch.object(
            bootstrap, "load_acceptance_candidate_identity", return_value=identity
        ):
            self.prepare(
                profile="bootstrap-implementation-conformance",
                acceptance_run_input=prepared,
                extra_scopes=[deleted, prepared],
            )
            manifest = self.read_json("review-input.json")
            freeze = manifest["acceptanceCandidateFreeze"]
            self.assertEqual([relative], [item["artifact"] for item in freeze["deletedArtifacts"]])
            self.assertIn(relative, manifest["contextClassArtifacts"]["changed-production-code"])
            view = self.read_json("artifact-view/manifest.json")
            entry = next(item for item in view["entries"] if item["originalPath"] == relative)
            self.assertEqual("deleted", entry["sourceState"])
            self.assertEqual(raw, (self.run_dir / entry["snapshotPath"]).read_bytes())
            self.assertEqual("immutable-git-baseline", entry["sourceAuthority"]["kind"])
            bootstrap.load_run(str(self.run_dir))

        deleted.write_bytes(raw)
        with mock.patch.object(
            bootstrap, "load_acceptance_candidate_identity", return_value=identity
        ), self.assertRaisesRegex(bootstrap.BootstrapError, "reappeared"):
            bootstrap.prepare_acceptance_candidate_freeze(
                self.repo, prepared.relative_to(self.repo).as_posix()
            )

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
        args.extend(["--directory-scope-attestation", bootstrap.DIRECTORY_SCOPE_ATTESTATION])
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
            self.complete_access_proof(
                manifest, bootstrap.primary_access_proof_role(manifest)
            )
        args = ["authorize-launch", "--run-dir", str(self.run_dir)]
        if acknowledge_high_cost:
            args.append("--ack-high-cost")
        self.assertEqual(0, bootstrap.main(args))

    def complete_access_proof(
        self, manifest: dict, proof_role: str = "discovery",
        reviewer_role: str | None = None,
    ) -> None:
        if proof_role == "discovery" and reviewer_role is None:
            for roles, _path, _route in bootstrap.discovery_access_route_groups(
                self.run_dir, manifest
            ):
                self.complete_access_proof(
                    manifest, proof_role, reviewer_role=roles[0]
                )
            return
        suffix = (
            "verifier"
            if proof_role == "independent_verifier"
            else (reviewer_role or "discovery")
        )
        attempt_dir = self.run_dir / "attempts" / f"test-{suffix}-access-probe"
        attempt_dir.mkdir(parents=True, exist_ok=True)
        handshake_path = attempt_dir / "access-handshake.json"
        handshake = bootstrap.access_handshake_payload(self.run_dir, manifest, "model_probe")
        self.write_json(f"attempts/test-{suffix}-access-probe/access-handshake.json", handshake)
        proof_path, route, gate_hash = bootstrap.access_proof_route(
            self.run_dir, manifest, proof_role, reviewer_role=reviewer_role
        )
        _child_environment, environment_evidence = bootstrap.child_environment()
        proof = {
            "schemaVersion": "bootstrap-access-proof.v2",
            "proofRole": proof_role,
            "reviewId": manifest["reviewId"],
            "inputHash": manifest["inputHash"],
            "artifactViewManifestHash": manifest["artifactView"]["manifestHash"],
            "model": route["model"],
            "reasoningEffort": route["reasoningEffort"],
            "gateStateHash": gate_hash,
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
        self.write_json(proof_path.relative_to(self.run_dir).as_posix(), proof)

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

    def complete_codex_gate_with_blocker(
        self, *, complete_verifier_access: bool = True, verifier_risk_class: str = "standard"
    ) -> tuple[dict, dict]:
        self.prepare(execution_mode="codex-exec")
        self.complete_preflight()
        self.authorize_launch()
        for layer in bootstrap.LAYERS:
            output = self.read_json(f"reviewer-outputs/{layer}.json")
            output["status"] = "completed"
            output["coverage"]["readArtifacts"] = output["coverage"]["requiredArtifacts"]
            output["coverage"]["missingArtifacts"] = []
            candidate = self.candidate()
            candidate["verifierRiskClass"] = verifier_risk_class
            output["candidates"] = [candidate] if layer == "blind_hunter" else []
            self.write_json(f"reviewer-outputs/{layer}.json", output)
            self.complete_process_lease(f"reviewer:{layer}", layer)
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        manifest = self.read_json("review-input.json")
        if complete_verifier_access:
            self.complete_access_proof(manifest, "independent_verifier")
        return manifest, self.read_json("review-candidates.json")["findings"][0]

    def verifier_attempt_candidate(
        self, manifest: dict, attempt_id: str, decisions: list[dict]
    ) -> tuple[dict, Path]:
        attempt_dir = self.run_dir / "attempts" / attempt_id
        attempt_dir.mkdir(parents=True, exist_ok=False)
        handshake = bootstrap.access_handshake_payload(
            self.run_dir, manifest, "independent_verifier"
        )
        self.write_json(f"attempts/{attempt_id}/access-handshake.json", handshake)
        identity = bootstrap.process_creation_identity(os.getpid())
        self.assertIsNotNone(identity)
        self.write_json(
            f"attempts/{attempt_id}/process-result.json",
            {
                "schemaVersion": "bootstrap-process-result.v1",
                "attemptId": attempt_id,
                "pid": os.getpid(),
                "exitCode": 0,
                "completedAt": bootstrap.utc_now(),
            },
        )
        write_set = [(self.run_dir / "verifier-output.json").relative_to(self.repo).as_posix()]
        bootstrap.append_process_event(
            self.run_dir,
            {
                "eventType": "attempt-started",
                "timestamp": bootstrap.utc_now(),
                "attemptId": attempt_id,
                "operationId": "verifier",
                "role": "independent_verifier",
                "pid": os.getpid(),
                "processIdentity": identity,
                "writeSet": write_set,
            },
        )
        return (
            {
                "schemaVersion": "bootstrap-layer-candidate.v1",
                "attemptId": attempt_id,
                "role": "independent_verifier",
                "inputHash": manifest["inputHash"],
                "accessHandshakeHash": handshake["handshakeHash"],
                "payload": {"decisions": decisions},
            },
            attempt_dir,
        )

    def reviewer_attempt_candidate(
        self,
        manifest: dict,
        attempt_id: str,
        role: str,
        payload: dict,
    ) -> tuple[dict, Path]:
        attempt_dir = self.run_dir / "attempts" / attempt_id
        attempt_dir.mkdir(parents=True, exist_ok=False)
        handshake = bootstrap.access_handshake_payload(self.run_dir, manifest, role)
        self.write_json(f"attempts/{attempt_id}/access-handshake.json", handshake)
        identity = bootstrap.process_creation_identity(os.getpid())
        self.assertIsNotNone(identity)
        self.write_json(
            f"attempts/{attempt_id}/process-result.json",
            {
                "schemaVersion": "bootstrap-process-result.v1",
                "attemptId": attempt_id,
                "pid": os.getpid(),
                "exitCode": 0,
                "completedAt": bootstrap.utc_now(),
            },
        )
        write_set = [
            (self.run_dir / "reviewer-outputs" / f"{role}.json")
            .relative_to(self.repo)
            .as_posix()
        ]
        bootstrap.append_process_event(
            self.run_dir,
            {
                "eventType": "attempt-started",
                "timestamp": bootstrap.utc_now(),
                "attemptId": attempt_id,
                "operationId": f"reviewer:{role}",
                "role": role,
                "pid": os.getpid(),
                "processIdentity": identity,
                "writeSet": write_set,
            },
        )
        return (
            {
                "schemaVersion": "bootstrap-layer-candidate.v1",
                "attemptId": attempt_id,
                "role": role,
                "inputHash": manifest["inputHash"],
                "accessHandshakeHash": handshake["handshakeHash"],
                "payload": payload,
            },
            attempt_dir,
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
            "maintenanceRiskClass": "runtime_product_risk",
            "verifierRiskClass": "standard",
            "proposedSeverity": severity,
            "severityRationale": "The reachable workflow executes the wrong required work",
            "confidence": 0.95,
            "dimension": "plan",
            "authorityOwner": "upstream plan",
            "consumer": "implementation operator",
            "validatorRef": "manual phase exit",
        }

    def authority_root_ref(self) -> dict[str, str]:
        profile = bootstrap.load_profile("bootstrap-upstream-plan")
        return bootstrap.authority_root_reference(profile)

    def test_repair_binding_excludes_current_authority_only_closure(self) -> None:
        artifacts = [
            {"artifact": "plan.md", "sha256": "sha256:" + "1" * 64},
            {
                "artifact": "repair/bootstrap-repair-closure.v1.json",
                "sha256": "sha256:" + "2" * 64,
            },
        ]
        bound = bootstrap.repair_binding_hashes(
            artifacts,
            {"plan-source": ["plan.md"]},
            [],
            "repair/bootstrap-repair-closure.v1.json",
        )
        self.assertEqual(bound["candidateHash"], bootstrap.value_hash([artifacts[0]]))
        self.assertNotEqual(bound["candidateHash"], bootstrap.value_hash(artifacts))

    def test_repair_closure_requires_proof_for_fixed_items(self) -> None:
        closure = {
            "schemaVersion": "bootstrap-repair-closure.v1",
            "predecessorRun": "run",
            "predecessorInputHash": "sha256:" + "a" * 64,
            "predecessorResultHash": "sha256:" + "b" * 64,
            "findingIds": ["F-1"],
            "items": [{
                "findingId": "F-1", "disposition": "fixed", "risk": "normal",
                "proofFamily": "regression", "reason": "fixed",
                "fixRefs": [], "validationCommands": [], "evidence": [],
            }],
            "currentBindings": {"candidateHash": "sha256:" + "c" * 64, "sourceHash": "sha256:" + "d" * 64, "validatorHash": "sha256:" + "e" * 64},
            "gitIndexHash": "sha256:" + "f" * 64,
            "writeSetHash": "sha256:" + "1" * 64,
            "executionReadSetHash": "sha256:" + "2" * 64,
            "dependencyClosureHash": "sha256:" + "3" * 64,
        }
        errors = bootstrap.schema_validation_errors("bootstrap-repair-closure.v1.schema.json", closure)
        self.assertTrue(any("minItems" in error for error in errors))

    def test_repair_closure_rejects_null_evidence_path_without_type_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            predecessor = root / "predecessor"
            predecessor.mkdir()
            gate = predecessor / "review-gate-result.json"
            gate.write_text("{}\n", encoding="utf-8")
            (predecessor / "review-dispositions.json").write_text(
                json.dumps({"dispositions": [{"findingId": "F-1"}]}), encoding="utf-8"
            )
            closure_path = root / "repair-closure.json"
            closure = {
                "schemaVersion": "bootstrap-repair-closure.v1",
                "predecessorRun": "predecessor",
                "predecessorInputHash": "sha256:" + "a" * 64,
                "predecessorResultHash": bootstrap.file_hash(gate),
                "findingIds": ["F-1"],
                "items": [{
                    "findingId": "F-1", "disposition": "fixed", "risk": "normal",
                    "proofFamily": "regression", "reason": "fixed", "fixRefs": ["x"],
                    "validationCommands": ["x"], "evidence": [{"path": None, "sha256": "sha256:" + "0" * 64}],
                }],
                "currentBindings": {"candidateHash": "sha256:" + "c" * 64, "sourceHash": "sha256:" + "d" * 64, "validatorHash": "sha256:" + "e" * 64},
                "gitIndexHash": "sha256:" + "f" * 64,
                "writeSetHash": "sha256:" + "1" * 64,
                "executionReadSetHash": "sha256:" + "2" * 64,
                "dependencyClosureHash": "sha256:" + "3" * 64,
            }
            closure_path.write_text(json.dumps(closure), encoding="utf-8")
            predecessor_manifest = {"inputHash": closure["predecessorInputHash"]}
            with mock.patch.object(bootstrap, "finalized_review_result", return_value={"findings": []}):
                with self.assertRaises(bootstrap.BootstrapError) as raised:
                    bootstrap.validate_repair_closure(
                        closure_path, root, predecessor, predecessor_manifest,
                        closure["currentBindings"], closure["gitIndexHash"],
                        ["write"], ["read"], ["dependency"],
                    )
            self.assertIn("repair evidence path is invalid", str(raised.exception))

    def write_p2_registry(self, manifest: dict) -> tuple[Path, dict[str, str]]:
        exclusions = ["implementation-acceptance", "protected-handoff", "release", "commit", "done"]
        registry = {
            "schemaVersion": "bootstrap-p2-command-registry.v1",
            "registryId": "registry-001",
            "rootId": "p2-command-root.v1",
            "authorityRootRef": self.authority_root_ref(),
            "signerId": "bootstrap-operator",
            "consumer": "bootstrap-p2-disposition",
            "runnerIdentity": "bootstrap-p2-runner.v1",
            "reviewId": manifest["reviewId"],
            "inputHash": manifest["inputHash"],
            "candidateHash": manifest["authorityContextHash"],
            "policyRevision": manifest["policyRevision"],
            "authorityRevision": manifest["authorityRevision"],
            "commands": [
                {
                    "commandId": "recheck-command",
                    "commandClass": "p2-recheck",
                    "executable": "py",
                    "argv": ["-3", "-c", "print('recheck passed')"],
                    "cwd": ".",
                },
                {
                    "commandId": "closure-command",
                    "commandClass": "p2-closure",
                    "executable": "py",
                    "argv": ["-3", "-c", "print('closure passed')"],
                    "cwd": ".",
                },
            ],
            "authorizes": [],
            "doesNotAuthorize": exclusions,
        }
        path = self.repo / "command-registry.json"
        path.write_text(json.dumps(registry), encoding="utf-8", newline="\n")
        return path, {
            "path": path.relative_to(self.repo).as_posix(),
            "sha256": bootstrap.file_hash(path),
        }

    def run_p2_command(self, finding_id: str, command_id: str) -> dict[str, str]:
        before = set((self.run_dir / "p2-process-events").glob("*/process-result.json")) if (self.run_dir / "p2-process-events").is_dir() else set()
        self.assertEqual(0, bootstrap.main([
            "run-p2-command",
            "--run-dir", str(self.run_dir),
            "--registry", "command-registry.json",
            "--finding-id", finding_id,
            "--command-id", command_id,
        ]))
        after = set((self.run_dir / "p2-process-events").glob("*/process-result.json"))
        created = after - before
        self.assertEqual(1, len(created))
        path = created.pop()
        return {
            "path": path.relative_to(self.repo).as_posix(),
            "sha256": bootstrap.file_hash(path),
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
        self.assertEqual(bootstrap.MAINTENANCE_MODE, manifest["maintenanceMode"])
        self.assertEqual("discovery", manifest["findingMode"])
        self.assertEqual(bootstrap.FINDING_MODE_POLICY, manifest["findingModePolicy"])
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
            self.assertIn("this repository is AI-native and has one", prompt)
            self.assertIn("human maintainer", prompt)
            self.assertIn("P0 to P1, P1 to non-blocking P2, and P2 to ignored", prompt)
            self.assertIn("Preferred Codex exec model: `gpt-5.6-terra`", prompt)
            self.assertIn("Fallback models: `gpt-5.5, gpt-5.4`", prompt)
            self.assertIn("Forbidden models: ``", prompt)
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

    def test_parent_cli_applies_single_maintainer_severity_policy(self) -> None:
        self.prepare()
        manifest = self.read_json("review-input.json")
        runtime = self.candidate("BOOT-RUNTIME-001", "P0")
        runtime["maintenanceRiskClass"] = "runtime_product_risk"
        self.assertEqual(
            "P0",
            bootstrap.finding_from_candidate(runtime, "blind_hunter", manifest)[
                "proposedSeverity"
            ],
        )
        concurrency = self.candidate("BOOT-CONCURRENCY-001", "P0")
        concurrency["maintenanceRiskClass"] = "multi_maintainer_concurrency"
        shifted = bootstrap.finding_from_candidate(
            concurrency, "blind_hunter", manifest
        )
        self.assertEqual("P1", shifted["proposedSeverity"])
        self.assertEqual("P0", shifted["reportedSeverity"])
        injected = self.candidate("BOOT-INJECTION-001", "P1")
        injected["maintenanceRiskClass"] = "external_requirement_injection"
        self.assertEqual(
            "P2",
            bootstrap.finding_from_candidate(injected, "blind_hunter", manifest)[
                "proposedSeverity"
            ],
        )
        ignored = self.candidate("BOOT-CONCURRENCY-002", "P2")
        ignored["maintenanceRiskClass"] = "multi_maintainer_concurrency"
        self.assertEqual(
            "ignored",
            bootstrap.finding_from_candidate(ignored, "blind_hunter", manifest)[
                "proposedSeverity"
            ],
        )

    def test_new_candidate_requires_maintenance_risk_class(self) -> None:
        self.prepare()
        manifest = self.read_json("review-input.json")
        candidate = self.candidate()
        del candidate["maintenanceRiskClass"]
        code, reason = bootstrap.candidate_reason(
            candidate, manifest, self.repo, self.run_dir
        )
        self.assertEqual("schema_invalid", code)
        self.assertIn("fields", reason)

    def test_new_candidate_requires_structured_verifier_risk_class(self) -> None:
        self.prepare()
        manifest = self.read_json("review-input.json")
        candidate = self.candidate()
        del candidate["verifierRiskClass"]
        code, reason = bootstrap.candidate_reason(
            candidate, manifest, self.repo, self.run_dir
        )
        self.assertEqual("schema_invalid", code)
        self.assertIn("fields", reason)

    def test_manifest_requires_lineage_contract_for_current_runs(self) -> None:
        self.prepare()
        manifest = self.read_json("review-input.json")
        for field in ("lineageFamilyId", "candidateBindingHash", "repairReviewDelta", "reviewEntryDecision"):
            manifest.pop(field, None)
        with self.assertRaisesRegex(bootstrap.BootstrapError, "lineage-family contract"):
            bootstrap.validate_manifest_controls(manifest, bootstrap.load_profile("bootstrap-upstream-plan"))

    def test_manifest_requires_finding_mode_contract_for_current_runs(self) -> None:
        self.prepare()
        manifest = self.read_json("review-input.json")
        for field in ("maintenanceMode", "findingMode", "findingModePolicy"):
            manifest.pop(field, None)
        with self.assertRaisesRegex(bootstrap.BootstrapError, "finding-mode policy"):
            bootstrap.validate_manifest_controls(manifest, bootstrap.load_profile("bootstrap-upstream-plan"))

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
            self.assertEqual(bootstrap.ACCESS_PROBE_POLICY, profile["accessProbePolicy"])
            self.assertEqual("gpt-5.6-terra", profile["verifierPolicy"]["preferredModel"])
            self.assertEqual("gpt-5.6-sol", profile["verifierPolicy"]["escalatedModel"])
            self.assertEqual("max", profile["verifierPolicy"]["escalatedReasoningEffort"])
            self.assertNotIn("gpt-5.6-sol", profile["codexExecPolicy"]["forbiddenModels"])
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
            "high",
            profiles["bootstrap-skill-route"]["codexExecPolicy"]
            ["reasoningEffortByRole"]["blind_hunter"],
        )
        self.assertEqual(
            "gpt-5.6-terra",
            profiles["bootstrap-skill-route"]["codexExecPolicy"]["preferredModel"],
        )

    def test_model_and_effort_routes_follow_round_role_and_gate_risk(self) -> None:
        implementation = bootstrap.load_profile("bootstrap-implementation-conformance")
        ordinary = bootstrap.discovery_execution_route(
            {**implementation, "fullReviewRound": 1}, "blind_hunter"
        )
        self.assertEqual(("gpt-5.6-terra", "high"), (
            ordinary["model"], ordinary["reasoningEffort"]
        ))

        skill = bootstrap.load_profile("bootstrap-skill-route")
        for review_round in (1, 2):
            for role in bootstrap.LAYERS:
                route = bootstrap.discovery_execution_route(
                    {**skill, "fullReviewRound": review_round}, role
                )
                self.assertEqual(("gpt-5.6-terra", "high"), (
                    route["model"], route["reasoningEffort"]
                ))

        for profile_name in (
            "bootstrap-upstream-plan", "bootstrap-implementation-conformance",
            "bootstrap-skill-route", "bootstrap-focused-change",
        ):
            profile = bootstrap.load_profile(profile_name)
            for role in bootstrap.LAYERS:
                route = bootstrap.discovery_execution_route(
                    {**profile, "fullReviewRound": 3}, role
                )
                self.assertEqual(("gpt-5.6-sol", "high"), (
                    route["model"], route["reasoningEffort"]
                ))

        p1_route = bootstrap.verifier_execution_route(
            implementation, [{"proposedSeverity": "P1", "dimension": "code"}]
        )
        p0_route = bootstrap.verifier_execution_route(
            implementation, [{"proposedSeverity": "P0", "dimension": "code"}]
        )
        security_route = bootstrap.verifier_execution_route(
            implementation, [{"proposedSeverity": "P1", "dimension": "security"}]
        )
        high_risk_p1_route = bootstrap.verifier_execution_route(
            implementation,
            [{
                "proposedSeverity": "P1",
                "dimension": "code",
                "verifierRiskClass": "shared_entrypoint",
            }],
        )
        self.assertEqual(("gpt-5.6-terra", "high"), (
            p1_route["model"], p1_route["reasoningEffort"]
        ))
        self.assertEqual(("gpt-5.6-sol", "high"), (
            high_risk_p1_route["model"], high_risk_p1_route["reasoningEffort"]
        ))
        self.assertEqual(("gpt-5.6-sol", "max"), (
            p0_route["model"], p0_route["reasoningEffort"]
        ))
        self.assertEqual(("gpt-5.6-sol", "max"), (
            security_route["model"], security_route["reasoningEffort"]
        ))

    def test_discovery_access_proofs_cover_each_distinct_role_route(self) -> None:
        self.prepare(execution_mode="codex-exec")
        manifest = self.read_json("review-input.json")
        groups = bootstrap.discovery_access_route_groups(self.run_dir, manifest)
        self.assertEqual(2, len(groups))
        self.assertEqual(["blind_hunter"], groups[0][0])
        self.assertEqual("medium", groups[0][2]["reasoningEffort"])
        self.assertEqual(["edge_case_hunter", "acceptance_auditor"], groups[1][0])
        self.assertEqual("high", groups[1][2]["reasoningEffort"])

        self.complete_access_proof(manifest)
        aggregate_hash = bootstrap.validate_access_proof(
            self.run_dir, manifest, "discovery"
        )
        self.assertRegex(aggregate_hash or "", r"^sha256:[0-9a-f]{64}$")
        self.complete_preflight()
        self.authorize_launch()
        self.assertEqual(
            aggregate_hash,
            self.read_json("review-launch-authorization.json")["accessProofHash"],
        )
        for role in bootstrap.LAYERS:
            path, route, _gate_hash = bootstrap.access_proof_route(
                self.run_dir, manifest, "discovery", reviewer_role=role
            )
            proof = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(route["reasoningEffort"], proof["reasoningEffort"])

    def test_focused_route_uses_frozen_predecessor_policy_and_complete_candidates(self) -> None:
        predecessor = self.repo / "focused-route-predecessor"
        predecessor.mkdir()
        current = bootstrap.load_profile("bootstrap-focused-repair-verification")
        current.update({
            "repositoryRoot": str(self.repo),
            "predecessorRun": predecessor.relative_to(self.repo).as_posix(),
        })
        legacy_manifest = {
            "codexExecPolicy": {
                "preferredModel": "gpt-5.6-sol",
                "fallbackModels": [],
                "reasoningEffortByRole": {"independent_verifier": "high"},
            }
        }
        (predecessor / "review-input.json").write_text(
            json.dumps(legacy_manifest), encoding="utf-8", newline="\n"
        )
        (predecessor / "review-candidates.json").write_text(
            json.dumps({"findings": [{"proposedSeverity": "P1", "dimension": "code"}]}),
            encoding="utf-8", newline="\n",
        )
        with mock.patch.object(bootstrap, "finalized_review_result", return_value={}):
            legacy_route = bootstrap.focused_repair_execution_route(current)
        self.assertEqual(("gpt-5.6-sol", "high"), (
            legacy_route["model"], legacy_route["reasoningEffort"]
        ))

        current_predecessor = bootstrap.load_profile("bootstrap-implementation-conformance")
        (predecessor / "review-input.json").write_text(
            json.dumps(current_predecessor), encoding="utf-8", newline="\n"
        )
        (predecessor / "review-candidates.json").write_text(
            json.dumps({"findings": [
                {
                    "findingId": "VISIBLE-P1", "proposedSeverity": "P1",
                    "dimension": "code", "verifierRiskClass": "standard",
                },
                {
                    "findingId": "HIDDEN-P0", "proposedSeverity": "P0",
                    "dimension": "security", "verifierRiskClass": "protected_path",
                },
            ]}),
            encoding="utf-8", newline="\n",
        )
        with mock.patch.object(bootstrap, "finalized_review_result", return_value={
            "findings": [{"findingId": "VISIBLE-P1", "proposedSeverity": "P1"}]
        }):
            complete_route = bootstrap.focused_repair_execution_route(current)
        self.assertEqual(("gpt-5.6-sol", "max"), (
            complete_route["model"], complete_route["reasoningEffort"]
        ))

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
                        "--lineage-family-id", f"profile-change-{index:03d}",
                        "--review-round", "1",
                        "--profile", profile_name,
                        *profile_args,
                        *(
                            ["--directory-scope-attestation", bootstrap.DIRECTORY_SCOPE_ATTESTATION]
                            if profile_name in bootstrap.BOUNDED_SCOPE_PROFILES
                            and profile_name != "bootstrap-skill-route"
                            else []
                        ),
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
                    "codexExecPolicy", "verifierPolicy", "accessProbePolicy",
                    "completenessPolicy", "reviewerInstructionPolicy",
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
                expected_strategy = (
                    "profile-complete-directory"
                    if profile_name == "bootstrap-upstream-plan"
                    else "attested-minimal-complete-closure"
                )
                self.assertEqual(expected_strategy, manifest["reviewScopePolicy"]["strategy"])
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

    def test_bounded_profile_rejects_directory_scope_without_attestation(self) -> None:
        profile = bootstrap.load_profile("bootstrap-implementation-conformance")
        context_args = [
            item
            for context_class in profile["requiredContextClasses"]
            for item in ("--context-class", f"{context_class}={self.scope}")
        ]
        result = bootstrap.main([
            "prepare",
            "--repository-root", str(self.repo),
            "--review-id", "unbounded-implementation-scope",
            "--change-id", "unbounded-implementation-change",
            "--review-round", "1",
            "--profile", "bootstrap-implementation-conformance",
            "--scope", str(self.scope),
            *context_args,
            "--required-check", f"implementation-proof={self.scope}",
            "--execution-mode", "manual",
            "--semantic-review-exclusivity", "no-other-semantic-review-in-cycle",
            "--out-dir", str(self.run_dir),
        ])
        self.assertEqual(1, result)
        self.assertFalse((self.run_dir / "review-input.json").exists())

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

    def test_skill_route_freezes_direct_runtime_dependency_inventory(self) -> None:
        dependencies = bootstrap.bootstrap_skill_route_runtime_dependencies(
            bootstrap.REPOSITORY_ROOT, [bootstrap.BOOTSTRAP_ROUTE_PATH]
        )
        self.assertEqual(
            list(bootstrap.BOOTSTRAP_ROUTE_RUNTIME_DEPENDENCIES), dependencies
        )
        self.assertIn(
            ".agents/skills/run-phase-bootstrap-review/references/historical-policy-revisions.v1.json",
            dependencies,
        )
        mapping = {
            "skill-source": [".agents/skills/run-phase-bootstrap-review/SKILL.md"],
            "operator-guide": ["execution-plans/2026-07-12-llm-review-evidence-gate-hardening/09-bootstrap-review-operator-guide.md"],
            "route-or-cli": [bootstrap.BOOTSTRAP_ROUTE_PATH],
            "profiles-and-config": [".agents/skills/run-phase-bootstrap-review/references/review-profiles.v1.json"],
            "schemas": [".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-reviewer-output.v1.schema.json"],
            "tests": [".agents/skills/run-phase-bootstrap-review/tests/test_bootstrap_review.py"],
            "usage-evidence": ["logs/ci/model-probes/skill-route-review-model-selection-20260713.json"],
            "repository-rules": ["AGENTS.md"],
        }
        artifacts = [{"artifact": bootstrap.BOOTSTRAP_ROUTE_PATH}]
        with self.assertRaisesRegex(bootstrap.BootstrapError, "outside the prepared Artifact View"):
            bootstrap.validate_bootstrap_skill_route_dependency_inventory(
                bootstrap.REPOSITORY_ROOT, "bootstrap-skill-route", artifacts, mapping
            )
        augmented = bootstrap.augment_bootstrap_skill_route_dependency_context(
            "bootstrap-skill-route", mapping, dependencies
        )
        self.assertIn(dependencies[0], augmented["route-or-cli"])
        profile_dependencies = {
            ".agents/skills/run-phase-bootstrap-review/references/authority-roots.v1.json",
            ".agents/skills/run-phase-bootstrap-review/references/review-cost-calibration.v1.json",
            ".agents/skills/run-phase-bootstrap-review/references/historical-policy-revisions.v1.json",
        }
        self.assertTrue(profile_dependencies.issubset(set(augmented["profiles-and-config"])))
        legacy_dependencies = [
            path for path in dependencies
            if path != ".agents/skills/run-phase-bootstrap-review/references/historical-policy-revisions.v1.json"
        ]
        legacy_artifacts = [{"artifact": bootstrap.BOOTSTRAP_ROUTE_PATH}] + [
            {"artifact": path} for path in legacy_dependencies
        ]
        legacy_mapping = {
            name: [
                path for path in paths
                if path != ".agents/skills/run-phase-bootstrap-review/references/historical-policy-revisions.v1.json"
            ]
            for name, paths in augmented.items()
        }
        with self.assertRaisesRegex(bootstrap.BootstrapError, "outside the prepared Artifact View"):
            bootstrap.validate_bootstrap_skill_route_dependency_inventory(
                bootstrap.REPOSITORY_ROOT, "bootstrap-skill-route", legacy_artifacts, legacy_mapping
            )
        bootstrap.validate_bootstrap_skill_route_dependency_inventory(
            bootstrap.REPOSITORY_ROOT,
            "bootstrap-skill-route",
            legacy_artifacts,
            legacy_mapping,
            allow_frozen_historical_policy_omission=True,
        )

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
            "schemas/bootstrap-repair-review-delta.v1.schema.json",
            "schemas/bootstrap-review-lineage-state.v1.schema.json",
            "schemas/bootstrap-review-round-entry-decision.v1.schema.json",
            "schemas/bootstrap-lineage-adoption.v1.schema.json",
            "schemas/bootstrap-finalized-run-validation.v1.schema.json",
            "schemas/bootstrap-finalized-run-validation.v2.schema.json",
            "schemas/bootstrap-finalized-run-validation.v3.schema.json",
            "schemas/bootstrap-historical-policy-revisions.v1.schema.json",
            "schemas/bootstrap-review-history-index.v1.schema.json",
            "schemas/bootstrap-review-cost-calibration.v1.schema.json",
            "schemas/bootstrap-review-calibration-corpus.v1.schema.json",
            "references/review-profiles.v1.json",
            "references/historical-policy-revisions.v1.json",
            "references/review-cost-calibration.v1.json",
        ):
            value = json.loads((plan_root / relative).read_text(encoding="utf-8"))
            self.assertIsInstance(value, dict)

    def test_finalized_legacy_schemas_remain_frozen_while_v3_owns_reuse_binding(self) -> None:
        plan_root = MODULE_PATH.parents[1]
        v1 = json.loads((plan_root / "schemas/bootstrap-finalized-run-validation.v1.schema.json").read_text(encoding="utf-8"))
        v2 = json.loads((plan_root / "schemas/bootstrap-finalized-run-validation.v2.schema.json").read_text(encoding="utf-8"))
        v3 = json.loads((plan_root / "schemas/bootstrap-finalized-run-validation.v3.schema.json").read_text(encoding="utf-8"))
        self.assertNotIn("lineageFamilyId", v1["required"])
        self.assertIn("lineageFamilyId", v2["required"])
        self.assertNotIn("candidateBindingHash", v2["required"])
        self.assertIn("candidateBindingHash", v3["required"])
        self.assertEqual("bootstrap-finalized-run-validator.v2", v1["properties"]["validatorRevision"]["const"])
        self.assertEqual("bootstrap-finalized-run-validator.v3", v2["properties"]["validatorRevision"]["const"])
        self.assertEqual("bootstrap-finalized-run-validator.v4", v3["properties"]["validatorRevision"]["const"])

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
        self.assertIn("Fallback models: ``", verifier_prompt)
        self.assertIn("Forbidden models: ``", verifier_prompt)
        self.assertIn("Reasoning effort: `high`", verifier_prompt)
        self.assertIn("`findingId`, `decision`, `reason`, and `evidenceChecked`", verifier_prompt)
        self.assertIn("do not use `rationale`", verifier_prompt)

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

    def test_runner_owned_preflight_rejects_shell_descriptors(self) -> None:
        with self.assertRaises(bootstrap.BootstrapError):
            bootstrap._preflight_descriptor(
                self.repo,
                self.scope,
                self.run_dir,
                {
                    "executable": "cmd",
                    "argv": ["/c", "echo unsafe"],
                    "cwd": {"type": "repo_path", "value": "."},
                    "timeout_seconds": 60,
                },
            )

    def test_runner_owned_preflight_accepts_registered_dotnet_build(self) -> None:
        argv, cwd, timeout = bootstrap._preflight_descriptor(
            self.repo,
            self.scope,
            self.run_dir,
            {
                "executable": "dotnet",
                "argv": ["test", "PhaseA.Platform.Tests.csproj"],
                "cwd": {"type": "repo_path", "value": "."},
                "timeout_seconds": 2400,
            },
        )
        self.assertEqual(
            ["dotnet", "test", "PhaseA.Platform.Tests.csproj"], argv
        )
        self.assertEqual(self.repo, cwd)
        self.assertEqual(2400, timeout)

    def test_runner_owned_preflight_rejects_excessive_timeout(self) -> None:
        with self.assertRaises(bootstrap.BootstrapError):
            bootstrap._preflight_descriptor(
                self.repo,
                self.scope,
                self.run_dir,
                {
                    "executable": "py",
                    "argv": ["-3", "check.py"],
                    "cwd": {"type": "repo_path", "value": "."},
                    "timeout_seconds": 3601,
                },
            )

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

    def test_gate_rejects_completed_coverage_out_of_manifest_order(self) -> None:
        self.prepare()
        self.complete_layers()
        output = self.read_json("reviewer-outputs/acceptance_auditor.json")
        output["coverage"]["readArtifacts"] = list(reversed(output["coverage"]["readArtifacts"]))
        self.write_json("reviewer-outputs/acceptance_auditor.json", output)
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        gate = self.read_json("review-gate-result.json")
        self.assertEqual("incomplete", gate["status"])
        self.assertEqual(["acceptance_auditor"], gate["failedLayers"])
        self.assertIn("prepared manifest order", gate["layerFailures"][0]["reason"])

    def test_gate_rejects_duplicate_completed_coverage(self) -> None:
        self.prepare()
        self.complete_layers()
        output = self.read_json("reviewer-outputs/acceptance_auditor.json")
        output["coverage"]["readArtifacts"].append(
            output["coverage"]["readArtifacts"][0]
        )
        self.write_json("reviewer-outputs/acceptance_auditor.json", output)
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        gate = self.read_json("review-gate-result.json")
        self.assertEqual("incomplete", gate["status"])
        self.assertEqual(["acceptance_auditor"], gate["failedLayers"])
        self.assertIn("duplicates", gate["layerFailures"][0]["reason"])

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

    def test_gate_deduplicates_risk_class_disagreement_and_retains_high_risk(self) -> None:
        self.prepare()
        standard = self.candidate("BOOT-CANDIDATE-STANDARD")
        high_risk = self.candidate("BOOT-CANDIDATE-HIGH-RISK")
        high_risk["verifierRiskClass"] = "protected_path"
        self.complete_layers({
            "blind_hunter": [standard], "edge_case_hunter": [high_risk]
        })
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        findings = self.read_json("review-candidates.json")["findings"]
        self.assertEqual(1, len(findings))
        self.assertEqual("protected_path", findings[0]["verifierRiskClass"])
        self.assertEqual(
            ["blind_hunter", "edge_case_hunter"], findings[0]["sourceReviewers"]
        )

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
        self.assertEqual("bootstrap-finalized-run-validation.v3", envelope["schemaVersion"])
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
        self.assertEqual(
            bootstrap.file_hash(self.run_dir / "verifier-output.json"),
            envelope["artifactHashes"]["verifierOutput"],
        )
        self.assertIsNone(envelope["artifactHashes"]["p2Dispositions"])
        self.assertEqual("bootstrap-finalized-run-validator.v4", envelope["validatorRevision"])
        self.assertEqual(manifest["candidateBindingHash"], envelope["candidateBindingHash"])
        legacy_v2 = dict(envelope)
        legacy_v2["schemaVersion"] = "bootstrap-finalized-run-validation.v2"
        legacy_v2["validatorRevision"] = "bootstrap-finalized-run-validator.v3"
        legacy_v2.pop("candidateBindingHash")
        self.assertEqual([], bootstrap.schema_validation_errors(
            "bootstrap-finalized-run-validation.v2.schema.json", legacy_v2
        ))
        replayed_legacy_v3 = dict(envelope)
        replayed_legacy_v3["candidateBindingHash"] = None
        self.assertEqual([], bootstrap.schema_validation_errors(
            "bootstrap-finalized-run-validation.v3.schema.json", replayed_legacy_v3
        ))

    def test_validate_finalized_run_replays_registered_historical_profile(self) -> None:
        self.prepare()
        self.complete_layers()
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        self.assertEqual(0, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        manifest = self.read_json("review-input.json")
        registries = self.repo / "historical-validation-registries"
        registries.mkdir()
        current_registry = json.loads(bootstrap.PROFILE_PATH.read_text(encoding="utf-8"))
        profile_name = manifest["profileName"]
        outgoing = copy.deepcopy(current_registry["profiles"][profile_name])
        replacement = copy.deepcopy(outgoing)
        replacement["reviewDepth"] += " Replacement policy."
        replacement["policyRevision"] = bootstrap.value_hash({
            key: value for key, value in replacement.items() if key != "policyRevision"
        })
        current_registry["profiles"][profile_name] = replacement
        current_path = registries / "review-profiles.v1.json"
        current_path.write_text(
            json.dumps(current_registry, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        history = {
            "schemaVersion": "bootstrap-historical-policy-revisions.v1",
            "revisions": [{
                "profileName": profile_name,
                "policyRevision": outgoing["policyRevision"],
                "replayScope": "baseline-and-successor",
                "authorityRootRegistry": outgoing["authorityRootRegistry"],
            }],
            "authorizes": [],
        }
        history_path = registries / "historical-policy-revisions.v1.json"
        history_path.write_text(
            json.dumps(history, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        output = self.repo / "historical-finalized-validation.json"

        with mock.patch.object(bootstrap, "PROFILE_PATH", current_path), mock.patch.object(
            bootstrap, "HISTORICAL_POLICY_PATH", history_path
        ):
            self.assertEqual(0, bootstrap.main([
                "validate-finalized-run", "--run-dir", str(self.run_dir),
                "--output", str(output),
            ]))
        self.assertEqual(
            outgoing["policyRevision"],
            json.loads(output.read_text(encoding="utf-8"))["policyRevision"],
        )

    def test_baseline_only_historical_replay_accepts_pre_artifact_view_controls(self) -> None:
        self.prepare()
        manifest = self.read_json("review-input.json")
        profile = bootstrap.load_profile(manifest["profileName"])
        for field in (
            "writeSet", "executionReadSet", "dependencyClosure", "gitIndexHash",
            "artifactView", "repairClosure", "controlPlaneRevision",
        ):
            manifest.pop(field, None)
        history = {
            "schemaVersion": "bootstrap-historical-policy-revisions.v1",
            "revisions": [{
                "profileName": manifest["profileName"],
                "policyRevision": manifest["policyRevision"],
                "replayScope": "baseline-only",
                "authorityRootRegistry": manifest["authorityRootRegistry"],
            }],
            "authorizes": [],
        }
        history_path = self.repo / "baseline-only-history.json"
        history_path.write_text(
            json.dumps(history, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        current_registry = json.loads(bootstrap.PROFILE_PATH.read_text(encoding="utf-8"))
        current_registry["profiles"][manifest["profileName"]]["policyRevision"] = (
            "sha256:" + "f" * 64
        )
        current_path = self.repo / "baseline-only-current-profiles.json"
        current_path.write_text(
            json.dumps(current_registry, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        with mock.patch.object(bootstrap, "PROFILE_PATH", current_path), mock.patch.object(
            bootstrap, "HISTORICAL_POLICY_PATH", history_path
        ):
            bootstrap.validate_manifest_controls(
                manifest, profile, historical_replay=True
            )

    def test_validate_finalized_run_rejects_stale_verifier_output(self) -> None:
        self.prepare()
        self.complete_layers()
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        self.assertEqual(0, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        (self.run_dir / "verifier-output.json").write_text("{}", encoding="utf-8", newline="\n")
        self.assertEqual(1, bootstrap.main([
            "validate-finalized-run", "--run-dir", str(self.run_dir),
            "--output", str(self.repo / "finalized-validation.json"),
        ]))

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

    def test_implementation_profile_gate_fails_closed_without_acceptance_companion(self) -> None:
        self.prepare(profile="bootstrap-implementation-conformance")
        self.complete_layers()
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        gate = self.read_json("review-gate-result.json")
        self.assertEqual("incomplete", gate["status"])
        self.assertEqual(["acceptance_auditor"], gate["failedLayers"])
        self.assertTrue(gate["layerFailures"][0]["reason"].startswith("companion_missing:"))

    def test_implementation_profile_gate_accepts_parent_owned_companion_bundle(self) -> None:
        self.prepare(profile="bootstrap-implementation-conformance")
        self.complete_layers()
        manifest = self.read_json("review-input.json")
        reviewer = self.read_json("reviewer-outputs/acceptance_auditor.json")
        reviewer["attemptId"] = "acceptance-auditor-parent-attempt"
        self.write_json("reviewer-outputs/acceptance_auditor.json", reviewer)
        attestation = {
            "schemaVersion": "bootstrap-acceptance-inventory-attestation.v1",
            "reviewId": manifest["reviewId"],
            "attemptId": "acceptance-auditor-parent-attempt",
            "inputHash": manifest["inputHash"],
            "capabilityId": "acceptance-inventory-attestation",
            "capabilityVersion": "1.0",
            "producerRole": "acceptance_auditor",
            "status": "complete",
            "scopeHash": bootstrap.acceptance_attestation_scope_hash(manifest),
            "coverage": [],
        }
        bundle = bootstrap.build_acceptance_auditor_role_bundle(
            reviewer, attestation, attestation["attemptId"], manifest
        )
        self.write_json("reviewer-outputs/acceptance_auditor.role-bundle.json", bundle)
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        self.assertEqual("clean", self.read_json("review-gate-result.json")["status"])

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

    def test_process_lease_lock_binds_pid_and_process_identity(self) -> None:
        self.prepare()
        lock_path = self.run_dir / ".process-leases.lock"
        with bootstrap.process_lease_lock(self.run_dir):
            owner = json.loads(lock_path.read_text(encoding="utf-8"))
            self.assertEqual(os.getpid(), owner["pid"])
            self.assertEqual(
                bootstrap.process_creation_identity(os.getpid()),
                owner["processIdentity"],
            )
        self.assertFalse(lock_path.exists())

    def test_process_lease_lock_retries_its_own_windows_cleanup(self) -> None:
        self.prepare()
        lock_path = self.run_dir / ".process-leases.lock"
        original_unlink = Path.unlink
        attempts = 0

        def flaky_unlink(path: Path, *args: object, **kwargs: object) -> None:
            nonlocal attempts
            if path == lock_path and attempts == 0:
                attempts += 1
                raise PermissionError("transient sharing violation")
            original_unlink(path, *args, **kwargs)

        with mock.patch.object(Path, "unlink", new=flaky_unlink):
            with bootstrap.process_lease_lock(self.run_dir):
                pass

        self.assertEqual(1, attempts)
        self.assertFalse(lock_path.exists())

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
        self.complete_access_proof(
            self.read_json("review-input.json"), "independent_verifier"
        )
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

    def test_launch_authorization_does_not_consume_round_one(self) -> None:
        self.prepare()
        self.complete_preflight()
        self.authorize_launch()
        self.run_dir = self.repo / "bootstrap-run-restarted"
        self.prepare(
            review_id="upstream-manual-restarted",
            change_id="upstream-change-001",
        )
        self.assertTrue((self.run_dir / "review-input.json").exists())

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

    def test_active_attempt_blocks_abandon_and_same_round_replacement(self) -> None:
        self.prepare(execution_mode="codex-exec")
        self.complete_preflight()
        self.authorize_launch()
        manifest = self.read_json("review-input.json")
        formal = (
            self.run_dir / "reviewer-outputs" / "blind_hunter.json"
        ).relative_to(self.repo).as_posix()
        bootstrap.append_process_event(
            self.run_dir,
            {
                "eventType": "attempt-started",
                "timestamp": bootstrap.utc_now(),
                "attemptId": "live-reviewer",
                "operationId": "reviewer:blind_hunter",
                "role": "blind_hunter",
                "pid": os.getpid(),
                "processIdentity": bootstrap.process_creation_identity(os.getpid()),
                "writeSet": [formal],
            },
        )

        self.assertEqual(
            1,
            bootstrap.main(
                [
                    "seal-run",
                    "--run-dir",
                    str(self.run_dir),
                    "--state",
                    "abandoned",
                    "--reason",
                    "operator-replaced-run",
                ]
            ),
        )
        self.assertFalse((self.run_dir / "run-seal.json").exists())

        self.run_dir = self.repo / "bootstrap-run-live-attempt-replacement"
        self.prepare(
            execution_mode="codex-exec",
            review_id="upstream-live-attempt-replacement",
            change_id=manifest["changeId"],
            expected_result=1,
        )
        self.assertFalse((self.run_dir / "review-input.json").exists())

    def test_inspect_run_routes_passed_codex_preflight_to_access_proof(self) -> None:
        self.prepare(execution_mode="codex-exec")
        self.complete_preflight()
        classification = bootstrap.classify_run(
            self.run_dir, self.read_json("review-input.json")
        )
        self.assertEqual("prove-access", classification["nextAction"])

    def test_verifier_requires_gate_derived_role_specific_access_proof(self) -> None:
        manifest, _finding = self.complete_codex_gate_with_blocker(
            complete_verifier_access=False
        )
        discovery_proof = self.read_json("access-proof.json")
        self.assertEqual("discovery", discovery_proof["proofRole"])
        self.assertEqual("gpt-5.6-terra", discovery_proof["model"])
        self.assertEqual(
            "prove-verifier-access",
            bootstrap.classify_run(self.run_dir, manifest)["nextAction"],
        )
        attempts_before = sorted(path.name for path in (self.run_dir / "attempts").iterdir())
        self.assertEqual(1, bootstrap.main([
            "run-layer", "--run-dir", str(self.run_dir),
            "--role", "independent_verifier",
            "--codex-command", "test-codex-command",
            "--model", "gpt-5.6-terra",
        ]))
        self.assertEqual(
            attempts_before,
            sorted(path.name for path in (self.run_dir / "attempts").iterdir()),
        )

        self.complete_access_proof(manifest, "independent_verifier")
        verifier_proof = self.read_json("verifier-access-proof.json")
        self.assertEqual("independent_verifier", verifier_proof["proofRole"])
        self.assertEqual("gpt-5.6-terra", verifier_proof["model"])
        self.assertEqual("high", verifier_proof["reasoningEffort"])
        self.assertEqual(
            bootstrap.file_hash(self.run_dir / "review-gate-state.json"),
            verifier_proof["gateStateHash"],
        )
        self.assertEqual(
            "run-independent-verifier",
            bootstrap.classify_run(self.run_dir, manifest)["nextAction"],
        )

    def test_high_risk_p1_verifier_access_proof_uses_sol_high(self) -> None:
        manifest, _finding = self.complete_codex_gate_with_blocker(
            complete_verifier_access=False,
            verifier_risk_class="protected_path",
        )
        self.complete_access_proof(manifest, "independent_verifier")
        verifier_proof = self.read_json("verifier-access-proof.json")
        self.assertEqual("gpt-5.6-sol", verifier_proof["model"])
        self.assertEqual("high", verifier_proof["reasoningEffort"])

    def test_verifier_access_probe_is_rejected_before_gate(self) -> None:
        self.prepare(execution_mode="codex-exec")
        self.complete_preflight()
        self.authorize_launch()
        attempts_before = sorted(path.name for path in (self.run_dir / "attempts").iterdir())
        self.assertEqual(1, bootstrap.main([
            "prove-access", "--run-dir", str(self.run_dir),
            "--codex-command", "missing-codex-command",
            "--role", "independent_verifier",
        ]))
        self.assertEqual(
            attempts_before,
            sorted(path.name for path in (self.run_dir / "attempts").iterdir()),
        )
        self.assertFalse((self.run_dir / "verifier-access-proof.json").exists())

    def test_finalize_fails_closed_when_verifier_access_proof_is_removed(self) -> None:
        _manifest, finding = self.complete_codex_gate_with_blocker()
        verifier = self.read_json("verifier-output.json")
        verifier["decisions"] = [{
            "findingId": finding["findingId"],
            "decision": "confirmed",
            "reason": "The exact frozen evidence confirms the reachable failure",
            "evidenceChecked": ["upstream-plan/plan.md:1", "upstream-plan/plan.md:3"],
        }]
        self.write_json("verifier-output.json", verifier)
        self.complete_process_lease("verifier", "independent_verifier")
        verifier_proof = self.read_json("verifier-access-proof.json")
        (self.run_dir / "verifier-access-proof.json").unlink()
        self.assertEqual(1, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        self.assertNotEqual(
            "review-result.v1",
            self.read_json("review-gate-result.json")["schemaVersion"],
        )
        self.write_json("verifier-access-proof.json", verifier_proof)
        self.assertEqual(0, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        finalized_manifest = self.read_json("review-input.json")
        envelope = bootstrap.validate_finalized_run_evidence(
            self.run_dir, finalized_manifest, self.repo
        )
        self.assertEqual("bootstrap-finalized-run-validation.v3", envelope["schemaVersion"])

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

    def test_clean_predecessor_does_not_trigger_round_two(self) -> None:
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
            expected_result=1,
        )
        self.assertFalse((self.run_dir / "review-input.json").exists())

    def test_p2_only_predecessor_does_not_trigger_full_review(self) -> None:
        self.prepare()
        self.complete_layers({"blind_hunter": [self.candidate(severity="P2")]})
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        findings = self.read_json("review-candidates.json")["findings"]
        finding_id = findings[0]["findingId"]
        manifest = self.read_json("review-input.json")
        _registry_path, registry_ref = self.write_p2_registry(manifest)
        process_ref = self.run_p2_command(finding_id, "closure-command")
        self.write_json("p2-dispositions.json", {
            "schemaVersion": "bootstrap-p2-dispositions.v1",
            "reviewId": manifest["reviewId"],
            "inputHash": manifest["inputHash"],
            "candidateHash": manifest["authorityContextHash"],
            "policyRevision": manifest["policyRevision"],
            "authorityRevision": manifest["authorityRevision"],
            "findingIds": [finding_id],
            "dispositions": [{
                "findingId": finding_id,
                "status": "fixed",
                "risk": "normal",
                "reason": "The registered targeted closure command passed",
                "closureCommandId": "closure-command",
                "closureCommandRegistryRef": registry_ref,
                "closureProcessResultRef": process_ref,
            }],
        })
        self.assertEqual(0, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        round_one = self.run_dir

        self.run_dir = self.repo / "bootstrap-run-p2-round-2"
        self.prepare(
            review_id="upstream-p2-manual-002",
            review_round=2,
            predecessor_run=round_one,
            expected_result=1,
        )
        self.assertFalse((self.run_dir / "review-input.json").exists())

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

    def test_lineage_family_prevents_successor_change_id_from_restarting_round_one(self) -> None:
        family_id = "stable-acceptance-target"
        self.prepare(lineage_family_id=family_id)
        self.complete_preflight()
        self.authorize_launch()
        self.assertEqual(0, bootstrap.main(["mark-semantic-start", "--run-dir", str(self.run_dir)]))
        first = self.run_dir

        state = bootstrap.build_lineage_state(self.repo, family_id)
        self.assertEqual(1, state["semanticRoundsConsumed"])
        self.assertEqual(2, state["nextFullReviewRound"])
        self.assertEqual(
            bootstrap.value_hash({key: value for key, value in state.items() if key != "lineageStateHash"}),
            state["lineageStateHash"],
        )

        self.run_dir = self.repo / "bootstrap-run-successor-reset"
        self.prepare(
            review_id="upstream-successor-reset",
            change_id="renamed-successor-change",
            lineage_family_id=family_id,
            expected_result=1,
        )
        self.assertTrue(first.is_dir())
        self.assertFalse((self.run_dir / "review-input.json").exists())

    def test_lineage_history_ignores_artifact_view_and_snapshot_copies(self) -> None:
        family_id = "stable-artifact-view-family"
        self.prepare(lineage_family_id=family_id)
        self.complete_preflight()
        self.authorize_launch()
        self.assertEqual(0, bootstrap.main(["mark-semantic-start", "--run-dir", str(self.run_dir)]))

        copied_run = (
            self.repo
            / "logs"
            / "ci"
            / "review-copy-holder"
            / "artifact-view"
            / "tree"
            / "logs"
            / "ci"
            / "copied-round-one"
        )
        shutil.copytree(self.run_dir, copied_run)
        snapshot_run = (
            self.repo
            / "execution-plans"
            / "example"
            / ".acceptance-snapshots"
            / "candidate"
            / "logs"
            / "ci"
            / "copied-round-one"
        )
        shutil.copytree(self.run_dir, snapshot_run)
        worktree_run = (
            self.repo
            / "logs"
            / "agent-worktrees"
            / "detached-copy"
            / "logs"
            / "ci"
            / "copied-round-one"
        )
        shutil.copytree(self.run_dir, worktree_run)

        state = bootstrap.build_lineage_state(self.repo, family_id)
        self.assertEqual(1, state["semanticRoundsConsumed"])
        self.assertEqual(
            [self.run_dir.relative_to(self.repo).as_posix()],
            [item["runDirectory"] for item in state["runs"]],
        )

    def test_round_three_requires_typed_novel_finding_entry_and_repair_delta(self) -> None:
        family_id = "bounded-repair-family"
        self.prepare(lineage_family_id=family_id)
        self.write_synthetic_blocked_result("BSR-FIRST")
        round_one = self.run_dir

        self.target.write_text("# Plan\n\nRound two repair.\n", encoding="utf-8", newline="\n")
        self.run_dir = self.repo / "bootstrap-run-round-2-success"
        self.prepare(
            review_id="upstream-round-two",
            lineage_family_id=family_id,
            review_round=2,
            predecessor_run=round_one,
        )
        self.assertEqual("repair_delta_closure", self.read_json("review-input.json")["repairReviewDelta"]["strategy"])
        self.write_synthetic_blocked_result("BSR-SECOND")
        round_two = self.run_dir

        self.target.write_text("# Plan\n\nRound three repair.\n", encoding="utf-8", newline="\n")
        self.run_dir = self.repo / "bootstrap-run-round-3-missing-entry"
        self.prepare(
            review_id="upstream-round-three-missing",
            lineage_family_id=family_id,
            review_round=3,
            predecessor_run=round_two,
            expected_result=1,
        )
        self.assertFalse((self.run_dir / "review-input.json").exists())

        self.run_dir = self.repo / "bootstrap-run-round-3-success"
        self.prepare(
            review_id="upstream-round-three",
            lineage_family_id=family_id,
            review_round=3,
            predecessor_run=round_two,
            round_entry_reason="novel_p0_p1",
        )
        decision = self.read_json("review-input.json")["reviewEntryDecision"]
        self.assertEqual("novel_p0_p1", decision["reason"])
        self.assertEqual(["BSR-SECOND"], decision["triggerFindingIds"])

    def test_repair_delta_support_contains_only_reachable_unchanged_artifacts(self) -> None:
        before = {
            "artifacts": [
                {"artifact": "scope/changed.md", "sha256": "sha256:" + "a" * 64},
                {"artifact": "scope/reachable.md", "sha256": "sha256:" + "b" * 64},
                {"artifact": "scope/unrelated.md", "sha256": "sha256:" + "c" * 64},
            ]
        }
        current = [
            {"artifact": "scope/changed.md", "sha256": "sha256:" + "d" * 64},
            {"artifact": "scope/reachable.md", "sha256": "sha256:" + "b" * 64},
            {"artifact": "scope/unrelated.md", "sha256": "sha256:" + "c" * 64},
        ]
        delta = bootstrap.build_repair_review_delta(
            self.repo,
            "logs/review-1",
            before,
            current,
            "sha256:" + "e" * 64,
            ["scope/changed.md", "scope/reachable.md"],
        )
        self.assertEqual(["scope/reachable.md"], delta["supportArtifacts"])

    def test_repair_delta_does_not_treat_omitted_unchanged_artifact_as_deleted(self) -> None:
        omitted = self.repo / "upstream-plan" / "omitted.md"
        omitted.write_text("unchanged\n", encoding="utf-8", newline="\n")
        digest = bootstrap.file_hash(omitted)
        delta = bootstrap.build_repair_review_delta(
            self.repo,
            "logs/review-1",
            {"artifacts": [
                {"artifact": "upstream-plan/plan.md", "sha256": "sha256:" + "a" * 64},
                {"artifact": "upstream-plan/omitted.md", "sha256": digest},
            ]},
            [{"artifact": "upstream-plan/plan.md", "sha256": "sha256:" + "b" * 64}],
            "sha256:" + "c" * 64,
            ["upstream-plan/plan.md"],
        )
        self.assertEqual([], delta["removedArtifacts"])

    def test_round_three_rejects_same_semantic_blocker_with_a_new_finding_id(self) -> None:
        family_id = "stable-novelty-family"
        self.prepare(lineage_family_id=family_id)
        self.write_synthetic_blocked_result("BSR-FIRST", semantic_key="same-defect")
        round_one = self.run_dir
        self.target.write_text("# Plan\n\nRound two repair.\n", encoding="utf-8", newline="\n")
        self.run_dir = self.repo / "bootstrap-stable-round-2"
        self.prepare(
            review_id="stable-round-two",
            lineage_family_id=family_id,
            review_round=2,
            predecessor_run=round_one,
        )
        self.write_synthetic_blocked_result("BSR-SECOND", semantic_key="same-defect")
        round_two = self.run_dir
        self.target.write_text("# Plan\n\nRound three repair.\n", encoding="utf-8", newline="\n")
        self.run_dir = self.repo / "bootstrap-stable-round-3"
        self.prepare(
            review_id="stable-round-three",
            lineage_family_id=family_id,
            review_round=3,
            predecessor_run=round_two,
            round_entry_reason="novel_p0_p1",
            expected_result=1,
        )

    def test_gate_only_predecessor_is_not_finalized(self) -> None:
        self.prepare(lineage_family_id="gate-only-family")
        manifest = self.read_json("review-input.json")
        self.write_json(
            "review-gate-result.json",
            {
                "schemaVersion": "review-result.v1",
                **bootstrap.bootstrap_sidecar_binding(manifest),
                "status": "awaiting_verification",
                "findings": [],
            },
        )
        with self.assertRaisesRegex(bootstrap.BootstrapError, "not finalized"):
            bootstrap.finalized_review_result(self.run_dir, manifest)

    def test_acceptance_repair_route_binds_replayed_completeness(self) -> None:
        completeness = {
            "schemaVersion": "acceptance-repair-completeness.v1",
            "status": "passed",
            "lineageFamilyId": "acceptance-family",
            "semanticRoundsConsumed": 1,
            "authorizes": [],
        }
        route = {
            "schemaVersion": "implementation-acceptance-bootstrap-route.v1",
            "routeKind": "focused_repair_review",
            "lineageFamilyId": "acceptance-family",
            "semanticRoundsConsumed": 1,
            "nextFullReviewRound": 2,
            "roundEntryReason": None,
            "repairCompletenessHash": bootstrap.value_hash(completeness),
            "maintenanceMode": bootstrap.MAINTENANCE_MODE,
            "findingMode": "discovery",
            "findingModeReentry": "user_confirmation_required",
            "findingSeverityPolicy": bootstrap.FINDING_MODE_POLICY["severityShift"],
            "authorizes": [],
        }
        route_path = self.repo / "route.json"
        completeness_path = self.repo / "completeness.json"
        route_path.write_text(json.dumps(route), encoding="utf-8", newline="\n")
        completeness_path.write_text(
            json.dumps(completeness), encoding="utf-8", newline="\n"
        )
        bindings = bootstrap.validate_acceptance_repair_route(
            route_path,
            completeness_path,
            self.repo,
            "acceptance-family",
            2,
            None,
        )
        self.assertEqual("route.json", bindings["acceptanceRepairRoute"]["path"])
        tampered = dict(completeness)
        tampered["semanticRoundsConsumed"] = 0
        completeness_path.write_text(json.dumps(tampered), encoding="utf-8", newline="\n")
        with self.assertRaisesRegex(bootstrap.BootstrapError, "matching Acceptance"):
            bootstrap.validate_acceptance_repair_route(
                route_path,
                completeness_path,
                self.repo,
                "acceptance-family",
                2,
                None,
            )

    def test_later_discovery_requires_confirmation_but_not_a_positive_recommendation(self) -> None:
        family_id = "finding-reentry-advisory-recommendation"
        self.prepare(lineage_family_id=family_id)
        predecessor = self.run_dir
        authorization_path = self.repo / "finding-reentry-advisory.json"
        common_args = [
            "authorize-finding-mode-reentry",
            "--repository-root", str(self.repo),
            "--lineage-family-id", family_id,
            "--next-review-round", "2",
            "--predecessor-run-dir", str(predecessor),
            "--round-entry-reason", "high_risk_boundary_changed",
            "--recommendation", "do_not_recommend",
            "--confidence", "0.91",
            "--rationale", "Expected discovery yield is lower than the projected cost",
            "--out", str(authorization_path),
        ]

        self.assertEqual(1, bootstrap.main(common_args))
        self.assertFalse(authorization_path.exists())
        self.assertEqual(0, bootstrap.main([*common_args, "--user-confirmed"]))
        authorization = json.loads(authorization_path.read_text(encoding="utf-8"))
        self.assertEqual("do_not_recommend", authorization["recommendation"])
        self.assertTrue(authorization["userConfirmed"])

    def test_implementation_conformance_repair_prepare_requires_acceptance_route(self) -> None:
        family_id = "acceptance-prepare-family"
        self.prepare(
            profile="bootstrap-implementation-conformance",
            lineage_family_id=family_id,
        )
        self.write_synthetic_blocked_result("BSR-ACCEPTANCE-FIRST")
        predecessor = self.run_dir
        self.target.write_text("# Plan\n\nRepair.\n", encoding="utf-8", newline="\n")
        target_relative = self.target.relative_to(self.repo).as_posix()
        completeness = {
            "schemaVersion": "acceptance-repair-completeness.v1",
            "status": "passed",
            "acceptanceTarget": "execution-plans/example",
            "lineageFamilyId": family_id,
            "semanticRoundsConsumed": 1,
            "predecessorRun": predecessor.relative_to(self.repo).as_posix(),
            "baselineManifest": {"path": target_relative, "sha256": bootstrap.file_hash(self.target)},
            "candidateManifest": {"path": target_relative, "sha256": bootstrap.file_hash(self.target)},
            "changedPaths": [target_relative],
            "changedPathBindings": [{
                "path": target_relative, "state": "present", "sha256": bootstrap.file_hash(self.target),
            }],
            "directConsumers": [{"path": target_relative, "sha256": bootstrap.file_hash(self.target)}],
            "targetedTests": [{"path": target_relative, "sha256": bootstrap.file_hash(self.target)}],
            "validationRefs": [{"path": target_relative, "sha256": bootstrap.file_hash(self.target)}],
            "rootCauseInventories": [{
                "inventoryId": "focused-plan-callsites",
                "searchTerm": "Repair",
                "searchRoots": ["."],
                "matches": [{
                    "path": target_relative, "sha256": bootstrap.file_hash(self.target), "lineNumbers": [3],
                }],
                "addressedPaths": [target_relative],
                "exclusions": [],
            }],
            "compositionChecks": [{
                "checkId": "focused-plan-composition",
                "bindings": [
                    {"role": "producer", "path": target_relative, "sha256": bootstrap.file_hash(self.target)},
                    {"role": "consumer", "path": target_relative, "sha256": bootstrap.file_hash(self.target)},
                ],
                "commandRegistry": {"path": target_relative, "sha256": bootstrap.file_hash(self.target)},
                "receipt": {"path": target_relative, "sha256": bootstrap.file_hash(self.target)},
            }],
            "novelP0P1FindingIds": [],
            "authorityGraphChanged": False,
            "authorityGraphArtifacts": [],
            "highRiskBoundaryChanged": True,
            "highRiskBoundaryArtifacts": [target_relative],
            "requestHash": "sha256:" + "a" * 64,
            "authorizes": [],
        }
        route = {
            "schemaVersion": "implementation-acceptance-bootstrap-route.v1",
            "routeKind": "full_implementation_conformance",
            "lineageFamilyId": family_id,
            "semanticRoundsConsumed": 1,
            "nextFullReviewRound": 2,
            "roundEntryReason": "high_risk_boundary_changed",
            "repairCompletenessHash": bootstrap.value_hash(completeness),
            "maintenanceMode": bootstrap.MAINTENANCE_MODE,
            "findingMode": "discovery",
            "findingModeReentry": "user_confirmation_required",
            "findingSeverityPolicy": bootstrap.FINDING_MODE_POLICY["severityShift"],
            "authorizes": [],
        }
        route_path = self.repo / "acceptance-route.json"
        completeness_path = self.repo / "acceptance-completeness.json"
        route_path.write_text(json.dumps(route), encoding="utf-8", newline="\n")
        completeness_path.write_text(
            json.dumps(completeness), encoding="utf-8", newline="\n"
        )
        authorization_path = self.repo / "finding-reentry-authorization.json"
        self.assertEqual(0, bootstrap.main([
            "authorize-finding-mode-reentry",
            "--repository-root", str(self.repo),
            "--lineage-family-id", family_id,
            "--next-review-round", "2",
            "--predecessor-run-dir", str(predecessor),
            "--acceptance-repair-route", str(route_path),
            "--round-entry-reason", "high_risk_boundary_changed",
            "--recommendation", "recommend",
            "--confidence", "0.87",
            "--rationale", "The typed boundary change justifies one additional discovery pass",
            "--user-confirmed",
            "--out", str(authorization_path),
        ]))
        self.run_dir = self.repo / "bootstrap-implementation-round-2-missing-route"
        self.prepare(
            profile="bootstrap-implementation-conformance",
            review_id="implementation-round-two-missing",
            lineage_family_id=family_id,
            review_round=2,
            predecessor_run=predecessor,
            expected_result=1,
        )
        self.run_dir = self.repo / "bootstrap-implementation-round-2-missing-auth"
        self.prepare(
            profile="bootstrap-implementation-conformance",
            review_id="implementation-round-two-missing-auth",
            lineage_family_id=family_id,
            review_round=2,
            predecessor_run=predecessor,
            acceptance_route=route_path,
            acceptance_completeness=completeness_path,
            round_entry_reason="high_risk_boundary_changed",
            high_risk_boundaries=[target_relative],
            expected_result=1,
        )
        self.run_dir = self.repo / "bootstrap-implementation-round-2"
        self.prepare(
            profile="bootstrap-implementation-conformance",
            review_id="implementation-round-two",
            lineage_family_id=family_id,
            review_round=2,
            predecessor_run=predecessor,
            acceptance_route=route_path,
            acceptance_completeness=completeness_path,
            round_entry_reason="high_risk_boundary_changed",
            high_risk_boundaries=[target_relative],
            finding_reentry_authorization=authorization_path,
        )
        manifest = self.read_json("review-input.json")
        self.assertEqual(
            "acceptance-route.json", manifest["acceptanceRepairRoute"]["path"]
        )

    def test_focused_repair_profile_projects_single_verifier_and_escalation(self) -> None:
        acceptance_schema = (
            self.repo
            / ".agents/skills/run-refactor-implementation-acceptance/schemas/acceptance-repair-completeness.v1.schema.json"
        )
        acceptance_schema.parent.mkdir(parents=True, exist_ok=True)
        acceptance_schema.write_bytes(
            (
                REPOSITORY_ROOT
                / ".agents/skills/run-refactor-implementation-acceptance/schemas/acceptance-repair-completeness.v1.schema.json"
            ).read_bytes()
        )
        family_id = "focused-repair-family"
        finding_id = "BSR-FOCUSED-FIRST"
        self.prepare(
            profile="bootstrap-implementation-conformance",
            lineage_family_id=family_id,
        )
        self.write_synthetic_blocked_result(finding_id)
        predecessor = self.run_dir
        self.target.write_text("# Plan\n\nRepair.\n", encoding="utf-8", newline="\n")
        target_relative = self.target.relative_to(self.repo).as_posix()
        completeness = {
            "schemaVersion": "acceptance-repair-completeness.v1",
            "status": "passed",
            "acceptanceTarget": "execution-plans/example",
            "lineageFamilyId": family_id,
            "semanticRoundsConsumed": 1,
            "predecessorRun": predecessor.relative_to(self.repo).as_posix(),
            "baselineManifest": {"path": "plan.md", "sha256": bootstrap.file_hash(self.target)},
            "candidateManifest": {"path": "plan.md", "sha256": bootstrap.file_hash(self.target)},
            "changedPaths": ["plan.md"],
            "changedPathBindings": [{
                "path": "plan.md", "state": "present", "sha256": bootstrap.file_hash(self.target),
            }],
            "directConsumers": [{"path": "plan.md", "sha256": bootstrap.file_hash(self.target)}],
            "targetedTests": [{"path": "plan.md", "sha256": bootstrap.file_hash(self.target)}],
            "validationRefs": [{"path": "plan.md", "sha256": bootstrap.file_hash(self.target)}],
            "rootCauseInventories": [{
                "inventoryId": "focused-plan-callsites",
                "searchTerm": "Repair",
                "searchRoots": ["."],
                "matches": [{
                    "path": "plan.md", "sha256": bootstrap.file_hash(self.target), "lineNumbers": [3],
                }],
                "addressedPaths": ["plan.md"],
                "exclusions": [],
            }],
            "compositionChecks": [{
                "checkId": "focused-plan-composition",
                "bindings": [
                    {"role": "producer", "path": "plan.md", "sha256": bootstrap.file_hash(self.target)},
                    {"role": "consumer", "path": "plan.md", "sha256": bootstrap.file_hash(self.target)},
                ],
                "targetedTests": ["plan.md"],
                "commandRegistry": {"path": "plan.md", "sha256": bootstrap.file_hash(self.target)},
                "receipt": {"path": "plan.md", "sha256": bootstrap.file_hash(self.target)},
                "controlledReplay": {
                    "schemaVersion": "acceptance-composition-controlled-replay.v1",
                    "authorizes": [],
                    "commandId": "focused-plan-composition",
                    "commandRegistryHash": "sha256:" + "1" * 64,
                    "environmentIdentity": {"names": [], "hash": "sha256:" + "2" * 64},
                    "invocation": {},
                    "invocationHash": "sha256:" + "3" * 64,
                    "exitCode": 0,
                    "writeManifestDelta": {},
                    "writeManifestDeltaHash": "sha256:" + "4" * 64,
                    "inputBindings": [],
                    "inputBindingsHash": "sha256:" + "5" * 64,
                },
            }],
            "novelP0P1FindingIds": [],
            "authorityGraphChanged": False,
            "authorityGraphArtifacts": [],
            "highRiskBoundaryChanged": False,
            "highRiskBoundaryArtifacts": [],
            "requestHash": "sha256:" + "a" * 64,
            "authorizes": [],
        }
        for field in ("baselineManifest", "candidateManifest"):
            completeness[field]["path"] = target_relative
        completeness["changedPaths"] = [target_relative]
        for field in ("changedPathBindings", "directConsumers", "targetedTests", "validationRefs"):
            completeness[field][0]["path"] = target_relative
        completeness["rootCauseInventories"][0]["matches"][0]["path"] = target_relative
        completeness["rootCauseInventories"][0]["addressedPaths"] = [target_relative]
        for binding in completeness["compositionChecks"][0]["bindings"]:
            binding["path"] = target_relative
        completeness["compositionChecks"][0]["commandRegistry"]["path"] = target_relative
        completeness["compositionChecks"][0]["receipt"]["path"] = target_relative
        repair_request = {"producer": "focused-test"}
        route = {
            "schemaVersion": "implementation-acceptance-bootstrap-route.v1",
            "routeKind": "focused_repair_verification",
            "lineageFamilyId": family_id,
            "semanticRoundsConsumed": 1,
            "nextFullReviewRound": 2,
            "roundEntryReason": None,
            "repairCompletenessHash": bootstrap.value_hash(completeness),
            "repairCompletenessRequest": repair_request,
            "repairCompletenessRequestHash": bootstrap.value_hash(repair_request),
            "maintenanceMode": bootstrap.MAINTENANCE_MODE,
            "findingMode": "verification_only",
            "findingModeReentry": "not_applicable",
            "findingSeverityPolicy": bootstrap.FINDING_MODE_POLICY["severityShift"],
            "authorizes": [],
        }
        route_path = self.repo / "focused-route.json"
        completeness_path = self.repo / "focused-completeness.json"
        route_path.write_text(json.dumps(route), encoding="utf-8", newline="\n")
        completeness_path.write_text(
            json.dumps(completeness), encoding="utf-8", newline="\n"
        )
        self.run_dir = self.repo / "bootstrap-focused-round-2"
        replay_patch = mock.patch.object(
            bootstrap,
            "replay_acceptance_repair_completeness",
            return_value=completeness,
        )
        replay_patch.start()
        self.addCleanup(replay_patch.stop)
        self.prepare(
            profile="bootstrap-focused-repair-verification",
            review_id="focused-round-two",
            lineage_family_id=family_id,
            review_round=2,
            predecessor_run=predecessor,
            acceptance_route=route_path,
            acceptance_completeness=completeness_path,
        )
        manifest = self.read_json("review-input.json")
        self.assertEqual([bootstrap.FOCUSED_REPAIR_ROLE], manifest["requiredLayers"])
        self.assertEqual("verification_only", manifest["findingMode"])
        _proof_path, focused_route, gate_hash = bootstrap.access_proof_route(
            self.run_dir, manifest, bootstrap.FOCUSED_REPAIR_ROLE
        )
        self.assertIsNone(gate_hash)
        self.assertEqual(("gpt-5.6-terra", "high"), (
            focused_route["model"], focused_route["reasoningEffort"]
        ))
        with self.assertRaisesRegex(
            bootstrap.BootstrapError, "Discovery access is forbidden"
        ):
            bootstrap.access_proof_route(self.run_dir, manifest, "discovery")
        focused_prompt = (
            self.run_dir
            / "reviewer-prompts"
            / f"{bootstrap.FOCUSED_REPAIR_ROLE}.md"
        ).read_text(encoding="utf-8")
        self.assertIn("already consumed its", focused_prompt)
        self.assertIn("finding round", focused_prompt)
        self.assertIn("return empty newBlockers", focused_prompt)
        output = bootstrap.focused_repair_output_template(manifest)
        output["status"] = "completed"
        output["coverage"] = bootstrap.completed_reviewer_coverage(manifest)
        output["decisions"] = [{
            "findingId": finding_id,
            "status": "verified_fixed",
            "evidenceChecked": [self.target.relative_to(self.repo).as_posix()],
        }]
        self.write_json(
            f"reviewer-outputs/{bootstrap.FOCUSED_REPAIR_ROLE}.json", output
        )
        escalated_output = copy.deepcopy(output)
        escalated_output["newBlockers"] = [{
            "findingId": "BSR-FOCUSED-NOVEL",
            "severity": "P1",
            "dimension": "code",
            "artifact": self.target.relative_to(self.repo).as_posix(),
            "startLine": 3,
            "endLine": 3,
            "exactEvidence": "Repair.",
        }]
        escalated_output["escalation"]["novelP0P1FindingIds"] = ["BSR-FOCUSED-NOVEL"]
        with self.assertRaisesRegex(
            bootstrap.BootstrapError, "cannot create findings or reopen discovery"
        ):
            bootstrap.project_focused_repair_gate(
                escalated_output, manifest, self.repo, self.run_dir
            )

        self.complete_preflight()
        self.authorize_launch()
        self.complete_process_lease(
            f"reviewer:{bootstrap.FOCUSED_REPAIR_ROLE}", bootstrap.FOCUSED_REPAIR_ROLE
        )
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        gate = self.read_json("review-gate-result.json")
        self.assertEqual("passed", gate["status"])
        self.assertEqual("deterministic-closure", gate["nextAction"])
        self.assertEqual(0, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        envelope = self.read_json("focused-repair-validation-envelope.json")
        self.assertEqual("passed", envelope["status"])
        self.assertEqual([], envelope["authorizes"])
        validation_path = self.repo / "focused-validation.json"
        self.assertEqual(0, bootstrap.main([
            "validate-finalized-run", "--run-dir", str(self.run_dir),
            "--output", str(validation_path),
        ]))
        self.assertEqual(envelope, json.loads(validation_path.read_text(encoding="utf-8")))
        self.assertEqual(1, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        classified = bootstrap.classify_run(self.run_dir, manifest)
        self.assertEqual("finalized", classified["runExecutionState"])
        self.assertEqual("accepted", classified["changeCycleState"])

    def test_hard_limit_focused_recovery_is_same_round_verification_only(self) -> None:
        family_id = "hard-limit-recovery-family"
        finding_id = "BSR-HARD-LIMIT-ONE"
        predecessor = self.repo / "blocked-round-three"
        predecessor.mkdir()
        target_relative = self.target.relative_to(self.repo).as_posix()
        skill_profile = bootstrap.load_profile("bootstrap-skill-route")
        predecessor_manifest = {
            "reviewId": "blocked-round-three-review",
            "changeId": "blocked-round-three-change",
            "lineageFamilyId": family_id,
            "fullReviewRound": 3,
            "profileName": "bootstrap-skill-route",
            "routeVersion": skill_profile["routeVersion"],
            "reviewProfile": skill_profile["reviewProfile"],
            "policyRevision": skill_profile["policyRevision"],
            "authorityRevision": bootstrap.git_revision(self.repo),
            "inputHash": "sha256:" + "1" * 64,
            "artifacts": [{"artifact": target_relative, "sha256": bootstrap.file_hash(self.target)}],
            "executionMode": "manual",
            "processLeasePolicy": {"sidecar": "process-leases.json"},
        }
        (predecessor / "review-input.json").write_text(
            json.dumps(predecessor_manifest), encoding="utf-8", newline="\n"
        )
        self.run_dir = predecessor
        self.write_synthetic_blocked_result(finding_id)
        envelope_path = predecessor / "finalized-run-validation.v3.json"
        envelope_path.write_text(
            json.dumps({
                "schemaVersion": "bootstrap-finalized-run-validation.v3",
                "validationStatus": "passed",
                "reviewId": predecessor_manifest["reviewId"],
                "inputHash": predecessor_manifest["inputHash"],
                "fullReviewRound": 3,
                "profileName": "bootstrap-skill-route",
                "finalStatus": "blocked",
                "findingClosure": {"unverifiedCount": 0},
                "authorizes": [],
            }),
            encoding="utf-8",
            newline="\n",
        )
        self.target.write_text("# Plan\n\nRepaired.\n", encoding="utf-8", newline="\n")
        repair_path = self.repo / "round-three-deterministic-repair.json"
        repair_path.write_text(
            json.dumps({
                "schemaVersion": "bootstrap-round3-deterministic-repair-closure.v1",
                "lineageFamilyId": family_id,
                "predecessorRun": predecessor.relative_to(self.repo).as_posix(),
                "predecessorEnvelope": {
                    "path": envelope_path.relative_to(self.repo).as_posix(),
                    "sha256": bootstrap.file_hash(envelope_path),
                    "finalStatus": "blocked",
                },
                "findingIds": [finding_id],
                "repairs": [{
                    "findingIds": [finding_id],
                    "result": "fixed",
                    "reason": "Current protocol bytes close the predecessor finding",
                    "evidence": [{"path": target_relative, "sha256": bootstrap.file_hash(self.target)}],
                }],
                "validation": [{"command": "targeted-test", "status": "passed"}],
                "authorizes": [],
                "doesNotAuthorize": ["acceptance-passed"],
            }),
            encoding="utf-8",
            newline="\n",
        )
        authorization_path = self.repo / "hard-limit-recovery.json"
        predecessor_manifest["fullReviewRound"] = 2
        (predecessor / "review-input.json").write_text(
            json.dumps(predecessor_manifest), encoding="utf-8", newline="\n"
        )
        self.assertEqual(1, bootstrap.main([
            "authorize-hard-limit-focused-recovery",
            "--repository-root", str(self.repo),
            "--lineage-family-id", family_id,
            "--predecessor-run-dir", str(predecessor),
            "--deterministic-repair-closure", str(repair_path),
            "--recommendation", "recommend", "--confidence", "0.92",
            "--rationale", "invalid round fixture", "--user-confirmed",
            "--out", str(authorization_path),
        ]))
        predecessor_manifest["fullReviewRound"] = 3
        (predecessor / "review-input.json").write_text(
            json.dumps(predecessor_manifest), encoding="utf-8", newline="\n"
        )
        result_path = predecessor / "review-gate-result.json"
        metrics_path = predecessor / "review-metrics.json"
        blocked_result = json.loads(result_path.read_text(encoding="utf-8"))
        blocked_metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        clean_result = {**blocked_result, "status": "clean"}
        clean_metrics = {**blocked_metrics, "status": "clean"}
        result_path.write_text(json.dumps(clean_result), encoding="utf-8", newline="\n")
        metrics_path.write_text(json.dumps(clean_metrics), encoding="utf-8", newline="\n")
        self.assertEqual(1, bootstrap.main([
            "authorize-hard-limit-focused-recovery",
            "--repository-root", str(self.repo),
            "--lineage-family-id", family_id,
            "--predecessor-run-dir", str(predecessor),
            "--deterministic-repair-closure", str(repair_path),
            "--recommendation", "recommend", "--confidence", "0.92",
            "--rationale", "clean predecessor fixture", "--user-confirmed",
            "--out", str(authorization_path),
        ]))
        result_path.write_text(json.dumps(blocked_result), encoding="utf-8", newline="\n")
        metrics_path.write_text(json.dumps(blocked_metrics), encoding="utf-8", newline="\n")
        self.assertEqual(1, bootstrap.main([
            "authorize-hard-limit-focused-recovery",
            "--repository-root", str(self.repo),
            "--lineage-family-id", "different-family",
            "--predecessor-run-dir", str(predecessor),
            "--deterministic-repair-closure", str(repair_path),
            "--recommendation", "recommend", "--confidence", "0.92",
            "--rationale", "different family fixture", "--user-confirmed",
            "--out", str(authorization_path),
        ]))
        self.assertEqual(0, bootstrap.main([
            "authorize-hard-limit-focused-recovery",
            "--repository-root", str(self.repo),
            "--lineage-family-id", family_id,
            "--predecessor-run-dir", str(predecessor),
            "--deterministic-repair-closure", str(repair_path),
            "--recommendation", "recommend",
            "--confidence", "0.92",
            "--rationale", "One exact verifier is cheaper than another discovery round",
            "--user-confirmed",
            "--out", str(authorization_path),
        ]))
        upstream_profile = bootstrap.load_profile("bootstrap-upstream-plan")
        predecessor_manifest["profileName"] = "bootstrap-upstream-plan"
        predecessor_manifest["routeVersion"] = upstream_profile["routeVersion"]
        predecessor_manifest["reviewProfile"] = upstream_profile["reviewProfile"]
        predecessor_manifest["policyRevision"] = upstream_profile["policyRevision"]
        (predecessor / "review-input.json").write_text(
            json.dumps(predecessor_manifest), encoding="utf-8", newline="\n"
        )
        for sidecar_name in ("review-gate-result.json", "review-dispositions.json", "review-metrics.json"):
            sidecar_path = predecessor / sidecar_name
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
            sidecar.update(bootstrap.bootstrap_sidecar_binding(predecessor_manifest))
            sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8", newline="\n")
        envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
        envelope["profileName"] = "bootstrap-upstream-plan"
        envelope_path.write_text(json.dumps(envelope), encoding="utf-8", newline="\n")
        repair_document = json.loads(repair_path.read_text(encoding="utf-8"))
        repair_document["predecessorEnvelope"]["sha256"] = bootstrap.file_hash(envelope_path)
        repair_path.write_text(json.dumps(repair_document), encoding="utf-8", newline="\n")
        upstream_authorization_path = self.repo / "hard-limit-upstream-plan-recovery.json"
        self.assertEqual(0, bootstrap.main([
            "authorize-hard-limit-focused-recovery",
            "--repository-root", str(self.repo),
            "--lineage-family-id", family_id,
            "--predecessor-run-dir", str(predecessor),
            "--deterministic-repair-closure", str(repair_path),
            "--recommendation", "recommend", "--confidence", "0.92",
            "--rationale", "Plan authority review uses the same verification-only recovery contract",
            "--user-confirmed",
            "--out", str(upstream_authorization_path),
        ]))
        authorization = json.loads(authorization_path.read_text(encoding="utf-8"))
        self.assertEqual([], authorization["authorizes"])
        self.run_dir = self.repo / "hard-limit-focused-run"
        self.prepare(
            profile="bootstrap-focused-repair-verification",
            review_id="hard-limit-focused-review",
            change_id="hard-limit-focused-change",
            lineage_family_id=family_id,
            review_round=3,
            predecessor_run=predecessor,
            hard_limit_recovery=upstream_authorization_path,
        )
        manifest = self.read_json("review-input.json")
        self.assertEqual("verification_only", manifest["findingMode"])
        self.assertFalse(bootstrap.run_consumes_semantic_round(self.run_dir, manifest))
        codex_manifest = copy.deepcopy(manifest)
        codex_manifest["executionMode"] = "codex-exec"
        with mock.patch.object(
            bootstrap, "load_run", return_value=(self.run_dir, codex_manifest, self.repo)
        ), mock.patch.object(
            bootstrap, "validate_preflight_result", return_value="sha256:" + "a" * 64
        ) as preflight_validation, mock.patch.object(
            bootstrap, "validate_launch_authorization"
        ) as launch_validation, mock.patch.object(
            bootstrap, "access_proof_route",
            side_effect=bootstrap.BootstrapError("stop-before-process"),
        ):
            self.assertEqual(1, bootstrap.main([
                "prove-access", "--run-dir", str(self.run_dir),
                "--codex-command", "codex", "--role", bootstrap.FOCUSED_REPAIR_ROLE,
                "--model", "gpt-5.6-sol", "--ack-high-cost",
            ]))
            preflight_validation.assert_called_once()
            launch_validation.assert_not_called()
        with self.assertRaisesRegex(bootstrap.BootstrapError, "Discovery access is forbidden"):
            bootstrap.access_proof_route(self.run_dir, manifest, "discovery")
        output = bootstrap.focused_repair_output_template(manifest)
        output["status"] = "completed"
        output["coverage"] = bootstrap.completed_reviewer_coverage(manifest)
        output["decisions"] = [{
            "findingId": finding_id,
            "status": "verified_fixed",
            "evidenceChecked": [target_relative],
        }]
        self.write_json(f"reviewer-outputs/{bootstrap.FOCUSED_REPAIR_ROLE}.json", output)
        invalid = copy.deepcopy(output)
        invalid["newBlockers"] = [{
            "findingId": "BSR-NEW",
            "severity": "P1",
            "dimension": "code",
            "artifact": target_relative,
            "startLine": 3,
            "endLine": 3,
            "exactEvidence": "Repaired.",
        }]
        invalid["escalation"]["novelP0P1FindingIds"] = ["BSR-NEW"]
        with self.assertRaisesRegex(bootstrap.BootstrapError, "cannot create findings"):
            bootstrap.validate_focused_repair_output(
                invalid, manifest, self.repo, self.run_dir
            )
        self.complete_preflight()
        self.authorize_launch()
        self.complete_process_lease(
            f"reviewer:{bootstrap.FOCUSED_REPAIR_ROLE}", bootstrap.FOCUSED_REPAIR_ROLE
        )
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        self.assertEqual(0, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        authority = self.read_json("hard-limit-protocol-repair-authority.json")
        self.assertEqual(["manual-pause-protocol-review"], authority["authorizes"])
        self.assertNotIn("acceptance-passed", authority["authorizes"])
        repair_path.write_text(repair_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        self.assertEqual(1, bootstrap.main([
            "validate-finalized-run",
            "--run-dir", str(self.run_dir),
            "--output", str(self.repo / "stale-hard-limit-validation.json"),
        ]))

    def test_focused_repair_profile_is_revision_pinned_from_base_profile(self) -> None:
        expected = bootstrap.load_profile("bootstrap-focused-repair-verification")
        registry = bootstrap.read_json(bootstrap.PROFILE_PATH)
        registry["profiles"]["bootstrap-implementation-conformance"]["reviewDepth"] = (
            "future-base-profile-depth"
        )
        mutated_registry = self.repo / "mutated-review-profiles.json"
        mutated_registry.write_text(
            json.dumps(registry, indent=2) + "\n", encoding="utf-8", newline="\n"
        )

        with mock.patch.object(bootstrap, "PROFILE_PATH", mutated_registry):
            actual = bootstrap.load_profile("bootstrap-focused-repair-verification")

        self.assertEqual(expected, actual)
        self.assertEqual(
            "sha256:12c7ee7e1c12ede2c59e31d7ae5b49f3d79c1a20497960566218fc3d9a39e900",
            actual["policyRevision"],
        )

    def test_p2_closure_v2_is_compact_fail_closed_and_high_risk_safe(self) -> None:
        self.run_dir.mkdir()
        evidence = self.repo / "targeted-result.json"
        manifest = {
            "reviewId": "p2-v2-review",
            "inputHash": "sha256:" + "1" * 64,
            "authorityContextHash": "sha256:" + "2" * 64,
            "policyRevision": "sha256:" + "3" * 64,
            "authorityRevision": "test-revision",
            "repositoryRoot": str(self.repo),
        }
        evidence_binding = {
            "reviewId": manifest["reviewId"],
            "inputHash": manifest["inputHash"],
            "candidateHash": manifest["authorityContextHash"],
            "authorityRevision": manifest["authorityRevision"],
        }
        evidence.write_text(
            json.dumps({
                "schemaVersion": "targeted-check.v1",
                **evidence_binding,
                "status": "passed",
            }),
            encoding="utf-8",
            newline="\n",
        )
        evidence_ref = {
            "path": evidence.relative_to(self.repo).as_posix(),
            "sha256": bootstrap.file_hash(evidence),
            "schemaVersion": "targeted-check.v1",
            **evidence_binding,
            "producedAt": "2026-08-01T00:00:00Z",
            "successField": "status",
            "successValue": "passed",
        }
        closure = {
            "schemaVersion": "bootstrap-p2-closure.v2",
            "reviewId": manifest["reviewId"],
            "inputHash": manifest["inputHash"],
            "candidateHash": manifest["authorityContextHash"],
            "policyRevision": manifest["policyRevision"],
            "authorityRevision": manifest["authorityRevision"],
            "findingIds": ["BSR-P2-V2"],
            "closures": [{
                "findingId": "BSR-P2-V2",
                "status": "fixed",
                "risk": "normal",
                "reason": "Targeted validation closes the advisory finding.",
                "evidence": [evidence_ref],
            }],
            "authorizes": [],
            "doesNotAuthorize": bootstrap.FINALIZED_DOES_NOT_AUTHORIZE,
        }
        self.write_json("p2-closure.v2.json", closure)
        findings = [{
            "findingId": "BSR-P2-V2",
            "proposedSeverity": "P2",
            "dimension": "code",
        }]
        mapped = bootstrap.validate_p2_dispositions(self.run_dir, manifest, findings)
        self.assertEqual("fixed", mapped["BSR-P2-V2"]["status"])

        closure["closures"][0].update({
            "status": "deferred",
            "risk": "high",
            "owner": "maintainer",
            "expiry": "2099-01-01T00:00:00Z",
            "recheckTrigger": "next protocol change",
            "nonImpactEvidence": [evidence_ref],
            "recheckEvidence": [evidence_ref],
        })
        findings[0]["dimension"] = "security"
        self.write_json("p2-closure.v2.json", closure)
        with self.assertRaisesRegex(bootstrap.BootstrapError, "high-risk P2 requires"):
            bootstrap.validate_p2_dispositions(self.run_dir, manifest, findings)

        findings[0]["dimension"] = "code"
        closure["closures"][0]["risk"] = "normal"
        closure["closures"][0]["status"] = "fixed"
        closure["closures"][0].pop("owner")
        closure["closures"][0].pop("expiry")
        closure["closures"][0].pop("recheckTrigger")
        closure["closures"][0].pop("nonImpactEvidence")
        closure["closures"][0].pop("recheckEvidence")
        closure["closures"][0]["evidence"][0]["sha256"] = "sha256:" + "0" * 64
        self.write_json("p2-closure.v2.json", closure)
        with self.assertRaisesRegex(bootstrap.BootstrapError, "missing or stale"):
            bootstrap.validate_p2_dispositions(self.run_dir, manifest, findings)

    def test_review_registry_reconciles_repository_history_and_revalidates_bytes(self) -> None:
        self.prepare()
        discovered = self.repo / "imported-review"
        shutil.copytree(self.run_dir, discovered)
        subprocess.run(["git", "add", "imported-review"], cwd=self.repo, check=True)
        subprocess.run(
            ["git", "commit", "-qm", "import review history"], cwd=self.repo, check=True
        )
        rows = bootstrap.review_run_manifests(self.repo)
        self.assertEqual(
            {self.run_dir.resolve(), discovered.resolve()},
            {path for path, _manifest in rows},
        )
        manifest_path = self.run_dir / "review-input.json"
        manifest_path.write_text(
            manifest_path.read_text(encoding="utf-8") + "\n",
            encoding="utf-8",
            newline="\n",
        )
        with self.assertRaisesRegex(bootstrap.BootstrapError, "missing or stale"):
            bootstrap.review_run_manifests(self.repo)

    def test_explicit_adoption_bridges_only_selected_legacy_history(self) -> None:
        legacy_dir = self.repo / "legacy-review"
        legacy_dir.mkdir()
        manifest = {
            "schemaVersion": "bootstrap-review-input.v1",
            "reviewId": "legacy-review-001",
            "changeId": "legacy-change-001",
            "fullReviewRound": 1,
            "inputHash": "sha256:" + "a" * 64,
            "executionMode": "manual",
            "processLeasePolicy": {"sidecar": "process-leases.json"},
        }
        (legacy_dir / "review-input.json").write_text(
            json.dumps(manifest), encoding="utf-8", newline="\n"
        )
        (legacy_dir / "process-events.jsonl").write_text(
            json.dumps({
                "schemaVersion": "bootstrap-process-event.v1",
                "eventType": bootstrap.SEMANTIC_ROUND_STARTED_EVENT,
                "reviewId": manifest["reviewId"],
                "inputHash": manifest["inputHash"],
            }) + "\n",
            encoding="utf-8", newline="\n",
        )
        policy = self.repo / "docs" / "adr" / "ADR-test.md"
        policy.parent.mkdir(parents=True)
        policy.write_text("# Test policy\n\nStatus: Accepted\n", encoding="utf-8", newline="\n")
        registry = bootstrap._review_registry_path(self.repo)
        if registry.exists():
            registry.unlink()
        output = self.repo / "decision-logs" / "legacy.lineage-adoption.v1.json"
        self.assertEqual(0, bootstrap.main([
            "adopt-lineage",
            "--repository-root", str(self.repo),
            "--lineage-family-id", "ria-current-family",
            "--legacy-change-id", "legacy-change-001",
            "--historical-run-dir", "legacy-review",
            "--policy-authority", "docs/adr/ADR-test.md",
            "--reason", "Explicitly preserve the approved legacy round budget",
            "--out", str(output),
        ]))
        state = bootstrap.build_lineage_state(self.repo, "ria-current-family")
        self.assertEqual(1, state["semanticRoundsConsumed"])
        self.assertEqual(["legacy-review"], [item["runDirectory"] for item in state["runs"]])

    def test_round_three_high_risk_boundary_accepts_a_removed_artifact(self) -> None:
        family_id = "removed-boundary-family"
        boundary = self.scope / "security-boundary.txt"
        boundary.write_text("protected\n", encoding="utf-8", newline="\n")
        self.prepare(lineage_family_id=family_id)
        self.write_synthetic_blocked_result("BSR-FIRST-BOUNDARY")
        round_one = self.run_dir

        self.target.write_text("# Plan\n\nRound two repair.\n", encoding="utf-8", newline="\n")
        self.run_dir = self.repo / "bootstrap-boundary-round-2"
        self.prepare(
            review_id="boundary-round-two",
            lineage_family_id=family_id,
            review_round=2,
            predecessor_run=round_one,
        )
        self.write_synthetic_blocked_result("BSR-SECOND-BOUNDARY")
        round_two = self.run_dir

        boundary.unlink()
        self.target.write_text("# Plan\n\nRound three boundary repair.\n", encoding="utf-8", newline="\n")
        self.run_dir = self.repo / "bootstrap-boundary-round-3"
        boundary_relative = boundary.relative_to(self.repo).as_posix()
        self.prepare(
            review_id="boundary-round-three",
            lineage_family_id=family_id,
            review_round=3,
            predecessor_run=round_two,
            round_entry_reason="high_risk_boundary_changed",
            high_risk_boundaries=[boundary_relative],
        )
        manifest = self.read_json("review-input.json")
        self.assertIn(boundary_relative, manifest["repairReviewDelta"]["removedArtifacts"])
        self.assertEqual(
            [boundary_relative],
            manifest["reviewEntryDecision"]["highRiskBoundaryArtifacts"],
        )
        prompt = bootstrap.prompt_text("blind_hunter", manifest, self.run_dir)
        self.assertIn(f"Removed artifact tombstones: `{boundary_relative}`", prompt)
        removed = manifest["repairReviewDelta"]["removedArtifactSnapshots"][0]
        self.assertIn(
            boundary_relative,
            manifest["artifactView"]["requiredArtifacts"],
        )
        self.assertIn(
            boundary_relative,
            bootstrap.completed_reviewer_coverage(manifest)["requiredArtifacts"],
        )
        self.assertIn(boundary_relative, bootstrap.reviewer_template("blind_hunter", manifest)["coverage"]["requiredArtifacts"])
        deleted_candidate = self.candidate("DELETED-BOUNDARY-001")
        deleted_candidate.update(
            {
                "artifact": boundary_relative,
                "artifactHash": removed["sha256"],
                "startLine": 1,
                "endLine": 1,
                "exactEvidence": "protected",
                "contextRead": [f"{boundary_relative}:1"],
            }
        )
        self.assertEqual(
            (None, ""),
            bootstrap.candidate_reason(
                deleted_candidate, manifest, self.repo, self.run_dir
            ),
        )
        snapshot = self.run_dir / removed["snapshotPath"]
        snapshot.write_text("tampered\n", encoding="utf-8", newline="\n")
        with self.assertRaisesRegex(bootstrap.BootstrapError, "Artifact View"):
            bootstrap.load_run(str(self.run_dir))


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
        self.assertIn("Do not return coverage arrays", prompt)
        self.assertIn("artifactViewReadReceipt", prompt)
        self.assertIn("the parent owns formal coverage", prompt)
        self.assertIn("Do not edit formal output files", prompt)
        self.assertNotIn("fill\n`reviewer-outputs/blind_hunter.json`", prompt)

    def test_codex_runner_prompt_maps_mandatory_skill_authority_to_snapshots(self) -> None:
        authority_scopes = []
        for relative in bootstrap.DELEGATED_BOOTSTRAP_AUTHORITY_PATHS:
            target = self.repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f"authority for {relative}\n", encoding="utf-8", newline="\n")
            authority_scopes.append(target)
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "add delegated authority"], cwd=self.repo, check=True)
        self.prepare(execution_mode="codex-exec", extra_scopes=authority_scopes)
        manifest = self.read_json("review-input.json")
        attempt_dir = self.run_dir / "attempts" / "delegated-authority-prompt"
        attempt_dir.mkdir(parents=True)
        helper_path, request_path, output_path = bootstrap.materialize_access_handshake_helper(
            self.run_dir, manifest, "blind_hunter", attempt_dir
        )

        prompt = bootstrap.runner_prompt(
            self.run_dir, manifest, "blind_hunter", "delegated-authority-prompt",
            helper_path, request_path, output_path,
        )

        self.assertIn("# Frozen Delegated Bootstrap Authority", prompt)
        view = json.loads(
            (self.run_dir / manifest["artifactView"]["manifestPath"]).read_text(encoding="utf-8")
        )
        entries = {item["originalPath"]: item for item in view["entries"]}
        for relative in bootstrap.DELEGATED_BOOTSTRAP_AUTHORITY_PATHS:
            self.assertIn(f'"originalPath": "{relative}"', prompt)
            snapshot = bootstrap.ensure_within(
                self.run_dir / entries[relative]["snapshotPath"],
                self.run_dir / "artifact-view",
                "Test delegated authority snapshot",
            )
            self.assertIn(json.dumps(str(snapshot)), prompt)
        self.assertIn("do not fail merely because a live `.agents` path is inaccessible", prompt)

    def test_codex_runner_prompt_fails_before_launch_when_skill_authority_is_incomplete(self) -> None:
        skill = self.repo / bootstrap.DELEGATED_BOOTSTRAP_AUTHORITY_PATHS[0]
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text("# Bootstrap Skill\n", encoding="utf-8", newline="\n")
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "add incomplete authority"], cwd=self.repo, check=True)
        self.prepare(execution_mode="codex-exec", extra_scopes=[skill])
        manifest = self.read_json("review-input.json")
        attempt_dir = self.run_dir / "attempts" / "incomplete-authority-prompt"
        attempt_dir.mkdir(parents=True)
        helper_path, request_path, output_path = bootstrap.materialize_access_handshake_helper(
            self.run_dir, manifest, "blind_hunter", attempt_dir
        )

        with self.assertRaisesRegex(bootstrap.BootstrapError, "missing mandatory delegated"):
            bootstrap.runner_prompt(
                self.run_dir, manifest, "blind_hunter", "incomplete-authority-prompt",
                helper_path, request_path, output_path,
            )

    def test_acceptance_auditor_prompt_contains_exact_inventory_attestation_contract(self) -> None:
        self.prepare(
            execution_mode="codex-exec",
            profile="bootstrap-implementation-conformance",
        )
        manifest = self.read_json("review-input.json")
        attempt_dir = self.run_dir / "attempts" / "acceptance-prompt-contract"
        attempt_dir.mkdir(parents=True)
        helper_path, request_path, output_path = bootstrap.materialize_access_handshake_helper(
            self.run_dir, manifest, "acceptance_auditor", attempt_dir
        )

        prompt = bootstrap.runner_prompt(
            self.run_dir,
            manifest,
            "acceptance_auditor",
            "acceptance-prompt-contract",
            helper_path,
            request_path,
            output_path,
        )

        expected = {
            "schemaVersion": "bootstrap-acceptance-inventory-attestation.v1",
            "reviewId": manifest["reviewId"],
            "attemptId": "acceptance-prompt-contract",
            "inputHash": manifest["inputHash"],
            "capabilityId": "acceptance-inventory-attestation",
            "capabilityVersion": "1.0",
            "producerRole": "acceptance_auditor",
            "status": "complete",
            "scopeHash": bootstrap.acceptance_attestation_scope_hash(manifest),
            "coverage": [],
        }
        self.assertIn(
            json.dumps(expected, ensure_ascii=False, separators=(",", ":")), prompt
        )
        self.assertIn("distinct from artifactViewReadReceipt", prompt)
        self.assertIn("do not copy artifactViewManifestHash", prompt)

    def test_verifier_prompt_lists_full_finding_range_and_context_requirements(self) -> None:
        self.prepare(execution_mode="codex-exec")
        manifest = self.read_json("review-input.json")
        blocker = {
            "findingId": "BSR-FULLRANGE001",
            "artifact": "upstream-plan/plan.md",
            "startLine": 1,
            "endLine": 3,
            "contextRead": [
                "upstream-plan/plan.md:1-2",
                "upstream-plan/zz-unrelated.md",
            ],
        }

        prompt = bootstrap.verifier_prompt(self.run_dir, manifest, [blocker])

        self.assertIn("Required finding evidence: `upstream-plan/plan.md:1-3`", prompt)
        self.assertIn("one `evidenceChecked` reference must cover the entire inclusive", prompt)
        self.assertIn("`upstream-plan/plan.md:1-2`", prompt)
        self.assertIn("`upstream-plan/zz-unrelated.md`", prompt)
        self.assertIn(
            'Required `evidenceChecked` minimum closure: copy this JSON array verbatim',
            prompt,
        )
        self.assertIn(
            '["upstream-plan/plan.md:1-3", "upstream-plan/plan.md:1-2", '
            '"upstream-plan/zz-unrelated.md"]',
            prompt,
        )

    def test_codex_verifier_runtime_expands_frozen_requirements_for_legacy_prompt(self) -> None:
        self.prepare(execution_mode="codex-exec")
        manifest = self.read_json("review-input.json")
        attempt_dir = self.run_dir / "attempts" / "verifier-prompt-contract"
        attempt_dir.mkdir(parents=True)
        helper_path, request_path, output_path = bootstrap.materialize_access_handshake_helper(
            self.run_dir, manifest, "independent_verifier", attempt_dir
        )
        (self.run_dir / "verification-prompt.md").write_text(
            "# Legacy verifier prompt\n\n- BSR-FULLRANGE001: upstream-plan/plan.md:1\n",
            encoding="utf-8",
            newline="\n",
        )
        blocker = {
            "findingId": "BSR-FULLRANGE001",
            "artifact": "upstream-plan/plan.md",
            "startLine": 1,
            "endLine": 3,
            "contextRead": [
                "upstream-plan/plan.md:1-2",
                "upstream-plan/zz-unrelated.md",
            ],
        }

        with mock.patch.object(
            bootstrap,
            "load_gate_blockers",
            return_value={blocker["findingId"]: blocker},
        ):
            prompt = bootstrap.runner_prompt(
                self.run_dir,
                manifest,
                "independent_verifier",
                "verifier-prompt-contract",
                helper_path,
                request_path,
                output_path,
            )

        self.assertIn("# Legacy verifier prompt", prompt)
        self.assertIn("# Frozen Gate Evidence Requirements", prompt)
        self.assertIn("Required finding evidence: `upstream-plan/plan.md:1-3`", prompt)
        self.assertIn("`upstream-plan/plan.md:1-2`", prompt)
        self.assertIn("`upstream-plan/zz-unrelated.md`", prompt)
        self.assertIn("Required `evidenceChecked` minimum closure: copy this JSON array verbatim", prompt)

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

    def test_parent_synthesizes_ordered_codex_coverage_from_compact_receipt(self) -> None:
        self.prepare(execution_mode="codex-exec")
        self.complete_preflight()
        self.authorize_launch()
        manifest = self.read_json("review-input.json")
        payload = {
            "status": "completed",
            "artifactViewReadReceipt": bootstrap.artifact_view_read_receipt(manifest),
            "candidates": [],
        }
        self.assertNotIn("coverage", payload)
        candidate, attempt_dir = self.reviewer_attempt_candidate(
            manifest, "compact-coverage", "blind_hunter", payload
        )

        with mock.patch.object(
            bootstrap, "run_codex_attempt", return_value=(candidate, attempt_dir)
        ):
            self.assertEqual(0, bootstrap.main([
                "run-layer",
                "--run-dir", str(self.run_dir),
                "--role", "blind_hunter",
                "--codex-command", "test-codex-command",
                "--model", manifest["codexExecPolicy"]["preferredModel"],
            ]))

        required = [item["artifact"] for item in manifest["artifacts"]]
        formal = self.read_json("reviewer-outputs/blind_hunter.json")
        self.assertEqual("completed", formal["status"])
        self.assertEqual(required, formal["coverage"]["requiredArtifacts"])
        self.assertEqual(required, formal["coverage"]["readArtifacts"])
        self.assertEqual([], formal["coverage"]["missingArtifacts"])

    def test_wrong_compact_receipt_is_transport_failure_and_preserves_formal_output(self) -> None:
        self.prepare(execution_mode="codex-exec")
        self.complete_preflight()
        self.authorize_launch()
        manifest = self.read_json("review-input.json")
        receipt = bootstrap.artifact_view_read_receipt(manifest)
        receipt["artifactCount"] += 1
        payload = {
            "status": "completed",
            "artifactViewReadReceipt": receipt,
            "candidates": [],
        }
        candidate, attempt_dir = self.reviewer_attempt_candidate(
            manifest, "bad-compact-coverage", "blind_hunter", payload
        )
        formal_path = self.run_dir / "reviewer-outputs" / "blind_hunter.json"
        formal_before = formal_path.read_bytes()

        with mock.patch.object(
            bootstrap, "run_codex_attempt", return_value=(candidate, attempt_dir)
        ):
            self.assertEqual(1, bootstrap.main([
                "run-layer",
                "--run-dir", str(self.run_dir),
                "--role", "blind_hunter",
                "--codex-command", "test-codex-command",
                "--model", manifest["codexExecPolicy"]["preferredModel"],
            ]))

        self.assertEqual(formal_before, formal_path.read_bytes())
        failed_event = bootstrap.read_process_events(self.run_dir)[-1]
        self.assertEqual("attempt-failed", failed_event["eventType"])
        self.assertEqual("transport", failed_event["failureClass"])

    def test_malformed_child_json_records_retryable_transport_failure(self) -> None:
        self.prepare(execution_mode="codex-exec")
        manifest = self.read_json("review-input.json")
        formal_path = self.run_dir / "reviewer-outputs" / "blind_hunter.json"
        formal_before = formal_path.read_bytes()

        class MalformedProcess:
            pid = os.getpid()
            returncode = 0

            def __init__(self, output_path: Path) -> None:
                self.output_path = output_path

            def communicate(self, _prompt: str) -> tuple[str, str]:
                self.output_path.write_text("{not-json", encoding="utf-8", newline="\n")
                return "", ""

        def fake_popen(argv: list[str], **_kwargs: object) -> MalformedProcess:
            output_path = Path(argv[argv.index("--output-last-message") + 1])
            return MalformedProcess(output_path)

        with mock.patch.object(bootstrap.subprocess, "Popen", side_effect=fake_popen):
            with self.assertRaises(bootstrap.TransportAttemptError):
                bootstrap.run_codex_attempt(
                    self.run_dir,
                    manifest,
                    "blind_hunter",
                    "codex",
                    manifest["codexExecPolicy"]["preferredModel"],
                )

        self.assertEqual(formal_before, formal_path.read_bytes())
        failed_event = bootstrap.read_process_events(self.run_dir)[-1]
        self.assertEqual("attempt-failed", failed_event["eventType"])
        self.assertEqual("transport", failed_event["failureClass"])

    def test_non_utf8_child_json_records_retryable_transport_failure(self) -> None:
        self.prepare(execution_mode="codex-exec")
        manifest = self.read_json("review-input.json")
        formal_path = self.run_dir / "reviewer-outputs" / "blind_hunter.json"
        formal_before = formal_path.read_bytes()

        class NonUtf8Process:
            pid = os.getpid()
            returncode = 0

            def __init__(self, output_path: Path) -> None:
                self.output_path = output_path

            def communicate(self, _prompt: str) -> tuple[str, str]:
                self.output_path.write_bytes(b"\xff\xfe")
                return "", ""

        def fake_popen(argv: list[str], **_kwargs: object) -> NonUtf8Process:
            output_path = Path(argv[argv.index("--output-last-message") + 1])
            return NonUtf8Process(output_path)

        with mock.patch.object(bootstrap.subprocess, "Popen", side_effect=fake_popen):
            with self.assertRaises(bootstrap.TransportAttemptError):
                bootstrap.run_codex_attempt(
                    self.run_dir,
                    manifest,
                    "blind_hunter",
                    "codex",
                    manifest["codexExecPolicy"]["preferredModel"],
                )

        self.assertEqual(formal_before, formal_path.read_bytes())
        failed_event = bootstrap.read_process_events(self.run_dir)[-1]
        self.assertEqual("attempt-failed", failed_event["eventType"])
        self.assertEqual("transport", failed_event["failureClass"])

    def test_child_json_read_error_is_transport_failure(self) -> None:
        candidate_path = self.run_dir / "candidate.json"
        candidate_path.parent.mkdir(parents=True)
        candidate_path.write_text("{}", encoding="utf-8", newline="\n")

        with mock.patch.object(Path, "read_text", side_effect=OSError("read failed")):
            with self.assertRaisesRegex(
                bootstrap.TransportAttemptError, "not readable UTF-8"
            ):
                bootstrap.parse_child_json(candidate_path)

    def test_failed_codex_payload_is_retryable_transport_and_preserves_formal_output(self) -> None:
        self.prepare(execution_mode="codex-exec")
        self.complete_preflight()
        self.authorize_launch()
        manifest = self.read_json("review-input.json")
        formal_path = self.run_dir / "reviewer-outputs" / "blind_hunter.json"
        formal_before = formal_path.read_bytes()
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
        self.assertEqual(formal_before, formal_path.read_bytes())
        failed_event = bootstrap.read_process_events(self.run_dir)[-1]
        self.assertEqual("attempt-failed", failed_event["eventType"])
        self.assertEqual("transport", failed_event["failureClass"])
        self.assertEqual(1, manifest["fullReviewRound"])
        write_set = [formal_path.relative_to(self.repo).as_posix()]
        bootstrap.reserve_codex_attempt(
            self.run_dir,
            manifest,
            "blind_hunter",
            "retry-after-transport",
            "reviewer:blind_hunter",
            formal_path,
            write_set,
        )

    def test_reviewer_authority_drift_before_publication_preserves_formal_output(self) -> None:
        self.prepare(execution_mode="codex-exec")
        self.complete_preflight()
        self.authorize_launch()
        manifest = self.read_json("review-input.json")
        payload = {
            "status": "completed",
            "artifactViewReadReceipt": bootstrap.artifact_view_read_receipt(manifest),
            "candidates": [self.candidate()],
        }
        candidate, attempt_dir = self.reviewer_attempt_candidate(
            manifest,
            "reviewer-prepublication-drift",
            "blind_hunter",
            payload,
        )
        formal_path = self.run_dir / "reviewer-outputs" / "blind_hunter.json"
        formal_before = formal_path.read_bytes()

        with mock.patch.object(
            bootstrap,
            "run_codex_attempt",
            return_value=(candidate, attempt_dir),
        ), mock.patch.object(
            bootstrap,
            "validate_launch_authorization",
            side_effect=[None, bootstrap.BootstrapError("Frozen authority changed before publication")],
        ) as validate_authority:
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

        self.assertEqual(2, validate_authority.call_count)
        self.assertEqual(formal_before, formal_path.read_bytes())
        attempt_events = [
            event
            for event in bootstrap.read_process_events(self.run_dir)
            if event.get("attemptId") == attempt_dir.name
        ]
        self.assertEqual("attempt-failed", attempt_events[-1]["eventType"])
        self.assertFalse(any(event["eventType"] == "attempt-completed" for event in attempt_events))

    def test_verifier_authority_drift_before_publication_preserves_formal_output(self) -> None:
        manifest, finding = self.complete_codex_gate_with_blocker()
        valid_decision = {
            "findingId": finding["findingId"],
            "decision": "confirmed",
            "reason": "The exact finding and required context were both checked",
            "evidenceChecked": ["upstream-plan/plan.md:1", "upstream-plan/plan.md:3"],
        }
        candidate, attempt_dir = self.verifier_attempt_candidate(
            manifest, "verifier-prepublication-drift", [valid_decision]
        )
        formal_path = self.run_dir / "verifier-output.json"
        formal_before = formal_path.read_bytes()

        with mock.patch.object(
            bootstrap,
            "run_codex_attempt",
            return_value=(candidate, attempt_dir),
        ), mock.patch.object(
            bootstrap,
            "validate_launch_authorization",
            side_effect=[None, bootstrap.BootstrapError("Frozen authority changed before publication")],
        ) as validate_authority:
            self.assertEqual(
                1,
                bootstrap.main(
                    [
                        "run-layer",
                        "--run-dir",
                        str(self.run_dir),
                        "--role",
                        "independent_verifier",
                        "--codex-command",
                        "test-codex-command",
                        "--model",
                        manifest["verifierPolicy"]["preferredModel"],
                    ]
                ),
            )

        self.assertEqual(2, validate_authority.call_count)
        self.assertEqual(formal_before, formal_path.read_bytes())
        attempt_events = [
            event
            for event in bootstrap.read_process_events(self.run_dir)
            if event.get("attemptId") == attempt_dir.name
        ]
        self.assertEqual("attempt-failed", attempt_events[-1]["eventType"])
        self.assertFalse(any(event["eventType"] == "attempt-completed" for event in attempt_events))

    def test_verifier_semantic_failure_does_not_replace_formal_output(self) -> None:
        manifest, finding = self.complete_codex_gate_with_blocker()
        invalid_decision = {
            "findingId": finding["findingId"],
            "decision": "confirmed",
            "reason": "The child cited context but omitted the exact finding span",
            "evidenceChecked": ["upstream-plan/plan.md:1"],
        }
        candidate, attempt_dir = self.verifier_attempt_candidate(
            manifest, "invalid-verifier-semantic", [invalid_decision]
        )
        formal_path = self.run_dir / "verifier-output.json"
        formal_before = formal_path.read_bytes()

        with mock.patch.object(
            bootstrap, "run_codex_attempt", return_value=(candidate, attempt_dir)
        ):
            self.assertEqual(
                1,
                bootstrap.main(
                    [
                        "run-layer",
                        "--run-dir",
                        str(self.run_dir),
                        "--role",
                        "independent_verifier",
                        "--codex-command",
                        "test-codex-command",
                        "--model",
                        manifest["verifierPolicy"]["preferredModel"],
                    ]
                ),
            )

        self.assertEqual(formal_before, formal_path.read_bytes())
        attempt_events = [
            event
            for event in bootstrap.read_process_events(self.run_dir)
            if event.get("attemptId") == attempt_dir.name
        ]
        self.assertEqual("attempt-failed", attempt_events[-1]["eventType"])
        self.assertFalse(any(event["eventType"] == "attempt-completed" for event in attempt_events))

    def test_append_only_verifier_recovery_reopens_retry_and_finalizes(self) -> None:
        manifest, finding = self.complete_codex_gate_with_blocker()
        invalid_decision = {
            "findingId": finding["findingId"],
            "decision": "confirmed",
            "reason": "Legacy runner accepted split evidence that did not cover the finding span",
            "evidenceChecked": ["upstream-plan/plan.md:1"],
        }
        _candidate, legacy_attempt = self.verifier_attempt_candidate(
            manifest, "legacy-invalid-verifier", [invalid_decision]
        )
        verifier = self.read_json("verifier-output.json")
        verifier["decisions"] = [invalid_decision]
        self.write_json("verifier-output.json", verifier)
        identity = bootstrap.process_creation_identity(os.getpid())
        self.assertIsNotNone(identity)
        write_set = [(self.run_dir / "verifier-output.json").relative_to(self.repo).as_posix()]
        bootstrap.append_process_event(
            self.run_dir,
            {
                "eventType": "attempt-completed",
                "timestamp": bootstrap.utc_now(),
                "attemptId": legacy_attempt.name,
                "operationId": "verifier",
                "role": "independent_verifier",
                "pid": os.getpid(),
                "processIdentity": identity,
                "writeSet": write_set,
            },
        )
        bootstrap.rebuild_process_leases_from_events(self.run_dir, manifest)
        rejected_before = (self.run_dir / "verifier-output.json").read_bytes()
        self.assertEqual(
            "recover-invalid-verifier",
            bootstrap.classify_run(self.run_dir, manifest)["nextAction"],
        )

        self.assertEqual(
            0,
            bootstrap.main(["recover-verifier", "--run-dir", str(self.run_dir)]),
        )
        self.assertEqual(rejected_before, (self.run_dir / "verifier-output.json").read_bytes())
        recovery_events = [
            event
            for event in bootstrap.read_process_events(self.run_dir)
            if event.get("eventType") == bootstrap.VERIFIER_RECOVERY_EVENT
        ]
        self.assertEqual(1, len(recovery_events))
        recovery_path = self.run_dir / recovery_events[0]["recoveryPath"]
        recovery = json.loads(recovery_path.read_text(encoding="utf-8"))
        self.assertEqual(
            [],
            bootstrap.schema_validation_errors(
                "bootstrap-verifier-recovery.v1.schema.json", recovery
            ),
        )
        rejected_path = self.run_dir / recovery["rejectedOutput"]["path"]
        self.assertEqual(rejected_before, rejected_path.read_bytes())
        invalid_recovery = dict(recovery)
        invalid_recovery["unexpected"] = True
        self.assertTrue(
            bootstrap.schema_validation_errors(
                "bootstrap-verifier-recovery.v1.schema.json", invalid_recovery
            )
        )
        verifier_lease = next(
            item
            for item in self.read_json("process-leases.json")["leases"]
            if item["operationId"] == "verifier"
        )
        self.assertEqual("failed", verifier_lease["state"])
        self.assertEqual(
            "run-independent-verifier",
            bootstrap.classify_run(self.run_dir, manifest)["nextAction"],
        )
        self.assertEqual(
            0,
            bootstrap.main(["recover-verifier", "--run-dir", str(self.run_dir)]),
        )
        self.assertEqual(
            1,
            sum(
                event.get("eventType") == bootstrap.VERIFIER_RECOVERY_EVENT
                for event in bootstrap.read_process_events(self.run_dir)
            ),
        )

        bootstrap.reserve_codex_attempt(
            self.run_dir,
            manifest,
            "independent_verifier",
            "recovery-reservation",
            "verifier",
            self.run_dir / "verifier-output.json",
            write_set,
        )
        bootstrap.append_attempt_event_and_rebuild(
            self.run_dir,
            manifest,
            {
                "eventType": "attempt-failed",
                "timestamp": bootstrap.utc_now(),
                "attemptId": "recovery-reservation",
                "operationId": "verifier",
                "role": "independent_verifier",
                "pid": os.getpid(),
                "processIdentity": identity,
                "writeSet": write_set,
                "note": "Test releases the reopened reservation",
            },
        )

        valid_decision = {
            "findingId": finding["findingId"],
            "decision": "confirmed",
            "reason": "The exact finding and required context were both checked",
            "evidenceChecked": ["upstream-plan/plan.md:1", "upstream-plan/plan.md:3"],
        }
        candidate, retry_attempt = self.verifier_attempt_candidate(
            manifest, "valid-verifier-retry", [valid_decision]
        )
        with mock.patch.object(
            bootstrap, "run_codex_attempt", return_value=(candidate, retry_attempt)
        ):
            self.assertEqual(
                0,
                bootstrap.main(
                    [
                        "run-layer",
                        "--run-dir",
                        str(self.run_dir),
                        "--role",
                        "independent_verifier",
                        "--codex-command",
                        "test-codex-command",
                        "--model",
                        manifest["verifierPolicy"]["preferredModel"],
                    ]
                ),
            )
        self.assertEqual([valid_decision], self.read_json("verifier-output.json")["decisions"])
        self.assertEqual("finalize", bootstrap.classify_run(self.run_dir, manifest)["nextAction"])
        self.assertEqual(0, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        self.assertEqual("blocked", self.read_json("review-gate-result.json")["status"])

    def test_recover_verifier_rejects_valid_completed_output(self) -> None:
        manifest, finding = self.complete_codex_gate_with_blocker()
        valid_decision = {
            "findingId": finding["findingId"],
            "decision": "confirmed",
            "reason": "The complete evidence set confirms the reachable failure",
            "evidenceChecked": ["upstream-plan/plan.md:1", "upstream-plan/plan.md:3"],
        }
        _candidate, attempt_dir = self.verifier_attempt_candidate(
            manifest, "valid-completed-verifier", [valid_decision]
        )
        verifier = self.read_json("verifier-output.json")
        verifier["decisions"] = [valid_decision]
        self.write_json("verifier-output.json", verifier)
        identity = bootstrap.process_creation_identity(os.getpid())
        self.assertIsNotNone(identity)
        bootstrap.append_process_event(
            self.run_dir,
            {
                "eventType": "attempt-completed",
                "timestamp": bootstrap.utc_now(),
                "attemptId": attempt_dir.name,
                "operationId": "verifier",
                "role": "independent_verifier",
                "pid": os.getpid(),
                "processIdentity": identity,
                "writeSet": [
                    (self.run_dir / "verifier-output.json").relative_to(self.repo).as_posix()
                ],
            },
        )
        bootstrap.rebuild_process_leases_from_events(self.run_dir, manifest)

        self.assertEqual(
            1,
            bootstrap.main(["recover-verifier", "--run-dir", str(self.run_dir)]),
        )
        self.assertFalse((self.run_dir / "verifier-recoveries").exists())

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
        self.assertEqual("bootstrap-cost-calibration-legacy-v1", estimate["costCalibration"]["calibrationId"])
        self.assertEqual("conservative-fallback", estimate["costCalibrationCohortId"])
        replayed = bootstrap.review_cost_estimate(
            profile, artifacts, calibration_ref=estimate["costCalibration"]
        )
        self.assertEqual(estimate, replayed)
        legacy = bootstrap.legacy_review_cost_estimate(profile, artifacts)
        self.assertNotIn("costCalibration", legacy)
        self.assertNotIn("schemaVersion", legacy)
        self.assertEqual(
            max(1, int(sum(item["sizeBytes"] for item in artifacts) // 4 * 1.25)),
            legacy["estimatedInputTokens"]["high"],
        )
        self.assertTrue(legacy["highCost"])
        self.assertEqual(17, legacy["basisSampleCount"])

    def test_cost_calibration_rejects_inverted_percentiles(self) -> None:
        calibration = json.loads(bootstrap.COST_CALIBRATION_PATH.read_text(encoding="utf-8"))
        calibration["conservativeFallback"]["tokenMultiplierP90"] = 0.1
        with mock.patch.object(bootstrap, "read_json", return_value=calibration), mock.patch.object(
            bootstrap, "schema_validation_errors", return_value=[]
        ):
            with self.assertRaisesRegex(bootstrap.BootstrapError, "inverted percentiles"):
                bootstrap.load_cost_calibration()

    def test_cost_calibration_rejects_non_finite_statistics(self) -> None:
        calibration = json.loads(bootstrap.COST_CALIBRATION_PATH.read_text(encoding="utf-8"))
        calibration["conservativeFallback"]["tokenMultiplierP90"] = math.inf
        with mock.patch.object(bootstrap, "read_json", return_value=calibration), mock.patch.object(
            bootstrap, "schema_validation_errors", return_value=[]
        ):
            with self.assertRaisesRegex(bootstrap.BootstrapError, "non-finite"):
                bootstrap.load_cost_calibration()
        calibration["conservativeFallback"]["tokenMultiplierP90"] = 10 ** 10000
        with mock.patch.object(bootstrap, "read_json", return_value=calibration), mock.patch.object(
            bootstrap, "schema_validation_errors", return_value=[]
        ):
            with self.assertRaisesRegex(bootstrap.BootstrapError, "non-finite"):
                bootstrap.load_cost_calibration()

    def test_cost_estimate_rejects_corrupt_promoted_calibration_binding(self) -> None:
        profile = bootstrap.load_profile("bootstrap-skill-route")
        with mock.patch.object(bootstrap, "COST_CALIBRATION_HASH", "sha256:" + "0" * 64):
            with self.assertRaisesRegex(bootstrap.BootstrapError, "hash-invalid"):
                bootstrap.review_cost_estimate(profile, [])

    def test_cost_estimate_uses_matching_promoted_cohort(self) -> None:
        profile = bootstrap.load_profile("bootstrap-skill-route")
        artifacts = [{
            "artifact": "scope/item.md", "sha256": "sha256:" + "a" * 64,
            "sizeBytes": 4000, "textEncoding": "utf-8", "lineCount": 40,
        }]
        match = {
            "reviewProfile": profile["reviewProfile"],
            "policyRevision": profile["policyRevision"],
            "routeVersion": profile["routeVersion"],
            "controlPlaneRevision": profile["controlPlaneRevision"],
            "model": bootstrap.cost_model_cohort_key({**profile, "fullReviewRound": 1}),
            "reasoningProfile": bootstrap.cost_reasoning_profile(
                {**profile, "fullReviewRound": 1}
            ),
            "fullReviewRound": 1,
            "workloadBucket": "small",
        }
        statistics = {
            "basisSampleCount": 6, "confidence": "medium",
            "tokenMultiplierP50": 1.0, "tokenMultiplierP90": 2.0,
            "minimumTotalTokensP50": 30000, "minimumTotalTokensP90": 60000,
            "tokensPerWallMinute": 12000, "retryRisk": "low",
        }
        calibration = {
            "conservativeFallback": statistics,
            "cohorts": [{"cohortId": "matched", "match": match, "statistics": statistics}],
        }
        with mock.patch.object(
            bootstrap, "load_cost_calibration",
            return_value=(calibration, {"calibrationId": "test-calibration"}),
        ):
            estimate = bootstrap.review_cost_estimate(profile, artifacts)
        self.assertEqual("matched", estimate["costCalibrationCohortId"])
        self.assertEqual(6, estimate["basisSampleCount"])

    def test_structured_cost_evidence_separates_roles_probe_and_retry(self) -> None:
        run_dir = self.repo / "cost-run"
        input_hash = "sha256:" + "a" * 64
        manifest = {
            "executionMode": "codex-exec",
            "inputHash": input_hash,
            "requiredLayers": ["blind_hunter"],
            "executionReadSet": [],
            "dependencyClosure": [],
            "artifactView": {
                "manifestPath": "artifact-view/manifest.json",
                "manifestHash": "sha256:" + "f" * 64,
            },
            "codexExecPolicy": {
                "preferredModel": "gpt-test",
                "fallbackModels": [],
                "reasoningEffortByRole": {
                    "blind_hunter": "high", "independent_verifier": "high",
                },
            },
        }
        run_dir.mkdir()
        (run_dir / "review-candidates.json").write_text(json.dumps({
            "findings": [{"proposedSeverity": "P1"}],
        }), encoding="utf-8", newline="\n")
        events = []
        events.extend(self.write_cost_attempt(
            run_dir, "reviewer-failed", "blind_hunter", 100,
            input_hash=input_hash, start_minute=0, terminal_type="attempt-failed",
            exit_code=1,
        ))
        events.extend(self.write_cost_attempt(
            run_dir, "reviewer-success", "blind_hunter", 120,
            input_hash=input_hash, start_minute=3,
        ))
        events.extend(self.write_cost_attempt(
            run_dir, "verifier-attempt", "independent_verifier", 40,
            input_hash=input_hash, start_minute=5,
        ))
        events.extend(self.write_cost_attempt(
            run_dir, "probe-attempt", "model_probe", 10,
            input_hash=input_hash, start_minute=7,
        ))
        with mock.patch.object(bootstrap, "read_process_events", return_value=events):
            result = bootstrap.structured_run_cost_evidence(run_dir, manifest)
        self.assertTrue(result["complete"])
        self.assertEqual(220, result["reviewerTokens"])
        self.assertEqual(40, result["verifierTokens"])
        self.assertEqual(10, result["probeTokens"])
        self.assertEqual(100, result["transportRetryTokens"])
        self.assertEqual(270, result["totalTokens"])
        self.assertEqual("gpt-test", result["selectedModel"])
        self.assertEqual(240.0, result["wallSeconds"])
        self.assertEqual([], result["exclusionReasons"])

        (run_dir / "attempts" / "reviewer-success" / "candidate-output.json").unlink()
        with mock.patch.object(bootstrap, "read_process_events", return_value=events):
            incomplete = bootstrap.structured_run_cost_evidence(run_dir, manifest)
        self.assertFalse(incomplete["complete"])
        self.assertIn(
            "missing-completed-attempt-evidence:reviewer-success:candidate-output.json",
            incomplete["exclusionReasons"],
        )

    def test_structured_cost_evidence_accepts_allowed_model_fallbacks(self) -> None:
        run_dir = self.repo / "mixed-cost-run"
        run_dir.mkdir()
        input_hash = "sha256:" + "b" * 64
        manifest = {
            "executionMode": "codex-exec",
            "inputHash": input_hash,
            "requiredLayers": ["blind_hunter"],
            "executionReadSet": [],
            "dependencyClosure": [],
            "artifactView": {
                "manifestPath": "artifact-view/manifest.json",
                "manifestHash": "sha256:" + "f" * 64,
            },
            "codexExecPolicy": {
                "preferredModel": "gpt-a",
                "fallbackModels": ["gpt-b"],
                "reasoningEffortByRole": {
                    "blind_hunter": "high", "independent_verifier": "high",
                },
            },
        }
        events = self.write_cost_attempt(
            run_dir, "first", "blind_hunter", 10,
            input_hash=input_hash, model="gpt-a", start_minute=0,
        )
        events += self.write_cost_attempt(
            run_dir, "second", "blind_hunter", 10,
            input_hash=input_hash, model="gpt-b", start_minute=2,
        )
        with mock.patch.object(bootstrap, "read_process_events", return_value=events):
            result = bootstrap.structured_run_cost_evidence(run_dir, manifest)
        self.assertFalse(result["complete"])
        self.assertTrue(result["modelConsistent"])
        self.assertEqual(["gpt-a", "gpt-b"], result["selectedModels"])
        self.assertNotIn("model-selection-not-unique", result["exclusionReasons"])
        with mock.patch.object(bootstrap, "read_process_events", return_value=events[:3]):
            orphaned = bootstrap.structured_run_cost_evidence(run_dir, manifest)
        self.assertFalse(orphaned["complete"])

    def test_structured_cost_evidence_accepts_terra_discovery_and_sol_verifier(self) -> None:
        run_dir = self.repo / "mixed-route-cost-run"
        run_dir.mkdir()
        input_hash = "sha256:" + "d" * 64
        profile = bootstrap.load_profile("bootstrap-implementation-conformance")
        manifest = {
            "executionMode": "codex-exec",
            "inputHash": input_hash,
            "fullReviewRound": 1,
            "requiredLayers": list(bootstrap.LAYERS),
            "executionReadSet": [],
            "dependencyClosure": [],
            "artifactView": {
                "manifestPath": "artifact-view/manifest.json",
                "manifestHash": "sha256:" + "f" * 64,
            },
            "codexExecPolicy": profile["codexExecPolicy"],
            "verifierPolicy": profile["verifierPolicy"],
            "accessProbePolicy": profile["accessProbePolicy"],
        }
        (run_dir / "review-candidates.json").write_text(json.dumps({
            "findings": [
                {
                    "proposedSeverity": "P1",
                    "dimension": "correctness",
                    "verifierRiskClass": "protected_path",
                },
                {"proposedSeverity": "P2", "dimension": "security"},
            ],
        }), encoding="utf-8", newline="\n")
        (run_dir / "verifier-access-proof.json").write_text(
            "{}\n", encoding="utf-8", newline="\n"
        )
        events = []
        for index, role in enumerate(bootstrap.LAYERS):
            events.extend(self.write_cost_attempt(
                run_dir, f"reviewer-{role}", role, 20,
                input_hash=input_hash, model="gpt-5.6-terra", start_minute=index,
            ))
        events.extend(self.write_cost_attempt(
            run_dir, "discovery-probe", "model_probe", 5,
            input_hash=input_hash, model="gpt-5.6-terra", start_minute=3,
        ))
        events.extend(self.write_cost_attempt(
            run_dir, "verifier-probe", "model_probe", 5,
            input_hash=input_hash, model="gpt-5.6-sol", start_minute=4,
        ))
        events.extend(self.write_cost_attempt(
            run_dir, "verifier", "independent_verifier", 30,
            input_hash=input_hash, model="gpt-5.6-sol", start_minute=5,
        ))
        with mock.patch.object(bootstrap, "read_process_events", return_value=events):
            result = bootstrap.structured_run_cost_evidence(run_dir, manifest)
        self.assertTrue(result["complete"])
        self.assertTrue(result["modelConsistent"])
        self.assertIsNone(result["selectedModel"])
        self.assertEqual(["gpt-5.6-sol", "gpt-5.6-terra"], result["selectedModels"])
        self.assertRegex(result["modelCohortKey"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual([], result["exclusionReasons"])

    def test_structured_cost_evidence_binds_probe_to_exact_discovery_role_route(self) -> None:
        run_dir = self.repo / "role-bound-probe-cost-run"
        run_dir.mkdir()
        input_hash = "sha256:" + "c" * 64
        profile = bootstrap.load_profile("bootstrap-upstream-plan")
        manifest = {
            "executionMode": "codex-exec",
            "inputHash": input_hash,
            "fullReviewRound": 1,
            "requiredLayers": list(bootstrap.LAYERS),
            "executionReadSet": [],
            "dependencyClosure": [],
            "artifactView": {
                "manifestPath": "artifact-view/manifest.json",
                "manifestHash": "sha256:" + "f" * 64,
            },
            "codexExecPolicy": profile["codexExecPolicy"],
            "verifierPolicy": profile["verifierPolicy"],
            "accessProbePolicy": profile["accessProbePolicy"],
        }
        (run_dir / "review-candidates.json").write_text(
            json.dumps({"findings": []}), encoding="utf-8", newline="\n"
        )
        (run_dir / "access-proof.edge_case_hunter.json").write_text(
            "{}\n", encoding="utf-8", newline="\n"
        )
        events = []
        for index, role in enumerate(bootstrap.LAYERS):
            effort = bootstrap.reviewer_execution_route(manifest, role)["reasoningEffort"]
            events.extend(self.write_cost_attempt(
                run_dir, f"reviewer-{role}", role, 10,
                input_hash=input_hash, model="gpt-5.6-terra",
                start_minute=index, reasoning_effort=effort,
            ))
        events.extend(self.write_cost_attempt(
            run_dir, "probe-blind", "model_probe", 5,
            input_hash=input_hash, model="gpt-5.6-terra", start_minute=3,
            operation_id="model-probe:discovery:blind_hunter:gpt-5.6-terra",
            reasoning_effort="medium",
        ))
        events.extend(self.write_cost_attempt(
            run_dir, "probe-edge", "model_probe", 5,
            input_hash=input_hash, model="gpt-5.6-terra", start_minute=4,
            operation_id="model-probe:discovery:edge_case_hunter:gpt-5.6-terra",
            reasoning_effort="high",
        ))
        with mock.patch.object(bootstrap, "read_process_events", return_value=events):
            result = bootstrap.structured_run_cost_evidence(run_dir, manifest)
        self.assertTrue(result["complete"])

        request_path = run_dir / "attempts" / "probe-edge" / "request.json"
        request = json.loads(request_path.read_text(encoding="utf-8"))
        request["argv"][request["argv"].index("model_reasoning_effort=high")] = (
            "model_reasoning_effort=medium"
        )
        request_path.write_text(json.dumps(request), encoding="utf-8", newline="\n")
        for event in events:
            if event.get("attemptId") == "probe-edge" and event.get("eventType") == "attempt-started":
                event["requestHash"] = bootstrap.value_hash(request)
        with mock.patch.object(bootstrap, "read_process_events", return_value=events):
            mismatch = bootstrap.structured_run_cost_evidence(run_dir, manifest)
        self.assertFalse(mismatch["complete"])
        self.assertFalse(mismatch["modelConsistent"])

    def test_structured_cost_evidence_replays_registered_placeholder_policy(self) -> None:
        run_dir = self.repo / "historical-placeholder-cost-run"
        run_dir.mkdir()
        input_hash = "sha256:" + "e" * 64
        historical_policy = copy.deepcopy(next(
            policy for policy in bootstrap.HISTORICAL_CONTROL_PLANE_POLICIES
            if policy["typedPlaceholders"]["reasoning_effort"] == "enum:medium|high"
        ))
        manifest = {
            "executionMode": "codex-exec",
            "inputHash": input_hash,
            "requiredLayers": ["blind_hunter"],
            "executionReadSet": [],
            "dependencyClosure": [],
            "artifactView": {
                "manifestPath": "artifact-view/manifest.json",
                "manifestHash": "sha256:" + "f" * 64,
            },
            "codexExecPolicy": {
                "preferredModel": "gpt-test",
                "fallbackModels": [],
                "reasoningEffortByRole": {
                    "blind_hunter": "high", "independent_verifier": "high",
                },
            },
            "controlPlanePolicy": historical_policy,
        }
        (run_dir / "review-candidates.json").write_text(
            json.dumps({"findings": []}), encoding="utf-8", newline="\n"
        )
        events = self.write_cost_attempt(
            run_dir, "reviewer", "blind_hunter", 20,
            input_hash=input_hash, start_minute=0,
            typed_placeholders=historical_policy["typedPlaceholders"],
        )
        events.extend(self.write_cost_attempt(
            run_dir, "probe", "model_probe", 5,
            input_hash=input_hash, start_minute=2,
            typed_placeholders=historical_policy["typedPlaceholders"],
        ))
        with mock.patch.object(bootstrap, "read_process_events", return_value=events):
            result = bootstrap.structured_run_cost_evidence(run_dir, manifest)
        self.assertTrue(result["complete"])
        self.assertEqual([], result["exclusionReasons"])

        substituted = copy.deepcopy(manifest)
        substituted["controlPlanePolicy"]["typedPlaceholders"]["reasoning_effort"] = "enum:low"
        with mock.patch.object(bootstrap, "read_process_events", return_value=events):
            rejected = bootstrap.structured_run_cost_evidence(run_dir, substituted)
        self.assertFalse(rejected["complete"])
        self.assertIn("invalid-cost-control-plane-policy", rejected["exclusionReasons"])

    def test_codex_token_usage_reads_machine_jsonl(self) -> None:
        stdout = "\n".join([
            json.dumps({"type": "item.completed"}),
            json.dumps({"type": "turn.completed", "usage": {"input_tokens": 12, "output_tokens": 3}}),
        ])
        self.assertEqual(15, bootstrap.codex_token_usage(stdout))
        self.assertIsNone(bootstrap.codex_token_usage("not-json"))

    def test_structured_cost_evidence_rejects_sidecar_and_lifecycle_drift(self) -> None:
        run_dir = self.repo / "drifted-cost-run"
        run_dir.mkdir()
        input_hash = "sha256:" + "c" * 64
        manifest = {
            "executionMode": "codex-exec",
            "inputHash": input_hash,
            "requiredLayers": list(bootstrap.LAYERS),
            "executionReadSet": [],
            "dependencyClosure": [],
            "artifactView": {
                "manifestPath": "artifact-view/manifest.json",
                "manifestHash": "sha256:" + "f" * 64,
            },
            "codexExecPolicy": {
                "preferredModel": "gpt-test",
                "fallbackModels": [],
                "reasoningEffortByRole": {
                    "blind_hunter": "high", "edge_case_hunter": "high",
                    "acceptance_auditor": "high", "independent_verifier": "high",
                },
            },
        }
        events = self.write_cost_attempt(
            run_dir, "reviewer", "blind_hunter", 25,
            input_hash=input_hash, start_minute=0,
        )
        events += self.write_cost_attempt(
            run_dir, "probe", "model_probe", 5,
            input_hash=input_hash, start_minute=4,
        )
        token_path = run_dir / "attempts" / "reviewer" / "token-usage.json"
        token_path.write_text(json.dumps({
            "schemaVersion": "bootstrap-token-usage.v1", "tokens": 999,
        }), encoding="utf-8", newline="\n")
        with mock.patch.object(bootstrap, "read_process_events", return_value=events):
            mismatch = bootstrap.structured_run_cost_evidence(run_dir, manifest)
        self.assertFalse(mismatch["complete"])
        self.assertIn("token-jsonl-mismatch:reviewer", mismatch["exclusionReasons"])
        self.assertIn(
            "required-role-not-complete:edge_case_hunter", mismatch["exclusionReasons"]
        )
        self.assertIn(
            "required-role-not-complete:acceptance_auditor", mismatch["exclusionReasons"]
        )

        token_path.write_text(json.dumps({
            "schemaVersion": "bootstrap-token-usage.v1", "tokens": 25,
        }), encoding="utf-8", newline="\n")
        request_path = run_dir / "attempts" / "reviewer" / "request.json"
        request = json.loads(request_path.read_text(encoding="utf-8"))
        request["argv"][request["argv"].index("model_reasoning_effort=high")] = (
            "model_reasoning_effort=medium"
        )
        request_path.write_text(json.dumps(request), encoding="utf-8", newline="\n")
        with mock.patch.object(bootstrap, "read_process_events", return_value=events):
            policy_drift = bootstrap.structured_run_cost_evidence(run_dir, manifest)
        self.assertIn(
            "invalid-execution-policy-binding:reviewer",
            policy_drift["exclusionReasons"],
        )
        request["argv"][request["argv"].index("model_reasoning_effort=medium")] = (
            "model_reasoning_effort=high"
        )
        request_path.write_text(json.dumps(request), encoding="utf-8", newline="\n")
        model_index = request["argv"].index("-m") + 1
        manifest["codexExecPolicy"]["fallbackModels"] = ["gpt-other"]
        request["argv"][model_index] = "gpt-other"
        request_path.write_text(json.dumps(request), encoding="utf-8", newline="\n")
        with mock.patch.object(bootstrap, "read_process_events", return_value=events):
            model_drift = bootstrap.structured_run_cost_evidence(run_dir, manifest)
        self.assertIn(
            "invalid-lifecycle-request-binding:reviewer",
            model_drift["exclusionReasons"],
        )
        request["argv"][model_index] = "gpt-test"
        request_path.write_text(json.dumps(request), encoding="utf-8", newline="\n")
        missing_request = run_dir / "attempts" / "missing-request"
        missing_request.mkdir()
        with mock.patch.object(bootstrap, "read_process_events", return_value=events):
            missing = bootstrap.structured_run_cost_evidence(run_dir, manifest)
        self.assertIn("missing-request:missing-request", missing["exclusionReasons"])
        missing_request.rmdir()

        duplicate = [events[0], *events]
        with mock.patch.object(bootstrap, "read_process_events", return_value=duplicate):
            duplicated = bootstrap.structured_run_cost_evidence(run_dir, manifest)
        self.assertFalse(duplicated["complete"])
        self.assertIn(
            "invalid-lifecycle-cardinality:reviewer", duplicated["exclusionReasons"]
        )

        request_path = run_dir / "attempts" / "reviewer" / "request.json"
        request = json.loads(request_path.read_text(encoding="utf-8"))
        request.pop("environmentEvidence")
        request_path.write_text(json.dumps(request), encoding="utf-8", newline="\n")
        with mock.patch.object(bootstrap, "read_process_events", return_value=events):
            incomplete_request = bootstrap.structured_run_cost_evidence(run_dir, manifest)
        self.assertIn(
            "invalid-request-binding:reviewer", incomplete_request["exclusionReasons"]
        )

        lifecycle_without_identity = [dict(event) for event in events]
        lifecycle_without_identity[0].pop("processIdentity")
        with mock.patch.object(
            bootstrap, "read_process_events", return_value=lifecycle_without_identity
        ):
            incomplete_event = bootstrap.structured_run_cost_evidence(run_dir, manifest)
        self.assertIn(
            "invalid-lifecycle-execution-facts:reviewer",
            incomplete_event["exclusionReasons"],
        )

    def test_build_review_baseline_keeps_manual_cost_operational_only(self) -> None:
        self.prepare()
        self.complete_layers()
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        self.assertEqual(0, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        finalized_dir = self.run_dir
        prepared_dir = self.repo / "prepared-history-run"
        self.run_dir = prepared_dir
        self.prepare(
            review_id="prepared-history-001",
            change_id="prepared-history-change-001",
            lineage_family_id="prepared-history-family-001",
        )
        self.run_dir = finalized_dir
        out_dir = self.repo / "logs" / "review-governance" / "baseline-test"
        self.assertEqual(0, bootstrap.main([
            "build-review-baseline", "--repository-root", str(self.repo),
            "--run-dir", str(self.run_dir), "--run-dir", str(prepared_dir),
            "--out-dir", str(out_dir),
        ]))
        history = json.loads((out_dir / "review-history-index.v1.json").read_text(encoding="utf-8"))
        calibration = json.loads((out_dir / "review-cost-calibration-candidate.v1.json").read_text(encoding="utf-8"))
        self.assertEqual([], history["authorizes"])
        self.assertEqual(2, history["runCount"])
        self.assertEqual(1, history["eligibleRunCount"])
        finalized_row = next(
            item for item in history["runs"] if item["runDirectory"] == "bootstrap-run"
        )
        prepared_row = next(
            item for item in history["runs"] if item["runDirectory"] == "prepared-history-run"
        )
        self.assertTrue(finalized_row["eligibleForSemanticStatistics"])
        self.assertFalse(finalized_row["eligibleForCostCalibration"])
        self.assertEqual(0, finalized_row["findingClosure"]["candidateCount"])
        self.assertEqual(
            finalized_row["findingClosure"], history["semanticYield"]["totals"]
        )
        self.assertEqual(0.0, history["semanticYield"]["confirmedPerEligibleRun"])
        self.assertIn(
            "not-a-codex-exec-run", finalized_row["costEvidence"]["exclusionReasons"]
        )
        self.assertEqual("prepared", prepared_row["runExecutionState"])
        self.assertFalse(prepared_row["eligibleForSemanticStatistics"])
        self.assertIsNone(prepared_row["findingClosure"])
        self.assertEqual([], calibration["cohorts"])
        self.assertEqual(0, calibration["eligibleSampleCount"])
        self.assertEqual([], calibration["authorizes"])
        self.assertEqual(1, bootstrap.main([
            "build-review-baseline", "--repository-root", str(self.repo),
            "--run-dir", str(self.run_dir), "--run-dir", str(prepared_dir),
            "--out-dir", str(out_dir),
        ]))
        self.assertEqual(1, bootstrap.main([
            "build-review-baseline", "--repository-root", str(self.repo),
            "--run-dir", str(self.run_dir),
            "--out-dir", str(self.repo / "baseline-outside-logs"),
        ]))

        failed_out = self.repo / "logs" / "review-governance" / "baseline-write-failure"
        original_write = bootstrap.write_json
        def fail_second_document(path, value, **kwargs):
            if Path(path).name == "review-cost-calibration-candidate.v1.json":
                raise bootstrap.BootstrapError("synthetic publication failure")
            return original_write(path, value, **kwargs)
        with mock.patch.object(bootstrap, "write_json", side_effect=fail_second_document):
            with self.assertRaisesRegex(bootstrap.BootstrapError, "synthetic publication failure"):
                bootstrap.build_review_baseline(
                    self.repo, [str(self.run_dir), str(prepared_dir)], failed_out
                )
        self.assertFalse(failed_out.exists())
        self.assertEqual([], list(failed_out.parent.glob(f".{failed_out.name}.stage-*")))

    def test_explicit_baseline_rejects_a_hash_self_consistent_non_run(self) -> None:
        fake_dir = self.repo / "not-a-formal-run"
        fake_dir.mkdir()
        manifest = {
            "schemaVersion": "bootstrap-review-input.v1",
            "reviewId": "synthetic-not-formal",
            "fullReviewRound": 1,
        }
        manifest["inputHash"] = bootstrap.value_hash(manifest)
        (fake_dir / "review-input.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        with self.assertRaises(bootstrap.BootstrapError):
            bootstrap._baseline_runs(self.repo, [str(fake_dir)])

    def test_baseline_accepts_historical_access_proof_and_run_seal(self) -> None:
        self.prepare(execution_mode="codex-exec")
        manifest = self.read_json("review-input.json")
        self.complete_access_proof(manifest)
        bootstrap.validate_baseline_formal_sidecars(self.run_dir, manifest)
        self.assertEqual(0, bootstrap.main([
            "seal-run", "--run-dir", str(self.run_dir), "--state", "abandoned",
            "--reason", "operator-replaced-run",
        ]))
        bootstrap.validate_baseline_formal_sidecars(self.run_dir, manifest)

    def test_historical_launch_replay_ignores_current_environment_identity(self) -> None:
        self.prepare(execution_mode="codex-exec")
        self.complete_preflight()
        self.authorize_launch()
        manifest = self.read_json("review-input.json")
        with mock.patch.object(
            bootstrap,
            "child_environment",
            return_value=({}, {"PATH": "drifted-after-review"}),
        ):
            with self.assertRaisesRegex(
                bootstrap.BootstrapError, "environment identity has drifted"
            ):
                bootstrap.validate_launch_authorization(self.run_dir, manifest)
            bootstrap.validate_launch_authorization(
                self.run_dir, manifest, historical_replay=True
            )

    def test_historical_load_uses_registered_content_addressed_profile(self) -> None:
        self.prepare()
        manifest = self.read_json("review-input.json")
        registries = self.repo / "registries"
        registries.mkdir()
        current_registry = json.loads(
            bootstrap.PROFILE_PATH.read_text(encoding="utf-8")
        )
        profile_name = manifest["profileName"]
        outgoing = copy.deepcopy(current_registry["profiles"][profile_name])
        replacement = copy.deepcopy(outgoing)
        replacement["reviewDepth"] += " Replacement policy."
        replacement["policyRevision"] = bootstrap.value_hash({
            key: value for key, value in replacement.items() if key != "policyRevision"
        })
        current_registry["profiles"][profile_name] = replacement
        current_path = registries / "review-profiles.v1.json"
        current_path.write_text(
            json.dumps(current_registry, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        history = {
            "schemaVersion": "bootstrap-historical-policy-revisions.v1",
            "revisions": [{
                "profileName": profile_name,
                "policyRevision": outgoing["policyRevision"],
                "replayScope": "baseline-and-successor",
                "authorityRootRegistry": outgoing["authorityRootRegistry"],
            }],
            "authorizes": [],
        }
        history_path = registries / "historical-policy-revisions.v1.json"
        history_path.write_text(
            json.dumps(history, indent=2) + "\n", encoding="utf-8", newline="\n"
        )

        with mock.patch.object(bootstrap, "PROFILE_PATH", current_path), mock.patch.object(
            bootstrap, "HISTORICAL_POLICY_PATH", history_path
        ):
            with self.assertRaisesRegex(
                bootstrap.BootstrapError, "stale or substituted policyRevision"
            ):
                bootstrap.load_run(str(self.run_dir))
            loaded_dir, loaded_manifest, loaded_root = bootstrap.load_run(
                str(self.run_dir), require_fresh_artifacts=False
            )
            self.assertEqual(self.run_dir.resolve(), loaded_dir)
            self.assertEqual(manifest, loaded_manifest)
            self.assertEqual(self.repo.resolve(), loaded_root)

            tampered = copy.deepcopy(manifest)
            tampered["reviewDepth"] += " Substituted historical policy."
            tampered.pop("inputHash")
            tampered["inputHash"] = bootstrap.value_hash(tampered)
            self.write_json("review-input.json", tampered)
            with self.assertRaisesRegex(
                bootstrap.BootstrapError, "content-addressed revision"
            ):
                bootstrap.load_run(str(self.run_dir), require_fresh_artifacts=False)

    def test_historical_finalized_replay_uses_frozen_candidate_bytes(self) -> None:
        self.prepare()
        self.complete_layers({"blind_hunter": [self.candidate()]})
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        finding_id = self.read_json("review-candidates.json")["findings"][0]["findingId"]
        verifier = self.read_json("verifier-output.json")
        verifier["decisions"] = [{
            "findingId": finding_id,
            "decision": "refuted",
            "reason": "Frozen context shows the reported outcome is already guarded",
            "evidenceChecked": ["upstream-plan/plan.md:1", "upstream-plan/plan.md:3"],
        }]
        self.write_json("verifier-output.json", verifier)
        self.assertEqual(0, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        manifest = self.read_json("review-input.json")
        self.target.write_text(
            "# Plan\n\nRepaired after the finalized review.\n",
            encoding="utf-8",
            newline="\n",
        )
        with self.assertRaisesRegex(
            bootstrap.BootstrapError, "no longer reproduce review-candidates"
        ):
            bootstrap.validate_finalized_run_evidence(
                self.run_dir, manifest, self.repo
            )
        envelope = bootstrap.validate_finalized_run_evidence(
            self.run_dir, manifest, self.repo, historical_replay=True
        )
        self.assertEqual("clean", envelope["finalStatus"])

    def test_baseline_replays_round_one_after_round_two_is_consumed(self) -> None:
        family_id = "baseline-replay-family"
        self.prepare(lineage_family_id=family_id)
        self.write_synthetic_blocked_result("BSR-BASELINE-ROUND-ONE")
        round_one = self.run_dir
        self.target.write_text(
            "# Plan\n\nRound two repair.\n", encoding="utf-8", newline="\n"
        )
        self.run_dir = self.repo / "bootstrap-run-round-2"
        self.prepare(
            review_id="baseline-replay-round-two",
            lineage_family_id=family_id,
            review_round=2,
            predecessor_run=round_one,
        )
        self.write_synthetic_blocked_result("BSR-BASELINE-ROUND-TWO")
        loaded_dir, loaded_manifest, loaded_root = bootstrap.load_run(
            str(round_one), require_fresh_artifacts=False
        )
        self.assertEqual(round_one.resolve(), loaded_dir)
        self.assertEqual(self.repo.resolve(), loaded_root)
        self.assertEqual(1, loaded_manifest["fullReviewRound"])

    def test_baseline_rejects_terminal_residue_without_final_gate(self) -> None:
        self.prepare()
        self.complete_layers()
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        self.assertEqual(0, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        (self.run_dir / "review-gate-result.json").unlink()
        with self.assertRaisesRegex(
            bootstrap.BootstrapError, "missing review-gate-result.json"
        ):
            bootstrap.build_review_baseline(
                self.repo,
                [str(self.run_dir)],
                self.repo / "logs" / "review-governance" / "terminal-residue",
            )

    def test_registry_baseline_rejects_stale_manifest_input_hash(self) -> None:
        run_dir = self.repo / "registered-run"
        run_dir.mkdir()
        manifest = {
            "schemaVersion": "bootstrap-review-input.v1",
            "inputHash": "sha256:" + "0" * 64,
        }
        with mock.patch.object(
            bootstrap, "review_run_manifests", return_value=[(run_dir, manifest)]
        ):
            with self.assertRaisesRegex(bootstrap.BootstrapError, "stale input hash"):
                bootstrap._baseline_runs(self.repo, None)

    def test_synthetic_calibration_corpus_is_paired_and_non_authorizing(self) -> None:
        path = Path(__file__).resolve().parent / "fixtures" / "review-calibration-corpus.v1.json"
        corpus = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual([], bootstrap.schema_validation_errors(
            "bootstrap-review-calibration-corpus.v1.schema.json", corpus
        ))
        self.assertEqual([], corpus["authorizes"])
        self.assertEqual("forbidden", corpus["runtimePromptConsumption"])
        for pair in corpus["pairs"]:
            for case_name in ("confirmed", "refuted"):
                case = pair[case_name]
                projected = bootstrap.project_verified_blocker_disposition({
                    "findingId": f"synthetic-{case_name}",
                    "decision": case["verifierDecision"],
                    "reason": case["guardState"],
                })
                self.assertEqual(case["expectedDisposition"], projected["status"])
            self.assertNotIn("exactEvidence", pair["confirmed"])
            self.assertNotIn("exactEvidence", pair["refuted"])

    def test_p2_requires_disposition_and_rejects_high_risk_deferral(self) -> None:
        self.prepare()
        self.complete_layers({"blind_hunter": [self.candidate(severity="P2")]})
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        finding_id = self.read_json("review-candidates.json")["findings"][0]["findingId"]
        self.assertEqual(1, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        manifest = self.read_json("review-input.json")
        exclusions = ["implementation-acceptance", "protected-handoff", "release", "commit", "done"]
        identity = {
            "findingId": finding_id, "reviewId": manifest["reviewId"],
            "inputHash": manifest["inputHash"], "candidateHash": manifest["authorityContextHash"],
            "authorityRevision": manifest["authorityRevision"],
        }
        _, registry_ref = self.write_p2_registry(manifest)
        evidence_paths = {"command-registry.json": registry_ref}
        for name, payload in {
            "owner-authority.json": {
                "schemaVersion": "bootstrap-p2-owner-authority.v1", "receiptId": "owner-receipt-001",
                "rootId": "p2-owner-root.v1", "authorityRootRef": self.authority_root_ref(),
                "signerId": "bootstrap-operator", "predecessorAuthorityRef": self.authority_root_ref(),
                "consumer": "bootstrap-p2-disposition",
                "owner": "owner", **identity, "policyRevision": manifest["policyRevision"],
                "scope": "expiry-or-authority-change", "status": "active",
                "issuedAt": "2020-01-01T00:00:00Z", "expiresAt": "2099-01-01T00:00:00Z",
                "authorizes": [], "doesNotAuthorize": exclusions,
            },
        }.items():
            path = self.repo / name
            path.write_text(json.dumps(payload), encoding="utf-8", newline="\n")
            evidence_paths[name] = {
                "path": path.relative_to(self.repo).as_posix(),
                "sha256": bootstrap.file_hash(path),
            }
        for name, payload in {
            "non-impact.json": {
                "schemaVersion": "bootstrap-p2-evidence-result.v1", "resultId": "non-impact-001",
                "evidenceType": "non-impact", **identity, "scope": "expiry-or-authority-change",
                "result": "bounded", "observedAt": "2020-01-01T00:00:00Z",
                "expiresAt": "2099-01-01T00:00:00Z", "processResultRef": None,
                "authorizes": [], "doesNotAuthorize": exclusions,
            },
        }.items():
            path = self.repo / name
            path.write_text(json.dumps(payload), encoding="utf-8", newline="\n")
            evidence_paths[name] = {"path": path.relative_to(self.repo).as_posix(), "sha256": bootstrap.file_hash(path)}
        recheck_process_ref = self.run_p2_command(finding_id, "recheck-command")
        recheck_path = self.repo / "recheck.json"
        recheck_path.write_text(json.dumps({
            "schemaVersion": "bootstrap-p2-evidence-result.v1", "resultId": "recheck-evidence-001",
            "evidenceType": "recheck", **identity, "scope": "expiry-or-authority-change",
            "result": "passed", "observedAt": "2020-01-01T00:00:00Z",
            "expiresAt": "2099-01-01T00:00:00Z",
            "processResultRef": recheck_process_ref,
            "authorizes": [], "doesNotAuthorize": exclusions,
        }), encoding="utf-8", newline="\n")
        evidence_paths["recheck.json"] = {
            "path": recheck_path.relative_to(self.repo).as_posix(),
            "sha256": bootstrap.file_hash(recheck_path),
        }
        p2 = {
            "schemaVersion": "bootstrap-p2-dispositions.v1", "reviewId": manifest["reviewId"],
            "inputHash": manifest["inputHash"], "candidateHash": manifest["authorityContextHash"],
            "policyRevision": manifest["policyRevision"], "authorityRevision": manifest["authorityRevision"],
            "findingIds": [finding_id],
            "dispositions": [{
                "findingId": finding_id, "status": "deferred", "risk": "high",
                "reason": "Deferred for later", "owner": "owner",
                "expiry": "2099-01-01T00:00:00Z", "closureCommandId": "recheck-command",
                "closureCommandRegistryRef": evidence_paths["command-registry.json"],
                "ownerAuthorityRef": evidence_paths["owner-authority.json"],
                "nonImpactEvidenceRef": evidence_paths["non-impact.json"],
                "recheckEvidenceRef": evidence_paths["recheck.json"],
                "recheckTrigger": "expiry-or-authority-change",
            }],
        }
        owner_path = self.repo / "owner-authority.json"
        owner = json.loads(owner_path.read_text(encoding="utf-8"))
        self_issued_owner = dict(owner)
        self_issued_owner["predecessorAuthorityRef"] = None
        owner_path.write_text(json.dumps(self_issued_owner), encoding="utf-8", newline="\n")
        p2["dispositions"][0]["risk"] = "normal"
        p2["dispositions"][0]["ownerAuthorityRef"] = {
            "path": owner_path.relative_to(self.repo).as_posix(),
            "sha256": bootstrap.file_hash(owner_path),
        }
        self.write_json("p2-dispositions.json", p2)
        with self.assertRaisesRegex(bootstrap.BootstrapError, "not chained directly"):
            bootstrap.validate_p2_dispositions(
                self.run_dir,
                manifest,
                self.read_json("review-candidates.json")["findings"],
            )
        owner_path.write_text(json.dumps(owner), encoding="utf-8", newline="\n")
        p2["dispositions"][0]["risk"] = "high"
        p2["dispositions"][0]["ownerAuthorityRef"] = {
            "path": owner_path.relative_to(self.repo).as_posix(),
            "sha256": bootstrap.file_hash(owner_path),
        }
        self.write_json("p2-dispositions.json", p2)
        self.assertEqual(1, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        p2["dispositions"][0]["risk"] = "normal"
        p2["dispositions"][0]["expiry"] = "2020-01-01T00:00:00Z"
        self.write_json("p2-dispositions.json", p2)
        self.assertEqual(1, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        closure_process_ref = self.run_p2_command(finding_id, "closure-command")
        real_process_path = self.repo / closure_process_ref["path"]
        handwritten = json.loads(real_process_path.read_text(encoding="utf-8"))
        handwritten["processEventRef"] = evidence_paths["command-registry.json"]
        handwritten["processLogRef"] = evidence_paths["command-registry.json"]
        handwritten_path = self.repo / "handwritten-success-result.json"
        handwritten_path.write_text(json.dumps(handwritten), encoding="utf-8", newline="\n")
        p2["dispositions"][0] = {
            "findingId": finding_id, "status": "fixed", "risk": "normal",
            "reason": "Targeted validation proves closure", "closureCommandId": "closure-command",
            "closureCommandRegistryRef": evidence_paths["command-registry.json"],
            "closureProcessResultRef": {
                "path": handwritten_path.relative_to(self.repo).as_posix(),
                "sha256": bootstrap.file_hash(handwritten_path),
            },
        }
        self.write_json("p2-dispositions.json", p2)
        with self.assertRaisesRegex(bootstrap.BootstrapError, "event"):
            bootstrap.validate_p2_dispositions(
                self.run_dir,
                manifest,
                self.read_json("review-candidates.json")["findings"],
            )
        p2["dispositions"][0]["closureProcessResultRef"] = closure_process_ref
        self.write_json("p2-dispositions.json", p2)
        self.assertEqual(0, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        self.assertEqual("clean", self.read_json("review-gate-result.json")["status"])

    def test_multiple_p2_process_results_survive_later_log_appends(self) -> None:
        self.prepare()
        first = self.candidate("BOOT-CANDIDATE-001", "P2")
        second = self.candidate("BOOT-CANDIDATE-002", "P2")
        second["triggerInput"] = "A second independent P2 closure is required"
        self.complete_layers({"blind_hunter": [first, second]})
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        findings = self.read_json("review-candidates.json")["findings"]
        finding_ids = sorted(item["findingId"] for item in findings)
        self.assertEqual(2, len(finding_ids))
        manifest = self.read_json("review-input.json")
        _registry_path, registry_ref = self.write_p2_registry(manifest)
        process_refs = {
            finding_id: self.run_p2_command(finding_id, "closure-command")
            for finding_id in finding_ids
        }
        dispositions = {
            "schemaVersion": "bootstrap-p2-dispositions.v1",
            "reviewId": manifest["reviewId"],
            "inputHash": manifest["inputHash"],
            "candidateHash": manifest["authorityContextHash"],
            "policyRevision": manifest["policyRevision"],
            "authorityRevision": manifest["authorityRevision"],
            "findingIds": finding_ids,
            "dispositions": [
                {
                    "findingId": finding_id,
                    "status": "fixed",
                    "risk": "normal",
                    "reason": "The registered closure command passed",
                    "closureCommandId": "closure-command",
                    "closureCommandRegistryRef": registry_ref,
                    "closureProcessResultRef": process_refs[finding_id],
                }
                for finding_id in finding_ids
            ],
        }
        self.write_json("p2-dispositions.json", dispositions)

        for reference in process_refs.values():
            process = json.loads((self.repo / reference["path"]).read_text(encoding="utf-8"))
            self.assertEqual({"path", "eventHash"}, set(process["processLogRef"]))
        validated = bootstrap.validate_p2_dispositions(self.run_dir, manifest, findings)
        self.assertEqual(finding_ids, sorted(validated))

        first_reference = process_refs[finding_ids[0]]
        legacy_process = json.loads(
            (self.repo / first_reference["path"]).read_text(encoding="utf-8")
        )
        process_log_path = self.run_dir / "p2-process-events.jsonl"
        legacy_process["processLogRef"] = {
            "path": process_log_path.relative_to(self.repo).as_posix(),
            "sha256": bootstrap.file_hash(process_log_path),
        }
        legacy_path = self.repo / "legacy-p2-process-result.json"
        legacy_path.write_text(json.dumps(legacy_process), encoding="utf-8", newline="\n")
        dispositions["dispositions"][0]["closureProcessResultRef"] = {
            "path": legacy_path.relative_to(self.repo).as_posix(),
            "sha256": bootstrap.file_hash(legacy_path),
        }
        self.write_json("p2-dispositions.json", dispositions)
        legacy_validated = bootstrap.validate_p2_dispositions(self.run_dir, manifest, findings)
        self.assertEqual(finding_ids, sorted(legacy_validated))

        dispositions["dispositions"][0]["closureProcessResultRef"] = first_reference
        self.write_json("p2-dispositions.json", dispositions)
        self.assertEqual(0, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))
        self.assertEqual("clean", self.read_json("review-gate-result.json")["status"])

    def test_p2_rejects_stale_transitive_evidence(self) -> None:
        self.prepare()
        self.complete_layers({"blind_hunter": [self.candidate(severity="P2")]})
        self.assertEqual(0, bootstrap.main(["gate", "--run-dir", str(self.run_dir)]))
        finding_id = self.read_json("review-candidates.json")["findings"][0]["findingId"]
        manifest = self.read_json("review-input.json")
        evidence = self.repo / "p2-evidence.json"
        evidence.write_text("{}", encoding="utf-8", newline="\n")
        reference = {"path": evidence.relative_to(self.repo).as_posix(), "sha256": "sha256:" + "0" * 64}
        self.write_json("p2-dispositions.json", {
            "schemaVersion": "bootstrap-p2-dispositions.v1", "reviewId": manifest["reviewId"],
            "inputHash": manifest["inputHash"], "candidateHash": manifest["authorityContextHash"],
            "policyRevision": manifest["policyRevision"], "authorityRevision": manifest["authorityRevision"],
            "findingIds": [finding_id],
            "dispositions": [{
                "findingId": finding_id, "status": "deferred", "risk": "normal", "reason": "bounded",
                "owner": "owner", "expiry": "2099-01-01T00:00:00Z", "closureCommandId": "test-command",
                "closureCommandRegistryRef": reference, "ownerAuthorityRef": reference,
                "nonImpactEvidenceRef": reference, "recheckEvidenceRef": reference,
                "recheckTrigger": "expiry-or-authority-change",
            }],
        })
        self.assertEqual(1, bootstrap.main(["finalize", "--run-dir", str(self.run_dir)]))

    def test_successor_authorization_rejects_untrusted_actor_lineage_and_time(self) -> None:
        exclusions = ["plan-ready", "slice-ready", "bootstrap-review", "implementation-accepted", "protected-handoff", "release-ready"]
        policy_revision = bootstrap.load_profile("bootstrap-upstream-plan")["policyRevision"]
        authority_path = self.repo / "successor-authority.json"
        authority = {"schemaVersion": "bootstrap-successor-policy-authority.v1", "authorityId": "authority-001", "rootId": "successor-policy-root.v1", "authorityRootRef": self.authority_root_ref(), "signerId": "repository-operator", "policyRevision": policy_revision, "authorizedActors": [{"actorId": "operator-001", "role": "successor-policy-authorizer", "consumers": ["repository-maintenance-tdd-adapter-plan-reentry"], "scopes": ["plan-reentry"]}], "status": "active", "issuedAt": "2026-01-01T00:00:00Z", "expiresAt": "2099-01-01T00:00:00Z", "predecessorAuthorityRef": self.authority_root_ref(), "authorizes": [], "doesNotAuthorize": exclusions}
        authority_path.write_text(json.dumps(authority), encoding="utf-8", newline="\n")
        event_path = self.repo / "successor-event.json"
        event = {"schemaVersion": "bootstrap-successor-policy-authorization.v1", "eventId": "event-001", "decisionId": "decision-001", "actorId": "operator-001", "authoritySourceRef": {"path": "successor-authority.json", "sha256": bootstrap.file_hash(authority_path)}, "supersededReviewId": "review-old", "supersededChangeId": "change-old", "successorChangeId": "change-new", "policyRevision": policy_revision, "authorityRevision": "authority-new", "consumer": "repository-maintenance-tdd-adapter-plan-reentry", "scope": "plan-reentry", "status": "active", "issuedAt": "2026-01-02T00:00:00Z", "expiresAt": "2098-01-01T00:00:00Z", "predecessorEventRef": None, "revocationEventRef": None, "authorizes": [], "doesNotAuthorize": exclusions}
        event_path.write_text(json.dumps(event), encoding="utf-8", newline="\n")
        decision = {"schemaVersion": "bootstrap-successor-policy-decision.v1", "decisionId": "decision-001", "supersededReviewId": "review-old", "supersededChangeId": "change-old", "successorChangeId": "change-new", "policyRevision": policy_revision, "authorityRevision": "authority-new", "authorizationEventRef": {"path": "successor-event.json", "sha256": bootstrap.file_hash(event_path)}, "authorizationEventId": "event-001", "consumer": "repository-maintenance-tdd-adapter-plan-reentry", "authorizes": [], "doesNotAuthorize": exclusions, "decidedAt": "2026-01-03T00:00:00Z"}
        self.assertEqual(event, bootstrap.validate_successor_policy_authorization(self.repo, decision))
        for field, value in (("actorId", "intruder-001"), ("successorChangeId", "other-change"), ("revocationEventRef", {"path": "successor-authority.json", "sha256": bootstrap.file_hash(authority_path)}), ("expiresAt", "2020-01-01T00:00:00Z")):
            mutated = dict(event); mutated[field] = value
            event_path.write_text(json.dumps(mutated), encoding="utf-8", newline="\n")
            candidate = dict(decision); candidate["authorizationEventRef"] = {"path": "successor-event.json", "sha256": bootstrap.file_hash(event_path)}
            with self.subTest(field=field), self.assertRaises(bootstrap.BootstrapError):
                bootstrap.validate_successor_policy_authorization(self.repo, candidate)
        event_path.write_text(json.dumps(event), encoding="utf-8", newline="\n")
        candidate = dict(decision); candidate["authorizationEventRef"] = {"path": "successor-event.json", "sha256": bootstrap.file_hash(event_path)}; candidate["decidedAt"] = "2025-01-01T00:00:00Z"
        with self.assertRaises(bootstrap.BootstrapError):
            bootstrap.validate_successor_policy_authorization(self.repo, candidate)
        self_issued = dict(authority)
        self_issued["predecessorAuthorityRef"] = None
        authority_path.write_text(json.dumps(self_issued), encoding="utf-8", newline="\n")
        event_path.write_text(json.dumps(event), encoding="utf-8", newline="\n")
        event["authoritySourceRef"] = {"path": "successor-authority.json", "sha256": bootstrap.file_hash(authority_path)}
        event_path.write_text(json.dumps(event), encoding="utf-8", newline="\n")
        candidate = dict(decision)
        candidate["authorizationEventRef"] = {"path": "successor-event.json", "sha256": bootstrap.file_hash(event_path)}
        with self.assertRaisesRegex(bootstrap.BootstrapError, "not chained directly"):
            bootstrap.validate_successor_policy_authorization(self.repo, candidate)

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

        max_command = bootstrap.render_codex_command(
            "codex", "gpt-5.6-sol", "max", "workspace-write",
            (self.repo / "verifier-candidate.json").resolve(),
        )
        self.assertIn("model_reasoning_effort=max", max_command)
        with self.assertRaisesRegex(bootstrap.ControlPlaneError, "reasoning_effort"):
            bootstrap.render_codex_command(
                "codex", "gpt-5.6-sol", "unsupported", "workspace-write",
                (self.repo / "invalid-candidate.json").resolve(),
            )

        self.prepare()
        manifest = self.read_json("review-input.json")
        legacy_manifest = copy.deepcopy(manifest)
        legacy_manifest["controlPlanePolicy"] = copy.deepcopy(
            bootstrap.HISTORICAL_CONTROL_PLANE_POLICIES[0]
        )
        with self.assertRaisesRegex(bootstrap.BootstrapError, "controlPlanePolicy"):
            bootstrap.validate_manifest_controls(
                legacy_manifest, bootstrap.load_profile(manifest["profileName"])
            )
        bootstrap.validate_manifest_controls(
            legacy_manifest,
            bootstrap.load_profile(manifest["profileName"]),
            historical_replay=True,
        )

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
        events = bootstrap.read_process_events(self.run_dir)
        started = [event for event in events if event.get("eventType") == "attempt-started"]
        self.assertEqual(1, len(started))
        request = self.read_json(f"attempts/{started[0]['attemptId']}/request.json")
        self.assertEqual(bootstrap.value_hash(request), started[0]["requestHash"])
        self.assertEqual(model, started[0]["selectedModel"])
        rejected = [
            event
            for event in events
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

    def test_completed_formal_output_reconciles_interrupted_completion_event(self) -> None:
        self.prepare(execution_mode="codex-exec")
        manifest = self.read_json("review-input.json")
        role = "blind_hunter"
        operation_id = f"reviewer:{role}"
        attempt_id = "interrupted-after-formal-publication"
        formal_path = self.run_dir / "reviewer-outputs" / f"{role}.json"
        formal = self.read_json(f"reviewer-outputs/{role}.json")
        formal["status"] = "completed"
        formal["coverage"]["readArtifacts"] = formal["coverage"]["requiredArtifacts"]
        formal["coverage"]["missingArtifacts"] = []
        self.write_json(f"reviewer-outputs/{role}.json", formal)
        write_set = [formal_path.relative_to(self.repo).as_posix()]
        identity = bootstrap.process_creation_identity(os.getpid())
        self.assertIsNotNone(identity)
        common = {
            "attemptId": attempt_id,
            "operationId": operation_id,
            "role": role,
            "pid": 999999,
            "processIdentity": "dead-controller:test",
            "writeSet": write_set,
        }
        bootstrap.append_process_event(self.run_dir, {
            "eventType": "attempt-reserved",
            "timestamp": bootstrap.utc_now(),
            **common,
        })
        bootstrap.append_process_event(self.run_dir, {
            "eventType": "attempt-started",
            "timestamp": bootstrap.utc_now(),
            "requestHash": "sha256:" + "1" * 64,
            "selectedModel": manifest["codexExecPolicy"]["preferredModel"],
            **common,
        })
        bootstrap.append_process_event(self.run_dir, {
            "eventType": "attempt-process-completed",
            "timestamp": bootstrap.utc_now(),
            **common,
        })
        bootstrap.append_process_event(self.run_dir, {
            "eventType": "attempt-stale",
            "timestamp": bootstrap.utc_now(),
            "note": "Controller ended before completion publication",
            **common,
        })

        with self.assertRaisesRegex(bootstrap.BootstrapError, "reconciled as completed"):
            bootstrap.reserve_codex_attempt(
                self.run_dir, manifest, role, "retry-attempt", operation_id,
                formal_path, write_set,
            )

        completed = [
            event for event in bootstrap.read_process_events(self.run_dir)
            if event.get("eventType") == "attempt-completed"
            and event.get("attemptId") == attempt_id
        ]
        self.assertEqual(1, len(completed))
        lease = next(
            item for item in self.read_json("process-leases.json")["leases"]
            if item["operationId"] == operation_id
        )
        self.assertEqual("completed", lease["state"])

    def test_live_controller_prevents_duplicate_reconciliation_completion(self) -> None:
        self.prepare(execution_mode="codex-exec")
        manifest = self.read_json("review-input.json")
        role = "blind_hunter"
        operation_id = f"reviewer:{role}"
        attempt_id = "live-controller-after-formal-publication"
        formal_path = self.run_dir / "reviewer-outputs" / f"{role}.json"
        formal = self.read_json(f"reviewer-outputs/{role}.json")
        formal["status"] = "completed"
        formal["coverage"]["readArtifacts"] = formal["coverage"]["requiredArtifacts"]
        formal["coverage"]["missingArtifacts"] = []
        self.write_json(f"reviewer-outputs/{role}.json", formal)
        identity = bootstrap.process_creation_identity(os.getpid())
        self.assertIsNotNone(identity)
        reservation = {
            "attemptId": attempt_id,
            "operationId": operation_id,
            "role": role,
            "pid": os.getpid(),
            "processIdentity": identity,
            "writeSet": [formal_path.relative_to(self.repo).as_posix()],
        }
        child = {
            **reservation,
            "pid": 999999,
            "processIdentity": "dead-child:test",
        }
        bootstrap.append_process_event(self.run_dir, {
            "eventType": "attempt-reserved", "timestamp": bootstrap.utc_now(), **reservation,
        })
        bootstrap.append_process_event(self.run_dir, {
            "eventType": "attempt-started", "timestamp": bootstrap.utc_now(),
            "requestHash": "sha256:" + "1" * 64,
            "selectedModel": manifest["codexExecPolicy"]["preferredModel"], **child,
        })
        bootstrap.append_process_event(self.run_dir, {
            "eventType": "attempt-process-completed", "timestamp": bootstrap.utc_now(), **child,
        })

        with self.assertRaisesRegex(bootstrap.BootstrapError, "already completed"):
            bootstrap.reserve_codex_attempt(
                self.run_dir, manifest, role, "retry-attempt", operation_id,
                formal_path, reservation["writeSet"],
            )

        self.assertFalse(any(
            event.get("eventType") == "attempt-completed"
            for event in bootstrap.read_process_events(self.run_dir)
        ))
        bootstrap.append_process_event(self.run_dir, {
            "eventType": "attempt-completed", "timestamp": bootstrap.utc_now(), **child,
        })
        completed = [
            event for event in bootstrap.read_process_events(self.run_dir)
            if event.get("eventType") == "attempt-completed"
            and event.get("attemptId") == attempt_id
        ]
        self.assertEqual(1, len(completed))

    def test_completed_verifier_output_reconciles_interrupted_completion_event(self) -> None:
        manifest, finding = self.complete_codex_gate_with_blocker()
        role = "independent_verifier"
        operation_id = "verifier"
        attempt_id = "interrupted-verifier-after-formal-publication"
        formal_path = self.run_dir / "verifier-output.json"
        formal = bootstrap.verifier_template(manifest)
        formal["decisions"] = [{
            "findingId": finding["findingId"],
            "decision": "confirmed",
            "reason": "The exact finding and required context were both checked",
            "evidenceChecked": ["upstream-plan/plan.md:1", "upstream-plan/plan.md:3"],
        }]
        self.write_json("verifier-output.json", formal)
        write_set = [formal_path.relative_to(self.repo).as_posix()]
        common = {
            "attemptId": attempt_id,
            "operationId": operation_id,
            "role": role,
            "pid": 999999,
            "processIdentity": "dead-verifier-controller:test",
            "writeSet": write_set,
        }
        bootstrap.append_process_event(self.run_dir, {
            "eventType": "attempt-reserved", "timestamp": bootstrap.utc_now(), **common,
        })
        bootstrap.append_process_event(self.run_dir, {
            "eventType": "attempt-started", "timestamp": bootstrap.utc_now(),
            "requestHash": "sha256:" + "1" * 64,
            "selectedModel": manifest["verifierPolicy"]["preferredModel"], **common,
        })
        bootstrap.append_process_event(self.run_dir, {
            "eventType": "attempt-process-completed", "timestamp": bootstrap.utc_now(), **common,
        })

        with self.assertRaisesRegex(bootstrap.BootstrapError, "continue to finalize"):
            bootstrap.reserve_codex_attempt(
                self.run_dir, manifest, role, "retry-verifier", operation_id,
                formal_path, write_set,
            )

        completed = [
            event for event in bootstrap.read_process_events(self.run_dir)
            if event.get("eventType") == "attempt-completed"
            and event.get("attemptId") == attempt_id
        ]
        self.assertEqual(1, len(completed))

    def test_live_verifier_controller_prevents_duplicate_reconciliation_completion(self) -> None:
        manifest, finding = self.complete_codex_gate_with_blocker()
        role = "independent_verifier"
        operation_id = "verifier"
        attempt_id = "live-verifier-controller-after-formal-publication"
        formal_path = self.run_dir / "verifier-output.json"
        formal = bootstrap.verifier_template(manifest)
        formal["decisions"] = [{
            "findingId": finding["findingId"],
            "decision": "confirmed",
            "reason": "The exact finding and required context were both checked",
            "evidenceChecked": ["upstream-plan/plan.md:1", "upstream-plan/plan.md:3"],
        }]
        self.write_json("verifier-output.json", formal)
        write_set = [formal_path.relative_to(self.repo).as_posix()]
        identity = bootstrap.process_creation_identity(os.getpid())
        self.assertIsNotNone(identity)
        reservation = {
            "attemptId": attempt_id,
            "operationId": operation_id,
            "role": role,
            "pid": os.getpid(),
            "processIdentity": identity,
            "writeSet": write_set,
        }
        child = {
            **reservation,
            "pid": 999999,
            "processIdentity": "dead-verifier-child:test",
        }
        bootstrap.append_process_event(self.run_dir, {
            "eventType": "attempt-reserved", "timestamp": bootstrap.utc_now(), **reservation,
        })
        bootstrap.append_process_event(self.run_dir, {
            "eventType": "attempt-started", "timestamp": bootstrap.utc_now(),
            "requestHash": "sha256:" + "1" * 64,
            "selectedModel": manifest["verifierPolicy"]["preferredModel"], **child,
        })
        bootstrap.append_process_event(self.run_dir, {
            "eventType": "attempt-process-completed", "timestamp": bootstrap.utc_now(), **child,
        })

        with self.assertRaisesRegex(bootstrap.BootstrapError, "already completed"):
            bootstrap.reserve_codex_attempt(
                self.run_dir, manifest, role, "retry-verifier", operation_id,
                formal_path, write_set,
            )

        self.assertFalse(any(
            event.get("eventType") == "attempt-completed"
            for event in bootstrap.read_process_events(self.run_dir)
        ))

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

    def test_prepare_adds_knowledge_context_to_artifact_view(self) -> None:
        context = self.repo / "knowledge-context.v1.json"
        context.write_text(json.dumps({
            "decisions": [{
                "decision": "accepted", "satisfies": ["repository-rules"],
                "candidate": {
                    "path": "upstream-plan/plan.md",
                    "source_sha256": hashlib.sha256(self.target.read_bytes()).hexdigest(),
                },
            }],
        }), encoding="utf-8", newline="\n")
        freeze = self.repo / "knowledge-context.freeze.v1.json"
        freeze.write_text("{}\n", encoding="utf-8", newline="\n")
        frozen = {"path": "knowledge-context.v1.json", "sha256": bootstrap.file_hash(context), "freezePath": "knowledge-context.freeze.v1.json", "freezeSha256": bootstrap.file_hash(freeze), "accepted": [], "rejectedCount": 0}
        with mock.patch.object(bootstrap, "freeze_knowledge_context", return_value=frozen):
            self.prepare(knowledge_context=context)
        artifacts = {item["artifact"] for item in self.read_json("review-input.json")["artifacts"]}
        self.assertIn("knowledge-context.v1.json", artifacts)
        self.assertIn("knowledge-context.freeze.v1.json", artifacts)

    def test_stale_run_requires_explicit_nonfresh_load_for_closure_only(self) -> None:
        self.prepare()
        self.target.write_text("changed after review\n", encoding="utf-8", newline="\n")
        with self.assertRaisesRegex(bootstrap.BootstrapError, "Prepared input artifact is stale"):
            bootstrap.load_run(str(self.run_dir))
        _run_dir, manifest, repository_root = bootstrap.load_run(
            str(self.run_dir), require_fresh_artifacts=False
        )
        self.assertEqual(self.repo.resolve(), repository_root)
        self.assertEqual("bootstrap-upstream-plan", manifest["profileName"])

class BootstrapKnowledgeContextTests(unittest.TestCase):
    def test_rejected_candidate_cannot_satisfy_required_context_class(self) -> None:
        module_path = REPOSITORY_ROOT / ".agents" / "skills" / "run-phase-bootstrap-review" / "scripts" / "knowledge_context.py"
        if not module_path.is_file():
            self.fail("KWI-CONSUMPTION-INSUFFICIENT-SPECIFICITY: Bootstrap knowledge context adapter is missing")
        spec = importlib.util.spec_from_file_location("bootstrap_knowledge_context", module_path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.select_context(
            required_classes=["repository-rules"],
            decisions=[{"decision": "rejected", "satisfies": []}],
        )
        self.assertEqual("incomplete", result["status"])

    def test_prepare_freezes_only_hash_bound_accepted_context(self) -> None:
        import hashlib
        import tempfile
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "AGENTS.md"
            source.write_text("rules\n", encoding="utf-8", newline="\n")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            resource = root / "README.md"
            resource.write_text("support\n", encoding="utf-8", newline="\n")
            resource_digest = hashlib.sha256(resource.read_bytes()).hexdigest()
            context = root / "knowledge-context.v1.json"
            document = {
                "locator_request": {"snapshot": {}, "policy_revision": "policy-v2"},
                "locator_result": {"source_snapshot_id": "sha256:" + "a" * 64, "candidates": [{"path": "AGENTS.md", "source_sha256": digest, "read_set": [{"path": "AGENTS.md", "source_sha256": digest}, {"path": "README.md", "source_sha256": resource_digest}]}]},
                "request_sha256": "sha256:" + "b" * 64,
                "result_sha256": "sha256:" + "c" * 64,
                "decisions": [{"decision": "accepted", "satisfies": ["repository-rules"], "candidate": {"path": "AGENTS.md", "source_sha256": digest}}],
            }
            context.write_text(json.dumps(document), encoding="utf-8", newline="\n")
            context_hash = bootstrap.file_hash(context)
            freeze = root / "knowledge-context.freeze.v1.json"
            receipt = {
                "schema_version": "jimuyun.vdd-knowledge-freeze.v1", "context_path": context.name,
                "context_sha256": context_hash, "canonical_context_sha256": "sha256:canonical",
                "request_sha256": document["request_sha256"], "result_sha256": document["result_sha256"],
                "snapshot": {}, "source_snapshot_id": document["locator_result"]["source_snapshot_id"],
                "policy_revision": "policy-v2", "accepted": [{"path": "AGENTS.md", "source_sha256": digest, "satisfies": ["repository-rules"]}], "authorizes": [],
            }
            freeze.write_text(json.dumps(receipt), encoding="utf-8", newline="\n")
            validator = SimpleNamespace(
                validate_context=lambda *_args, **_kwargs: None,
                validate_worktree_sources=lambda *_args, **_kwargs: None,
                canonical_hash=lambda _value: "sha256:canonical",
            )
            artifacts = [
                {"artifact": "AGENTS.md", "sha256": bootstrap.file_hash(source)},
                {"artifact": "README.md", "sha256": bootstrap.file_hash(resource)},
                {"artifact": context.name, "sha256": context_hash},
                {"artifact": freeze.name, "sha256": bootstrap.file_hash(freeze)},
            ]
            with mock.patch.object(bootstrap, "_bound_knowledge_validator", return_value=validator):
                frozen = bootstrap.freeze_knowledge_context(root, context.name, artifacts)
            self.assertEqual([{"path": "AGENTS.md", "source_sha256": digest, "satisfies": ["repository-rules"], "readSet": [{"path": "AGENTS.md", "source_sha256": digest}, {"path": "README.md", "source_sha256": resource_digest}]}], frozen["accepted"])

    def test_prepare_rejects_context_that_fails_shared_provenance_validation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            context = root / "knowledge-context.v1.json"
            context.write_text(json.dumps({"decisions": []}), encoding="utf-8", newline="\n")
            freeze = root / "knowledge-context.freeze.v1.json"
            freeze.write_text("{}\n", encoding="utf-8")
            validator = SimpleNamespace(validate_context=lambda *_args, **_kwargs: "catalog_stale")
            with mock.patch.object(bootstrap, "_bound_knowledge_validator", return_value=validator):
                with self.assertRaisesRegex(bootstrap.BootstrapError, "catalog_stale"):
                    bootstrap.freeze_knowledge_context(root, context.name, [])

    def test_knowledge_context_augments_but_never_replaces_profile_mapping(self) -> None:
        mapped = {"repository-rules": ["README.md"], "tests": ["tests/test_a.py"]}
        context = {"accepted": [{"path": "AGENTS.md", "source_sha256": "a" * 64, "satisfies": ["repository-rules", "unknown"], "readSet": [{"path": "AGENTS.md"}]}]}
        actual = bootstrap.augment_context_class_artifacts(mapped, context, ["repository-rules", "tests"])
        self.assertEqual(["AGENTS.md", "README.md"], actual["repository-rules"])
        self.assertEqual(["tests/test_a.py"], actual["tests"])


if __name__ == "__main__":
    unittest.main()
