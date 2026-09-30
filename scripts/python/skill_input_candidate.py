"""Observe candidate changes against the authority-bound Git baseline (ADR-0060)."""
import re
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


def observe_candidate(root, authority_path, storage):
    root = Path(root).resolve()
    baseline = read_json(authority_path).get('skill_input_baseline')
    if not isinstance(baseline, str) or not re.fullmatch(r'[0-9a-f]{40}', baseline):
        raise ValueError('authority must bind a full skill_input_baseline Git commit')
    if Path(git(root, 'rev-parse', '--show-toplevel').strip()).resolve() != root:
        raise ValueError('candidate must use the repository root')
    git(root, 'merge-base', '--is-ancestor', baseline, 'HEAD')
    changed = set(filter(None, git(root, 'diff', '--no-ext-diff', '--no-renames', '--name-only', '-z', baseline, '--').split('\0')))
    changed.update(filter(None, git(root, 'ls-files', '--others', '--exclude-standard', '-z').split('\0')))
    # Ignore rules cannot conceal changes to Knowledge authority.
    changed.update(filter(None, git(root, 'ls-files', '--others', '--ignored', '--exclude-standard', '-z', '--',
        'knowledge/', '.agents/skills/maintain-knowledge-base/', ':(glob)scripts/python/*knowledge*.py').split('\0')))
    rows = []
    for path in sorted(changed):
        relative(path)
        # Runtime evidence and adapter-owned storage are not candidate authority.
        if (
            path.startswith(('logs/', '.skill-input-work/'))
            or path == storage
            or path.startswith(storage + '/')
            # Coordinator request/result files are transport artifacts. They
            # bind the current Skill-input pointer and must not recursively
            # change the candidate whose pointer they carry.
            or Path(path).name.startswith('acceptance-coordinator-request.')
        ):
            continue
        file = contained(root, path)
        if file.exists() and not file.is_file():
            raise ValueError('unsupported candidate object')
        rows.append({'path': path, 'sha256': digest(file.read_bytes()) if file.exists() else None})
    result = {'baseline': baseline, 'changes': rows}
    return {**result, 'candidate_hash': identity(result), 'changed_paths': [r['path'] for r in rows]}
