"""Repository-owned planning query adapter; never a publication authority."""
from pathlib import Path
import sys

# ADR-0048: the existing Locator owns validation and legacy result semantics.
_PYTHON = Path(__file__).resolve().parents[2] / "python"
if str(_PYTHON) not in sys.path:
    sys.path.insert(0, str(_PYTHON))
import _knowledge_locator_core as core


def _legacy(request, repository_root, catalog_path, policies_path, projections_path):
    """Return the shared read-only result and gate diagnostics without bypasses."""
    locator_request = dict(request)
    stage = locator_request.pop("stage", None)
    if stage is not None:
        identities = {"prd": "bmad-planning", "spec": "bmad-planning",
                      "architecture": "bmad-planning", "vdd-create": "vdd",
                      "vdd-repair": "vdd"}
        if stage not in identities or locator_request.get("consumer") != identities[stage]:
            raise ValueError("planning_consumer_stage_mismatch")
    output = core.query_with_diagnostics(
        locator_request, Path(repository_root), catalog_path=Path(catalog_path),
        policies_path=Path(policies_path), projections_path=Path(projections_path),
    )
    if stage is not None:
        # AD-2: caller stage is sidecar metadata, never a new Locator identity.
        output = {**output, "stage": stage, "consumer": locator_request["consumer"]}
        if any(item.get("code") == "publication_invalid" for item in output["diagnostics"]):
            pointer = Path(repository_root) / "knowledge/indexes/current.json"
            # The owner has already rejected the publication. Distinguish absence
            # from damaged bindings without interpreting an empty result as no match.
            reason = "integrity_failed" if pointer.exists() else "publication_missing"
            output["diagnostics"] = [
                {**item, "code": reason} if item.get("code") == "publication_invalid" else item
                for item in output["diagnostics"]
            ]
    return output

# ADR-0048 / approved AD-3..AD-8: bounded advice, never delivery authority.
import contextlib
import copy
import hashlib
import json
import re
import subprocess
import threading
import time
import tomllib
from datetime import datetime, timezone

_STAGES = {'prd': 'bmad-planning', 'spec': 'bmad-planning',
           'architecture': 'bmad-planning', 'vdd-create': 'vdd', 'vdd-repair': 'vdd'}
_LIMITS = {'max_candidates': (1, 20), 'max_output_bytes': (4096, 131072),
           'max_calls': (1, 5), 'timeout_seconds': (1, 60)}
_CANONICAL = ('knowledge/catalogs/repository-knowledge-catalog.v2.json',
              'knowledge/policies/consumer-policies.v2.json',
              'knowledge/projections/consumer-projections.v1.json')
_PROCESS_LOCK = threading.RLock()
_RECORD_PREFIX = '<!-- planning-query.v1 '


def _wire(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def _hash(data):
    return hashlib.sha256(data).hexdigest()


class _Stop(Exception):
    def __init__(self, reason):
        self.reason = reason


@contextlib.contextmanager
def _bounded_children(timeout, cancel, exits):
    """Bound the real core's subprocess transport without replacing its policy.

    The factory delegates other threads unchanged. The owned child remains a
    real Popen; concurrent binary readers bound buffering on Windows and Linux.
    No timeout/overflow payload is parsed, retried, or included in diagnostics.
    """
    with _PROCESS_LOCK:
        factory = subprocess.Popen
        owner = threading.get_ident()
        attempt_deadline = time.monotonic() + timeout
        def launch(*args, **kwargs):
            if threading.get_ident() != owner:
                return factory(*args, **kwargs)
            text = kwargs.pop('text', False) or kwargs.pop('universal_newlines', False)
            encoding = kwargs.pop('encoding', None)
            kwargs.pop('errors', None)
            text = text or encoding is not None
            child = factory(*args, **kwargs)
            started = time.monotonic()
            cached = []
            def communicate(input=None, timeout=None):
                if cached:
                    return cached[0]
                buffers = [bytearray(), bytearray()]
                fault = []
                def read(pipe, index):
                    if pipe is None:
                        return
                    try:
                        while True:
                            block = pipe.read(min(4096, 65537 - len(buffers[index])))
                            if not block:
                                break
                            if len(buffers[index]) + len(block) > 65536:
                                fault.append('budget_exhausted')
                                break
                            buffers[index].extend(block)
                    except (OSError, ValueError):
                        fault.append('unknown_failure')
                readers = [threading.Thread(target=read, args=(pipe, i), daemon=True)
                           for i, pipe in enumerate((child.stdout, child.stderr))]
                for thread in readers:
                    thread.start()
                def write():
                    if child.stdin is not None:
                        try:
                            if input is not None:
                                child.stdin.write(input.encode(encoding or 'utf-8') if isinstance(input, str) else input)
                                child.stdin.flush()
                        except BrokenPipeError:
                            pass
                        finally:
                            child.stdin.close()
                writer = threading.Thread(target=write, daemon=True)
                writer.start()
                deadline = min(float(timeout) if timeout is not None else limit, limit)
                reason = None
                while child.poll() is None or any(t.is_alive() for t in readers):
                    if fault:
                        reason = fault[0]
                    elif cancel is not None and cancel.is_set():
                        reason = 'cancelled'
                    elif time.monotonic() - started >= deadline:
                        reason = 'timeout'
                    if reason:
                        if child.poll() is None:
                            child.kill()
                        break
                    time.sleep(0.005)
                child.wait()
                writer.join(timeout=1)
                for thread in readers:
                    thread.join(timeout=1)
                exits.append(child.returncode)
                output = tuple(bytes(value) for value in buffers)
                if reason or fault:
                    cached.append((b'', b''))
                    raise _Stop(reason or fault[0])
                if text:
                    output = tuple(value.decode(encoding or 'utf-8') for value in output)
                cached.append(output)
                return output
            limit = max(0.0, attempt_deadline - started)
            child.communicate = communicate
            return child
        subprocess.Popen = launch
        try:
            yield lambda: max(0.0, attempt_deadline - time.monotonic())
        finally:
            subprocess.Popen = factory



def _stream_source_hashes(root, catalog, current_commit, timeout, cancel):
    """Hash Git source objects in bounded chunks; never buffer the source set.

    This is a transport implementation of the core freshness provider. The core
    still evaluates the full snapshot, exclusions, policy, and publication.
    """
    deadline = time.monotonic() + timeout
    snapshot = core.catalog_source_snapshot(catalog)
    if snapshot is None or current_commit is None:
        return {}
    ancestor = subprocess.run(['git', '-C', str(root), 'merge-base', '--is-ancestor',
                              snapshot['commit'], current_commit], capture_output=True, check=False)
    if ancestor.returncode:
        return {}
    paths = [item['path'] for item in snapshot['sources']]
    child = subprocess.Popen(['git', '-C', str(root), 'cat-file', '--batch'],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    hashes, errors = {}, []
    started = time.monotonic()
    def writer():
        try:
            for path in paths:
                child.stdin.write((current_commit + ':' + path + '\n').encode('utf-8'))
            child.stdin.flush()
        except (OSError, ValueError):
            errors.append('unknown_failure')
        finally:
            child.stdin.close()
    def reader():
        try:
            for path in paths:
                header = child.stdout.readline(512)
                parts = header.rstrip(b'\n').split(b' ')
                if len(parts) != 3 or parts[1] != b'blob' or not parts[2].isdigit():
                    errors.append('integrity_failed')
                    return
                remaining = int(parts[2])
                digest = hashlib.sha256()
                while remaining:
                    block = child.stdout.read(min(16384, remaining))
                    if not block:
                        errors.append('integrity_failed')
                        return
                    digest.update(block)
                    remaining -= len(block)
                if child.stdout.read(1) != b'\n':
                    errors.append('integrity_failed')
                    return
                hashes[path] = digest.hexdigest()
        except (OSError, ValueError):
            errors.append('unknown_failure')
    def stderr():
        if len(child.stderr.read(65537)) > 65536:
            errors.append('budget_exhausted')
    workers = [threading.Thread(target=fn, daemon=True) for fn in (writer, reader, stderr)]
    for worker in workers:
        worker.start()
    try:
        while child.poll() is None or any(t.is_alive() for t in workers):
            if errors:
                raise _Stop(errors[0])
            if cancel is not None and cancel.is_set():
                raise _Stop('cancelled')
            if time.monotonic() >= deadline:
                raise _Stop('timeout')
            time.sleep(.005)
        if errors or child.returncode:
            raise _Stop(errors[0] if errors else 'unknown_failure')
        return hashes
    finally:
        if child.poll() is None:
            child.kill()
        child.wait()
        for worker in workers:
            worker.join(timeout=1)
        for pipe in (child.stdout, child.stderr):
            pipe.close()


@contextlib.contextmanager
def _source_hash_transport(timeout, cancel):
    # Scoped and serialized with the process adapter. Restore the original
    # provider even on cancellation. Formal callers outside this call retain
    # their existing implementation and semantics.
    original = core._main_source_hashes
    owner = threading.get_ident()
    def bounded(root, catalog, current_commit=None):
        if threading.get_ident() != owner:
            return original(root, catalog, current_commit)
        return _stream_source_hashes(root, catalog, current_commit, timeout(), cancel)
    core._main_source_hashes = bounded
    try:
        yield
    finally:
        core._main_source_hashes = original


def _path(root, relative):
    if not isinstance(relative, str) or not relative or '\\' in relative:
        raise _Stop('path_denied')
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts or ':' in relative:
        raise _Stop('path_denied')
    target = root / path
    if not target.resolve().is_relative_to(root) or not target.is_file():
        raise _Stop('path_denied')
    # Do not open repository credential stores as source evidence.
    if path.parts[0] in {'.git', '.aws', '.ssh'} or path.name.startswith('.env'):
        raise _Stop('path_denied')
    return target


def _digest_file(path):
    digest = hashlib.sha256()
    excerpt = b''
    with path.open('rb') as stream:
        while block := stream.read(65536):
            digest.update(block)
            if len(excerpt) < 2048:
                excerpt += block[:2048-len(excerpt)]
    return digest.hexdigest(), excerpt.decode('utf-8', errors='ignore')


def _configuration(root, request):
    path = root / 'knowledge/planning-query.toml'
    if not path.exists():
        raise _Stop('config_missing')
    try:
        if not path.resolve().is_relative_to(root):
            raise ValueError('outside')
        with path.open('rb') as stream:
            config_bytes = stream.read(65537)
        if len(config_bytes) > 65536:
            raise ValueError('configuration size')
        data = tomllib.loads(config_bytes.decode('utf-8'))
        value = data['query']
        if set(data) != {'query'} or set(value) != {'enabled', 'stages', *_LIMITS}:
            raise ValueError('fields')
        if type(value['enabled']) is not bool or not isinstance(value['stages'], list):
            raise ValueError('types')
        if len(value['stages']) != len(_STAGES) or set(value['stages']) != set(_STAGES):
            raise ValueError('stages')
        for name, (low, high) in _LIMITS.items():
            if type(value[name]) is not int or not low <= value[name] <= high:
                raise ValueError('bounds')
        origins = {name: 'knowledge/planning-query.toml' for name in value}
        narrow = request.get('narrow_overrides', {})
        if not isinstance(narrow, dict) or not set(narrow) <= set(_LIMITS):
            raise ValueError('overrides')
        for name, number in narrow.items():
            if type(number) is not int or not _LIMITS[name][0] <= number <= value[name]:
                raise ValueError('widening')
            value[name] = number
            origins[name] = 'narrow_overrides (repository intersection)'
        return {**value, 'origins': origins, 'consumer': request['consumer']}
    except (ValueError, KeyError, TypeError, OSError):
        raise _Stop('invalid_config') from None


def _previous(record):
    if record is None:
        return None
    # Bounded tail, never import a whole plan/history as query authority.
    with record.open('rb') as stream:
        stream.seek(0, 2)
        stream.seek(max(0, stream.tell() - 262144))
        tail = stream.read(262144).decode('utf-8', errors='ignore')
    for line in reversed(tail.splitlines()):
        if line.startswith(_RECORD_PREFIX) and line.endswith(' -->'):
            try:
                value = json.loads(line[len(_RECORD_PREFIX):-4])
                if isinstance(value, dict) and value.get('schema') == 'planning-query.v1':
                    return value
            except ValueError:
                pass
    return None


def _read_sources(root, paths, origin, index):
    def git(*args):
        proc = subprocess.run(['git', '-C', str(root), *args], capture_output=True,
                              text=True, encoding='utf-8', check=False)
        if proc.returncode:
            raise _Stop('unknown_failure')
        return proc.stdout.strip()
    commit = git('rev-parse', 'HEAD')
    branch = git('rev-parse', '--abbrev-ref', 'HEAD')
    reads = []
    for relative in sorted(set(paths)):
        path = _path(root, relative)
        digest, excerpt = _digest_file(path)
        dirty = git('status', '--porcelain', '--', relative)
        kind = 'worktree' if dirty else ('main' if branch == 'main' else 'branch')
        identity = {'kind': kind, 'commit': commit}
        if dirty:
            identity.update(base_commit=commit, sha256=digest)
        actual_origin = origin
        if dirty or (index and commit != index.get('commit')):
            actual_origin = 'direct-source'
        reads.append({'path': relative, 'origin': actual_origin, 'sha256': digest,
                      'read_identity': identity, 'excerpt_range': {'start_byte': 0,
                      'end_byte': len(excerpt.encode('utf-8'))}, 'excerpt': excerpt})
    return reads


def diagnose(request, repository_root, catalog_path, policies_path, projections_path):
    """Separate ordinary planning advice from unchanged formal Locator gates."""
    if 'operation' not in request:
        return _legacy(request, repository_root, catalog_path, policies_path, projections_path)
    root = Path(repository_root).resolve()
    stage, consumer = request.get('stage'), request.get('consumer')
    output = {'schema': 'planning-query.v1', 'episode_id': _hash(_wire({
        'stage': stage, 'operation': request.get('operation'), 'task': request.get('task_id')})),
        'stage': stage, 'operation': request.get('operation'), 'consumer': consumer,
        'outcome': 'blocked', 'reason_code': 'invalid_request', 'index_identity': None,
        'candidates': [], 'read_set': [],
        'budget_usage': {'calls': 0, 'candidates': 0, 'output_bytes': 0},
        'diagnostic': {'incomplete': True, 'exit_code': None, 'raw_status': None,
                       'recorded_at': datetime.now(timezone.utc).isoformat()}}
    record = None
    config = {'max_output_bytes': 65536}
    previous = None
    prior_bytes = 0
    exits = []
    valid_publication = None
    def state(outcome, reason):
        output.update(outcome=outcome, reason_code=reason)
        output['diagnostic']['incomplete'] = outcome != 'hit'
    try:
        if not isinstance(stage, str) or stage not in _STAGES or _STAGES[stage] != consumer:
            raise _Stop('invalid_request')
        if request.get('operation') not in {'create', 'repair', 'update', 'resume'}:
            raise _Stop('invalid_request')
        if not isinstance(request.get('task_id'), str) or not request['task_id']:
            raise _Stop('invalid_request')
        required = {'schema_version', 'request_id', 'consumer', 'query', 'snapshot', 'policy_revision'}
        optional = {'stage', 'operation', 'task_id', 'scope', 'relevant_inputs',
                    'narrow_overrides', 'record_path', 'delivery_stream',
                    'cancel_event', 'supplement_reason'}
        snapshot = request.get('snapshot')
        if (not required <= request.keys() or not request.keys() <= required | optional
                or request.get('schema_version') != 'jimuyun.knowledge-locator-request.v1'
                or any(not isinstance(request.get(k), str) or not request[k].strip()
                       for k in ('request_id', 'query', 'policy_revision'))
                or not isinstance(snapshot, dict) or set(snapshot) != {'ref', 'commit'}
                or snapshot.get('ref') != 'refs/heads/main'
                or not isinstance(snapshot.get('commit'), str)
                or re.fullmatch('[0-9a-f]{40}', snapshot['commit']) is None):
            raise _Stop('invalid_request')
        config = _configuration(root, request)
        output['diagnostic']['effective_config'] = config
        paths = [Path(p) if Path(p).is_absolute() else root/Path(p)
                 for p in (catalog_path, policies_path, projections_path)]
        if any(p != root/name or p.resolve() != (root/name).resolve()
               for p, name in zip(paths, _CANONICAL)):
            raise _Stop('path_denied')
        if any(not p.resolve().is_relative_to(root) for p in paths):
            raise _Stop('path_denied')
        scope = request.get('scope')
        if not isinstance(scope, list) or not scope or any(not isinstance(p, str) for p in scope):
            raise _Stop('invalid_request')
        source_hashes = {p: _digest_file(_path(root, p))[0] for p in sorted(set(scope))}
        if request.get('record_path') is not None:
            record = _path(root, request['record_path'])
        previous = _previous(record)
        intent = {'stage': stage, 'operation': request['operation'], 'task': request['task_id'],
                  'scope': sorted(source_hashes), 'inputs': request.get('relevant_inputs', {}),
                  'query': request.get('query'), 'consumer': consumer}
        output['episode_id'] = _hash(_wire({'intent': intent, 'sources': source_hashes}))
        output['diagnostic'].update(intent_hash=_hash(_wire(intent)), source_hashes=source_hashes)
        if previous and previous.get('episode_id') == output['episode_id']:
            usage = previous.get('budget_usage', {})
            if any(type(usage.get(k)) is not int or usage[k] < 0
                   for k in ('calls', 'candidates', 'output_bytes')):
                raise _Stop('integrity_failed')
            output['budget_usage'] = dict(usage)
            prior_bytes = usage['output_bytes']
        elif previous:
            output['diagnostic'].update(predecessor_episode_id=previous['episode_id'],
                refresh_reason='task_changed' if previous.get('diagnostic', {}).get('intent_hash') != _hash(_wire(intent)) else 'source_changed')
        # Pin the input bytes before invoking the shared core. A concurrent
        # publication cannot reattribute already loaded candidates.
        catalog = json.loads(paths[0].read_text(encoding='utf-8'))
        policy = json.loads(paths[1].read_text(encoding='utf-8'))
        effective_policy = core._policy_for(request, policy)
        if effective_policy and type(effective_policy.get('max_candidates')) is int:
            config['max_candidates'] = min(config['max_candidates'], effective_policy['max_candidates'])
        pointer_path = root/'knowledge/indexes/current.json'
        valid_publication = core.verify_current_publication(root, catalog_path=paths[0], policy_path=paths[1], projections_path=paths[2])
        if valid_publication:
            pointer = json.loads(pointer_path.read_text(encoding='utf-8'))
            snapshot = core.catalog_source_snapshot(catalog)
            output['index_identity'] = {**{k: v for k, v in snapshot.items() if k != 'sources'}, 'generation_id': pointer['generation_id'],
                                        'policy_revision': policy['policy_revision']}
        output['diagnostic']['permission_checked'] = effective_policy is not None and valid_publication
        same = previous and previous.get('episode_id') == output['episode_id']
        if same and previous.get('diagnostic', {}).get('closed'):
            # No new query, delivery, or success record after the one terminal
            # report. Return its immutable diagnostic to the recovering caller.
            closed = copy.deepcopy(previous)
            closed.pop('query', None)
            return closed
        if same and valid_publication and effective_policy and not request.get('supplement_reason'):
            old = previous.get('diagnostic', {})
            reads_valid = all(_digest_file(_path(root, r['path']))[0] == r['sha256']
                              for r in previous.get('read_set', []))
            if reads_valid and previous.get('outcome') in {'hit', 'no_match', 'degraded'}:
                current = output['diagnostic']
                output = copy.deepcopy(previous)
                output['diagnostic'].update(current, reused=True)
                # Reuse retains the identity of the actual original query.
                output['index_identity'] = previous['index_identity']
                raise _Stop('reused')
        usage = output['budget_usage']
        if same and (usage['calls'] >= config['max_calls'] or usage['candidates'] >= config['max_candidates']):
            raise _Stop('budget_exhausted')
        if not config['enabled']:
            if not valid_publication or effective_policy is None:
                raise _Stop('integrity_failed' if not valid_publication else 'policy_denied')
            state('unavailable', 'disabled')
            with _bounded_children(config['timeout_seconds'], request.get('cancel_event'), exits):
                output['read_set'] = _read_sources(root, scope, 'direct-source', output['index_identity'])
            raise _Stop('finished')
        usage['calls'] += 1
        locator = {key: value for key, value in request.items() if key in {
            'schema_version', 'request_id', 'consumer', 'query', 'snapshot', 'policy_revision'}}
        with _bounded_children(config['timeout_seconds'], request.get('cancel_event'), exits) as remaining:
            with _source_hash_transport(remaining, request.get('cancel_event')):
                raw = core.query_with_diagnostics(locator, root, catalog_path=paths[0],
                    policies_path=paths[1], projections_path=paths[2],
                    max_candidates=config['max_candidates']-usage['candidates'])
            if not isinstance(raw, dict) or not isinstance(raw.get('result'), dict) or not isinstance(raw.get('diagnostics'), list):
                raise _Stop('unknown_failure')
            result = raw['result']
            output.update(result=result, diagnostics=raw['diagnostics'])
            output['diagnostic'].update(raw_status=result.get('status'), evidence_refs=[{'sha256': _hash(_wire(raw))}])
            codes = {d.get('code') for d in raw['diagnostics'] if isinstance(d, dict)}
            # Integrity/policy errors always outrank stale, empty, or cancel.
            if not valid_publication or 'publication_invalid' in codes:
                raise _Stop('integrity_failed' if pointer_path.exists() else 'publication_missing')
            if codes & {'snapshot_missing', 'snapshot_mismatch', 'projection_invalid'}:
                raise _Stop('integrity_failed')
            if effective_policy is None or 'policy_missing' in codes:
                raise _Stop('policy_denied')
            if any(code not in {'stale'} for code in codes):
                raise _Stop('unknown_failure')
            if any(code not in {0, 1} for code in exits):
                raise _Stop('unknown_failure')
            candidates = result.get('candidates')
            if not isinstance(candidates, list):
                raise _Stop('unknown_failure')
            known = {m['source_path']: m['source_sha256'] for m in catalog.get('modules', [])}
            for candidate in candidates:
                if not isinstance(candidate, dict) or candidate.get('path') not in known:
                    raise _Stop('integrity_failed')
                if candidate.get('source_sha256') != known[candidate['path']]:
                    raise _Stop('integrity_failed')
                _path(root, candidate['path'])
            usage['candidates'] += len(candidates)
            if usage['candidates'] > config['max_candidates']:
                raise _Stop('budget_exhausted')
            if 'stale' in codes:
                state('degraded', 'stale_verified')
            elif result.get('status') == 'insufficient_match':
                state('degraded', 'insufficient_match') if candidates else state('no_match', 'empty')
            elif result.get('status') == 'matched' and candidates:
                if any(c.get('rank_evidence', {}).get('confidence') not in {'high', 'medium'} for c in candidates):
                    state('degraded', 'low_confidence')
                else:
                    state('hit', 'matched')
            else:
                raise _Stop('unknown_failure')
            if request.get('cancel_event') is not None and request['cancel_event'].is_set():
                raise _Stop('cancelled')
            chosen = [c['path'] for c in candidates] if output['outcome'] == 'hit' else []
            # Explicit source scope remains separate from query candidates.
            output['read_set'] = _read_sources(root, [*chosen, *scope],
                'locator' if output['outcome'] == 'hit' else 'direct-source', output['index_identity'])
            if output['outcome'] == 'hit' and any(r['origin'] == 'direct-source' and r['path'] in known
                  and r['sha256'].removeprefix('sha256:') != known[r['path']].removeprefix('sha256:') for r in output['read_set']):
                state('degraded', 'source_changed')
                for r in output['read_set']:
                    r['origin'] = 'direct-source'
            output['candidates'] = candidates if output['outcome'] == 'hit' else []
    except _Stop as error:
        if error.reason not in {'finished', 'reused'}:
            reason = error.reason
            kind = {'config_missing': 'unavailable', 'timeout': 'unavailable',
                    'cancelled': 'cancelled', 'budget_exhausted': 'budget_exhausted'}.get(reason, 'blocked')
            # Preserve a previously observed integrity error on cancellation.
            if reason == 'cancelled' and (valid_publication is False or
                    (previous and previous.get('reason_code') == 'integrity_failed')):
                kind, reason = 'blocked', 'integrity_failed'
            state(kind, reason)
            output['candidates'], output['read_set'] = [], []
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        state('blocked', 'unknown_failure')
        output['candidates'], output['read_set'] = [], []
    diagnostic = output['diagnostic']
    if output['outcome'] in {'blocked', 'cancelled', 'budget_exhausted'}:
        result = output.get('result')
        if isinstance(result, dict) and result.get('candidates'):
            # The original payload's digest remains diagnostic evidence. Never
            # forward rejected content as an apparently usable nested result.
            output['result'] = {**result, 'status': 'blocked', 'candidates': []}
    diagnostic.setdefault('evidence_refs', [{'reason_code': output['reason_code']}])
    diagnostic['requires_source_check'] = output['outcome'] in {'no_match', 'degraded', 'unavailable'}
    if output['outcome'] in {'blocked', 'cancelled', 'budget_exhausted'} and 'result' not in output:
        output['result'] = {'status': 'blocked', 'candidates': []}
    diagnostic['closed'] = output['outcome'] in {'cancelled', 'budget_exhausted'}
    def encode():
        # Solve the byte-count field's own decimal length to a fixed point.
        for _ in range(8):
            data = _wire(output)
            count = prior_bytes + len(data)
            if output['budget_usage']['output_bytes'] == count:
                return data
            output['budget_usage']['output_bytes'] = count
        return _wire(output)
    data = encode()
    if len(data) + prior_bytes > config['max_output_bytes'] - 4096:
        state('budget_exhausted', 'budget_exhausted')
        output['candidates'], output['read_set'] = [], []
        output['index_identity'] = None
        output.pop('result', None)
        output.pop('diagnostics', None)
        output['diagnostic'] = {'incomplete': True, 'closed': True,
            'summary': 'The bounded episode has no remaining delivery allowance.',
            'recorded_at': datetime.now(timezone.utc).isoformat(),
            **({'effective_config': config} if len(_wire(config)) < 2048 else {})}
        data = encode()
    if len(data) + prior_bytes > config['max_output_bytes']:
        # A closed episode is never reopened to emit additional content.
        raise ValueError('planning_episode_delivery_exhausted')
    if record is not None:
        log = {**output, 'query': request.get('query')}
        with record.open('ab') as stream:
            stream.write((_RECORD_PREFIX + _wire(log).decode('utf-8') + ' -->\n').encode('utf-8'))
    delivery = request.get('delivery_stream')
    if delivery is not None:
        delivery.write(data)
    return output
