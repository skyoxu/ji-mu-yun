from __future__ import annotations

from pathlib import Path
import subprocess
import sys

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from runtime_evidence import current_snapshot
from coverage_predicates import _replay_snapshot
import pytest


def _init(root: Path) -> tuple[str, list[dict[str, str]]]:
    paths = {
        "src/value.py": "VALUE=1\n",
        "plan/semantic.json": "{}\n",
        "plan/contract.txt": "contract\n",
        "run/descriptors/red.json": "{}\n",
        "tests/fixture.txt": "fixture\n",
        "requirements.md": "# FR-1\nbehavior\n",
        "validators.txt": "validator\n",
        "state.json": "{}\n",
        "docs/note.md": "ordinary documentation\n",
    }
    for raw, text in paths.items():
        path = root / raw
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "snapshot@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Snapshot Harness"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=root, check=True, capture_output=True, text=True)
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
    roots = [
        {"root_kind": "candidate_tree", "repository_relative_posix_path": "src", "inclusion_reason": "candidate"},
        {"root_kind": "plan", "repository_relative_posix_path": "plan/semantic.json", "inclusion_reason": "plan"},
        {"root_kind": "contract", "repository_relative_posix_path": "plan/contract.txt", "inclusion_reason": "contract"},
        {"root_kind": "descriptor", "repository_relative_posix_path": "run/descriptors", "inclusion_reason": "descriptor"},
        {"root_kind": "fixture", "repository_relative_posix_path": "tests/fixture.txt", "inclusion_reason": "fixture"},
        {"root_kind": "source", "repository_relative_posix_path": "requirements.md", "inclusion_reason": "source"},
        {"root_kind": "validator_judge", "repository_relative_posix_path": "validators.txt", "inclusion_reason": "validator"},
        {"root_kind": "plan_state_transition", "repository_relative_posix_path": "state.json", "inclusion_reason": "state"},
    ]
    return base, roots


def test_ordinary_documentation_change_is_excluded_from_runtime_snapshot(tmp_path: Path) -> None:
    base, roots = _init(tmp_path)
    before = current_snapshot(tmp_path, roots, source_commit=base, base_commit=base)
    (tmp_path / "docs" / "note.md").write_text("ordinary documentation changed\n", encoding="utf-8")
    after = current_snapshot(tmp_path, roots, source_commit=base, base_commit=base)
    assert after["git_delta"] == {"base_commit": base, "additions": [], "deletions": [], "renames": []}
    assert after["sha256"] == before["sha256"]


def test_unknown_code_or_config_outside_runtime_roots_is_not_an_implicit_slice_input(tmp_path: Path) -> None:
    base, roots = _init(tmp_path)
    (tmp_path / "unknown.cfg").write_text("semantic_or_runtime_unknown=true\n", encoding="utf-8")
    snap = current_snapshot(tmp_path, roots, source_commit=base, base_commit=base)
    assert snap["git_delta"] == {"base_commit": base, "additions": [], "deletions": [], "renames": []}


def test_governance_provenance_change_is_excluded_when_not_explicitly_bound(tmp_path: Path) -> None:
    base, roots = _init(tmp_path)
    path = tmp_path / "_bmad-output" / "planning-artifacts" / "architecture" / "reviews" / "review-r19.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("provenance only\n", encoding="utf-8")
    snap = current_snapshot(tmp_path, roots, source_commit=base, base_commit=base)
    assert snap["git_delta"] == {"base_commit": base, "additions": [], "deletions": [], "renames": []}



def test_multi_path_plan_replay_allows_only_declared_append(tmp_path: Path) -> None:
    """ADR-0058: Acceptance delta allowance composes with frozen multi-path roots."""
    base, roots = _init(tmp_path)
    plan = next(row for row in roots if row["root_kind"] == "plan")
    plan.pop("repository_relative_posix_path")
    plan["repository_relative_posix_paths"] = ["plan/semantic.json", "plan/evidence"]
    (tmp_path / "plan/evidence").mkdir()
    frozen = {"snapshot_manifest": current_snapshot(tmp_path, roots, source_commit=base)}
    (tmp_path / "plan/evidence/result.json").write_text("{}", encoding="utf-8")
    assert _replay_snapshot(tmp_path, roots, base, None, frozen, ["plan/evidence"]) == frozen["snapshot_manifest"]
    (tmp_path / "plan/semantic.json").write_text('{"changed":true}', encoding="utf-8")
    with pytest.raises(ValueError, match="root stale: plan"):
        _replay_snapshot(tmp_path, roots, base, None, frozen, ["plan/evidence"])


def test_slice_snapshot_reuse_keeps_production_inputs_bound(tmp_path: Path) -> None:
    """ADR-0041: unrelated slice edits may reuse proof; owner drift cannot."""
    base, roots = _init(tmp_path)
    frozen = {"snapshot_manifest": current_snapshot(tmp_path, roots, source_commit=base)}
    (tmp_path / "src/other.py").write_text("OTHER=2\n", encoding="utf-8")
    inputs = ["src/value.py", "tests/fixture.txt"]
    assert _replay_snapshot(tmp_path, roots, base, None, frozen, slice_input_paths=inputs) == frozen["snapshot_manifest"]
    with pytest.raises(ValueError, match="root stale: candidate_tree"):
        _replay_snapshot(tmp_path, roots, base, None, frozen)
    (tmp_path / "src/value.py").write_text("VALUE=2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="root stale: candidate_tree"):
        _replay_snapshot(tmp_path, roots, base, None, frozen, slice_input_paths=inputs)
