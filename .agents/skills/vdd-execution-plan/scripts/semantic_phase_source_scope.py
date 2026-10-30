"""ADR-0041/0043: trusted caller source scope, not worker-issued permission.

The explicit public CLI may bind an already authorized Phase task to exact
files. This validates input integrity, not caller identity or human approval.
It grants no filesystem capability or substitute for AGENTS protected approval.
Default Toolchain exclusions remain in force without this caller context.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import fnmatch
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from threading import Lock

_current = None
_session_root = None
_occupied = False
_lock = Lock()
_BUILD_METADATA_READ_PATHS = frozenset({'PhaseA.Platform/PhaseA.Platform.csproj',
                                       'PhaseA.Platform/packages.lock.json'})


def _relative(value):
    if (not isinstance(value, str) or not value or '\\' in value or ':' in value
            or '\x00' in value or any(c in value for c in '*?[]')):
        raise ValueError('source-scope: invalid exact path')
    p = PurePosixPath(value)
    if not p.parts or p.is_absolute() or str(p) != value or '..' in p.parts or '.' in p.parts:
        raise ValueError('source-scope: noncanonical path')
    if p.parts[0] in {'.git', '.aws', '.ssh', 'secrets'} or p.name.startswith('.env'):
        raise ValueError('source-scope: excluded path')
    return value


def _path(root, value, *, required=True):
    value = _relative(value)
    p = root / value
    if any(q.is_symlink() or getattr(q, 'is_junction', lambda: False)()
           for q in (p, *p.parents) if q.is_relative_to(root)):
        raise ValueError('source-scope: symlink path')
    if not p.resolve().is_relative_to(root):
        raise ValueError('source-scope: escaped path')
    if any(q.exists() and not q.is_dir() for q in p.parents if q != p):
        raise ValueError('source-scope: invalid parent')
    if p.exists() and not p.is_file():
        raise ValueError('source-scope: file required')
    if required and not p.is_file():
        raise ValueError('source-scope: missing file')
    return p


def _digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _mentions(text, task):
    return re.search(r'(?<![A-Za-z0-9-])'+re.escape(task)+r'(?![A-Za-z0-9-])', text) is not None


def _binding(root, row, fields):
    if not isinstance(row, dict) or set(row) != fields:
        raise ValueError('source-scope: invalid dependency binding')
    p = _path(root, row['path'])
    if p.stat().st_size > 262144:
        raise ValueError('source-scope: dependency too large')
    if (not isinstance(row['sha256'], str)
            or not re.fullmatch('[0-9a-f]{64}', row['sha256'])
            or _digest(p) != row['sha256']):
        raise ValueError('source-scope: dependency hash mismatch')
    return p


@dataclass(frozen=True)
class SourceScope:
    root: Path
    task_id: str
    write_paths: frozenset
    read_paths: frozenset
    support_paths: frozenset
    dependencies: tuple
    identity: str


def load(root, requirements, path):
    """Load caller-selected authoring input; never call this on worker output."""
    root = Path(root).resolve()
    path = Path(path)
    path = path if path.is_absolute() else root / path
    try:
        name = path.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError('source-scope: file outside repository') from exc
    p = _path(root, name)
    if p.stat().st_size > 65536:
        raise ValueError('source-scope: input too large')
    value = json.loads(p.read_text(encoding='utf-8'))
    fields = {'schema', 'task_id', 'requirements', 'adr', 'authorization',
              'write_paths', 'read_paths', 'support_paths', 'authorizes'}
    if (not isinstance(value, dict) or set(value) != fields
            or value['schema'] != 'vdd.phase-source-scope.v1'
            or value['authorizes'] != []
            or not isinstance(value['task_id'], str)
            or not re.fullmatch('[A-Z0-9]+(?:-[A-Z0-9]+)+', value['task_id'])):
        raise ValueError('source-scope: unknown or malformed scope')
    req = _binding(root, value['requirements'], {'path', 'sha256'})
    selected = Path(requirements)
    selected = selected if selected.is_absolute() else root / selected
    if req != selected.resolve():
        raise ValueError('source-scope: wrong requirements')
    text = req.read_text(encoding='utf-8')
    if not _mentions(text, value['task_id']):
        raise ValueError('source-scope: unrelated requirements')
    adr = _binding(root, value['adr'], {'path', 'sha256', 'section'})
    section = value['adr']['section']
    adr_text = adr.read_text(encoding='utf-8')
    if (not value['adr']['path'].startswith('docs/adr/ADR-')
            or not re.search(r'^- Status: Accepted\s*$', adr_text, re.M)
            or not isinstance(section, str) or not section.startswith('## ')
            or not _mentions(section, value['task_id']) or section not in text
            or section not in adr_text or value['adr']['path'] not in text):
        raise ValueError('source-scope: Accepted source authority required')
    def fragment_of(value):
        headings = list(re.finditer(r'^'+re.escape(section)+r'\s*$', value, re.M))
        if len(headings) != 1:
            raise ValueError('source-scope: ambiguous authority section')
        return value[headings[0].end():].split('\n## ', 1)[0].strip()
    fragment = fragment_of(adr_text)
    source_fragment = fragment_of(text)
    def notation(value):
        # Input projection may label non-file route/directory code spans.
        # Raw requirements/ADR identities above remain exact, never normalized.
        value = re.sub(r'`([^`\r\n]+)`', r'\1', value)
        return re.sub(r'(?:HTTP route|evidence directory) (?=[^\s]*/)', '', value)
    if not fragment or notation(fragment) != notation(source_fragment):
        raise ValueError('source-scope: authority fragment is not a requirement source')
    auth = _binding(root, value['authorization'], {'path', 'sha256'})
    record = json.loads(auth.read_text(encoding='utf-8'))
    if (not isinstance(record, dict) or not isinstance(record.get('user_request'), str)
            or not _mentions(record['user_request'], value['task_id'])
            or record.get('workspace') != str(root)
            or not isinstance(record.get('authorized_stages'), list)
            or any(not isinstance(q, str) for q in record['authorized_stages'])
            or not {'VDD', 'Quick Dev TDD'} <= set(record['authorized_stages'])):
        raise ValueError('source-scope: existing task authorization required')
    sets = []
    for key in ('write_paths', 'read_paths', 'support_paths'):
        paths = value[key]
        if (not isinstance(paths, list) or len(paths) > 256
                or any(not isinstance(q, str) for q in paths)
                or len(set(paths)) != len(paths)):
            raise ValueError('source-scope: invalid path set')
        for q in paths:
            if key == 'support_paths':
                support = q == 'PhaseA.Platform/README.md' or q.startswith(
                    ('PhaseA.Platform.Tests/', 'scripts/python/tests/', 'tests/', 'docs/'))
                if not support or not Path(q).suffix:
                    raise ValueError('source-scope: only exact test/document support files supported')
            elif key == 'read_paths' and q in _BUILD_METADATA_READ_PATHS:
                pass
            elif not q.startswith('PhaseA.Platform/') or not q.endswith('.cs'):
                raise ValueError('source-scope: only exact Phase C# paths supported')
            _path(root, q, required=q in _BUILD_METADATA_READ_PATHS)
        sets.append(frozenset(paths))
    if not sets[0]:
        raise ValueError('source-scope: empty write scope')
    if sets[0] & sets[1]:
        raise ValueError('source-scope: conflicting read/write roles')
    deps = tuple(sorted({(name, _digest(p)),
                         (value['requirements']['path'], _digest(req)),
                         (value['adr']['path'], _digest(adr)),
                         (value['authorization']['path'], _digest(auth))}
                        | {(q, _digest(_path(root, q)))
                           for q in sets[1] & _BUILD_METADATA_READ_PATHS}))
    if (sets[0] | sets[2]) & {p for p, _h in deps}:
        raise ValueError('source-scope: authority inputs cannot be writable')
    material = json.dumps({'scope': value, 'dependencies': deps}, sort_keys=True,
                          separators=(',', ':')).encode('utf-8')
    return SourceScope(root, value['task_id'], sets[0], sets[1], sets[2], deps,
                       hashlib.sha256(material).hexdigest())


@contextmanager
def session(root, value):
    global _current, _occupied, _session_root
    with _lock:
        if _occupied:
            raise ValueError('source-scope: overlapping caller sessions')
        if value is not None and (not isinstance(value, SourceScope)
                                  or value.root != Path(root).resolve()):
            raise ValueError('source-scope: invalid caller context')
        _current = value
        _session_root = Path(root).resolve()
        _occupied = True
    try:
        yield
    finally:
        with _lock:
            _current = None
            _session_root = None
            _occupied = False


def current(root):
    scope = _current
    if scope is None or scope.root != Path(root).resolve():
        return None
    for path, digest in scope.dependencies:
        if _digest(_path(scope.root, path)) != digest:
            raise ValueError('source-scope: current dependency changed')
    for path in scope.write_paths | scope.read_paths | scope.support_paths:
        _path(scope.root, path, required=path in _BUILD_METADATA_READ_PATHS)
    return scope


def description(root):
    scope = current(root)
    if scope is None:
        return None
    return {'task_id': scope.task_id, 'sha256': scope.identity,
            'write_paths': sorted(scope.write_paths), 'read_paths': sorted(scope.read_paths),
            'support_paths': sorted(scope.support_paths),
            'inputs': [{'path': p, 'sha256': h} for p, h in scope.dependencies],
            'authorizes': []}


def protected(path):
    # Classify aliases conservatively; only exact canonical spellings can
    # match an approved file set. Normalization never grants an exception.
    lowered = str(PurePosixPath(str(path).replace('\\', '/'))).casefold()
    return (lowered == 'phasea.platform' or lowered.startswith('phasea.platform/')
            or lowered == 'runtime/phase-a' or lowered.startswith('runtime/phase-a/'))


def preserve_forbidden(path):
    """Keep the selected route's negative boundary through every normalizer."""
    return _current is not None or protected(path)


def validate_hints(root, hints):
    """Final V3 projections, including published/inline repair overlays."""
    selected = current(root)
    for hint in hints:
        forbidden = hint.get('forbidden_paths', [])
        rollback = hint.get('rollback_scope', {}).get('production_paths', [])
        writes = [p for key in ('production_owners', 'allowed_write_paths', 'planned_new_files')
                  for p in hint.get(key, [])] + rollback
        for path in writes:
            if selected is not None:
                if path not in selected.write_paths | selected.support_paths:
                    raise ValueError('source-scope: final write outside scope: ' + path)
                if conflict(path, forbidden):
                    raise ValueError('source-scope: final forbidden write: ' + path)
            elif protected(path):
                raise ValueError('source-scope: final Phase/runtime write without scope: ' + path)
        if selected is not None:
            snapshots = hint.get('execution_snapshot_paths', [])
            if any(path not in snapshots for path, _ in selected.dependencies):
                raise ValueError('source-scope: final dependency not frozen')
            for path in snapshots:
                if conflict(path, forbidden):
                    raise ValueError('source-scope: final forbidden read: ' + path)
                if protected(path) and path not in selected.write_paths | selected.read_paths | selected.support_paths:
                    raise ValueError('source-scope: final read outside scope: ' + path)


def validate_bundle(root, bundle):
    """Validate before publication/reuse, without rebinding an old identity."""
    actual = description(root)
    if bundle.get('source_scope') != actual:
        raise ValueError('source-scope: published scope identity differs from current input')
    if actual is None:
        return
    contexts = {c['slice_id']: c for c in bundle.get('agent_contexts', [])}
    for item in bundle.get('slices', []):
        context = contexts.get(item.get('slice_id'), {})
        hint = dict(item)
        hint['forbidden_paths'] = list(item.get('forbidden_paths', [])) + list(context.get('forbidden_paths', []))
        validate_hints(root, [hint])
        extra = dict(hint, allowed_write_paths=context.get('allowed_paths', []))
        validate_hints(root, [extra])


def validate_active_bundle(bundle):
    if _session_root is not None:
        validate_bundle(_session_root, bundle)


def conflict(path, forbidden):
    path = path.casefold()
    return any(fnmatch.fnmatchcase(path, p.casefold()) or path == p.casefold().rstrip('/')
               or path.startswith(p.casefold().rstrip('/') + '/')
               for p in forbidden if isinstance(p, str) and p)


def prompt(root):
    scope = description(root)
    if scope is None:
        return ('No caller-approved Phase scope is selected. PhaseA.Platform and runtime/phase-a '
                'remain forbidden as production owners or writes; do not invent a scope override. ')
    return ('Only the public-entry source scope permits the exact Phase paths in source_scope. '
            'Writes are limited to its exact write_paths and test/document support_paths; do not invent '
            'Toolchain or other-domain writes. Other Phase paths and all runtime/phase-a paths remain forbidden. Explicit forbidden_paths '
            'always win. This is plan authoring scope, not protected-write or execution permission. ')
