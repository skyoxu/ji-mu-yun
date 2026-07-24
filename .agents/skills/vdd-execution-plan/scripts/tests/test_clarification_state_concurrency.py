from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = SKILL_ROOT / "scripts" / "clarification_state.py"
HASH = "sha256:" + "a" * 64


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["py", "-3", str(SCRIPT), *args], text=True, capture_output=True, check=False)


class ClarificationResumeTests(unittest.TestCase):
    def test_resume_state_is_optional_and_single_writer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            initialized = run("init", "--project-root", str(root), "--target", "execution-plans/example", "--mode", "create", "--authority-hash", HASH, "--target-hash", HASH, "--run-id", "resume-1")
            self.assertEqual(0, initialized.returncode, initialized.stderr)
            state = json.loads(initialized.stdout)["state"]
            resumed = run("init", "--project-root", str(root), "--target", "execution-plans/example", "--mode", "create", "--authority-hash", HASH, "--target-hash", HASH, "--run-id", "resume-1")
            self.assertEqual("resume", json.loads(resumed.stdout)["status"])
            self.assertFalse((root / ".vdd-clarification-registry").exists())
            self.assertFalse((root / "vdd-clarification-registry").exists())
            self.assertTrue(Path(state).is_file())

    def test_only_material_unresolved_decisions_block_close(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            state = json.loads(run("init", "--project-root", str(root), "--target", "execution-plans/example", "--mode", "repair", "--authority-hash", HASH, "--target-hash", HASH, "--run-id", "resume-1").stdout)["state"]
            decisions = Path(tmp) / "decisions.json"
            decisions.write_text(json.dumps({"decisions": [{"id": "CQ-001", "summary": "Confirm destructive boundary.", "material": True, "status": "open"}]}), encoding="utf-8", newline="\n")
            self.assertEqual(0, run("record", "--project-root", str(root), "--state", state, "--decisions-file", str(decisions)).returncode)
            blocked = run("close", "--project-root", str(root), "--state", state)
            self.assertEqual(1, blocked.returncode)
            self.assertEqual("VDD-CLARIFICATION-BLOCKER", json.loads(blocked.stdout)["rule_id"])
            decisions.write_text(json.dumps({"decisions": []}), encoding="utf-8", newline="\n")
            self.assertEqual(0, run("record", "--project-root", str(root), "--state", state, "--decisions-file", str(decisions)).returncode)
            self.assertEqual("closed", json.loads(run("close", "--project-root", str(root), "--state", state).stdout)["status"])

    def test_path_escape_and_sensitive_payload_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            escaped = run("init", "--project-root", str(root), "--target", "../outside", "--mode", "create", "--authority-hash", HASH, "--target-hash", HASH, "--run-id", "resume-1")
            self.assertEqual("VDD-CLARIFICATION-PATH", json.loads(escaped.stdout)["rule_id"])
            state = json.loads(run("init", "--project-root", str(root), "--target", "execution-plans/example", "--mode", "create", "--authority-hash", HASH, "--target-hash", HASH, "--run-id", "resume-2").stdout)["state"]
            payload = Path(tmp) / "sensitive.json"
            payload.write_text(json.dumps({"api_token": "nope", "decisions": []}), encoding="utf-8", newline="\n")
            rejected = run("record", "--project-root", str(root), "--state", state, "--decisions-file", str(payload))
            self.assertEqual("VDD-CLARIFICATION-MINIMIZATION", json.loads(rejected.stdout)["rule_id"])
            payload.write_text(json.dumps({"decisions": [{"id": "CQ-001", "summary": "Bearer token-value", "material": False, "status": "resolved"}]}), encoding="utf-8", newline="\n")
            rejected_value = run("record", "--project-root", str(root), "--state", state, "--decisions-file", str(payload))
            self.assertEqual("VDD-CLARIFICATION-MINIMIZATION", json.loads(rejected_value.stdout)["rule_id"])


if __name__ == "__main__":
    unittest.main()
