"""Observe candidate changes against the authority-bound Git baseline (ADR-0060)."""
import fnmatch
import os
import re
import stat
import subprocess
from pathlib import Path
try:
    from .skill_input_protocol import contained, digest, identity, read_json, relative
except ImportError:
    from skill_input_protocol import contained, digest, identity, read_json, relative


def git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True, check=False)
    if result.returncode:
        raise ValueError('candidate Git baseline is unavailable or invalid')
    return result.stdout.decode('utf-8', errors='strict')


_PUBLISHER_MUTEX = 'knowledge/indexes/.publication-acquire.lock'


def _is_publisher_mutex_metadata(path):
    """ADR-0060: recognize the publisher's one-byte guard, not lock payloads.

    The caller requires the exact untracked, ignored publisher path. Keep the
    persistent mutex inode intact; never acquire, release, truncate or unlink it.
    """
    def stamp(value):
        return (value.st_dev, value.st_ino, value.st_mode, value.st_nlink,
                value.st_size, value.st_mtime_ns, value.st_ctime_ns)
    before = path.lstat()
    if (not stat.S_ISREG(before.st_mode) or before.st_size != 1
            or before.st_nlink != 1):
        return False
    descriptor = None
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
                             | getattr(os, 'O_NONBLOCK', 0))
        opened = os.fstat(descriptor)
        payload = os.read(descriptor, 2)
        after = os.fstat(descriptor)
        current = path.lstat()
        if not (stamp(before) == stamp(opened) == stamp(after) == stamp(current)):
            raise ValueError('publisher runtime mutex changed during observation')
        return payload == b'\0'
    except OSError as exc:
        raise ValueError('publisher runtime mutex changed during observation') from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def observe_candidate(root, authority_path, storage):
    root = Path(root).resolve()
    authority = read_json(authority_path)
    baseline = authority.get('skill_input_baseline')
    if not isinstance(baseline, str) or not re.fullmatch(r'[0-9a-f]{40}', baseline):
        raise ValueError('authority must bind a full skill_input_baseline Git commit')
    if Path(git(root, 'rev-parse', '--show-toplevel').strip()).resolve() != root:
        raise ValueError('candidate must use the repository root')
    git(root, 'merge-base', '--is-ancestor', baseline, 'HEAD')
    tracked_changes = set(filter(None, git(root, 'diff', '--no-ext-diff', '--no-renames', '--name-only', '-z', baseline, '--').split('\0')))
    changed = set(tracked_changes)
    changed.update(filter(None, git(root, 'ls-files', '--others', '--exclude-standard', '-z').split('\0')))
    # Ignore rules cannot conceal changes to Knowledge authority.
    ignored_knowledge = set(filter(None, git(root, 'ls-files', '--others', '--ignored', '--exclude-standard', '-z', '--',
        'knowledge/', '.agents/skills/maintain-knowledge-base/', ':(glob)scripts/python/*knowledge*.py').split('\0')))
    changed.update(ignored_knowledge)
    # Git may omit an empty ignored directory: an invalid mutex object must
    # still fail closed rather than disappear from its file inventory.
    mutex = contained(root, _PUBLISHER_MUTEX)
    if mutex.exists() and not mutex.is_file():
        raise ValueError('unsupported candidate object')
    target_plan = authority.get('target_plan')
    generated = {storage.rstrip('/') + '/', '.skill-input-work/'}
    if isinstance(target_plan, str) and target_plan:
        target_plan = target_plan.replace('\\', '/').rstrip('/')
        generated.update({
            f'{target_plan}/acceptance-runs/',
            f'{target_plan}/acceptance-inputs/',
            f'{target_plan}/.acceptance-snapshots/',
            # ADR-0060: finalization output has separate lifecycle custody.
            f'{target_plan}/acceptance-current.v1.json',
            f'{target_plan}/acceptance-coordinator-request.*',
            f'{target_plan}/acceptance-projection-request.v1.json',
            f'{target_plan}/acceptance-run-request.*.json',
            f'{target_plan}/compact-vdd-projection-request.*.json',
            f'{target_plan}/knowledge-context.refactor-acceptance-*.json',
        })

    def is_generated(path):
        normalized = path.replace('\\', '/')
        return any(
            normalized.startswith(pattern) if pattern.endswith('/')
            else fnmatch.fnmatch(normalized, pattern)
            for pattern in generated
        )

    rows = []
    for path in sorted(changed):
        relative(path)
        # Runtime evidence and adapter-owned storage are not candidate authority.
        if path.startswith('logs/') or path == storage or is_generated(path):
            continue
        file = contained(root, path)
        if (path == _PUBLISHER_MUTEX and path not in tracked_changes
                and path in ignored_knowledge
                and _is_publisher_mutex_metadata(file)):
            continue
        if file.exists() and not file.is_file():
            raise ValueError('unsupported candidate object')
        rows.append({'path': path, 'sha256': digest(file.read_bytes()) if file.exists() else None})
    result = {'baseline': baseline, 'changes': rows}
    return {**result, 'candidate_hash': identity(result), 'changed_paths': [r['path'] for r in rows]}
