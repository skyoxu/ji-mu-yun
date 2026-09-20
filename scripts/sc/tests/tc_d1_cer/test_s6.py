"""CER coverage for S6 repair-boundary preservation checks."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
SC_DIR = ROOT / "scripts" / "sc"
if str(SC_DIR) not in sys.path:
    sys.path.insert(0, str(SC_DIR))

from _git_snapshot import current_git_fingerprint, git_snapshots_match, has_complete_content_identity  # noqa: E402


_CURRENT_SNAPSHOT_INPUT_CATEGORIES = {
    "git_baseline",
    "skill_input_v2_selection",
    "skill_input_v2_content",
    "code",
    "fixtures",
    "contracts",
    "consumers",
    "tests",
    "targets",
    "validators",
    "dependencies",
    "sources",
    "evidence",
    "normalization_policy",
}


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


def _repository(root: Path) -> None:
    _git(root, "init")
    _git(root, "config", "user.email", "review@example.invalid")
    _git(root, "config", "user.name", "Review Test")
    (root / "protected.txt").write_bytes(b"frozen protected bytes\n")
    _git(root, "add", "protected.txt")
    _git(root, "commit", "-m", "baseline")


def _tracked_paths(root: Path) -> set[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        text=True,
        encoding="utf-8",
    )
    return {line for line in result.stdout.splitlines() if line}


@pytest.mark.cer_assertion("ASSERT-O-88F036CDC1A1-BYTE-IMMUTABILITY")
def test_historical_byte_mutation_is_rejected_by_the_snapshot_comparison() -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as directory:
        root = Path(directory)
        _repository(root)
        baseline = current_git_fingerprint(root=root)

        (root / "protected.txt").write_bytes(b"changed protected bytes\n")
        candidate = current_git_fingerprint(root=root)

        mutation_rejected = (
            has_complete_content_identity(baseline)
            and has_complete_content_identity(candidate)
            and not git_snapshots_match(baseline, candidate)
        )
        if not mutation_rejected:
            print("FAILURE_ID:HISTORICAL_BYTE_MUTATION_REJECTED")
        assert mutation_rejected, "a changed protected historical byte was accepted"


@pytest.mark.cer_assertion("A-FR5-REPOSITORY_RELATIVE_PATHS-UNCHANGED")
def test_repository_relative_path_relocation_is_rejected_by_the_snapshot_comparison() -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as directory:
        root = Path(directory)
        _repository(root)
        baseline = current_git_fingerprint(root=root)
        baseline_paths = _tracked_paths(root)

        _git(root, "mv", "protected.txt", "relocated.txt")
        candidate = current_git_fingerprint(root=root)
        candidate_paths = _tracked_paths(root)

        mutation_rejected = (
            baseline_paths == {"protected.txt"}
            and candidate_paths == {"relocated.txt"}
            and has_complete_content_identity(baseline)
            and has_complete_content_identity(candidate)
            and not git_snapshots_match(baseline, candidate)
        )
        if not mutation_rejected:
            print("FAILURE_ID:REPOSITORY_RELATIVE_PATH_MUTATION")
        assert mutation_rejected, "a relocated repository-relative path was accepted"


@pytest.mark.cer_assertion("ASSERT-FR5-HISTORICAL-MEMBERSHIP-UNCHANGED")
def test_historical_membership_addition_is_rejected_by_the_snapshot_comparison() -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as directory:
        root = Path(directory)
        _repository(root)
        baseline = current_git_fingerprint(root=root)
        baseline_paths = _tracked_paths(root)

        (root / "added.txt").write_bytes(b"new tracked member\n")
        _git(root, "add", "added.txt")
        candidate = current_git_fingerprint(root=root)
        candidate_paths = _tracked_paths(root)

        mutation_rejected = (
            candidate_paths == baseline_paths | {"added.txt"}
            and has_complete_content_identity(baseline)
            and has_complete_content_identity(candidate)
            and not git_snapshots_match(baseline, candidate)
        )
        if not mutation_rejected:
            print("FAILURE_ID:HISTORICAL_MEMBERSHIP_MUTATION_REJECTED")
        assert mutation_rejected, "an added historical tracked member was accepted"


@pytest.mark.cer_assertion("ASSERT-SM6-SNAPSHOT-COMPLETE")
def test_current_snapshot_requires_each_result_determining_input_category() -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as directory:
        root = Path(directory)
        _repository(root)
        snapshot = current_git_fingerprint(root=root)
        inputs = snapshot.get("result_determining_inputs")
        snapshot_complete = (
            has_complete_content_identity(snapshot)
            and isinstance(inputs, dict)
            and _CURRENT_SNAPSHOT_INPUT_CATEGORIES <= set(inputs)
            and all(
                isinstance(inputs[category], dict)
                and isinstance(inputs[category].get("immutable_identity"), str)
                and inputs[category]["immutable_identity"].startswith("sha256:")
                for category in _CURRENT_SNAPSHOT_INPUT_CATEGORIES
            )
        )
        if not snapshot_complete:
            print("FAILURE_ID:SNAPSHOT_INPUT_OMISSION_REJECTED")
        assert snapshot_complete, "the Current Snapshot omitted a result-determining input category"
