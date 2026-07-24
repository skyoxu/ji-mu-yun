from __future__ import annotations

import base64
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = SKILL_ROOT / "scripts" / "clarification_state.py"
HASH_A = "sha256:" + "a" * 64


def load_clarification_state():
    spec = importlib.util.spec_from_file_location("clarification_state_review", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["py", "-3", "-B", str(SCRIPT), *args], text=True, capture_output=True, check=False)


def init_state(root: Path, run_id: str = "review-1") -> Path:
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
        run_id,
    )
    if result.returncode != 0:
        raise AssertionError(result.stdout or result.stderr)
    return Path(json.loads(result.stdout)["state"])


def decision(summary: str, *, status: str = "open") -> dict[str, object]:
    return {
        "id": "CQ-001",
        "summary": summary,
        "material": True,
        "status": status,
        "kind": "fact_gap",
        "depends_on": [],
    }


class ClarificationReviewRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.state_module = load_clarification_state()

    def test_sensitive_key_variants_and_common_credential_values_are_detected(self) -> None:
        for key in (
            "tokens",
            "credentials",
            "api_tokens",
            "passwords",
            "authorization_header",
            "password_hash",
            "conversation_history",
            "private_key_pem",
            "APIToken",
            "aws_secret_access_key",
        ):
            with self.subTest(key=key):
                self.assertTrue(self.state_module.is_sensitive_key(key))
        for value in (
            "github_pat_" + "A" * 30,
            "AIza" + "A" * 35,
            "postgresql://user:password@example.test/database",
            "ASIA" + "A" * 16,
            "aws_secret_access_key=" + "A" * 40,
        ):
            with self.subTest(value=value[:12]):
                self.assertTrue(self.state_module.is_sensitive_value(value))

    def test_common_credential_summary_quarantines_before_status_can_echo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            state = init_state(root)
            secret = "github_pat_" + "A" * 30
            payload = Path(tmp) / "decisions.json"
            payload.write_text(json.dumps({"decisions": [decision(secret)]}), encoding="utf-8", newline="\n")
            recorded = run("record", "--project-root", str(root), "--state", str(state), "--decisions-file", str(payload))
            self.assertEqual("VDD-CLARIFICATION-QUARANTINED", json.loads(recorded.stdout)["rule_id"])
            self.assertNotIn(secret, recorded.stdout)
            self.assertNotIn(secret, state.read_text(encoding="utf-8"))
            status = run("status", "--project-root", str(root), "--state", str(state))
            self.assertEqual("VDD-CLARIFICATION-QUARANTINED", json.loads(status.stdout)["rule_id"])

    def test_basic_wording_is_benign_but_encoded_credentials_quarantine(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            state = init_state(root)
            payload = Path(tmp) / "decisions.json"
            payload.write_text(
                json.dumps({"decisions": [decision("Document Basic authentication behavior.")]}),
                encoding="utf-8",
                newline="\n",
            )
            benign = run("record", "--project-root", str(root), "--state", str(state), "--decisions-file", str(payload))
            self.assertEqual(0, benign.returncode, benign.stdout or benign.stderr)
            encoded = base64.b64encode(b"user:password").decode("ascii")
            payload.write_text(
                json.dumps({"decisions": [decision(f"Authorization: Basic {encoded}")]}),
                encoding="utf-8",
                newline="\n",
            )
            sensitive = run("record", "--project-root", str(root), "--state", str(state), "--decisions-file", str(payload))
            self.assertEqual("VDD-CLARIFICATION-QUARANTINED", json.loads(sensitive.stdout)["rule_id"])

    def test_sensitive_location_bound_state_quarantines_before_vocabulary_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            state = init_state(root)
            stored = json.loads(state.read_text(encoding="utf-8"))
            stored["status"] = "corrupt"
            stored["credential"] = "Bearer " + "A" * 24
            state.write_text(json.dumps(stored), encoding="utf-8", newline="\n")
            result = run("status", "--project-root", str(root), "--state", str(state))
            self.assertEqual("VDD-CLARIFICATION-QUARANTINED", json.loads(result.stdout)["rule_id"])
            self.assertEqual("quarantined", json.loads(state.read_text(encoding="utf-8"))["status"])

    def test_windows_path_aliases_and_noncanonical_targets_are_rejected(self) -> None:
        for target in ("C:relative", "a//b", "a/./b", "execution-plans/CON"):
            with self.subTest(target=target):
                self.assertFalse(self.state_module.is_valid_target(target))
        for run_id in ("CON", "NUL", "COM1", "resume."):
            with self.subTest(run_id=run_id):
                self.assertFalse(self.state_module.is_valid_run_id(run_id))
        if os.name != "nt":
            return
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            state = init_state(root, "RunA")
            alias = run(
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
                "runa",
            )
            self.assertEqual("VDD-CLARIFICATION-IDENTITY", json.loads(alias.stdout)["rule_id"])
            self.assertEqual("RunA", json.loads(state.read_text(encoding="utf-8"))["run_id"])

    def test_closed_state_with_open_material_decision_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            state = init_state(root)
            stored = json.loads(state.read_text(encoding="utf-8"))
            stored["status"] = "closed"
            stored["decisions"] = [decision("Still unresolved")]
            state.write_text(json.dumps(stored), encoding="utf-8", newline="\n")
            before = state.read_bytes()
            result = run("status", "--project-root", str(root), "--state", str(state))
            self.assertEqual("VDD-CLARIFICATION-STATE", json.loads(result.stdout)["rule_id"])
            self.assertEqual(before, state.read_bytes())

    def test_excessive_json_nesting_returns_json_error_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            state = init_state(root)
            before = state.read_bytes()
            payload = Path(tmp) / "deep.json"
            payload.write_bytes(b'{"decisions":' + b"[" * 2000 + b"0" + b"]" * 2000 + b"}")
            result = run("record", "--project-root", str(root), "--state", str(state), "--decisions-file", str(payload))
            self.assertEqual(1, result.returncode)
            self.assertEqual("error", json.loads(result.stdout)["status"])
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(before, state.read_bytes())


if __name__ == "__main__":
    unittest.main()
