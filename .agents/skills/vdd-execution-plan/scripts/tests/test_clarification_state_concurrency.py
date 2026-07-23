from __future__ import annotations

import importlib.util
import hmac
import hashlib
import os
import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


SKILL_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = SKILL_ROOT / "scripts" / "clarification_state.py"
PROMOTION_SCRIPT = SKILL_ROOT / "scripts" / "clarification_promotion.py"
RESOLVER_SCRIPT = SKILL_ROOT / "scripts" / "clarification_authority_resolver.py"
PASS_FIXTURE = SKILL_ROOT / "scripts" / "fixtures" / "clarification-state-pass.json"
HASH_VALUE = "sha256:" + "a" * 64


def load_clarification_module():
    spec = importlib.util.spec_from_file_location("clarification_state_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_promotion_module():
    spec = importlib.util.spec_from_file_location("clarification_promotion_under_test", PROMOTION_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def init_command(
    project_root: Path,
    target: str,
    run_id: str,
    evidence_root: str | None = None,
) -> list[str]:
    command = [
        "init",
        "--project-root",
        str(project_root),
        "--target",
        target,
        "--mode",
        "create",
        "--interaction-mode",
        "interactive",
        "--run-id",
        run_id,
        "--authority-hash",
        HASH_VALUE,
        "--target-hash",
        HASH_VALUE,
    ]
    if evidence_root is not None:
        command.extend(["--evidence-root", evidence_root])
    return command


def start_cli(args: list[str]) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, str(SCRIPT), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )


def round_payload(round_id: str, first_question: int, boundary: str) -> dict[str, object]:
    fixture = json.loads(PASS_FIXTURE.read_text(encoding="utf-8"))
    questions = []
    for offset in range(5):
        number = first_question + offset
        questions.append(
            {
                "id": f"CQ-{number:03d}",
                "status": "open",
                "blocking": False,
                "summary": f"Clarify boundary {number}.",
                "recommendation": f"Confirm boundary {number} explicitly.",
                "basis": "gap",
                "primary_type": "fact_gap",
            }
        )
    return {
        "round_id": round_id,
        "questions": questions,
        "same_level_exhausted": False,
        "same_level_exhausted_reason": None,
        "confidence": 96,
        "dimension_scores": fixture["rounds"][0]["dimension_scores"],
        "dimension_evidence": fixture["rounds"][0]["dimension_evidence"],
        "recommend_exit": True,
        "analysis": f"Recorded {round_id}.",
        "user_turn_id": f"user-{round_id.lower()}",
        "confirmed_boundaries": [boundary],
        "non_goals": [],
        "conflicts": [],
        "open_items": [],
    }


class ClarificationStateConcurrencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_clarification_module()
        cls.promotion = load_promotion_module()

    def test_windows_case_alias_resumes_the_existing_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            first = run_cli(*init_command(project_root, "execution-plans/NewPlan", "run-a"))
            second = run_cli(*init_command(project_root, "execution-plans/newplan", "run-b"))

            self.assertEqual(0, first.returncode, first.stdout + first.stderr)
            self.assertEqual(0, second.returncode, second.stdout + second.stderr)
            first_payload = json.loads(first.stdout)
            second_payload = json.loads(second.stdout)
            self.assertEqual("initialized", first_payload["status"])
            self.assertEqual("resume_required", second_payload["status"])
            self.assertEqual([first_payload["state"]], second_payload["active_states"])

    def test_init_freezes_a_baseline_authority_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            initialized = run_cli(*init_command(project_root, "execution-plans/example", "run-a"))
            state_path = Path(json.loads(initialized.stdout)["state"])
            baseline_path = state_path.parent / "baseline-authority.json"
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            self.assertEqual("vdd.clarification-baseline-authority.v1", baseline["schema_version"])
            self.assertEqual(HASH_VALUE, baseline["authority_hash"])
            self.assertEqual(HASH_VALUE, baseline["target_hash"])
            self.assertTrue(baseline["manifest_hash"].startswith("sha256:"))

    def test_init_rejects_stale_explicit_authority_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            manifest_path = Path(tmp) / "authority.json"
            manifest = {
                "schema_version": "vdd.clarification-authority-manifest.v1",
                "target": "execution-plans/example",
                "authority_hash": HASH_VALUE,
                "target_hash": HASH_VALUE,
                "sources": [],
            }
            manifest["manifest_hash"] = self.module._canonical_hash(manifest)
            manifest["target_hash"] = "sha256:" + "b" * 64
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8", newline="\n")
            rejected = run_cli(*init_command(project_root, "execution-plans/example", "run-a"), "--authority-manifest", str(manifest_path))
            self.assertEqual(1, rejected.returncode, rejected.stdout + rejected.stderr)
            self.assertEqual("VDD-CLARIFICATION-BASELINE-AUTHORITY", json.loads(rejected.stdout)["rule_id"])

    def test_promotion_baseline_validator_rejects_a_tampered_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            initialized = run_cli(*init_command(project_root, "execution-plans/example", "run-a"))
            state_path = Path(json.loads(initialized.stdout)["state"])
            state = json.loads(state_path.read_text(encoding="utf-8"))
            baseline_path = state_path.parent / "baseline-authority.json"
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline["target"] = "forged"
            baseline_path.write_text(json.dumps(baseline), encoding="utf-8", newline="\n")
            valid, message = self.promotion.validate_baseline(state_path, state)
            self.assertFalse(valid)
            self.assertIn("does not bind", message)

    def test_promotion_approval_capability_binds_candidate_and_expiry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            approval_path = Path(tmp) / "approval.json"
            capability = {
                "issuer": "repository-local-hmac", "promotion_id": "promotion-001",
                "candidate_hash": HASH_VALUE, "expires_at": "2099-01-01T00:00:00Z", "nonce": "nonce-001",
                "scope": "clarification-promotion", "before_manifest_hash": HASH_VALUE, "canonical_paths": ["docs/authority.md"],
                "issued_at": "2026-01-01T00:00:00Z", "actor": "user-001", "session_id": "session-001", "turn_id": "turn-001",
                "identity_level": "trusted-user-identity", "revocation_state": "active",
            }
            signing_key = "test-approval-signing-key"
            capability["signature"] = hmac.new(
                signing_key.encode("utf-8"), self.promotion.canonical_hash(capability).encode("ascii"), hashlib.sha256
            ).hexdigest()
            approval_path.write_text(
                json.dumps(capability),
                encoding="utf-8", newline="\n",
            )
            with mock.patch.dict(os.environ, {"VDD_CLARIFICATION_APPROVAL_SIGNING_KEY": signing_key}):
                self.assertEqual(
                    (True, ""),
                    self.promotion.validate_approval_capability(approval_path, "promotion-001", HASH_VALUE, HASH_VALUE),
                )
                self.assertFalse(
                    self.promotion.validate_approval_capability(approval_path, "promotion-002", HASH_VALUE, HASH_VALUE)[0]
                )

    def test_promotion_nonce_reservation_is_idempotent_and_rejects_cross_promotion_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            run_dir.mkdir()
            approval_path = Path(tmp) / "approval.json"
            capability = {
                "issuer": "repository-local-hmac", "promotion_id": "promotion-001",
                "candidate_hash": HASH_VALUE, "expires_at": "2099-01-01T00:00:00Z", "nonce": "nonce-001",
                "scope": "clarification-promotion", "before_manifest_hash": HASH_VALUE, "canonical_paths": ["docs/authority.md"],
                "issued_at": "2026-01-01T00:00:00Z", "actor": "user-001", "session_id": "session-001", "turn_id": "turn-001",
                "identity_level": "trusted-user-identity", "revocation_state": "active", "signature": "not-validated-by-this-unit-test",
            }
            approval_path.write_text(json.dumps(capability), encoding="utf-8", newline="\n")

            self.assertEqual((True, "reserved"), self.promotion.reserve_approval_nonce(
                run_dir, approval_path, "promotion-001", HASH_VALUE
            ))
            self.assertEqual((True, "idempotent"), self.promotion.reserve_approval_nonce(
                run_dir, approval_path, "promotion-001", HASH_VALUE
            ))
            self.assertEqual((False, "approval nonce has already been reserved by another promotion"), self.promotion.reserve_approval_nonce(
                run_dir, approval_path, "promotion-002", HASH_VALUE
            ))
            records = (run_dir / "promotion-approvals.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(1, len(records))

    def test_promotion_nonce_consumption_is_idempotent_only_for_the_reserved_transaction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            run_dir.mkdir()
            approval_path = Path(tmp) / "approval.json"
            capability = {
                "issuer": "repository-local-hmac", "promotion_id": "promotion-001",
                "candidate_hash": HASH_VALUE, "expires_at": "2099-01-01T00:00:00Z", "nonce": "nonce-001",
                "scope": "clarification-promotion", "before_manifest_hash": HASH_VALUE, "canonical_paths": ["docs/authority.md"],
                "issued_at": "2026-01-01T00:00:00Z", "actor": "user-001", "session_id": "session-001", "turn_id": "turn-001",
                "identity_level": "trusted-user-identity", "revocation_state": "active", "signature": "unit-test",
            }
            approval_path.write_text(json.dumps(capability), encoding="utf-8", newline="\n")
            self.assertEqual((True, "reserved"), self.promotion.reserve_approval_nonce(
                run_dir, approval_path, "promotion-001", HASH_VALUE
            ))
            capability_hash = self.promotion.canonical_hash(capability)
            self.assertEqual((True, "consumed"), self.promotion.consume_approval_nonce(
                run_dir, "promotion-001", HASH_VALUE, capability_hash
            ))
            self.assertEqual((True, "idempotent"), self.promotion.consume_approval_nonce(
                run_dir, "promotion-001", HASH_VALUE, capability_hash
            ))
            self.assertEqual((False, "approval nonce was not reserved by this promotion"), self.promotion.consume_approval_nonce(
                run_dir, "promotion-002", HASH_VALUE, capability_hash
            ))

    def test_promotion_rejects_malformed_nonce_journal_without_authority_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            run_dir.mkdir()
            (run_dir / "promotion-approvals.jsonl").write_text("{partial", encoding="utf-8", newline="\n")
            before = (run_dir / "promotion-approvals.jsonl").read_bytes()
            valid, message = self.promotion.validate_approval_journal(run_dir)
            self.assertFalse(valid)
            self.assertIn("invalid at line 1", message)
            self.assertEqual(before, (run_dir / "promotion-approvals.jsonl").read_bytes())

    def test_generation_commit_publishes_only_complete_staged_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repository"
            root.mkdir()
            authority = root / "authority.md"
            candidate = root / "candidate.md"
            authority.write_text("before\n", encoding="utf-8", newline="\n")
            candidate.write_text("after\n", encoding="utf-8", newline="\n")
            before_hash = "sha256:" + hashlib.sha256(authority.read_bytes()).hexdigest()
            write_set = {
                "schema_version": "vdd.clarification-generation-write-set.v1",
                "entries": [{
                    "path": "authority.md", "owner": "authority-owner", "candidate_path": "candidate.md",
                    "before_sha256": before_hash,
                }],
                "resolver_readers": ["clarification_authority_resolver"],
                "consumer_manifest": self.promotion.registered_machine_reader_manifest(),
            }
            run_dir = Path(tmp) / "run"
            prepared, message, generation = self.promotion.prepare_generation(run_dir, root, "promotion-001", write_set)
            self.assertTrue(prepared, message)
            self.assertIsNotNone(generation)
            self.assertFalse((run_dir / "committed-generation.json").exists())
            self.assertEqual(b"before\n", authority.read_bytes())
            unavailable, _, _ = self.promotion.resolve_committed_generation(run_dir)
            self.assertFalse(unavailable)

            committed, message, pointer = self.promotion.commit_generation(run_dir, "promotion-001")
            self.assertTrue(committed, message)
            self.assertEqual("committed", pointer["state"])
            resolved, message, manifest = self.promotion.resolve_committed_generation(run_dir)
            self.assertTrue(resolved, message)
            self.assertEqual("sha256:" + hashlib.sha256(candidate.read_bytes()).hexdigest(), manifest["entries"][0]["candidate_sha256"])
            self.assertEqual(b"before\n", authority.read_bytes())
            resolver = subprocess.run(
                [sys.executable, str(RESOLVER_SCRIPT), "--run-dir", str(run_dir), "--authority-path", "authority.md"],
                check=False, capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(0, resolver.returncode, resolver.stdout + resolver.stderr)
            self.assertEqual((generation / "files" / "authority.md").resolve(), Path(json.loads(resolver.stdout)["path"]).resolve())

    def test_generation_prepare_rejects_stale_source_and_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repository"
            root.mkdir()
            (root / "authority.md").write_text("before\n", encoding="utf-8", newline="\n")
            (root / "candidate.md").write_text("after\n", encoding="utf-8", newline="\n")
            base = {
                "schema_version": "vdd.clarification-generation-write-set.v1",
                "entries": [{
                    "path": "authority.md", "owner": "authority-owner", "candidate_path": "candidate.md",
                    "before_sha256": HASH_VALUE,
                }],
                "resolver_readers": ["clarification_authority_resolver"],
                "consumer_manifest": self.promotion.registered_machine_reader_manifest(),
            }
            ok, message, _ = self.promotion.prepare_generation(Path(tmp) / "run", root, "promotion-001", base)
            self.assertFalse(ok)
            self.assertIn("stale", message)
            base["entries"][0]["path"] = "../outside.md"
            ok, message, _ = self.promotion.prepare_generation(Path(tmp) / "run", root, "promotion-002", base)
            self.assertFalse(ok)
            self.assertIn("unsafe", message)

    def test_generation_prepare_rejects_hardlink_authority_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repository"
            root.mkdir()
            authority = root / "authority.md"
            authority.write_text("before\n", encoding="utf-8", newline="\n")
            (root / "candidate.md").write_text("after\n", encoding="utf-8", newline="\n")
            alias = root / "authority-alias.md"
            try:
                os.link(authority, alias)
            except OSError as exc:
                self.skipTest(f"hardlinks unavailable: {exc}")
            write_set = {
                "schema_version": "vdd.clarification-generation-write-set.v1",
                "entries": [{
                    "path": "authority.md", "owner": "authority-owner", "candidate_path": "candidate.md",
                    "before_sha256": "sha256:" + hashlib.sha256(authority.read_bytes()).hexdigest(),
                }],
                "resolver_readers": ["clarification_authority_resolver"],
                "consumer_manifest": self.promotion.registered_machine_reader_manifest(),
            }
            ok, message, _ = self.promotion.prepare_generation(Path(tmp) / "run", root, "promotion-001", write_set)
            self.assertFalse(ok)
            self.assertIn("hardlink", message)

    def test_generation_rejects_unmigrated_direct_consumer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repository"
            root.mkdir()
            (root / "authority.md").write_text("before\n", encoding="utf-8", newline="\n")
            (root / "candidate.md").write_text("after\n", encoding="utf-8", newline="\n")
            write_set = {
                "schema_version": "vdd.clarification-generation-write-set.v1",
                "entries": [{
                    "path": "authority.md", "owner": "authority-owner", "candidate_path": "candidate.md",
                    "before_sha256": "sha256:" + hashlib.sha256((root / "authority.md").read_bytes()).hexdigest(),
                }],
                "resolver_readers": ["direct-markdown-reader"],
                "consumer_manifest": self.promotion.registered_machine_reader_manifest(),
            }
            ok, message, _ = self.promotion.prepare_generation(Path(tmp) / "run", root, "promotion-001", write_set)
            self.assertFalse(ok)
            self.assertIn("resolver reader", message)

    def test_generation_requires_the_complete_registered_machine_reader_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repository"
            root.mkdir()
            (root / "authority.md").write_text("before\n", encoding="utf-8", newline="\n")
            (root / "candidate.md").write_text("after\n", encoding="utf-8", newline="\n")
            write_set = {
                "schema_version": "vdd.clarification-generation-write-set.v1",
                "entries": [{
                    "path": "authority.md", "owner": "authority-owner", "candidate_path": "candidate.md",
                    "before_sha256": "sha256:" + hashlib.sha256((root / "authority.md").read_bytes()).hexdigest(),
                }],
                "resolver_readers": ["clarification_authority_resolver"],
            }
            valid, message, _ = self.promotion.validate_generation_write_set(root, write_set)
            self.assertFalse(valid)
            self.assertIn("consumer manifest", message)

    def test_concurrent_init_is_serialized_per_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            target = "execution-plans/example"
            target_root = (
                project_root
                / "logs"
                / "vdd-clarifications"
                / self.module._slug_for_target(target)
            )
            registry_root = self.module._canonical_registry_target_root(
                project_root,
                self.module._slug_for_target(target),
            )
            with self.module._target_lock(registry_root):
                first = start_cli(init_command(project_root, target, "run-a"))
                second = start_cli(init_command(project_root, target, "run-b"))
                time.sleep(0.2)
                self.assertIsNone(first.poll())
                self.assertIsNone(second.poll())

            outputs = [first.communicate(timeout=10), second.communicate(timeout=10)]
            payloads = []
            for process, (stdout, stderr) in zip((first, second), outputs):
                self.assertEqual(0, process.returncode, stdout + stderr)
                payloads.append(json.loads(stdout))
            self.assertEqual(
                ["initialized", "resume_required"],
                sorted(payload["status"] for payload in payloads),
            )
            states = list(target_root.glob("*/state.json"))
            self.assertEqual(1, len(states))
            self.assertEqual("active", json.loads(states[0].read_text(encoding="utf-8"))["status"])

    def test_different_evidence_roots_share_one_active_target_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            first = run_cli(
                *init_command(
                    project_root,
                    "execution-plans/example",
                    "run-a",
                    "logs/evidence-a",
                )
            )
            second = run_cli(
                *init_command(
                    project_root,
                    "execution-plans/example",
                    "run-b",
                    "logs/evidence-b",
                )
            )

            self.assertEqual(0, first.returncode, first.stdout + first.stderr)
            self.assertEqual(0, second.returncode, second.stdout + second.stderr)
            first_payload = json.loads(first.stdout)
            second_payload = json.loads(second.stdout)
            self.assertEqual("initialized", first_payload["status"])
            self.assertEqual("resume_required", second_payload["status"])
            self.assertEqual([first_payload["state"]], second_payload["active_states"])

    def test_concurrent_rounds_preserve_both_updates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            initialized = run_cli(*init_command(project_root, "execution-plans/example", "run-a"))
            self.assertEqual(0, initialized.returncode, initialized.stdout + initialized.stderr)
            state_path = Path(json.loads(initialized.stdout)["state"])
            payload_paths = []
            for round_id, first_question, boundary in (
                ("CR-001", 1, "Boundary one."),
                ("CR-002", 6, "Boundary two."),
            ):
                payload_path = Path(tmp) / f"{round_id}.json"
                payload_path.write_text(
                    json.dumps(round_payload(round_id, first_question, boundary), indent=2) + "\n",
                    encoding="utf-8",
                    newline="\n",
                )
                payload_paths.append(payload_path)

            state_before = json.loads(state_path.read_text(encoding="utf-8"))
            registry_root = self.module._canonical_registry_target_root(
                project_root,
                state_before["target_slug"],
            )
            with self.module._target_lock(registry_root):
                processes = [
                    start_cli(
                        [
                            "record-round",
                            "--state",
                            str(state_path),
                            "--round-file",
                            str(payload_path),
                        ]
                    )
                    for payload_path in payload_paths
                ]
                time.sleep(0.2)
                self.assertTrue(all(process.poll() is None for process in processes))

            for process in processes:
                stdout, stderr = process.communicate(timeout=10)
                self.assertEqual(0, process.returncode, stdout + stderr)
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual({"CR-001", "CR-002"}, {item["round_id"] for item in state["rounds"]})
            self.assertEqual(10, len(state["questions"]))
            self.assertEqual({"Boundary one.", "Boundary two."}, set(state["confirmed_boundaries"]))
            events = [
                json.loads(line)
                for line in (state_path.parent / "events.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(2, sum(event["event"] == "round_recorded" for event in events))

    def test_stable_question_definition_and_reopen_transition_are_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            initialized = run_cli(*init_command(project_root, "execution-plans/example", "run-a"))
            state_path = Path(json.loads(initialized.stdout)["state"])
            first_payload = round_payload("CR-001", 1, "Boundary one.")
            first_path = Path(tmp) / "first.json"
            first_path.write_text(
                json.dumps(first_payload, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            recorded = run_cli(
                "record-round", "--state", str(state_path), "--round-file", str(first_path)
            )
            self.assertEqual(0, recorded.returncode, recorded.stdout + recorded.stderr)

            for mutation in (
                {"summary": "Silently replaced summary."},
                {"status": "reopened"},
            ):
                with self.subTest(mutation=mutation):
                    changed = json.loads(json.dumps(first_payload))
                    changed["round_id"] = "CR-002"
                    changed["user_turn_id"] = "user-cr-002"
                    changed["questions"][0].update(mutation)
                    changed_path = Path(tmp) / "changed.json"
                    changed_path.write_text(
                        json.dumps(changed, indent=2) + "\n",
                        encoding="utf-8",
                        newline="\n",
                    )
                    rejected = run_cli(
                        "record-round",
                        "--state",
                        str(state_path),
                        "--round-file",
                        str(changed_path),
                    )
                    self.assertEqual(1, rejected.returncode, rejected.stdout + rejected.stderr)
                    self.assertEqual(
                        "VDD-CLARIFICATION-QUESTION-TRANSITION",
                        json.loads(rejected.stdout)["rule_id"],
                    )
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(1, len(state["rounds"]))
            self.assertEqual("Clarify boundary 1.", state["questions"][0]["summary"])

    def test_round_rejects_sensitive_or_unregistered_question_fields_without_persisting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            initialized = run_cli(*init_command(project_root, "execution-plans/example", "run-a"))
            state_path = Path(json.loads(initialized.stdout)["state"])
            for field_name, value in (
                ("accessToken", "not-a-real-token"),
                ("raw_user_text", "verbatim private conversation"),
                ("debugNote", "unregistered metadata"),
            ):
                with self.subTest(field_name=field_name):
                    payload = round_payload("CR-001", 1, "Boundary one.")
                    payload["questions"][0][field_name] = value
                    payload_path = Path(tmp) / f"{field_name}.json"
                    payload_path.write_text(
                        json.dumps(payload, indent=2) + "\n",
                        encoding="utf-8",
                        newline="\n",
                    )
                    rejected = run_cli(
                        "record-round",
                        "--state",
                        str(state_path),
                        "--round-file",
                        str(payload_path),
                    )
                    self.assertEqual(1, rejected.returncode, rejected.stdout + rejected.stderr)
                    state = json.loads(state_path.read_text(encoding="utf-8"))
                    self.assertEqual([], state["questions"])
                    self.assertEqual([], state["rounds"])

    def test_reopen_recomputes_blockers_and_rejects_superseded_questions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            for run_id, initial_status, expected_result in (
                ("run-answered", "answered", 0),
                ("run-superseded", "superseded", 1),
            ):
                with self.subTest(initial_status=initial_status):
                    initialized = run_cli(
                        *init_command(project_root, f"execution-plans/{run_id}", run_id)
                    )
                    state_path = Path(json.loads(initialized.stdout)["state"])
                    payload = round_payload("CR-001", 1, "Boundary one.")
                    for question in payload["questions"]:
                        question["status"] = "answered"
                    payload["questions"][0]["status"] = initial_status
                    payload["questions"][0]["blocking"] = True
                    payload_path = Path(tmp) / f"{run_id}-round.json"
                    payload_path.write_text(
                        json.dumps(payload, indent=2) + "\n",
                        encoding="utf-8",
                        newline="\n",
                    )
                    recorded = run_cli(
                        "record-round", "--state", str(state_path), "--round-file", str(payload_path)
                    )
                    self.assertEqual(0, recorded.returncode, recorded.stdout + recorded.stderr)
                    invalidated = run_cli(
                        "invalidate",
                        "--state",
                        str(state_path),
                        "--reason",
                        "Authority changed.",
                        "--current-authority-hash",
                        HASH_VALUE,
                        "--current-target-hash",
                        HASH_VALUE,
                    )
                    self.assertEqual(0, invalidated.returncode, invalidated.stdout + invalidated.stderr)
                    reopened = run_cli(
                        "reopen",
                        "--state",
                        str(state_path),
                        "--question-id",
                        "CQ-001",
                        "--reason",
                        "Recheck affected boundary.",
                    )
                    self.assertEqual(
                        expected_result,
                        reopened.returncode,
                        reopened.stdout + reopened.stderr,
                    )
                    state = json.loads(state_path.read_text(encoding="utf-8"))
                    if expected_result == 0:
                        self.assertEqual("active", state["status"])
                        self.assertEqual("reopened", state["questions"][0]["status"])
                        self.assertEqual(1, state["open_blocker_count"])
                    else:
                        self.assertEqual("invalidated", state["status"])
                        self.assertEqual("superseded", state["questions"][0]["status"])
                        self.assertEqual(
                            "VDD-CLARIFICATION-QUESTION-TRANSITION",
                            json.loads(reopened.stdout)["rule_id"],
                        )

    def test_pending_transition_recovers_event_once_before_next_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            initialized = run_cli(*init_command(project_root, "execution-plans/example", "run-a"))
            state_path = Path(json.loads(initialized.stdout)["state"])
            payload = round_payload("CR-001", 1, "Boundary one.")
            for question in payload["questions"]:
                question["status"] = "answered"
            round_path = Path(tmp) / "round.json"
            round_path.write_text(
                json.dumps(payload, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            self.assertEqual(
                0,
                run_cli(
                    "record-round", "--state", str(state_path), "--round-file", str(round_path)
                ).returncode,
            )
            exit_path = Path(tmp) / "exit.json"
            exit_path.write_text(
                json.dumps(
                    {
                        "actor": "user",
                        "explicit_no_more_clarification": True,
                        "explicit_write_permission": True,
                        "user_response_hash": HASH_VALUE,
                        "user_turn_id": "user-exit",
                        "summary": "The user explicitly ended clarification.",
                        "confidence": 96,
                        "current_authority_hash": HASH_VALUE,
                        "current_target_hash": HASH_VALUE,
                        "draft_only": False,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            with mock.patch.object(self.module, "_append_event", side_effect=OSError("injected")):
                with self.assertRaises(OSError):
                    self.module.command_close(
                        SimpleNamespace(state=str(state_path), exit_file=str(exit_path))
                    )
            self.assertTrue((state_path.parent / "pending-transition.json").is_file())
            self.assertEqual("closed", json.loads(state_path.read_text(encoding="utf-8"))["status"])

            result = self.module.command_invalidate(
                SimpleNamespace(
                    state=str(state_path),
                    reason="Authority changed after close.",
                    current_authority_hash=HASH_VALUE,
                    current_target_hash=HASH_VALUE,
                )
            )
            self.assertEqual("invalidated", result["status"])
            self.assertFalse((state_path.parent / "pending-transition.json").exists())
            events = [
                json.loads(line)
                for line in (state_path.parent / "events.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(
                1,
                sum(event["event"] == "clarification_exit_attested" for event in events),
            )
            transition_ids = [event.get("transition_id") for event in events]
            self.assertEqual(len(transition_ids), len(set(transition_ids)))

    def test_superseded_run_rejects_a_second_successor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            initialized = run_cli(*init_command(project_root, "execution-plans/example", "run-a"))
            state_path = Path(json.loads(initialized.stdout)["state"])
            first = run_cli(
                "supersede", "--state", str(state_path), "--successor-run-id", "run-b"
            )
            second = run_cli(
                "supersede", "--state", str(state_path), "--successor-run-id", "run-c"
            )
            self.assertEqual(0, first.returncode, first.stdout + first.stderr)
            self.assertEqual(1, second.returncode, second.stdout + second.stderr)
            self.assertEqual(
                "VDD-CLARIFICATION-STATE-TRANSITION",
                json.loads(second.stdout)["rule_id"],
            )
            events = [
                json.loads(line)
                for line in (state_path.parent / "events.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            successors = [event["successor_run_id"] for event in events if event["event"] == "superseded"]
            self.assertEqual(["run-b"], successors)

    def test_common_standalone_credentials_are_sensitive(self) -> None:
        values = (
            "ghp_abcdefghijklmnopqrstuvwxyz1234567890",
            "AKIAIOSFODNN7EXAMPLE",
        )
        for value in values:
            with self.subTest(value=value):
                self.assertEqual(["$.analysis"], self.module._sensitive_paths({"analysis": value}))

        sensitive_keys = ("accessToken", "raw_user_text", "rawUserInput")
        for key in sensitive_keys:
            with self.subTest(key=key):
                self.assertEqual([f"$.{key}"], self.module._sensitive_paths({key: "redacted"}))

    def test_recorded_event_has_a_hash_chain_and_immutable_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            initialized = run_cli(*init_command(project_root, "execution-plans/example", "run-a"))
            state_path = Path(json.loads(initialized.stdout)["state"])
            payload_path = Path(tmp) / "round.json"
            payload_path.write_text(
                json.dumps(round_payload("CR-001", 1, "Boundary one."), indent=2) + "\n",
                encoding="utf-8", newline="\n",
            )
            recorded = run_cli("record-round", "--state", str(state_path), "--round-file", str(payload_path))
            self.assertEqual(0, recorded.returncode, recorded.stdout + recorded.stderr)
            events = [json.loads(line) for line in (state_path.parent / "events.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual([1, 2], [event["sequence"] for event in events])
            self.assertIsNone(events[0]["predecessor_event_hash"])
            self.assertEqual(events[0]["event_hash"], events[1]["predecessor_event_hash"])
            self.assertEqual("user-cr-001", events[1]["user_turn_id"])
            self.assertEqual(HASH_VALUE, events[1]["authority_hash"])
            self.assertEqual(HASH_VALUE, events[1]["target_hash"])
            self.assertTrue(events[1]["event_id"])
            event_payload = {
                key: value for key, value in events[1].items()
                if key not in {"schema_version", "sequence", "predecessor_event_hash", "payload_hash", "payload_byte_length", "event_hash"}
            }
            self.assertEqual(len(self.module._canonical_bytes(event_payload)), events[1]["payload_byte_length"])
            self.assertEqual(self.module.REDUCER_VERSION, events[1]["reducer_version"])
            self.assertEqual(events[1]["state_projection"], json.loads(
                (state_path.parent / "snapshots" / "00000002.json").read_text(encoding="utf-8")
            )["state"])
            self.assertTrue((state_path.parent / "snapshots" / "00000002.json").is_file())

    def test_reducer_replay_rejects_event_projection_that_disagrees_with_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            initialized = run_cli(*init_command(project_root, "execution-plans/example", "run-a"))
            state_path = Path(json.loads(initialized.stdout)["state"])
            event_path = state_path.parent / "events.jsonl"
            event = json.loads(event_path.read_text(encoding="utf-8").splitlines()[0])
            event["state_projection"]["target"] = "forged-target"
            payload = {
                key: value for key, value in event.items()
                if key not in {"schema_version", "sequence", "predecessor_event_hash", "payload_hash", "payload_byte_length", "event_hash"}
            }
            event["payload_hash"] = self.module._canonical_hash(payload)
            event["payload_byte_length"] = len(self.module._canonical_bytes(payload))
            event["event_hash"] = self.module._canonical_hash({key: value for key, value in event.items() if key != "event_hash"})
            event_path.write_text(json.dumps(event) + "\n", encoding="utf-8", newline="\n")
            snapshot_path = state_path.parent / "snapshots" / "00000001.json"
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            snapshot["event_head"] = event["event_hash"]
            snapshot["snapshot_hash"] = self.module._canonical_hash(
                {key: value for key, value in snapshot.items() if key != "snapshot_hash"}
            )
            snapshot_path.write_text(json.dumps(snapshot) + "\n", encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(self.module.ClarificationCommandError, "projection") as raised:
                self.module._validate_event_chain(state_path.parent)
            self.assertEqual("VDD-CLARIFICATION-REDUCER-PROJECTION", raised.exception.rule_id)

    def test_restart_creates_one_successor_under_a_recoverable_target_transaction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            initialized = run_cli(*init_command(project_root, "execution-plans/example", "run-a"))
            self.assertEqual(0, initialized.returncode, initialized.stdout + initialized.stderr)
            predecessor = Path(json.loads(initialized.stdout)["state"])
            restarted = run_cli(
                "restart", "--state", str(predecessor), "--successor-run-id", "run-b", "--transition-id", "restart-001"
            )
            self.assertEqual(0, restarted.returncode, restarted.stdout + restarted.stderr)
            successor = Path(json.loads(restarted.stdout)["successor"])
            self.assertEqual("superseded", json.loads(predecessor.read_text(encoding="utf-8"))["status"])
            successor_state = json.loads(successor.read_text(encoding="utf-8"))
            self.assertEqual("active", successor_state["status"])
            self.assertEqual("run-a", successor_state["predecessor_run_id"])
            self.assertTrue((successor.parent / "legacy-bundle.json").is_file())
            retry = run_cli(
                "restart", "--state", str(predecessor), "--successor-run-id", "run-b", "--transition-id", "restart-001"
            )
            self.assertEqual(0, retry.returncode, retry.stdout + retry.stderr)
            self.assertTrue(json.loads(retry.stdout)["idempotent"])

    def test_successor_quarantines_when_legacy_bundle_member_drifts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            initialized = run_cli(*init_command(project_root, "execution-plans/example", "run-a"))
            predecessor = Path(json.loads(initialized.stdout)["state"])
            restarted = run_cli(
                "restart", "--state", str(predecessor), "--successor-run-id", "run-b", "--transition-id", "restart-001"
            )
            successor = Path(json.loads(restarted.stdout)["successor"])
            (predecessor.parent / "events.jsonl").write_text("tampered\n", encoding="utf-8", newline="\n")
            blocked = run_cli("status", "--state", str(successor))
            self.assertEqual(1, blocked.returncode, blocked.stdout + blocked.stderr)
            self.assertEqual("VDD-CLARIFICATION-LEGACY-QUARANTINE", json.loads(blocked.stdout)["rule_id"])

    def test_sensitive_incident_quarantines_and_disposes_every_run_local_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            initialized = run_cli(*init_command(project_root, "execution-plans/example", "run-a"))
            state_path = Path(json.loads(initialized.stdout)["state"])
            leaked = state_path.parent / "promotion-backup.txt"
            leaked.write_text("Bearer secret-value-12345678", encoding="utf-8", newline="\n")
            quarantined = run_cli(
                "quarantine", "--state", str(state_path), "--incident-id", "incident-001", "--reason", "sensitive value detected"
            )
            self.assertEqual(0, quarantined.returncode, quarantined.stdout + quarantined.stderr)
            custody = json.loads((state_path.parent / "sensitive-custody.json").read_text(encoding="utf-8"))
            self.assertEqual("quarantined-disposed", custody["status"])
            self.assertFalse(state_path.exists())
            self.assertFalse(leaked.exists())
            self.assertNotIn("secret-value", (state_path.parent / "sensitive-custody.json").read_text(encoding="utf-8"))
            blocked = run_cli("status", "--state", str(state_path))
            self.assertEqual(1, blocked.returncode, blocked.stdout + blocked.stderr)
            self.assertEqual("VDD-CLARIFICATION-SENSITIVE-QUARANTINE", json.loads(blocked.stdout)["rule_id"])

    def test_three_way_classifier_requires_owner_specific_deterministic_predicate(self) -> None:
        baseline = {"id": "TERM-001", "owner": "terms-owner", "value_hash": "sha256:" + "1" * 64, "consumers": ["reader"]}
        current = {"id": "TERM-001", "owner": "terms-owner", "value_hash": "sha256:" + "2" * 64, "consumers": ["reader"]}
        delta = {"id": "TERM-001", "owner": "terms-owner", "value_hash": "sha256:" + "3" * 64, "consumers": ["reader"]}
        self.assertEqual(("conflicting", "current authority changed without a deterministic compatible predicate"), self.promotion.classify_three_way_item(
            baseline, current, delta, []
        ))
        predicate = {
            "schema_version": "vdd.clarification-compatible-predicate.v1", "id": "TERM-001", "owner": "terms-owner",
            "baseline_hash": baseline["value_hash"], "current_hash": current["value_hash"], "delta_hash": delta["value_hash"],
            "consumer_hash": self.promotion.canonical_hash(["reader"]), "result": "compatible", "rule_version": "v1",
            "counterexample_rejected": True,
        }
        self.assertEqual(("compatible", "registered owner-specific predicate accepted the exact inputs"), self.promotion.classify_three_way_item(
            baseline, current, delta, [predicate]
        ))
        self.assertEqual(("unchanged", "current authority matches frozen baseline"), self.promotion.classify_three_way_item(
            baseline, baseline, delta, []
        ))
        self.assertFalse(self.promotion.validate_promotion_transition("blocked", "committed")[0])
        self.assertTrue(self.promotion.validate_promotion_transition("reserved", "committing")[0])

    def test_promotion_transaction_journal_rejects_illegal_commit_and_recovers_unknown_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            created, message, transaction = self.promotion.create_promotion_transaction(
                run_dir, "promotion-001", {"candidate_hash": HASH_VALUE, "event_head": HASH_VALUE}
            )
            self.assertTrue(created, message)
            self.assertEqual("prepared", transaction["state"])
            illegal, message, _ = self.promotion.transition_promotion_transaction(run_dir, "promotion-001", "committed")
            self.assertFalse(illegal)
            self.assertIn("illegal", message)
            self.assertTrue(self.promotion.transition_promotion_transaction(run_dir, "promotion-001", "reserved")[0])
            self.assertTrue(self.promotion.transition_promotion_transaction(run_dir, "promotion-001", "committing")[0])
            recovered, message, transaction = self.promotion.recover_promotion_transaction(run_dir, "promotion-001")
            self.assertTrue(recovered, message)
            self.assertEqual("recovery_required", transaction["state"])
            events = (run_dir / "promotion-transactions" / "promotion-001.events.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(4, len(events))

    def test_reserved_transaction_commits_only_after_complete_generation_is_staged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repository"
            root.mkdir()
            (root / "authority.md").write_text("before\n", encoding="utf-8", newline="\n")
            (root / "candidate.md").write_text("after\n", encoding="utf-8", newline="\n")
            before = "sha256:" + hashlib.sha256((root / "authority.md").read_bytes()).hexdigest()
            write_set = {
                "schema_version": "vdd.clarification-generation-write-set.v1",
                "entries": [{"path": "authority.md", "owner": "owner", "candidate_path": "candidate.md", "before_sha256": before}],
                "resolver_readers": ["clarification_authority_resolver"],
                "consumer_manifest": self.promotion.registered_machine_reader_manifest(),
            }
            run_dir = Path(tmp) / "run"
            prepared, message, generation = self.promotion.prepare_generation(run_dir, root, "promotion-001", write_set)
            self.assertTrue(prepared, message)
            manifest = json.loads((generation / "manifest.json").read_text(encoding="utf-8"))
            capability = {
                "issuer": "repository-local-hmac", "promotion_id": "promotion-001",
                "candidate_hash": HASH_VALUE, "nonce": "commit-nonce", "signature": "unit-test",
            }
            approval_path = Path(tmp) / "approval.json"
            approval_path.write_text(json.dumps(capability), encoding="utf-8", newline="\n")
            self.assertEqual((True, "reserved"), self.promotion.reserve_approval_nonce(
                run_dir, approval_path, "promotion-001", HASH_VALUE
            ))
            frozen_inputs = {
                "event_head": HASH_VALUE,
                "run_status": "closed",
                "exit_attestation_hash": HASH_VALUE,
                "baseline_manifest_hash": HASH_VALUE,
                "current_authority_manifest_hash": HASH_VALUE,
                "write_set_hash": self.promotion.canonical_hash(write_set),
                "generation_manifest_hash": manifest["manifest_hash"],
                "candidate_hash": HASH_VALUE,
                "approval_capability_hash": self.promotion.canonical_hash(capability),
            }
            self.assertTrue(self.promotion.create_promotion_transaction(
                run_dir, "promotion-001", {"clarification_freeze": frozen_inputs}
            )[0])
            self.assertTrue(self.promotion.transition_promotion_transaction(run_dir, "promotion-001", "reserved")[0])
            committed, message, result = self.promotion.commit_transaction_generation(run_dir, "promotion-001")
            self.assertTrue(committed, message)
            self.assertEqual("committed", result["transaction"]["state"])
            self.assertTrue(self.promotion.resolve_committed_generation(run_dir)[0])

    def test_transaction_commit_rejects_a_write_set_only_request_without_frozen_clarification_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repository"
            root.mkdir()
            (root / "authority.md").write_text("before\n", encoding="utf-8", newline="\n")
            (root / "candidate.md").write_text("after\n", encoding="utf-8", newline="\n")
            before = "sha256:" + hashlib.sha256((root / "authority.md").read_bytes()).hexdigest()
            write_set = {
                "schema_version": "vdd.clarification-generation-write-set.v1",
                "entries": [{"path": "authority.md", "owner": "owner", "candidate_path": "candidate.md", "before_sha256": before}],
                "resolver_readers": ["clarification_authority_resolver"],
                "consumer_manifest": self.promotion.registered_machine_reader_manifest(),
            }
            run_dir = Path(tmp) / "run"
            self.assertTrue(self.promotion.prepare_generation(run_dir, root, "promotion-001", write_set)[0])
            self.assertTrue(self.promotion.create_promotion_transaction(
                run_dir, "promotion-001", {"write_set_hash": self.promotion.canonical_hash(write_set)}
            )[0])
            self.assertTrue(self.promotion.transition_promotion_transaction(run_dir, "promotion-001", "reserved")[0])
            committed, message, _ = self.promotion.commit_transaction_generation(run_dir, "promotion-001")
            self.assertFalse(committed)
            self.assertIn("frozen clarification inputs", message)

    def test_transaction_commit_rejects_frozen_inputs_without_a_reserved_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repository"
            root.mkdir()
            (root / "authority.md").write_text("before\n", encoding="utf-8", newline="\n")
            (root / "candidate.md").write_text("after\n", encoding="utf-8", newline="\n")
            before = "sha256:" + hashlib.sha256((root / "authority.md").read_bytes()).hexdigest()
            write_set = {
                "schema_version": "vdd.clarification-generation-write-set.v1",
                "entries": [{"path": "authority.md", "owner": "owner", "candidate_path": "candidate.md", "before_sha256": before}],
                "resolver_readers": ["clarification_authority_resolver"],
                "consumer_manifest": self.promotion.registered_machine_reader_manifest(),
            }
            run_dir = Path(tmp) / "run"
            prepared, message, generation = self.promotion.prepare_generation(run_dir, root, "promotion-001", write_set)
            self.assertTrue(prepared, message)
            manifest = json.loads((generation / "manifest.json").read_text(encoding="utf-8"))
            freeze = {
                "event_head": HASH_VALUE, "run_status": "closed", "exit_attestation_hash": HASH_VALUE,
                "baseline_manifest_hash": HASH_VALUE, "current_authority_manifest_hash": HASH_VALUE,
                "write_set_hash": self.promotion.canonical_hash(write_set), "generation_manifest_hash": manifest["manifest_hash"],
                "candidate_hash": HASH_VALUE, "approval_capability_hash": HASH_VALUE,
            }
            self.assertTrue(self.promotion.create_promotion_transaction(
                run_dir, "promotion-001", {"clarification_freeze": freeze}
            )[0])
            self.assertTrue(self.promotion.transition_promotion_transaction(run_dir, "promotion-001", "reserved")[0])
            committed, message, _ = self.promotion.commit_transaction_generation(run_dir, "promotion-001")
            self.assertFalse(committed)
            self.assertIn("approval nonce", message)

    def test_transition_id_replay_with_a_different_payload_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            self.module._append_event(
                run_dir,
                {"event": "test", "at": "2026-07-23T00:00:00Z", "transition_id": "turn-001"},
            )
            with self.assertRaisesRegex(
                self.module.ClarificationCommandError,
                "transition ID was replayed with a different payload",
            ) as raised:
                self.module._append_event(
                    run_dir,
                    {"event": "test", "at": "2026-07-23T00:00:01Z", "transition_id": "turn-001"},
                )
            self.assertEqual("VDD-CLARIFICATION-IDEMPOTENCY", raised.exception.rule_id)

    def test_round_retry_is_idempotent_before_state_write_and_rejects_different_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            initialized = run_cli(*init_command(project_root, "execution-plans/example", "run-a"))
            state_path = Path(json.loads(initialized.stdout)["state"])
            payload = round_payload("CR-001", 1, "Boundary one.")
            payload_path = Path(tmp) / "round.json"
            payload_path.write_text(json.dumps(payload), encoding="utf-8", newline="\n")
            first = run_cli("record-round", "--state", str(state_path), "--round-file", str(payload_path))
            self.assertEqual(0, first.returncode, first.stdout + first.stderr)
            committed_state = state_path.read_bytes()
            retry = run_cli("record-round", "--state", str(state_path), "--round-file", str(payload_path))
            self.assertEqual(0, retry.returncode, retry.stdout + retry.stderr)
            self.assertTrue(json.loads(retry.stdout)["idempotent"])
            self.assertEqual(committed_state, state_path.read_bytes())
            payload["analysis"] = "A different replay payload."
            payload_path.write_text(json.dumps(payload), encoding="utf-8", newline="\n")
            rejected = run_cli("record-round", "--state", str(state_path), "--round-file", str(payload_path))
            self.assertEqual(1, rejected.returncode, rejected.stdout + rejected.stderr)
            self.assertEqual("VDD-CLARIFICATION-IDEMPOTENCY", json.loads(rejected.stdout)["rule_id"])
            self.assertEqual(committed_state, state_path.read_bytes())

    def test_promotion_preflight_rejects_active_run_without_writing_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            initialized = run_cli(*init_command(project_root, "execution-plans/example", "run-a"))
            state_path = Path(json.loads(initialized.stdout)["state"])
            before = state_path.read_bytes()
            completed = subprocess.run(
                [
                    sys.executable, str(PROMOTION_SCRIPT), "--state", str(state_path),
                    "--promotion-id", "promotion-001", "--candidate-hash", HASH_VALUE,
                    "--current-authority-hash", HASH_VALUE, "--current-target-hash", HASH_VALUE,
                ],
                check=False, capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(1, completed.returncode, completed.stdout + completed.stderr)
            result = json.loads(completed.stdout)
            self.assertEqual("blocked", result["status"])
            self.assertEqual("VDD-CLARIFICATION-PROMOTION-RUN-STATE", result["rule_id"])
            self.assertEqual([], result["authorizes"])
            self.assertEqual(before, state_path.read_bytes())
            attempts = (state_path.parent / "promotion-attempts.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(1, len(attempts))
            self.assertEqual(0, json.loads(attempts[0])["authority_write_count"])

    def test_tampered_event_blocks_recovery_before_a_new_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            initialized = run_cli(*init_command(project_root, "execution-plans/example", "run-a"))
            state_path = Path(json.loads(initialized.stdout)["state"])
            event_path = state_path.parent / "events.jsonl"
            event = json.loads(event_path.read_text(encoding="utf-8").splitlines()[0])
            event["run_id"] = "forged-run"
            event_path.write_text(json.dumps(event) + "\n", encoding="utf-8", newline="\n")
            status = run_cli("status", "--state", str(state_path))
            self.assertEqual(1, status.returncode, status.stdout + status.stderr)
            self.assertEqual("VDD-CLARIFICATION-EVENT-INTEGRITY", json.loads(status.stdout)["rule_id"])

    def test_partial_event_tail_blocks_recovery_with_a_stable_rule(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            initialized = run_cli(*init_command(project_root, "execution-plans/example", "run-a"))
            state_path = Path(json.loads(initialized.stdout)["state"])
            event_path = state_path.parent / "events.jsonl"
            event_path.write_bytes(event_path.read_bytes() + b'{"truncated":')
            status = run_cli("status", "--state", str(state_path))
            self.assertEqual(1, status.returncode, status.stdout + status.stderr)
            self.assertEqual("VDD-CLARIFICATION-EVENT-INTEGRITY", json.loads(status.stdout)["rule_id"])

    def test_tampered_snapshot_blocks_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            initialized = run_cli(*init_command(project_root, "execution-plans/example", "run-a"))
            state_path = Path(json.loads(initialized.stdout)["state"])
            snapshot_path = state_path.parent / "snapshots" / "00000001.json"
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            snapshot["state"]["target"] = "forged"
            snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8", newline="\n")
            status = run_cli("status", "--state", str(state_path))
            self.assertEqual(1, status.returncode, status.stdout + status.stderr)
            self.assertEqual("VDD-CLARIFICATION-SNAPSHOT-LINEAGE", json.loads(status.stdout)["rule_id"])

    def test_tampered_state_projection_blocks_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            initialized = run_cli(*init_command(project_root, "execution-plans/example", "run-a"))
            state_path = Path(json.loads(initialized.stdout)["state"])
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["non_goals"] = ["forged"]
            state_path.write_text(json.dumps(state), encoding="utf-8", newline="\n")
            status = run_cli("status", "--state", str(state_path))
            self.assertEqual(1, status.returncode, status.stdout + status.stderr)
            self.assertEqual("VDD-CLARIFICATION-REDUCER-PROJECTION", json.loads(status.stdout)["rule_id"])

    def test_registry_anchor_detects_a_complete_event_and_snapshot_tail_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            initialized = run_cli(*init_command(project_root, "execution-plans/example", "run-a"))
            state_path = Path(json.loads(initialized.stdout)["state"])
            (state_path.parent / "events.jsonl").unlink()
            (state_path.parent / "snapshots" / "00000001.json").unlink()
            status = run_cli("status", "--state", str(state_path))
            self.assertEqual(1, status.returncode, status.stdout + status.stderr)
            self.assertEqual("VDD-CLARIFICATION-REGISTRY-ANCHOR", json.loads(status.stdout)["rule_id"])

    def test_event_chain_rejects_a_rehashed_duplicate_event_or_transition_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            initialized = run_cli(*init_command(project_root, "execution-plans/example", "run-a"))
            state_path = Path(json.loads(initialized.stdout)["state"])
            run_dir = state_path.parent
            first = json.loads((run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()[0])
            duplicate = dict(first)
            duplicate["sequence"] = 2
            duplicate["predecessor_event_hash"] = first["event_hash"]
            duplicate["event_hash"] = self.module._canonical_hash(
                {key: value for key, value in duplicate.items() if key != "event_hash"}
            )
            (run_dir / "events.jsonl").write_text(
                json.dumps(first) + "\n" + json.dumps(duplicate) + "\n", encoding="utf-8", newline="\n"
            )
            snapshot = json.loads((run_dir / "snapshots" / "00000001.json").read_text(encoding="utf-8"))
            snapshot["sequence"] = 2
            snapshot["event_head"] = duplicate["event_hash"]
            snapshot["snapshot_hash"] = self.module._canonical_hash(
                {key: value for key, value in snapshot.items() if key != "snapshot_hash"}
            )
            (run_dir / "snapshots" / "00000002.json").write_text(
                json.dumps(snapshot), encoding="utf-8", newline="\n"
            )
            status = run_cli("status", "--state", str(state_path))
            self.assertEqual(1, status.returncode, status.stdout + status.stderr)
            self.assertEqual("VDD-CLARIFICATION-EVENT-INTEGRITY", json.loads(status.stdout)["rule_id"])

    def test_round_rejects_invalid_question_type_and_unsatisfied_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            initialized = run_cli(*init_command(project_root, "execution-plans/example", "run-a"))
            state_path = Path(json.loads(initialized.stdout)["state"])
            for name, mutate in (
                ("missing-type", lambda payload: payload["questions"][0].pop("primary_type")),
                ("type", lambda payload: payload["questions"][0].update({"primary_type": "unknown"})),
                ("dependency", lambda payload: payload["questions"][0].update({"depends_on": ["CQ-999"]})),
            ):
                payload = round_payload("CR-001", 1, "Boundary one.")
                mutate(payload)
                path = Path(tmp) / f"{name}.json"
                path.write_text(json.dumps(payload), encoding="utf-8", newline="\n")
                rejected = run_cli("record-round", "--state", str(state_path), "--round-file", str(path))
                self.assertEqual(1, rejected.returncode, rejected.stdout + rejected.stderr)

    def test_round_rejects_unbound_term_and_decision_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            initialized = run_cli(*init_command(project_root, "execution-plans/example", "run-a"))
            state_path = Path(json.loads(initialized.stdout)["state"])
            for name, field in (("term", "term_candidates"), ("decision", "decision_candidates")):
                payload = round_payload("CR-001", 1, "Boundary one.")
                payload["questions"][0][field] = [{"id": "candidate-001"}]
                path = Path(tmp) / f"{name}.json"
                path.write_text(json.dumps(payload), encoding="utf-8", newline="\n")
                rejected = run_cli("record-round", "--state", str(state_path), "--round-file", str(path))
                self.assertEqual(1, rejected.returncode, rejected.stdout + rejected.stderr)

    def test_round_persists_source_bound_term_and_decision_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            initialized = run_cli(*init_command(project_root, "execution-plans/example", "run-a"))
            state_path = Path(json.loads(initialized.stdout)["state"])
            payload = round_payload("CR-001", 1, "Boundary one.")
            payload["questions"][0]["term_candidates"] = [{
                "id": "TERM-001", "source_cq": "CQ-001", "definition": "A bounded term.",
                "scope": "clarification", "replaces": ["legacy term"],
            }]
            payload["questions"][0]["decision_candidates"] = [{
                "id": "ADR-CANDIDATE-001", "source_cq": "CQ-001", "irreversible": True,
                "context_sensitive": True, "tradeoff": "cost versus auditability",
                "evidence_refs": ["CQ-001"], "repository_adr_required": False,
                "disposition": "candidate_only",
            }]
            path = Path(tmp) / "candidates.json"
            path.write_text(json.dumps(payload), encoding="utf-8", newline="\n")
            recorded = run_cli("record-round", "--state", str(state_path), "--round-file", str(path))
            self.assertEqual(0, recorded.returncode, recorded.stdout + recorded.stderr)
            recovered = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual("TERM-001", recovered["questions"][0]["term_candidates"][0]["id"])
            self.assertEqual("ADR-CANDIDATE-001", recovered["questions"][0]["decision_candidates"][0]["id"])

    def test_round_rejects_invalid_scenario_probe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            initialized = run_cli(*init_command(project_root, "execution-plans/example", "run-a"))
            state_path = Path(json.loads(initialized.stdout)["state"])
            payload = round_payload("CR-001", 1, "Boundary one.")
            payload["questions"][0]["scenario_probe"] = {"kind": "invented"}
            path = Path(tmp) / "scenario.json"
            path.write_text(json.dumps(payload), encoding="utf-8", newline="\n")
            rejected = run_cli("record-round", "--state", str(state_path), "--round-file", str(path))
            self.assertEqual(1, rejected.returncode, rejected.stdout + rejected.stderr)


if __name__ == "__main__":
    unittest.main()
