from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = SKILL_ROOT / "scripts" / "clarification_state.py"
HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64
HASH_C = "sha256:" + "c" * 64


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["py", "-3", "-B", str(SCRIPT), *args], text=True, capture_output=True, check=False)


def init_state(root: Path, run_id: str = "resume-1", mode: str = "create") -> Path:
    result = run(
        "init",
        "--project-root",
        str(root),
        "--target",
        "execution-plans/example",
        "--mode",
        mode,
        "--authority-hash",
        HASH_A,
        "--target-hash",
        HASH_A,
        "--run-id",
        run_id,
    )
    if result.returncode != 0:
        raise AssertionError(result.stdout or result.stderr)
    return Path(json.loads(result.stdout)["state"])


def write_decisions(path: Path, decisions: list[dict[str, object]]) -> None:
    path.write_text(json.dumps({"decisions": decisions}), encoding="utf-8", newline="\n")


def decision(
    decision_id: str,
    *,
    summary: str | None = None,
    kind: str = "fact_gap",
    status: str = "open",
    depends_on: list[str] | None = None,
    material: bool = True,
) -> dict[str, object]:
    return {
        "id": decision_id,
        "summary": summary or f"Decision {decision_id}",
        "material": material,
        "status": status,
        "kind": kind,
        "depends_on": depends_on or [],
    }


class ClarificationResumeTests(unittest.TestCase):
    def test_resume_state_is_optional_v3_and_single_writer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            state = init_state(root)
            stored = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual("vdd.clarification-resume.v3", stored["schema_version"])
            resumed = run(
                "init",
                "--project-root",
                str(root),
                "--target",
                "execution-plans/example",
                "--mode",
                "create",
                "--authority-hash",
                HASH_A,
                "--target-hash",
                HASH_A,
                "--run-id",
                "resume-1",
            )
            self.assertEqual("resume", json.loads(resumed.stdout)["status"])
            self.assertFalse((root / ".vdd-clarification-registry").exists())
            self.assertFalse((root / "vdd-clarification-registry").exists())

    def test_typed_acyclic_decision_graph_is_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            state = init_state(root)
            payload = Path(tmp) / "decisions.json"
            decisions = [
                decision("CQ-001", status="resolved"),
                decision("CQ-002", kind="user_decision", status="resolved", depends_on=["CQ-001"]),
                decision("CQ-003", kind="authority_conflict", depends_on=["CQ-002"]),
            ]
            write_decisions(payload, decisions)
            recorded = run("record", "--project-root", str(root), "--state", str(state), "--decisions-file", str(payload))
            self.assertEqual(0, recorded.returncode, recorded.stdout)
            self.assertEqual(decisions, json.loads(state.read_text(encoding="utf-8"))["decisions"])

    def test_invalid_decision_graphs_fail_without_mutation(self) -> None:
        invalid_cases = {
            "unknown-kind": [decision("CQ-001", kind="other")],
            "non-string-kind": [decision("CQ-001", kind=["fact_gap"])],
            "duplicate-id": [decision("CQ-001"), decision("CQ-001")],
            "self-dependency": [decision("CQ-001", depends_on=["CQ-001"])],
            "missing-dependency": [decision("CQ-001", depends_on=["CQ-999"])],
            "duplicate-dependency": [decision("CQ-001"), decision("CQ-002", depends_on=["CQ-001", "CQ-001"])],
            "non-string-dependency": [decision("CQ-001", depends_on=[["CQ-999"]])],
            "cycle": [decision("CQ-001", depends_on=["CQ-002"]), decision("CQ-002", depends_on=["CQ-001"])],
            "resolved-before-parent": [decision("CQ-001"), decision("CQ-002", status="resolved", depends_on=["CQ-001"])],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            payload = Path(tmp) / "decisions.json"
            for index, (case_id, decisions) in enumerate(invalid_cases.items(), 1):
                with self.subTest(case_id=case_id):
                    state = init_state(root, f"resume-{index}")
                    before = state.read_bytes()
                    write_decisions(payload, decisions)
                    result = run("record", "--project-root", str(root), "--state", str(state), "--decisions-file", str(payload))
                    self.assertEqual(1, result.returncode)
                    self.assertIn(json.loads(result.stdout)["rule_id"], {"VDD-CLARIFICATION-DECISION", "VDD-CLARIFICATION-DEPENDENCY"})
                    self.assertEqual(before, state.read_bytes())

    def test_deep_acyclic_decision_graph_does_not_recurse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            state = init_state(root)
            payload = Path(tmp) / "decisions.json"
            decisions = [
                decision(f"CQ-{index:04d}", depends_on=[] if index == 1 else [f"CQ-{index - 1:04d}"])
                for index in range(1, 1501)
            ]
            write_decisions(payload, decisions)
            recorded = run("record", "--project-root", str(root), "--state", str(state), "--decisions-file", str(payload))
            self.assertEqual(0, recorded.returncode, recorded.stdout or recorded.stderr)

    def test_only_material_unresolved_decisions_block_close(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            state = init_state(root, mode="repair")
            payload = Path(tmp) / "decisions.json"
            write_decisions(payload, [decision("CQ-001")])
            self.assertEqual(0, run("record", "--project-root", str(root), "--state", str(state), "--decisions-file", str(payload)).returncode)
            blocked = run("close", "--project-root", str(root), "--state", str(state))
            self.assertEqual("VDD-CLARIFICATION-BLOCKER", json.loads(blocked.stdout)["rule_id"])
            write_decisions(payload, [])
            self.assertEqual(0, run("record", "--project-root", str(root), "--state", str(state), "--decisions-file", str(payload)).returncode)
            self.assertEqual("closed", json.loads(run("close", "--project-root", str(root), "--state", str(state)).stdout)["status"])

    def test_stale_is_byte_preserving_then_invalidate_and_reopen_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            state = init_state(root)
            self.assertEqual("closed", json.loads(run("close", "--project-root", str(root), "--state", str(state)).stdout)["status"])
            before_stale = state.read_bytes()
            stale = run(
                "init",
                "--project-root",
                str(root),
                "--target",
                "execution-plans/example",
                "--mode",
                "create",
                "--authority-hash",
                HASH_B,
                "--target-hash",
                HASH_C,
                "--run-id",
                "resume-1",
            )
            self.assertEqual("stale", json.loads(stale.stdout)["status"])
            self.assertEqual(before_stale, state.read_bytes())
            invalidated = run("invalidate", "--project-root", str(root), "--state", str(state))
            self.assertEqual("invalidated", json.loads(invalidated.stdout)["status"])
            before_repeat = state.read_bytes()
            self.assertEqual(0, run("invalidate", "--project-root", str(root), "--state", str(state)).returncode)
            self.assertEqual(before_repeat, state.read_bytes())
            self.assertEqual(1, run("close", "--project-root", str(root), "--state", str(state)).returncode)
            payload = Path(tmp) / "decisions.json"
            write_decisions(payload, [])
            self.assertEqual(1, run("record", "--project-root", str(root), "--state", str(state), "--decisions-file", str(payload)).returncode)
            reopened = run("reopen", "--project-root", str(root), "--state", str(state), "--authority-hash", HASH_B, "--target-hash", HASH_C)
            self.assertEqual("active", json.loads(reopened.stdout)["status"])
            stored = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual([], stored["decisions"])
            self.assertEqual(HASH_B, stored["authority_hash"])
            self.assertEqual(HASH_C, stored["target_hash"])
            before_invalid_reopen = state.read_bytes()
            self.assertEqual(1, run("reopen", "--project-root", str(root), "--state", str(state), "--authority-hash", HASH_B, "--target-hash", HASH_C).returncode)
            self.assertEqual(before_invalid_reopen, state.read_bytes())

    def test_mode_mismatch_is_not_reported_as_recoverable_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            state = init_state(root, mode="create")
            before = state.read_bytes()
            result = run(
                "init",
                "--project-root",
                str(root),
                "--target",
                "execution-plans/example",
                "--mode",
                "repair",
                "--authority-hash",
                HASH_A,
                "--target-hash",
                HASH_A,
                "--run-id",
                "resume-1",
            )
            self.assertEqual("VDD-CLARIFICATION-IDENTITY", json.loads(result.stdout)["rule_id"])
            self.assertEqual(before, state.read_bytes())

    def test_invalid_reopen_hash_is_byte_preserving(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            state = init_state(root)
            self.assertEqual(0, run("invalidate", "--project-root", str(root), "--state", str(state)).returncode)
            before = state.read_bytes()
            result = run("reopen", "--project-root", str(root), "--state", str(state), "--authority-hash", "bad", "--target-hash", HASH_A)
            self.assertEqual("VDD-CLARIFICATION-SCHEMA", json.loads(result.stdout)["rule_id"])
            self.assertEqual(before, state.read_bytes())

    def test_legacy_inspection_requires_exact_hash_and_never_mutates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            legacy_dir = root / "logs" / "legacy"
            legacy_dir.mkdir(parents=True)
            legacy = legacy_dir / "state.json"
            legacy.write_text(json.dumps({"schema_version": "vdd.clarification-state.v1", "run_id": "legacy-1", "target": "execution-plans/example", "mode": "repair", "status": "closed"}), encoding="utf-8", newline="\n")
            before = legacy.read_bytes()
            digest = "sha256:" + hashlib.sha256(before).hexdigest()
            inspected = run("inspect-legacy", "--project-root", str(root), "--state", str(legacy), "--expected-sha256", digest)
            self.assertEqual(0, inspected.returncode, inspected.stdout)
            self.assertTrue(json.loads(inspected.stdout)["read_only"])
            self.assertEqual(before, legacy.read_bytes())
            relative = run(
                "inspect-legacy",
                "--project-root",
                str(root),
                "--state",
                "logs/legacy/state.json",
                "--expected-sha256",
                digest,
            )
            self.assertEqual(0, relative.returncode, relative.stdout)
            mismatch = run("inspect-legacy", "--project-root", str(root), "--state", str(legacy), "--expected-sha256", HASH_A)
            self.assertEqual("VDD-CLARIFICATION-LEGACY-HASH", json.loads(mismatch.stdout)["rule_id"])
            self.assertEqual(before, legacy.read_bytes())
            rejected = run("status", "--project-root", str(root), "--state", str(legacy))
            self.assertEqual("VDD-CLARIFICATION-LEGACY-READ-ONLY", json.loads(rejected.stdout)["rule_id"])
            self.assertEqual(before, legacy.read_bytes())
            legacy_v2 = legacy_dir / "state-v2.json"
            legacy_v2.write_text(
                json.dumps(
                    {
                        "schema_version": "vdd.clarification-resume.v2",
                        "project_root": str(root.resolve()),
                        "evidence_root": "logs/legacy",
                        "run_id": "legacy-2",
                        "target": "execution-plans/example",
                        "mode": "repair",
                        "authority_hash": HASH_A,
                        "target_hash": HASH_A,
                        "status": "closed",
                        "decisions": [],
                        "updated_at": "2026-07-24T00:00:00Z",
                    }
                ),
                encoding="utf-8",
                newline="\n",
            )
            v2_before = legacy_v2.read_bytes()
            v2_digest = "sha256:" + hashlib.sha256(v2_before).hexdigest()
            v2_result = run("inspect-legacy", "--project-root", str(root), "--state", str(legacy_v2), "--expected-sha256", v2_digest)
            self.assertEqual("vdd.clarification-resume.v2", json.loads(v2_result.stdout)["schema_version"])
            self.assertEqual(v2_before, legacy_v2.read_bytes())

    def test_malformed_legacy_v2_is_rejected_without_echo_or_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            legacy_dir = root / "logs" / "legacy"
            legacy_dir.mkdir(parents=True)
            legacy = legacy_dir / "state.json"
            internal_note = "internal diagnostic note"
            legacy.write_text(
                json.dumps(
                    {
                        "schema_version": "vdd.clarification-resume.v2",
                        "run_id": "legacy-2",
                        "target": "execution-plans/example",
                        "mode": "repair",
                        "status": {"internal_notes": internal_note},
                    }
                ),
                encoding="utf-8",
                newline="\n",
            )
            before = legacy.read_bytes()
            legacy_digest = "sha256:" + hashlib.sha256(before).hexdigest()
            result = run("inspect-legacy", "--project-root", str(root), "--state", str(legacy), "--expected-sha256", legacy_digest)
            self.assertEqual("VDD-CLARIFICATION-LEGACY-SCHEMA", json.loads(result.stdout)["rule_id"])
            self.assertNotIn(internal_note, result.stdout)
            self.assertEqual(before, legacy.read_bytes())

    def test_sensitive_payload_quarantines_current_run_without_echo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            state = init_state(root)
            payload = Path(tmp) / "sensitive.json"
            secret = "ghp_1234567890abcdefghijkl"
            payload.write_text(json.dumps({"api_token": secret, "decisions": []}), encoding="utf-8", newline="\n")
            result = run("record", "--project-root", str(root), "--state", str(state), "--decisions-file", str(payload))
            self.assertEqual(1, result.returncode)
            self.assertNotIn(secret, result.stdout)
            self.assertNotIn("api_token", result.stdout)
            stored = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual("vdd.clarification-quarantine.v1", stored["schema_version"])
            self.assertEqual("quarantined", stored["status"])
            self.assertEqual({"schema_version", "status", "rule_id", "payload_sha256", "quarantined_at"}, set(stored))
            self.assertNotIn(secret, state.read_text(encoding="utf-8"))
            before_refusals = state.read_bytes()
            refused_commands = [
                ("status", "--project-root", str(root), "--state", str(state)),
                ("record", "--project-root", str(root), "--state", str(state), "--decisions-file", str(payload)),
                ("close", "--project-root", str(root), "--state", str(state)),
                ("invalidate", "--project-root", str(root), "--state", str(state)),
                ("reopen", "--project-root", str(root), "--state", str(state), "--authority-hash", HASH_A, "--target-hash", HASH_A),
                ("init", "--project-root", str(root), "--target", "execution-plans/example", "--mode", "create", "--authority-hash", HASH_A, "--target-hash", HASH_A, "--run-id", "resume-1"),
            ]
            for command in refused_commands:
                refused = run(*command)
                self.assertEqual("VDD-CLARIFICATION-QUARANTINED", json.loads(refused.stdout)["rule_id"])
                self.assertEqual(before_refusals, state.read_bytes())

    def test_sensitive_current_state_is_sanitized_after_containment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            state = init_state(root)
            stored = json.loads(state.read_text(encoding="utf-8"))
            stored["credential"] = "Bearer credential-value"
            state.write_text(json.dumps(stored), encoding="utf-8", newline="\n")
            result = run("status", "--project-root", str(root), "--state", str(state))
            self.assertEqual("VDD-CLARIFICATION-QUARANTINED", json.loads(result.stdout)["rule_id"])
            self.assertNotIn("credential-value", result.stdout)
            self.assertEqual("quarantined", json.loads(state.read_text(encoding="utf-8"))["status"])

    def test_duplicate_json_key_cannot_hide_sensitive_current_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            state = init_state(root)
            secret = "ghp_1234567890abcdefghijkl"
            hidden = json.dumps([decision("CQ-001", summary=f"Bearer {secret}")])
            original = state.read_text(encoding="utf-8")
            state.write_text(original.replace('"decisions": []', f'"decisions": {hidden},\n  "decisions": []'), encoding="utf-8", newline="\n")
            result = run("status", "--project-root", str(root), "--state", str(state))
            self.assertEqual("VDD-CLARIFICATION-QUARANTINED", json.loads(result.stdout)["rule_id"])
            self.assertNotIn(secret, result.stdout)
            self.assertNotIn(secret, state.read_text(encoding="utf-8"))

    def test_benign_token_metadata_and_bearer_wording_do_not_quarantine(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            state = init_state(root)
            payload = Path(tmp) / "decisions.json"
            payload.write_text(
                json.dumps({"token_count": 12, "decisions": [decision("CQ-001", summary="Confirm Bearer authentication behavior.")]}),
                encoding="utf-8",
                newline="\n",
            )
            result = run("record", "--project-root", str(root), "--state", str(state), "--decisions-file", str(payload))
            self.assertEqual(0, result.returncode, result.stdout)
            self.assertEqual("active", json.loads(state.read_text(encoding="utf-8"))["status"])

    def test_basic_authorization_value_quarantines_current_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            state = init_state(root)
            payload = Path(tmp) / "decisions.json"
            encoded = "dXNlcjpwYXNzd29yZA=="
            write_decisions(payload, [decision("CQ-001", summary=f"Authorization: Basic {encoded}")])
            result = run("record", "--project-root", str(root), "--state", str(state), "--decisions-file", str(payload))
            self.assertEqual("VDD-CLARIFICATION-QUARANTINED", json.loads(result.stdout)["rule_id"])
            self.assertNotIn(encoded, result.stdout)

    def test_sensitive_state_with_invalid_identity_fails_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            state = init_state(root)
            stored = json.loads(state.read_text(encoding="utf-8"))
            stored["run_id"] = "invalid run id"
            stored["credential"] = "Bearer credential-value"
            state.write_text(json.dumps(stored), encoding="utf-8", newline="\n")
            before = state.read_bytes()
            result = run("status", "--project-root", str(root), "--state", str(state))
            self.assertEqual("VDD-CLARIFICATION-SCHEMA", json.loads(result.stdout)["rule_id"])
            self.assertNotIn("credential-value", result.stdout)
            self.assertEqual(before, state.read_bytes())

    def test_sensitive_legacy_input_fails_digest_only_and_preserves_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            legacy = root / "legacy.json"
            secret = "sk-abcdefghijklmnop"
            legacy.write_text(json.dumps({"schema_version": "vdd.clarification-state.v1", "run_id": "legacy-1", "target": "example", "status": "closed", "note": secret}), encoding="utf-8", newline="\n")
            before = legacy.read_bytes()
            digest = "sha256:" + hashlib.sha256(before).hexdigest()
            result = run("inspect-legacy", "--project-root", str(root), "--state", str(legacy), "--expected-sha256", digest)
            envelope = json.loads(result.stdout)
            self.assertEqual("VDD-CLARIFICATION-LEGACY-SENSITIVE", envelope["rule_id"])
            self.assertEqual(digest, envelope["payload_sha256"])
            self.assertNotIn(secret, result.stdout)
            self.assertEqual(before, legacy.read_bytes())

    def test_path_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            escaped = run("init", "--project-root", str(root), "--target", "../outside", "--mode", "create", "--authority-hash", HASH_A, "--target-hash", HASH_A, "--run-id", "resume-1")
            self.assertEqual("VDD-CLARIFICATION-PATH", json.loads(escaped.stdout)["rule_id"])

    def test_current_state_path_must_match_target_and_run_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            state = init_state(root)
            copied = state.parents[2] / "copied" / "state.json"
            copied.parent.mkdir()
            copied.write_bytes(state.read_bytes())
            before = copied.read_bytes()
            result = run("invalidate", "--project-root", str(root), "--state", str(copied))
            self.assertEqual("VDD-CLARIFICATION-PATH", json.loads(result.stdout)["rule_id"])
            self.assertEqual(before, copied.read_bytes())

    def test_init_rejects_run_directory_symlink_outside_evidence_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            reference = init_state(root, run_id="reference")
            outside = Path(tmp) / "outside"
            outside.mkdir()
            link = reference.parent.parent / "linked-run"
            try:
                link.symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"directory symlinks unavailable: {exc}")
            result = run(
                "init",
                "--project-root",
                str(root),
                "--target",
                "execution-plans/example",
                "--mode",
                "create",
                "--authority-hash",
                HASH_A,
                "--target-hash",
                HASH_A,
                "--run-id",
                "linked-run",
            )
            self.assertEqual("VDD-CLARIFICATION-PATH", json.loads(result.stdout)["rule_id"])
            self.assertFalse((outside / "state.json").exists())


if __name__ == "__main__":
    unittest.main()
