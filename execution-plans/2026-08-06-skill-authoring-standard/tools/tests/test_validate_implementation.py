from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("validate_implementation", ROOT / "tools" / "validate_implementation.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class ValidateImplementationTests(unittest.TestCase):
    def _terminal_registry(self):
        return {
            "terminal_replay_command_ids": list(MODULE.REQUIRED_TERMINAL_COMMAND_IDS),
            "commands": [{
                "id": command_id,
                "executable": "py",
                "argv": MODULE.EXPECTED_TERMINAL_COMMAND_ARGV[command_id],
                "cwd": {"type": "repo_path", "value": "."},
                "timeout_seconds": 30,
                "shell": False,
            } for command_id in MODULE.REQUIRED_TERMINAL_COMMAND_IDS],
        }

    def test_missing_requires_files_and_fixture_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            original_root = MODULE.ROOT
            original_outputs = MODULE.REQUIRED_OUTPUTS
            original_directories = MODULE.REQUIRED_DIRECTORIES
            try:
                MODULE.ROOT = Path(directory)
                MODULE.REQUIRED_OUTPUTS = ["output.txt"]
                MODULE.REQUIRED_DIRECTORIES = ["fixtures"]
                (Path(directory) / "output.txt").mkdir()
                (Path(directory) / "fixtures").write_text("file", encoding="utf-8")
                self.assertEqual(["output.txt", "fixtures/"], MODULE.missing())
            finally:
                MODULE.ROOT = original_root
                MODULE.REQUIRED_OUTPUTS = original_outputs
                MODULE.REQUIRED_DIRECTORIES = original_directories

    def test_terminal_replay_executes_registered_commands(self) -> None:
        command_ids = list(MODULE.REQUIRED_TERMINAL_COMMAND_IDS)
        registry = self._terminal_registry()
        completed = type("Completed", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()
        with patch.object(MODULE.subprocess, "run", return_value=completed) as run:
            result = MODULE.run_terminal_replay(registry)
        self.assertEqual("passed", result["status"])
        self.assertEqual(command_ids, [item["commandId"] for item in result["commands"]])
        self.assertEqual(3, run.call_count)
        self.assertFalse(run.call_args.kwargs["shell"])

    def test_terminal_replay_fails_closed_on_registered_command_failure(self) -> None:
        command_ids = list(MODULE.REQUIRED_TERMINAL_COMMAND_IDS)
        registry = self._terminal_registry()
        completed = type("Completed", (), {"returncode": 1, "stdout": "", "stderr": "failed"})()
        with patch.object(MODULE.subprocess, "run", return_value=completed):
            result = MODULE.run_terminal_replay(registry)
        self.assertEqual("blocked", result["status"])
        self.assertEqual(1, result["commands"][0]["exitCode"])

    def test_terminal_replay_rejects_missing_or_reordered_required_commands(self) -> None:
        registry = {
            "terminal_replay_command_ids": ["standard-example-tests", "standard-contract-tests"],
            "commands": [],
        }
        result = MODULE.run_terminal_replay(registry)
        self.assertEqual("blocked", result["status"])
        self.assertIn("terminal-replay-command-set-incomplete-or-reordered", result["errors"])

    def test_terminal_replay_binds_id_to_expected_argv(self) -> None:
        registry = self._terminal_registry()
        registry["commands"][1]["argv"] = registry["commands"][0]["argv"]
        completed = type("Completed", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()
        with patch.object(MODULE.subprocess, "run", return_value=completed) as run:
            result = MODULE.run_terminal_replay(registry)
        self.assertEqual("blocked", result["status"])
        self.assertEqual(2, run.call_count)


if __name__ == "__main__":
    unittest.main()
