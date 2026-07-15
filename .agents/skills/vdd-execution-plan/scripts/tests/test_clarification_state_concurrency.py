from __future__ import annotations

import importlib.util
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
PASS_FIXTURE = SKILL_ROOT / "scripts" / "fixtures" / "clarification-state-pass.json"
HASH_VALUE = "sha256:" + "a" * 64


def load_clarification_module():
    spec = importlib.util.spec_from_file_location("clarification_state_under_test", SCRIPT)
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


if __name__ == "__main__":
    unittest.main()
