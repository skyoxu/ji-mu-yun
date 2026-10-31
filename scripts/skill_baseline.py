"""ADR-0041: content-bound regression admission for VDD and Quick Dev.

This is a trusted single-maintainer check, not a sandbox or a signature service.
The temporary authenticated test channel admits fixture commands only.
"""
from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager
from copy import deepcopy
import gzip
import hashlib
import importlib.metadata
import json
from multiprocessing import AuthenticationError
from multiprocessing.connection import Client, Listener
import os
from pathlib import Path
import platform
import secrets
import shlex
import shutil
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
POLICY = '.agents/skill-baselines/policy.v1.json'
STORE = '.agents/skill-baselines/admissions'
CHANNEL = 'JIMUYUN_REGRESSION_CHANNEL'
SCHEMA = 'toolchain.skill-admission.v1'
SKILLS = {'vdd': '.agents/skills/vdd-execution-plan',
          'quick-dev': '.agents/skills/quick-dev-tdd-adapter'}
SKIP_PARTS = {'__pycache__', '.pytest_cache', '.venv', 'venv', '.git'}


def wire(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def digest(value):
    return hashlib.sha256(value).hexdigest()


def fail(reason):
    raise ValueError('SKILL_ADMISSION:' + reason)


def path(root, relative, *, exists=True):
    if not isinstance(relative, str) or not relative or '\\' in relative or ':' in relative:
        fail('unsafe-path')
    p = Path(relative)
    if p.is_absolute() or '..' in p.parts:
        fail('unsafe-path')
    target = root / p
    for item in (target, *target.parents):
        if item == root:
            break
        if item.is_symlink() or getattr(item, 'is_junction', lambda: False)():
            fail('symlink-path')
    if not target.resolve().is_relative_to(root.resolve()) or (exists and not target.exists()):
        fail('missing-or-external-path:' + relative)
    return target


def read_json(p):
    if p.stat().st_size > 16 * 1024 * 1024:
        fail('oversized-record')
    return json.loads(p.read_text(encoding='utf-8'))


def atomic(p, value, *, replace=False):
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.is_symlink() or (p.exists() and not replace):
        fail('record-already-exists')
    temporary = p.with_name(p.name + '.' + secrets.token_hex(8))
    try:
        with temporary.open('xb') as stream:
            stream.write(wire(value) + b'\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, p)
    finally:
        temporary.unlink(missing_ok=True)


def policy(root):
    p = read_json(path(root, POLICY))
    if p.get('schema') != 'toolchain.skill-baseline-policy.v1' or set(p.get('skills', {})) != set(SKILLS):
        fail('policy-shape')
    for name, directory in SKILLS.items():
        row = p['skills'][name]
        if directory not in row['roots'] or not row.get('suites'):
            fail('policy-required-skill-or-suite')
        for target in row['suites']:
            source = target.split('::', 1)[0]
            if not source.endswith('.py') or 'test' not in Path(source).name:
                fail('policy-test-target')
            path(root, source)
    return p


def files(root, roots):
    result = {}
    for relative in roots:
        base = path(root, relative)
        for p in sorted(base.rglob('*')) if base.is_dir() else [base]:
            if set(p.relative_to(base if base.is_dir() else base.parent).parts) & SKIP_PARTS:
                continue
            if p.suffix in {'.pyc', '.pyo'}:
                continue
            if p.name.startswith('.env') or p.name.endswith('.user.toml'):
                continue
            if p.is_symlink() or getattr(p, 'is_junction', lambda: False)():
                fail('fingerprint-symlink')
            if p.is_file():
                name = p.relative_to(root).as_posix()
                if name.startswith(('logs/', STORE + '/')):
                    fail('circular-or-private-input')
                result[name] = digest(p.read_bytes())
    return dict(sorted(result.items()))


def test_configuration(root, targets):
    """Bind repository-owned pytest discovery inputs, never device configuration."""
    found = set()
    for target in targets:
        directory = path(root, target.split('::', 1)[0]).parent
        while directory.is_relative_to(root):
            for filename in ('conftest.py', 'pytest.ini', 'pyproject.toml', 'tox.ini', 'setup.cfg'):
                item = directory / filename
                if item.is_file():
                    found.add(item.relative_to(root).as_posix())
            if directory == root:
                break
            directory = directory.parent
    return found


def suite_files(root, targets):
    sources = {target.split('::', 1)[0] for target in targets}
    return files(root, sorted(sources | test_configuration(root, targets)))


def dependency_closure(root, inventory):
    """Conservative static local-import closure plus explicit policy data roots."""
    search = {root, root / 'scripts', root / 'scripts/sc', root / 'scripts/python',
              root / '.agents/skills/vdd-execution-plan/scripts',
              root / '.agents/skills/quick-dev-tdd-adapter/tools',
              root / '.agents/skills/run-refactor-implementation-acceptance/scripts'}
    search.update((root / p).parent for p in inventory if p.endswith('.py'))
    pending, seen = list(inventory), set()
    # Per-call resolution only. Never retain a filesystem decision across starts.
    resolutions = {}
    while pending:
        relative = pending.pop()
        if relative in seen or not relative.endswith('.py'):
            continue
        seen.add(relative)
        source = path(root, relative)
        # Importing a module (and pytest package collection) executes parent
        # initializers too. Enqueue them so their own imports are also bound.
        for parent in source.parents:
            if parent == root or not parent.is_relative_to(root):
                break
            initializer = parent / '__init__.py'
            if initializer.is_file():
                dependency = initializer.relative_to(root).as_posix()
                if dependency not in inventory:
                    inventory.update(files(root, [dependency]))
                    pending.append(dependency)
        for node in ast.walk(ast.parse(source.read_text(encoding='utf-8-sig'))):
            modules = []
            bases = search
            if isinstance(node, ast.Import):
                modules = [n.name for n in node.names]
            elif isinstance(node, ast.ImportFrom):
                name = node.module or ''
                modules = [name, *[(name + '.' if name else '') + n.name for n in node.names if n.name != '*']]
                if node.level:
                    base = source.parent
                    for _ in range(node.level - 1):
                        base = base.parent
                    bases = {base}
            for name in modules:
                if not name:
                    continue
                key = (name, frozenset(bases))
                if key not in resolutions:
                    found = []
                    for base in bases:
                        for p in (base / (name.replace('.', '/') + '.py'), base / name.replace('.', '/') / '__init__.py'):
                            if p.is_file() and p.is_relative_to(root) and p.relative_to(root).parts[0] not in {'logs', 'execution-plans'}:
                                found.append(p.relative_to(root).as_posix())
                    resolutions[key] = found
                for dependency in resolutions[key]:
                    if dependency not in inventory:
                        inventory.update(files(root, [dependency]))
                        pending.append(dependency)
    return dict(sorted(inventory.items()))


def fingerprint(root, name, p=None):
    p = p or policy(root)
    required = [POLICY, p['bootstrap_history'], 'scripts/skill_baseline.py', 'scripts/workflow_unit_budget.py',
                'scripts/vdd/compile_plan.py' if name == 'vdd' else 'scripts/quick_dev/run.py']
    test_sources = {t.split('::', 1)[0] for t in p['skills'][name]['suites']}
    inventory = files(root, [*required, *p['shared_roots'], *p['skills'][name]['roots'],
                             *sorted(test_sources | test_configuration(root, p['skills'][name]['suites']))])
    inventory = dependency_closure(root, inventory)
    return {'sha256': digest(wire(inventory)), 'files': inventory}


def platform_key():
    return platform.system().lower() + '-py' + '.'.join(map(str, sys.version_info[:2]))


def tool_versions():
    return {'platform': platform_key(), 'python': platform.python_version(),
            'pytest': importlib.metadata.version('pytest')}


def _strip_doc(body):
    return [n for n in body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)
                                   and isinstance(n.value.value, str))]


class _TestDisplayLabels(ast.NodeTransformer):
    """Normalize only declared pytest display/CER metadata, not test inputs."""
    def visit_Call(self, node):
        node = self.generic_visit(node)
        name = ast.unparse(node.func)
        if name == 'pytest.mark.parametrize':
            node.keywords = [kw for kw in node.keywords if kw.arg != 'ids']
        elif name == 'pytest.param':
            keywords = []
            for kw in node.keywords:
                if kw.arg == 'id':
                    continue
                if kw.arg == 'marks':
                    value = kw.value
                    if isinstance(value, (ast.List, ast.Tuple)):
                        value.elts = [mark for mark in value.elts if not self._cer(mark)]
                        if not value.elts:
                            continue
                    elif self._cer(value):
                        continue
                keywords.append(kw)
            node.keywords = keywords
        return node

    @staticmethod
    def _cer(node):
        return isinstance(node, ast.Call) and ast.unparse(node.func) == 'pytest.mark.cer_assertion'


def test_inventory(root, targets):
    result = {}
    for relative in sorted({t.split('::', 1)[0] for t in targets}):
        tree = ast.parse(path(root, relative).read_text(encoding='utf-8-sig'))
        selected = [t.split('::')[1:] for t in targets if t.split('::', 1)[0] == relative]
        def visit(nodes, prefix=''):
            for node in nodes:
                if isinstance(node, ast.ClassDef):
                    visit(node.body, prefix + node.name + '::')
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test'):
                    key = prefix + node.name
                    if not any(not s or key == '::'.join(s) for s in selected):
                        continue
                    clean = deepcopy(node)
                    clean.name = 'test'
                    clean.body = _strip_doc(clean.body)
                    for n in ast.walk(clean):
                        if isinstance(n, ast.Assert):
                            n.msg = None
                    clean.body = [n for n in clean.body if not (isinstance(n, ast.Expr)
                        and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name)
                        and n.value.func.id == 'print')]
                    # Assertion labels and comments do not constitute new behavior.
                    clean.decorator_list = [d for d in clean.decorator_list
                        if not (isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
                                and d.func.attr == 'cer_assertion')]
                    clean.decorator_list = [_TestDisplayLabels().visit(d) for d in clean.decorator_list]
                    body = [ast.dump(n, include_attributes=False) for n in clean.body]
                    assertions = [ast.dump(n.test, include_attributes=False) for n in ast.walk(clean)
                        if isinstance(n, ast.Assert) and not isinstance(n.test, ast.Constant)
                        and any(isinstance(v, ast.Name) for v in ast.walk(n.test))
                        and not (isinstance(n.test, ast.Compare) and len(n.test.comparators) == 1
                                 and ast.dump(n.test.left) == ast.dump(n.test.comparators[0]))]
                    assertions += [ast.dump(n, include_attributes=False) for n in ast.walk(clean)
                        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                        and isinstance(n.func.value, ast.Name)
                        and ((n.func.value.id == 'self' and n.func.attr.startswith('assert'))
                             or (n.func.value.id == 'pytest' and n.func.attr == 'raises'))]
                    result[relative + '::' + key] = {
                        'semantic_sha256': digest(ast.dump(clean, include_attributes=False).encode()),
                        'body': body, 'assertions': assertions,
                        'can_append_assertions': not any(isinstance(n, (ast.Return, ast.Raise)) for n in clean.body),
                        'signature': ast.dump(clean.args, include_attributes=False),
                        'decorators': [ast.dump(d, include_attributes=False) for d in clean.decorator_list]}
        visit(tree.body)
    return result


def check_increment(old, new):
    old_values = {v['semantic_sha256'] for v in old.values()}
    incremental = []
    consumed = set()
    for key, previous in old.items():
        matches = [k for k, v in new.items() if k not in consumed
                   and previous['semantic_sha256'] == v['semantic_sha256']]
        if matches:
            consumed.add(key if key in matches else matches[0])
            continue
        current = new.get(key)
        if (not current or key in consumed or not previous.get('can_append_assertions', False)
                or current['signature'] != previous['signature']
                or current['decorators'] != previous['decorators']
                or current['body'][:len(previous['body'])] != previous['body']
                or not set(previous['assertions']) < set(current['assertions'])):
            fail('test-removed-or-nonadditive-change:' + key)
        incremental.append(key)
        consumed.add(key)
    incremental += [k for k, v in new.items()
                    if v['semantic_sha256'] not in old_values and v['assertions']]
    if not incremental:
        fail('no-substantive-test-increment')
    return sorted(set(incremental))


def candidate(root, names):
    p = policy(root)
    out = {'schema': 'toolchain.skill-baseline-candidate.v1', 'policy_sha256': digest(wire(p)),
           'runner_sha256': digest(path(root, 'scripts/skill_baseline.py').read_bytes()),
           'tool_versions': tool_versions(),
           'skills': {}}
    for name in names:
        targets = p['skills'][name]['suites']
        inventory = test_inventory(root, targets)
        suite = {'targets': targets, 'files': suite_files(root, targets),
                 'cases': inventory}
        if not inventory:
            fail('empty-test-inventory')
        out['skills'][name] = {'fingerprint': fingerprint(root, name, p),
                               'suite_sha256': digest(wire(suite)), 'suite': suite}
    return out


def bootstrap_history(root, enrolled):
    """Bind first admission to retained source analysis and runnable case mappings."""
    history = read_json(path(root, policy(root)['bootstrap_history']))
    if (history.get('schema') != 'toolchain.skill-bootstrap-history.v1'
            or set(history.get('skills', {})) != set(SKILLS)
            or not history.get('fixed_main') or not history.get('scope_start_exclusive')
            or set(history.get('merge_boundaries', {})) != {'8-24', '8-05'}):
        fail('bootstrap-history-shape')
    for name, row in history['skills'].items():
        source = row['source_analysis']
        if digest(path(root, source['path']).read_bytes()) != source['sha256']:
            fail('bootstrap-history-source-mismatch')
        families = row.get('families', [])
        if not families or len({f['id'] for f in families}) != len(families):
            fail('bootstrap-history-families')
        available = enrolled['skills'][name]['suite']['cases']
        for family in families:
            if (not family.get('intent') or not family.get('commits')
                    or not family.get('implementation') or not family.get('replacement_basis')
                    or not family.get('tests') or not set(family['tests']) <= set(available)):
                fail('bootstrap-history-uncovered-family:' + family['id'])
    return history


def validate_report(report, nonce):
    if (report.get('schema') != 'toolchain.skill-baseline-case-report.v1'
            or report.get('stage') != 'baseline-regression'
            or report.get('nonce') != nonce or report.get('complete') is not True
            or report.get('exit_code') != 0 or report.get('errors') != [] or not report.get('selected')):
        fail('missing-or-failed-case-report')
    events = {}
    for row in report.get('events', []):
        key = (row['node_id'], row['phase'])
        if key in events:
            fail('ambiguous-case-report')
        events[key] = row
    selected = report['selected']
    if len(set(selected)) != len(selected) or set(selected) != set(report.get('collected', {})):
        fail('invalid-selection')
    for node in selected:
        for phase in ('setup', 'call', 'teardown'):
            row = events.get((node, phase), {})
            if row.get('outcome') != 'passed' or row.get('xfail'):
                fail('failed-skipped-or-unobserved-case:' + node)
    return len(selected)


def current(root):
    p = path(root, STORE + '/current.json', exists=False)
    if not p.exists():
        return None
    value = read_json(p)
    if value.get('schema') != SCHEMA:
        fail('current-record-shape')
    return value


def record(root, reference):
    if not isinstance(reference, dict) or set(reference) != {'path', 'sha256'}:
        fail('admission-reference-shape')
    p = path(root, reference['path'])
    if not p.is_relative_to(root / STORE) or digest(p.read_bytes()) != reference['sha256']:
        fail('admission-record-corrupt')
    value = read_json(p)
    if value.get('schema') != SCHEMA:
        fail('admission-record-shape')
    return value


def lineage(root, name, pointer, reference, value):
    genesis = path(root, STORE + '/bootstrap.json')
    if digest(genesis.read_bytes()) != pointer.get('bootstrap_sha256'):
        fail('bootstrap-record-corrupt')
    initial = read_json(genesis)['initial']['platforms']
    visited = set()
    while True:
        if reference['sha256'] in visited or value.get('skill') != name:
            fail('admission-lineage-cycle-or-skill')
        visited.add(reference['sha256'])
        previous = value.get('predecessor')
        if previous is None:
            if value.get('bootstrap') is not True or initial.get(value['platform'], {}).get(name) != reference:
                fail('invalid-bootstrap-lineage')
            return
        if value.get('bootstrap') is not False:
            fail('repeated-bootstrap')
        old = record(root, previous)
        changed = old['candidate_skill']['fingerprint'] != value['candidate_skill']['fingerprint']
        expected = (check_increment(old['candidate_skill']['suite']['cases'],
                                    value['candidate_skill']['suite']['cases']) if changed else [])
        if expected != value.get('incremental_tests'):
            fail('test-increment-lineage-mismatch')
        reference, value = previous, old


def approved(root, name):
    pointer = current(root)
    if pointer is None:
        fail('no-approved-baseline')
    ref = pointer.get('platforms', {}).get(platform_key(), {}).get(name)
    if not ref:
        fail('platform-or-skill-not-tested')
    value = record(root, ref)
    lineage(root, name, pointer, ref, value)
    p = policy(root)
    sealed = value['candidate_skill']
    suite = sealed['suite']
    targets = p['skills'][name]['suites']
    if (sealed['fingerprint'] != fingerprint(root, name, p)
            or value['runner_sha256'] != digest(path(root, 'scripts/skill_baseline.py').read_bytes())
            or value['policy_sha256'] != digest(wire(p))
            or value['tool_versions'] != tool_versions()
            or value['platform'] != platform_key()
            or suite['targets'] != targets
            or suite['files'] != suite_files(root, targets)
            or sealed['suite_sha256'] != digest(wire(suite))):
        fail('fingerprint-or-suite-mismatch')
    # Admission and its suite AST were validated by full candidate() at test and
    # admit. Their immutable record hash plus unchanged test bytes/pinned tools
    # avoids rebuilding the identical AST during every ordinary CLI startup.
    for unit in value['results']:
        proof = path(root, unit['proof'])
        if digest(proof.read_bytes()) != unit['proof_sha256']:
            fail('regression-proof-corrupt')
        with gzip.open(proof, 'rb') as stream:
            raw = stream.read(16 * 1024 * 1024 + 1)
        if len(raw) > 16 * 1024 * 1024:
            fail('oversized-regression-proof')
        validate_report(json.loads(raw), unit['nonce'])
    if [u['target'] for u in value['results']] != targets:
        fail('incomplete-mandatory-suite')
    return value


def _inside(raw, root, scratch):
    p = Path(raw)
    p = p if p.is_absolute() else root / p
    if p.is_symlink() or not p.resolve().is_relative_to(scratch.resolve()):
        return False
    return True


def fixture_command(root, scratch, name, argv):
    """The candidate channel cannot run a formal task outside its test fixture."""
    if any(x in argv for x in ('--help', '-h')):
        return len(argv) == 1
    protected = (('--requirements', '--out-dir', '--result-json') if name == 'vdd' else
                 ('--plan', '--run-dir', '--out', '--first-use-contract', '--execution-request'))
    values = {}
    for i, arg in enumerate(argv):
        option = arg.partition('=')[0]
        # Native argparse permits equals/abbreviated forms and last-value
        # repeats. The candidate channel deliberately accepts only one exact,
        # separated occurrence of each protected path option.
        if option.startswith('--') and option not in protected and any(
                flag.startswith(option) for flag in protected):
            return False
        if option in protected:
            if (arg != option or option in values or i + 1 == len(argv)
                    or argv[i + 1].startswith('--')):
                return False
            values[option] = argv[i + 1]
    if name == 'vdd':
        if '--out-dir' not in values or not _inside(values['--out-dir'], root, scratch):
            return False
        readonly = '--admission-only' in argv or '--recommendation-only' in argv
        if not readonly and ('--requirements' not in values
                             or not _inside(values['--requirements'], root, scratch)):
            return False
        return '--result-json' not in values or _inside(values['--result-json'], root, scratch)
    if '--plan' not in values or not _inside(values['--plan'], root, scratch):
        return False
    for field in ('--run-dir', '--out', '--first-use-contract', '--execution-request'):
        if field in values and not _inside(values[field], root, scratch):
            return False
    if '--execution-request' in values:
        value = read_json(Path(values['--execution-request']) if Path(values['--execution-request']).is_absolute()
                          else root / values['--execution-request'])
        if not _inside(value['out'], root, scratch):
            return False
        if any(not _inside(s['run_dir'], root, scratch) or not _inside(s['ready_path'], root, scratch)
               for s in value['slices']):
            return False
    bundle_path = Path(values['--plan'])
    bundle_path = bundle_path if bundle_path.is_absolute() else root / bundle_path
    if bundle_path.is_dir():
        bundle_path /= 'semantic-plan-bundle.v1.json'
    if bundle_path.is_file():
        bundle = read_json(bundle_path)
        for row in bundle.get('slices', []):
            for key in ('production_owners', 'allowed_write_paths', 'planned_new_files'):
                if any(not _inside(p, root, scratch) for p in row.get(key, [])):
                    return False
    return True


def _process(pid):
    """Read OS-owned ancestry, never trust a PID or argv claimed by the ticket."""
    if platform.system() == 'Linux':
        base = Path('/proc') / str(pid)
        status = (base / 'status').read_text()
        parent = int(next(line.split(':', 1)[1] for line in status.splitlines() if line.startswith('PPid:')))
        argv = [v.decode('utf-8') for v in (base / 'cmdline').read_bytes().split(b'\0') if v]
        return parent, argv, (base / 'cwd').resolve(), (base / 'exe').resolve()
    if platform.system() == 'Windows':
        command = ('[Console]::OutputEncoding=[Text.UTF8Encoding]::new();'
                   f'Get-CimInstance Win32_Process -Filter "ProcessId = {int(pid)}" | '
                   'Select-Object ParentProcessId,ExecutablePath,CommandLine | ConvertTo-Json -Compress')
        done = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', command],
                              capture_output=True, encoding='utf-8', timeout=10, shell=False, check=True)
        value = json.loads(done.stdout)
        argv = [s.strip('"') for s in shlex.split(value['CommandLine'], posix=False)]
        return int(value['ParentProcessId']), argv, ROOT, Path(value['ExecutablePath']).resolve()
    fail('unsupported-test-channel-platform')


def _runner_ancestor(root, pid):
    cursor = os.getpid()
    for _ in range(32):
        parent, argv, cwd, executable = _process(cursor)
        if cursor == pid:
            rest = argv[1:]
            while rest and rest[0] in ('-B', '-u'):
                rest = rest[1:]
            if len(rest) < 2 or rest[1] != 'test' or executable != Path(sys.executable).resolve():
                return False
            entry = Path(rest[0])
            return (entry if entry.is_absolute() else cwd / entry).resolve() == root / 'scripts/skill_baseline.py'
        if parent <= 0 or parent == cursor:
            break
        cursor = parent
    return False


class TestChannel:
    def __init__(self, root, scratch, enrolled):
        self.root, self.scratch, self.enrolled = root, scratch, enrolled
        self.key = secrets.token_bytes(32)
        self.listener = Listener(('127.0.0.1', 0), authkey=self.key)
        self.listener._listener._socket.settimeout(.2)
        self.stopped = False
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.context = scratch / 'test-channel.json'

    def serve(self):
        while not self.stopped:
            try:
                with self.listener.accept() as connection:
                    if not connection.poll(5):
                        continue
                    value = json.loads(connection.recv_bytes(65536))
                    name = value.get('skill')
                    execution_root = Path(value.get('root', ''))
                    entry = Path(value.get('entry', ''))
                    relative_entry = ('scripts/vdd/compile_plan.py' if name == 'vdd'
                                      else 'scripts/quick_dev/run.py')
                    okay = (name in self.enrolled['skills']
                        and (execution_root == self.root or _inside(str(execution_root), self.root, self.scratch))
                        and entry == execution_root / relative_entry
                        and entry.is_file() and not entry.is_symlink()
                        and digest(entry.read_bytes()) == self.enrolled['skills'][name]['fingerprint']['files'][relative_entry]
                        and value.get('fingerprint') == self.enrolled['skills'][name]['fingerprint']['sha256']
                        and fingerprint(self.root, name)['sha256'] == value.get('fingerprint')
                        and fixture_command(execution_root, self.scratch, name, value.get('argv', [])))
                    connection.send_bytes(wire(bool(okay)))
            except (OSError, EOFError, ValueError, KeyError, TypeError, AuthenticationError):
                continue

    def __enter__(self):
        atomic(self.context, {'schema': 'toolchain.skill-test-channel.v1', 'runner_pid': os.getpid(),
                             'address': self.listener.address, 'key_sha256': digest(self.key),
                             'candidate_sha256': digest(wire(self.enrolled)),
                             'candidate_path': (self.context.parent / 'candidate.json').relative_to(self.root).as_posix()})
        self.thread.start()
        return json.dumps({'context': self.context.relative_to(self.root).as_posix(), 'key': self.key.hex()})

    def __exit__(self, *_):
        self.stopped = True
        self.listener.close()
        self.thread.join(timeout=2)


def require_admission(root, name, argv):
    root = Path(root).resolve()
    # A valid candidate channel delegates the live scan to its authenticated
    # actual ancestor broker. Do not first rescan a known stale approval, or
    # duplicate the broker scan in each public entry and supervisor child.
    ticket = os.environ.get(CHANNEL)
    if ticket:
        try:
            trusted_root = ROOT
            context = json.loads(ticket)
            location = path(trusted_root, context['context'])
            if not location.is_relative_to(trusted_root / 'logs') or location.name != 'test-channel.json':
                fail('test-channel-location')
            actual = read_json(location)
            if actual.get('schema') != 'toolchain.skill-test-channel.v1' or not _runner_ancestor(trusted_root, actual['runner_pid']):
                fail('test-channel-runner-not-ancestor')
            key = bytes.fromhex(context['key'])
            if digest(key) != actual['key_sha256']:
                fail('test-channel-key')
            enrolled = read_json(path(trusted_root, actual['candidate_path']))
            if digest(wire(enrolled)) != actual['candidate_sha256'] or name not in enrolled['skills']:
                fail('test-channel-candidate-changed')
            # This declared fingerprint is only a claim. The authenticated
            # actual ancestor broker independently recomputes the live hash
            # before accepting it; the client need not scan it a second time.
            address = actual['address']
            if not (isinstance(address, list) and len(address) == 2 and address[0] == '127.0.0.1'):
                fail('test-channel-address')
            with Client(tuple(address), authkey=key) as connection:
                connection.send_bytes(wire({'root': str(root), 'skill': name, 'argv': list(argv),
                                           'entry': str(Path(sys.argv[0]).resolve()),
                                           'fingerprint': enrolled['skills'][name]['fingerprint']['sha256']}))
                if connection.poll(5) and json.loads(connection.recv_bytes(1024)) is True:
                    return
        except (OSError, ValueError, KeyError, EOFError, TypeError, AuthenticationError, subprocess.SubprocessError):
            pass
    try:
        approved(root, name)
        return
    except (OSError, ValueError, KeyError, TypeError) as original:
        fail(str(original))


def collect_unit(request_path, report_path, args):
    """Reuse the native case observer, without a second nested read auditor.

    Regression identity is bound before/after the suite. These reports cannot
    substitute for a task's native dependency-observed execution receipt.
    """
    sys.path[:0] = [str(Path.cwd()), str(ROOT / SKILLS['quick-dev'] / 'tools')]
    from pytest_case_collector import Collector
    import pytest
    request = read_json(Path(request_path))
    if request.get('stage') != 'baseline-regression':
        fail('invalid-regression-measurement-request')
    collector = Collector()
    code = int(pytest.main(args, plugins=[collector]))
    atomic(Path(report_path), {**request, 'schema': 'toolchain.skill-baseline-case-report.v1',
        'complete': True, 'exit_code': code, 'collected': collector.collected,
        'selected': collector.selected, 'events': collector.events, 'errors': collector.errors})
    return code


class ResourceRecovery:
    """ADR-0041: one owner-approved batch after two proven disk interruptions.

    This is a local maintainer operation, not independent review authority.
    The original ledger remains authoritative; a successor never gets a new
    budget for the stopped unit. A claim is consumed even if its process dies.
    """
    CHANGES = {'scripts/skill_baseline.py', 'scripts/tests/test_skill_baseline.py',
               'scripts/vdd/compiler_watchdog.py',
               '.agents/skills/vdd-execution-plan/scripts/tests/test_ch456_compile_watchdog.py',
               'docs/workflows/toolchain-skill-baseline.md',
               'docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md',
               '.agents/skill-baselines/capability-coverage.v1.json'}
    MIN_FREE = 512 * 1024 * 1024

    def __init__(self, root, enrolled, output, request_path):
        self.root, self.enrolled = root, enrolled
        self.request_path = path(root, request_path)
        if not self.request_path.is_relative_to(root / 'logs'):
            fail('resource-recovery-request-location')
        self.request_bytes = self.request_path.read_bytes()
        self.request = value = read_json(self.request_path)
        if (value.get('schema') != 'toolchain.skill-resource-recovery.v1'
                or value.get('owner_confirmation', {}).get('operation') != 'one-disk-recovery-batch'
                or not value.get('owner_confirmation', {}).get('message_id')
                or value.get('candidate_sha256') != digest(wire(enrolled))
                or value.get('output') != output
                or value.get('platform') != platform_key()
                or set(enrolled['skills']) != set(SKILLS)):
            fail('resource-recovery-request-binding')
        origin_path = path(root, value['origin_candidate']['path'])
        if (not origin_path.is_relative_to(root / 'logs')
                or digest(origin_path.read_bytes()) != value['origin_candidate']['sha256']):
            fail('resource-recovery-origin-identity')
        self.origin = old = read_json(origin_path)
        if (old.get('schema') != enrolled['schema'] or old['tool_versions'] != enrolled['tool_versions']
                or old['policy_sha256'] != enrolled['policy_sha256']
                or set(old['skills']) != set(SKILLS)):
            fail('resource-recovery-origin-contract')
        changed = set()
        for name in SKILLS:
            before, after = old['skills'][name], enrolled['skills'][name]
            if before['suite']['targets'] != after['suite']['targets']:
                fail('resource-recovery-suite-targets-changed')
            check_increment(before['suite']['cases'], after['suite']['cases'])
            a, b = before['fingerprint']['files'], after['fingerprint']['files']
            changed.update(p for p in set(a) | set(b) if a.get(p) != b.get(p))
        if not changed or not changed <= self.CHANGES or 'scripts/skill_baseline.py' not in changed:
            fail('resource-recovery-successor-scope')
        self.target = value['target']
        self.expected_uses = sum(s['suite']['targets'].count(self.target) for s in old['skills'].values())
        self.key = digest(wire({'candidate': old, 'target': self.target, 'platform': platform_key()}))
        if not self.expected_uses or value['unit_key'] != self.key:
            fail('resource-recovery-unit-identity')
        self.ledger = path(root, 'logs/workflow-unit-budgets/skill-baseline/' + self.key + '.json')
        self.before_bytes = self.expected_ledger = self.ledger.read_bytes()
        prior = read_json(self.ledger)
        if (digest(self.before_bytes) != value['ledger_sha256'] or prior.get('failures') != 2
                or not isinstance(prior.get('spent'), (float, int)) or isinstance(prior['spent'], bool)
                or not 0 < prior['spent'] < 1800):
            fail('resource-recovery-ledger-identity')
        failures = value['failures']
        if not isinstance(failures, list) or len(failures) != 2:
            fail('resource-recovery-two-disk-failures-required')
        seen, nonces, elapsed = set(), set(), 0
        for proof in failures:
            directory = path(root, proof['directory'])
            if not directory.is_relative_to(root / 'logs') or directory in seen:
                fail('resource-recovery-distinct-failure-location')
            seen.add(directory)
            if set(proof['files']) != {'argv.json', 'request.json', 'exit.json', 'stdout.log'}:
                fail('resource-recovery-raw-evidence-required')
            for name, identity in proof['files'].items():
                if digest(path(root, (directory / name).relative_to(root).as_posix()).read_bytes()) != identity:
                    fail('resource-recovery-evidence-changed')
            exit_result = read_json(directory / 'exit.json')
            if (exit_result.get('timeout') != 'insufficient-disk-during-unit'
                    or not isinstance(exit_result.get('exit_code'), int) or not exit_result['exit_code']
                    or not isinstance(exit_result.get('elapsed_seconds'), (int, float))
                    or not 0 < exit_result['elapsed_seconds'] < 1800):
                fail('resource-recovery-not-disk-interruption')
            if (directory / 'case-report.json').exists():
                fail('resource-recovery-completed-result-not-interruption')
            elapsed += exit_result['elapsed_seconds']
            request = read_json(directory / 'request.json')
            argv = read_json(directory / 'argv.json')
            if (request.get('stage') != 'baseline-regression' or request.get('run_id') != directory.name
                    or not isinstance(request.get('nonce'), str) or len(request['nonce']) != 48
                    or request['nonce'] in nonces
                    or argv != [sys.executable, '-u', '-B', str(root / 'scripts/skill_baseline.py'),
                        '_collect', str(directory / 'request.json'), str(directory / 'case-report.json'),
                        self.target, '-v', '-p', 'no:cacheprovider', '--basetemp', str(directory / 'scratch'),
                        '-o', 'tmp_path_retention_policy=failed', '-o', 'tmp_path_retention_count=1',
                        '--junitxml', str(directory / 'junit.xml')]):
                fail('resource-recovery-failed-command-binding')
            nonces.add(request['nonce'])
            # Diagnostic inventories also retain the full all-skill candidate.
            if read_json(path(root, (directory.parent.parent / 'candidate.json').relative_to(root).as_posix())) != old:
                fail('resource-recovery-failed-candidate-binding')
        if elapsed > prior['spent']:
            fail('resource-recovery-cost-history')
        if shutil.disk_usage(root).free < self.MIN_FREE:
            fail('resource-recovery-space-not-restored')
        self.receipt = path(root, 'logs/workflow-unit-budgets/skill-baseline/resource-recoveries/' + self.key + '.json', exists=False)
        self.state = {'schema': 'toolchain.skill-resource-recovery-receipt.v1',
                      'request_sha256': digest(self.request_bytes), 'candidate_sha256': digest(wire(enrolled)),
                      'origin_candidate_sha256': digest(wire(old)), 'unit_key': self.key,
                      'output': output, 'platform': platform_key(), 'target': self.target,
                      'prior': prior, 'expected_uses': self.expected_uses, 'uses': [], 'status': 'claimed'}

    def claim(self, out):
        self.receipt.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation, not atomic(replace=False), closes simultaneous
        # claims. Never remove a consumed claim to retry a failed batch.
        with self.receipt.open('xb') as stream:
            stream.write(wire(self.state) + b'\n')
            stream.flush()
            os.fsync(stream.fileno())
        (out / 'resource-recovery-request.json').write_bytes(self.request_bytes)
        (out / 'resource-recovery-ledger-preimage.json').write_bytes(self.before_bytes)

    def authorize(self, target, key, out):
        if (target != self.target or key != self.key or self.state['status'] != 'claimed'
                or len(self.state['uses']) >= self.expected_uses
                or self.ledger.read_bytes() != self.expected_ledger
                or self.request_path.read_bytes() != self.request_bytes
                or read_json(self.receipt) != self.state):
            fail('resource-recovery-use-or-ledger-mismatch')
        if shutil.disk_usage(self.root).free < self.MIN_FREE:
            fail('resource-recovery-space-not-restored')
        self.state['uses'].append({'out': out.relative_to(self.root).as_posix(), 'status': 'started',
                                   'prior': read_json(self.ledger)})
        atomic(self.receipt, self.state, replace=True)

    def end_unit(self, target, success):
        if target != self.target:
            if not success:
                self.state['status'] = 'failed'
                atomic(self.receipt, self.state, replace=True)
            return
        self.state['status'] = 'claimed' if success else 'failed'
        if self.state['uses'] and self.state['uses'][-1]['status'] == 'started':
            self.state['uses'][-1].update(status='passed' if success else 'failed', ledger=read_json(self.ledger))
        self.expected_ledger = self.ledger.read_bytes()
        atomic(self.receipt, self.state, replace=True)

    def complete(self, out):
        if (self.state['status'] != 'claimed' or len(self.state['uses']) != self.expected_uses
                or any(row['status'] != 'passed' for row in self.state['uses'])
                or self.ledger.read_bytes() != self.expected_ledger):
            fail('resource-recovery-incomplete-batch')
        self.state.update(status='complete', final_ledger=read_json(self.ledger))
        atomic(self.receipt, self.state, replace=True)
        return {'receipt': self.receipt.relative_to(self.root).as_posix(), 'sha256': digest(self.receipt.read_bytes()),
                'request_sha256': digest((out / 'resource-recovery-request.json').read_bytes())}


def run_unit(root, target, out, channel, budget_key, recovery=None):
    from workflow_unit_budget import Budget, terminate_tree
    out.mkdir(parents=True, exist_ok=False)
    scratch = out / 'scratch'
    scratch.mkdir()
    nonce = secrets.token_hex(24)
    request = out / 'request.json'
    atomic(request, {'nonce': nonce, 'run_id': out.name, 'stage': 'baseline-regression'})
    report = out / 'case-report.json'
    argv = [sys.executable, '-u', '-B', str(root / 'scripts/skill_baseline.py'),
            '_collect', str(request), str(report), target,
            '-v', '-p', 'no:cacheprovider', '--basetemp', str(scratch),
            '-o', 'tmp_path_retention_policy=failed', '-o', 'tmp_path_retention_count=1',
            '--junitxml', str(out / 'junit.xml')]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    # Public-entry fixture copies use the same trusted gate; no fixture-local
    # approval store or copied policy can grant candidate admission.
    env['PYTHONPATH'] = str(root / 'scripts') + os.pathsep + env.get('PYTHONPATH', '')
    env[CHANNEL] = channel
    for key in ('TMPDIR', 'TMP', 'TEMP'):
        env[key] = str(scratch)
    atomic(out / 'argv.json', argv)
    ledger = root / 'logs/workflow-unit-budgets/skill-baseline' / (budget_key + '.json')
    prior = read_json(ledger) if ledger.exists() else {'spent': 0, 'failures': 0}
    if prior['failures'] >= 2:
        if recovery is None:
            fail('repeated-unchanged-regression-failure:' + target)
        recovery.authorize(target, budget_key, out)
    started = time.monotonic()
    budget = Budget(total=1800, idle=600, spent={budget_key: prior['spent']}, now=started)
    budget.apply({'event': 'start', 'at': started, 'call': 'regression',
                  'key': budget_key, 'label': target})
    monitor_lock = threading.Lock()
    with (out / 'stdout.log').open('wb') as log:
        child = subprocess.Popen(argv, cwd=root, env=env, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, start_new_session=os.name != 'nt')
        def drain():
            while block := child.stdout.readline():
                log.write(block)
                log.flush()
                sys.stdout.buffer.write(block)
                sys.stdout.buffer.flush()
                with monitor_lock:
                    budget.apply({'event': 'progress', 'at': time.monotonic(),
                                  'call': 'regression', 'digest': digest(block)})
        reader = threading.Thread(target=drain, daemon=True)
        reader.start()
        timeout = None
        while child.poll() is None:
            with monitor_lock:
                violation = budget.tick(time.monotonic())
            if shutil.disk_usage(root).free < 120 * 1024 * 1024:
                timeout = 'insufficient-disk-during-unit'
                terminate_tree(child)
                break
            if violation:
                timeout = violation['reason']
                terminate_tree(child)
                break
            time.sleep(.1)
        code = child.wait()
        reader.join(timeout=5)
    exit_record = {'exit_code': code, 'timeout': timeout,
                   'elapsed_seconds': time.monotonic() - started}
    if recovery:
        exit_record['resource_recovery'] = {'unit_key': budget_key,
                                            'request_sha256': digest(recovery.request_bytes)}
    atomic(out / 'exit.json', exit_record)
    budget.apply({'event': 'end', 'at': time.monotonic(), 'call': 'regression'})
    atomic(ledger, {'spent': budget.spent.get(budget_key, prior['spent']),
                    'failures': prior['failures'] + int(bool(code or timeout))}, replace=ledger.exists())
    if code or timeout or not report.is_file():
        fail('regression-failed:' + target)
    try:
        value = read_json(report)
        validate_report(value, nonce)
        definitions = test_inventory(root, [target])
        observed = {n.split('[', 1)[0] for n in value['selected']}
        if not set(definitions) <= observed:
            fail('mandatory-test-definition-not-executed:' + target)
    except (OSError, ValueError, KeyError, TypeError):
        state = read_json(ledger)
        state['failures'] += 1
        atomic(ledger, state, replace=True)
        raise
    return {'target': target, 'nonce': nonce, 'source': report}


def run_tests(root, enrolled, out, *, bootstrap=False, diagnostic_target=None, defer_admission=False,
              resource_recovery=None):
    names = list(enrolled['skills'])
    if enrolled != candidate(root, names):
        fail('candidate-changed-before-tests')
    pointer = current(root)
    store = path(root, STORE, exists=False)
    if diagnostic_target:
        if bootstrap or not any(diagnostic_target in enrolled['skills'][n]['suite']['targets'] for n in names):
            fail('diagnostic-requires-declared-target-and-no-bootstrap')
    elif bootstrap:
        if set(names) != set(SKILLS) or pointer is not None or (store.exists() and any(store.iterdir())):
            fail('bootstrap-already-used-or-incomplete')
        history = bootstrap_history(root, enrolled)
    elif pointer is None:
        fail('explicit-first-bootstrap-required')
    increments = {}
    for name in names:
        if diagnostic_target:
            continue
        previous = (pointer or {}).get('platforms', {}).get(platform_key(), {}).get(name)
        if previous:
            old = record(root, previous)
            if old['candidate_skill']['fingerprint'] != enrolled['skills'][name]['fingerprint']:
                increments[name] = check_increment(old['candidate_skill']['suite']['cases'],
                                                   enrolled['skills'][name]['suite']['cases'])
        elif not bootstrap:
            fail('platform-baseline-missing')
    recovery = None
    if resource_recovery:
        if bootstrap or diagnostic_target or set(names) != set(SKILLS) or not defer_admission:
            fail('resource-recovery-requires-complete-successor-measurement')
        recovery = ResourceRecovery(root, enrolled, out, resource_recovery)
    out = path(root, out, exists=False)
    if not out.is_relative_to(root / 'logs') or out.exists():
        fail('fresh-logs-output-required')
    out.mkdir(parents=True)
    atomic(out / 'candidate.json', enrolled)
    if recovery:
        recovery.claim(out)
    results, failures = {}, []
    broker = TestChannel(root, out, enrolled)
    with broker as channel:
        for name in names:
            results[name] = []
            for i, target in enumerate(enrolled['skills'][name]['suite']['targets']):
                if diagnostic_target and target != diagnostic_target:
                    continue
                if shutil.disk_usage(root).free < 192 * 1024 * 1024:
                    fail('insufficient-disk-before-unit')
                broker.scratch = out / name / str(i) / 'scratch'
                key = digest(wire({'candidate': recovery.origin if recovery else enrolled,
                                   'target': target, 'platform': platform_key()}))
                try:
                    if recovery and target == recovery.target:
                        result = run_unit(root, target, out / name / str(i), channel, key, recovery=recovery)
                    else:
                        # Preserve the ordinary five-argument interface exactly.
                        result = run_unit(root, target, out / name / str(i), channel, key)
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    if recovery:
                        recovery.end_unit(target, False)
                    failures.append({'skill': name, 'target': target, 'reason': str(exc)})
                    atomic(out / 'failed-units.json', failures, replace=len(failures) > 1)
                    print(json.dumps({'status': 'failed-unit', **failures[-1]}), flush=True)
                    if recovery:
                        fail('resource-recovery-batch-failed:' + target)
                    continue
                if recovery:
                    recovery.end_unit(target, True)
                results[name].append(result)
                # Tests own this disposable directory; raw stdout/JUnit/case
                # reports remain outside it. Never clean other task directories.
                shutil.rmtree(out / name / str(i) / 'scratch')
    if failures:
        fail('mandatory-regression-units-failed:' + str(len(failures)))
    if enrolled != candidate(root, names):
        fail('candidate-changed-during-tests')
    if diagnostic_target:
        result = {'status': 'diagnostic-only', 'authorizes': [], 'target': diagnostic_target}
        atomic(out / 'diagnostic.json', result)
        return result
    if defer_admission:
        units = {name: [{**{k: row[k] for k in ('target', 'nonce')},
            'source': row['source'].relative_to(root).as_posix(),
            'sha256': digest(row['source'].read_bytes())} for row in rows]
            for name, rows in results.items()}
        measurement = {'schema': 'toolchain.skill-baseline-measurement.v1', 'candidate': enrolled,
            'predecessor': pointer, 'bootstrap': bootstrap, 'increments': increments,
            'history': history if bootstrap else None, 'units': units}
        if recovery:
            measurement['resource_recovery'] = recovery.complete(out)
        atomic(out / 'measurement.json', measurement)
        return {'status': 'measured-only', 'authorizes': [],
                'measurement': (out / 'measurement.json').relative_to(root).as_posix()}
    return publish_admission(root, enrolled, results, pointer, bootstrap, increments, history if bootstrap else None)


def publish_admission(root, enrolled, results, pointer, bootstrap, increments, history):
    names = list(enrolled['skills'])
    store = path(root, STORE, exists=False)
    store.mkdir(parents=True, exist_ok=True)
    lock = store / 'publishing.lock'
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        if current(root) != pointer:
            fail('admission-concurrent-update')
        updated = deepcopy(pointer or {'schema': SCHEMA, 'platforms': {}})
        scope = updated['platforms'].setdefault(platform_key(), {})
        for name in names:
            version = enrolled['skills'][name]['fingerprint']['sha256']
            directory = store / name / version / platform_key() / secrets.token_hex(12)
            directory.mkdir(parents=True)
            proofs = []
            for i, result in enumerate(results[name]):
                proof = directory / (str(i) + '.json.gz')
                with gzip.open(proof, 'xb') as stream:
                    stream.write(result['source'].read_bytes())
                proofs.append({k: result[k] for k in ('target', 'nonce')} | {
                    'proof': proof.relative_to(root).as_posix(), 'proof_sha256': digest(proof.read_bytes())})
            admission = {'schema': SCHEMA, 'skill': name, 'platform': platform_key(), 'bootstrap': bootstrap,
                'candidate_skill': enrolled['skills'][name], 'policy_sha256': enrolled['policy_sha256'],
                'runner_sha256': enrolled['runner_sha256'], 'results': proofs,
                'tool_versions': enrolled['tool_versions'],
                'predecessor': scope.get(name), 'incremental_tests': increments.get(name, [])}
            p = directory / 'admission.json'
            atomic(p, admission)
            scope[name] = {'path': p.relative_to(root).as_posix(), 'sha256': digest(p.read_bytes())}
        if bootstrap:
            atomic(store / 'bootstrap.json', {'schema': SCHEMA, 'initial': updated,
                                              'history': history, 'history_sha256': digest(wire(history))})
            updated['bootstrap_sha256'] = digest((store / 'bootstrap.json').read_bytes())
        atomic(store / 'current.json', updated, replace=pointer is not None)
    finally:
        os.close(fd)
        lock.unlink()
    return {'status': 'admitted', 'platform': platform_key(), 'skills': names,
            'fingerprints': {n: enrolled['skills'][n]['fingerprint']['sha256'] for n in names}}



def admit_measurement(root, measurement_path):
    location = path(root, measurement_path)
    if not location.is_relative_to(root / 'logs'):
        fail('measurement-location')
    value = read_json(location)
    enrolled = value['candidate']
    names = list(enrolled['skills'])
    if (value.get('schema') != 'toolchain.skill-baseline-measurement.v1'
            or enrolled != candidate(root, names) or current(root) != value['predecessor']):
        fail('measurement-candidate-or-predecessor-changed')
    bootstrap = value['bootstrap']
    if not isinstance(bootstrap, bool):
        fail('measurement-bootstrap-shape')
    pointer = current(root)
    store = path(root, STORE, exists=False)
    if bootstrap:
        if (set(names) != set(SKILLS) or pointer is not None
                or (store.exists() and any(store.iterdir())) or value['increments'] != {}
                or value['history'] != bootstrap_history(root, enrolled)):
            fail('measurement-bootstrap-invalid')
    else:
        if pointer is None:
            fail('measurement-predecessor-missing')
        increments = {}
        for name in names:
            ref = pointer.get('platforms', {}).get(platform_key(), {}).get(name)
            if not ref:
                fail('measurement-platform-baseline-missing')
            old = record(root, ref)
            if old['candidate_skill']['fingerprint'] != enrolled['skills'][name]['fingerprint']:
                increments[name] = check_increment(old['candidate_skill']['suite']['cases'],
                                                   enrolled['skills'][name]['suite']['cases'])
        if increments != value['increments']:
            fail('measurement-increment-mismatch')
    if set(value['units']) != set(names):
        fail('measurement-incomplete-skills')
    if (location.parent / 'resource-recovery-request.json').exists() != bool(value.get('resource_recovery')):
        fail('measurement-resource-recovery-binding-missing')
    if value.get('resource_recovery'):
        binding = value['resource_recovery']
        receipt = path(root, binding['receipt'])
        state = read_json(receipt)
        request_bytes = (location.parent / 'resource-recovery-request.json').read_bytes()
        recovery_request = json.loads(request_bytes)
        preimage = (location.parent / 'resource-recovery-ledger-preimage.json').read_bytes()
        if (digest(receipt.read_bytes()) != binding['sha256'] or state.get('status') != 'complete'
                or state.get('candidate_sha256') != digest(wire(enrolled))
                or state.get('output') != location.parent.relative_to(root).as_posix()
                or state.get('platform') != platform_key()
                or state.get('request_sha256') != digest(request_bytes) or digest(request_bytes) != binding['request_sha256']
                or digest(preimage) != recovery_request['ledger_sha256'] or json.loads(preimage) != state['prior']
                or len(state['uses']) != state['expected_uses']
                or any(row['status'] != 'passed' for row in state['uses'])
                or read_json(path(root, 'logs/workflow-unit-budgets/skill-baseline/' + state['unit_key'] + '.json')) != state['final_ledger']
                or state['final_ledger']['failures'] != state['prior']['failures']
                or state['final_ledger']['spent'] <= state['prior']['spent']):
            fail('measurement-resource-recovery-invalid')
        expected_uses = [str((location.parent / name / str(i)).relative_to(root))
                         for name in names for i, target in enumerate(enrolled['skills'][name]['suite']['targets'])
                         if target == state['target']]
        if [row['out'] for row in state['uses']] != expected_uses:
            fail('measurement-resource-recovery-units')
    results = {}
    for name in names:
        targets = enrolled['skills'][name]['suite']['targets']
        rows = value['units'][name]
        if [r['target'] for r in rows] != targets:
            fail('measurement-incomplete-suite')
        results[name] = []
        for i, row in enumerate(rows):
            expected = location.parent / name / str(i) / 'case-report.json'
            report = path(root, row['source'])
            if report != expected or digest(report.read_bytes()) != row['sha256']:
                fail('measurement-proof-changed')
            exit_result = read_json(report.parent / 'exit.json')
            if exit_result.get('exit_code') != 0 or exit_result.get('timeout') is not None:
                fail('measurement-unit-not-successful')
            recovery_exit = exit_result.get('resource_recovery')
            if recovery_exit and (not value.get('resource_recovery')
                    or recovery_exit != {'unit_key': state['unit_key'], 'request_sha256': state['request_sha256']}
                    or row['target'] != state['target']):
                fail('measurement-resource-recovery-exit-binding')
            if value.get('resource_recovery') and row['target'] == state['target'] and not recovery_exit:
                fail('measurement-resource-recovery-exit-missing')
            request = read_json(report.parent / 'request.json')
            if request.get('nonce') != row['nonce']:
                fail('measurement-request-mismatch')
            observed = read_json(report)
            validate_report(observed, row['nonce'])
            if not set(test_inventory(root, [row['target']])) <= {n.split('[', 1)[0] for n in observed['selected']}:
                fail('measurement-mandatory-case-not-observed')
            results[name].append({'target': row['target'], 'nonce': row['nonce'], 'source': report})
    return publish_admission(root, enrolled, results, pointer, bootstrap, value['increments'], value['history'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['candidate', 'test', 'check', 'admit'])
    parser.add_argument('--skill', choices=['all', *SKILLS], default='all')
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--out', required=False)
    parser.add_argument('--bootstrap', action='store_true')
    parser.add_argument('--defer-admission', action='store_true')
    parser.add_argument('--measurement')
    parser.add_argument('--diagnostic-target', help='One declared module, measured without any admission.')
    parser.add_argument('--resource-recovery', help='Owner-approved one-batch disk recovery request under logs/.')
    args = parser.parse_args()
    names = list(SKILLS) if args.skill == 'all' else [args.skill]
    try:
        if args.action == 'candidate':
            if not args.out:
                fail('candidate-output-required')
            value = candidate(ROOT, names)
            atomic(path(ROOT, args.out, exists=False), value)
            result = {'status': 'candidate-only', 'out': args.out,
                      'fingerprints': {n: value['skills'][n]['fingerprint']['sha256'] for n in names}}
        elif args.action == 'test':
            if not args.candidate or not args.out:
                fail('candidate-and-test-output-required')
            value = read_json(path(ROOT, args.candidate.as_posix()))
            if args.skill != 'all':
                if args.skill not in value['skills']:
                    fail('selected-skill-absent-from-candidate')
                value = {**value, 'skills': {args.skill: value['skills'][args.skill]}}
            result = run_tests(ROOT, value, args.out, bootstrap=args.bootstrap,
                               diagnostic_target=args.diagnostic_target, defer_admission=args.defer_admission,
                               resource_recovery=args.resource_recovery)
        elif args.action == 'admit':
            if not args.measurement:
                fail('measurement-required')
            result = admit_measurement(ROOT, args.measurement)
        else:
            result = {'status': 'approved', 'skills': {n: approved(ROOT, n)['candidate_skill']['fingerprint']['sha256'] for n in names}}
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, SyntaxError) as exc:
        print(json.dumps({'status': 'blocked', 'reason': str(exc)}))
        return 1


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '_collect':
        raise SystemExit(collect_unit(*sys.argv[2:4], sys.argv[4:]))
    raise SystemExit(main())
