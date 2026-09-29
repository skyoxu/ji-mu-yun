from __future__ import annotations

from pathlib import Path
import subprocess
import sys

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from runtime_evidence import current_snapshot


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
