from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parents[3]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from repeat_guard import repeat_guard
from runtime_evidence import selector_identity_from_descriptor


def _descriptor(candidate: str, marker: str) -> dict:
    return {
        "run_id": "R3",
        "plan_id": "PLAN-REPEAT",
        "slice_id": "S1",
        "stage": "red",
        "candidate_hash": candidate,
        "argv": [sys.executable, "-c", f"from pathlib import Path; Path({marker!r}).write_text('executed', encoding='utf-8')"],
        "cwd": ".",
        "shell": False,
        "timeout_seconds": 30,
        "target_refs": ["tests/repeat_selector.py"],
        "fixture_refs": ["tests/repeat_fixture.txt"],
        "acceptance_assertions": [
            {
                "acceptance_id": "A-REPEAT",
                "assertion_id": "ASSERT-REPEAT",
                "case_source_ref": "tests/repeat_selector.py",
                "target_ref": "tests/repeat_selector.py",
                "fixture_ref": "tests/repeat_fixture.txt",
            }
        ],
    }


def _history(descriptor: dict) -> list[dict]:
    selector = selector_identity_from_descriptor(descriptor)
    fingerprint = "sha256:" + "a" * 64
    return [
        {
            "failure_fingerprint": fingerprint,
            "candidate_hash": descriptor["candidate_hash"],
            "selector_identity": selector,
        },
        {
            "failure_fingerprint": fingerprint,
            "candidate_hash": descriptor["candidate_hash"],
            "selector_identity": selector,
        },
    ]


def test_repeat_guard_blocks_third_identical_attempt_and_source_change_reenters() -> None:
    descriptor = _descriptor("sha256:" + "1" * 64, "unused.marker")
    history = _history(descriptor)
    blocked = repeat_guard(descriptor=descriptor, history=history)
    assert blocked["status"] == "blocked"
    assert blocked["failure_family"] == "repeated-deterministic-failure"
    assert blocked["tests_executed"] is False and blocked["process_attempts"] == 0

    changed = dict(descriptor)
    changed["candidate_hash"] = "sha256:" + "2" * 64
    resumed = repeat_guard(descriptor=changed, history=history)
    assert resumed["status"] == "continue"
    assert resumed["matching_prior_failures"] == 0


def test_public_entrypoint_never_launches_third_identical_command() -> None:
    scratch_parent = ROOT / ".tmp-ch456-repeat-guard"
    scratch_parent.mkdir(exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="case-", dir=scratch_parent) as raw:
            scratch = Path(raw)
            marker = scratch / "should-not-exist.marker"
            descriptor = _descriptor("sha256:" + "3" * 64, marker.as_posix())
            descriptor_path = scratch / "descriptor.json"
            history_path = scratch / "history.json"
            descriptor_path.write_text(json.dumps(descriptor), encoding="utf-8")
            history_path.write_text(json.dumps(_history(descriptor)), encoding="utf-8")
            command = [
                sys.executable,
                str(ROOT / "scripts" / "quick_dev" / "run.py"),
                "--plan", str(scratch / "plan"),
                "--slice", "S1",
                "--action", "execute-stage",
                "--run-dir", str(scratch / "R3"),
                "--descriptor", str(descriptor_path),
                "--failure-history", str(history_path),
            ]
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
            assert completed.returncode == 0, completed.stderr
            result = json.loads(completed.stdout)
            assert result["status"] == "blocked"
            assert result["failure_family"] == "repeated-deterministic-failure"
            assert result["process_attempts"] == 0 and result["tests_executed"] is False
            assert not marker.exists(), "third identical selector command must not execute"
    finally:
        if scratch_parent.is_dir() and not any(scratch_parent.iterdir()):
            scratch_parent.rmdir()
