"""ADR-0060: only the publisher's exact immutable-shape mutex is metadata."""
import os
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.python import skill_input_v2 as v2
from scripts.python.skill_input_candidate import observe_candidate
from scripts.python.skill_input_protocol import digest, read_json
from scripts.python.tests.test_toolchain_workflow_repair_e2e import fixture

ROOT = Path(__file__).resolve().parents[3]
MUTEX = 'knowledge/indexes/.publication-acquire.lock'


def setup_mutex(root, *, ignored=True):
    request = fixture(root)
    path = root / MUTEX
    path.parent.mkdir(parents=True)
    if ignored:
        (root / '.git/info/exclude').write_text('/' + MUTEX + '\n', encoding='utf-8')
    return request, path


def test_actual_publisher_mutex_is_metadata_without_mutating_it(tmp_path, monkeypatch):
    request, path = setup_mutex(tmp_path)
    monkeypatch.syspath_prepend(str(ROOT / 'scripts/python'))
    from publish_knowledge_catalog import _acquisition_guard
    with _acquisition_guard(path.parent):
        assert path.read_bytes() == b'\0'
    before = path.stat()
    observed = observe_candidate(tmp_path, tmp_path / 'authority.json', request['storage'])
    assert MUTEX not in observed['changed_paths']
    assert v2.prepare(tmp_path, request)['status'] == 'prepared'
    after = path.stat()
    assert path.read_bytes() == b'\0'
    assert (before.st_ino, before.st_mode, before.st_size, before.st_mtime_ns) == (
        after.st_ino, after.st_mode, after.st_size, after.st_mtime_ns)


@pytest.mark.parametrize('payload', [b'', b'x', b'\0\0', b'{"content":true}'])
def test_unexpected_mutex_content_still_requires_review(tmp_path, payload):
    request, path = setup_mutex(tmp_path)
    path.write_bytes(payload)
    with pytest.raises(ValueError, match='review-required'):
        v2.prepare(tmp_path, request)


@pytest.mark.parametrize('neighbor', ['knowledge/indexes/publication.lock',
    'knowledge/indexes/.publication-acquire.lock.other',
    'knowledge/other/.publication-acquire.lock', 'knowledge/policies/consumer.json'])
def test_neighbor_and_ignored_knowledge_content_still_require_review(tmp_path, neighbor):
    request, path = setup_mutex(tmp_path)
    path.write_bytes(b'\0')
    other = tmp_path / neighbor
    other.parent.mkdir(parents=True, exist_ok=True)
    other.write_bytes(b'\0')
    with (tmp_path / '.git/info/exclude').open('a', encoding='utf-8') as out:
        out.write('/' + neighbor + '\n')
    with pytest.raises(ValueError, match='review-required'):
        v2.prepare(tmp_path, request)


def test_unignored_exact_path_is_not_silently_excluded(tmp_path):
    request, path = setup_mutex(tmp_path, ignored=False)
    path.write_bytes(b'\0')
    with pytest.raises(ValueError, match='review-required'):
        v2.prepare(tmp_path, request)


def test_tracked_mutex_change_remains_candidate_authority(tmp_path):
    request, path = setup_mutex(tmp_path)
    path.write_bytes(b'x')
    subprocess.run(['git', '-C', str(tmp_path), 'add', '-f', MUTEX], check=True)
    subprocess.run(['git', '-C', str(tmp_path), '-c', 'user.name=fixture',
        '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture tracked lock'], check=True)
    authority = read_json(tmp_path / 'authority.json')
    authority['skill_input_baseline'] = subprocess.check_output(
        ['git', '-C', str(tmp_path), 'rev-parse', 'HEAD'], text=True).strip()
    (tmp_path / 'authority.json').write_text(json.dumps(authority), encoding='utf-8')
    request['bindings']['authority']['sha256'] = digest((tmp_path / 'authority.json').read_bytes())
    path.write_bytes(b'\0')
    with pytest.raises(ValueError, match='review-required'):
        v2.prepare(tmp_path, request)


@pytest.mark.parametrize('commit_deletion', [False, True])
def test_baseline_tracked_deletion_with_ignored_recreated_mutex_requires_review(tmp_path, commit_deletion):
    request, path = setup_mutex(tmp_path)
    path.write_bytes(b'x')
    subprocess.run(['git', '-C', str(tmp_path), 'add', '-f', MUTEX], check=True)
    identity = ['-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid']
    subprocess.run(['git', '-C', str(tmp_path), *identity, 'commit', '-qm', 'fixture tracked lock'], check=True)
    authority = read_json(tmp_path / 'authority.json')
    authority['skill_input_baseline'] = subprocess.check_output(
        ['git', '-C', str(tmp_path), 'rev-parse', 'HEAD'], text=True).strip()
    (tmp_path / 'authority.json').write_text(json.dumps(authority), encoding='utf-8')
    request['bindings']['authority']['sha256'] = digest((tmp_path / 'authority.json').read_bytes())
    # Only this isolated Git fixture's index changes; keep the physical mutex.
    subprocess.run(['git', '-C', str(tmp_path), 'rm', '--cached', '-f', MUTEX], check=True)
    if commit_deletion:
        subprocess.run(['git', '-C', str(tmp_path), *identity, 'commit', '-qm', 'fixture untracked lock'], check=True)
    path.write_bytes(b'\0')
    observed = observe_candidate(tmp_path, tmp_path / 'authority.json', request['storage'])
    assert MUTEX in observed['changed_paths']
    with pytest.raises(ValueError, match='review-required'):
        v2.prepare(tmp_path, request)


@pytest.mark.parametrize('kind', ['symlink', 'directory', 'fifo', 'hardlink'])
def test_unsafe_mutex_shapes_do_not_qualify_as_metadata(tmp_path, kind):
    request, path = setup_mutex(tmp_path)
    if kind == 'symlink':
        other = tmp_path / 'real-lock'
        other.write_bytes(b'\0')
        path.symlink_to(other)
    elif kind == 'directory':
        path.mkdir()
    elif kind == 'fifo':
        if not hasattr(os, 'mkfifo'):
            pytest.skip('POSIX FIFO verification is not a Windows execution claim')
        os.mkfifo(path)
    elif kind == 'hardlink':
        other = tmp_path / 'real-lock'
        other.write_bytes(b'\0')
        os.link(other, path)
    with pytest.raises(ValueError, match='review-required|unsupported candidate object|symlink|reparse'):
        v2.prepare(tmp_path, request)


@pytest.mark.parametrize('mode', [0o600, 0o644, 0o755])
def test_publisher_umask_modes_do_not_change_the_single_byte_role(tmp_path, mode):
    request, path = setup_mutex(tmp_path)
    # os.open's publisher default is 0777 before umask; mode is not a payload.
    path.write_bytes(b'\0')
    path.chmod(mode)
    assert v2.prepare(tmp_path, request)['status'] == 'prepared'
    assert path.stat().st_mode & 0o777 == mode


def test_mutex_parent_symlink_cannot_qualify_as_metadata(tmp_path):
    request = fixture(tmp_path)
    outside = tmp_path / 'outside-index'
    outside.mkdir()
    (outside / '.publication-acquire.lock').write_bytes(b'\0')
    (tmp_path / 'knowledge').mkdir()
    (tmp_path / 'knowledge/indexes').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match='symlink|reparse'):
        v2.prepare(tmp_path, request)


def test_mutex_replacement_during_observation_fails_closed(tmp_path, monkeypatch):
    request, path = setup_mutex(tmp_path)
    path.write_bytes(b'\0')
    import scripts.python.skill_input_candidate as candidate
    if not hasattr(candidate, '_is_publisher_mutex_metadata'):
        pytest.fail('Publisher metadata classifier is missing')
    original = candidate.os.read
    inode = path.stat().st_ino
    def replace_while_reading(fd, size):
        result = original(fd, size)
        if os.fstat(fd).st_ino == inode:
            replacement = path.with_name('replacement')
            replacement.write_bytes(b'\0')
            replacement.replace(path)
        return result
    monkeypatch.setattr(candidate.os, 'read', replace_while_reading)
    with pytest.raises(ValueError, match='mutex changed'):
        observe_candidate(tmp_path, tmp_path / 'authority.json', request['storage'])
