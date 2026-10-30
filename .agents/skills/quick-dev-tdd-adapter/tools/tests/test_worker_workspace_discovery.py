"""ADR-0041: worker snapshots bind the selected workspace, never its ancestor."""
from pathlib import Path
import subprocess
import sys
import pytest
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / '.agents/skills/quick-dev-tdd-adapter/tools'))
from worker_orchestrator import workspace_snapshot, changed_paths, _validate_delta

def init(root):
    root.mkdir(exist_ok=True)
    subprocess.run(['git', 'init', '-q', str(root)], check=True)

def test_nested_workspace_does_not_inherit_parent_git_ignore(tmp_path):
    outer = tmp_path / 'outer'
    init(outer)
    (outer / '.gitignore').write_text('ignored/\n')
    root = outer / 'ignored' / 'task'
    root.mkdir(parents=True)
    source = root / 'subject.py'
    source.write_text('VALUE = 0\n')
    before = workspace_snapshot(root)
    assert before.get('subject.py') is not None
    source.write_text('VALUE = 1\n')
    delta = changed_paths(before, workspace_snapshot(root))
    assert delta == ['subject.py']
    with pytest.raises(ValueError, match='write-set violation'):
        _validate_delta(delta, allowed=['tests'], forbidden=['subject.py'], label='red-author')

def test_real_workspace_git_inventory_keeps_its_own_ignore_policy(tmp_path):
    init(tmp_path)
    (tmp_path / '.gitignore').write_text('ignored.py\n')
    (tmp_path / 'subject.py').write_text('VALUE = 0\n')
    (tmp_path / 'ignored.py').write_text('private test fixture, not an input\n')
    snapshot = workspace_snapshot(tmp_path)
    assert 'subject.py' in snapshot
    assert 'ignored.py' not in snapshot
