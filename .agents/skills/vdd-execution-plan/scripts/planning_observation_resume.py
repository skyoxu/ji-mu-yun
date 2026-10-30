"""ADR-0041/0048; adopted planning-query AD-8: reference an existing delivery.

This is deliberately limited to native group-repair chunks. It neither replays
semantic candidates nor queries/delivers advice, and never updates the episode.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

import semantic_compiler as sc
from semantic_resume_cache import _digest_request
import semantic_phase_source_scope as phase_scope
import semantic_worker_v3_group_repair_patch as group
from scripts.toolchain.knowledge_query import adapter


def _reject(reason):
    raise ValueError('PLANNING_OBSERVATION_REUSE_BLOCKED:' + reason)


def _file(root, value):
    if not isinstance(value, (str, Path)):
        _reject('unsafe_path')
    path = Path(value)
    if '..' in path.parts:
        _reject('unsafe_path')
    if not path.is_absolute():
        path = root / path
    try:
        relative = path.relative_to(root)
    except ValueError:
        _reject('outside_repository')
    if (not relative.parts or any('\\' in part or ':' in part for part in relative.parts)
            or relative.parts[0] in {'.git', '.ssh', '.aws', 'secrets'}):
        _reject('unsafe_path')
    for part in [path, *path.parents]:
        if part == root:
            break
        if part.is_symlink() or getattr(part, 'is_junction', lambda: False)():
            _reject('unsafe_path')
    if not path.is_file() or path.resolve() != path:
        _reject('missing_or_unsafe_file')
    return path


def _json(root, path):
    path = _file(root, path)
    if path.stat().st_size > 4 * 1024 * 1024:
        _reject('oversized_native_artifact')
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        _reject('invalid_native_object')
    return value


def _raw_hash(path):
    with path.open('rb') as stream:
        return 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest()


def _relative(root, path):
    return path.relative_to(root).as_posix()


def _delivery(root, out, origin):
    """Validate the existing host return and exact native chunk cache, not V3 approval."""
    request_path = _file(root, origin)
    if request_path.name != 'request.json' or not request_path.is_relative_to(root / 'logs'):
        _reject('explicit_native_request_required')
    call = request_path.parent
    request = _json(root, request_path)
    session = _json(root, call.parent / 'session.json')
    result = _json(root, call / 'result.json')
    response = _json(root, call / 'response.json')
    request_sha = _digest_request(request)
    if (request.get('schema') != 'jimuyun.host-request.v1'
            or request.get('repository_root') != str(root)
            or request.get('mode') != 'read-only' or request.get('authorizes') != []
            or request.get('request_id') != call.name
            or session.get('schema') != 'jimuyun.host-session.v1'
            or session.get('repository_root') != str(root) or session.get('authorizes') != []
            or request.get('session_id') != session.get('session_id')
            or result.get('status') != 'returned' or result.get('backend') != 'host-session'
            or response.get('schema') != 'jimuyun.host-response.v1'
            or response.get('session_id') != session.get('session_id')
            or any(x.get('request_id') != call.name or x.get('request_sha256') != request_sha
                   or x.get('authorizes') != [] for x in (result, response))):
        _reject('native_return_binding')
    # Historical deadline expiry is immaterial to an actually returned request.
    output = _file(root, request.get('output_path', ''))
    if output.parent != out / '.compiler-work':
        _reject('different_target')
    match = re.fullmatch(re.escape(group._GROUP_STAGE) + r'(-chunk-[a-zA-Z0-9-]+)-[0-9a-f]{24}-last-message\.json', output.name)
    if not match:
        _reject('unsupported_native_route')
    stage = group._GROUP_STAGE + match[1]
    prompt = request.get('prompt', '')
    if '\n\nINPUT:\n' not in prompt:
        _reject('native_input_missing')
    header, raw = prompt.split('\n\nINPUT:\n', 1)
    payload, end = json.JSONDecoder().raw_decode(raw)
    tail = raw[end:]
    if tail.strip() and not tail.startswith('\n\nORACLE UNIQUENESS CONSTRAINT:'):
        _reject('unsupported_native_suffix')
    if not isinstance(payload, dict) or not isinstance(payload.get('input'), dict):
        _reject('native_input_missing')
    prepared = payload['input'].get('planning_source_observations')
    marker = '\nPlanning source observations (advisory, not requirement authority):\n'
    try:
        header_observation = json.loads(header.split(marker, 1)[1].split('\n', 1)[0])
    except (IndexError, ValueError):
        _reject('native_advice_binding')
    if prepared != header_observation:
        _reject('native_advice_binding')
    cache = _file(root, out / '.compiler-cache' / sc._worker_cache_key(stage, payload))
    value = _json(root, cache)
    if (sc._parse_json_output(response.get('output_text', '')) != value
            or sc._parse_json_output(output.read_text(encoding='utf-8')) != value):
        _reject('native_cache_binding')
    # Current native domain/source/path validation is mandatory. Its result is
    # not returned as an adopted candidate; normal resume still owns all gates.
    if payload['input'].get('source_scope') != phase_scope.description(root):
        _reject('current_source_scope_changed')
    projected = group._project_execution_output(root, payload, deepcopy(value))
    from semantic_worker_v3_execution_contract_patch import _findings
    findings = [*group.gate._worker_schema_findings('v3', projected),
                *group.v3_domain._domain_findings('v3-schema-repair', payload, projected),
                *_findings(root, 'v3-schema-repair', payload, projected)]
    phase_scope.validate_hints(root, projected['slice_hints'])
    if findings:
        _reject('native_domain_or_source_invalid')
    progress = _file(root, out / '.compiler-work/compiler-progress.jsonl')
    starts, returns = [], []
    with progress.open(encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            if row.get('schema') != 'vdd.compiler-progress.v1':
                continue
            if (row.get('event') == 'worker-started' and row.get('backend') == 'host-session'
                    and row.get('stage') == 'v3-schema-repair' + match[1]
                    and Path(row.get('output_last_message', '')).as_posix() in {
                        str(output), _relative(root, output)}):
                starts.append(row)
            if row.get('event') == 'worker-returned':
                returns.append(row)
    if len(starts) != 1:
        _reject('native_call_ambiguous_or_missing')
    paired = [r for r in returns if r.get('call_id') == starts[0].get('call_id')]
    if (len(paired) != 1 or paired[0].get('exit_code') != 0
            or paired[0].get('pid') != starts[0].get('pid')
            or paired[0].get('stage') != starts[0].get('stage')):
        _reject('native_call_not_returned')
    witnesses = {name: {'path': _relative(root, path), 'sha256': _raw_hash(path)}
                 for name, path in [('request', request_path), ('response', call / 'response.json'),
                     ('result', call / 'result.json'), ('output', output), ('cache', cache)]}
    witnesses['request']['canonical_sha256'] = request_sha
    return prepared, witnesses


def _reference(*, root, out_dir, origin, request):
    root, out = Path(root).resolve(), Path(out_dir).resolve()
    if not out.is_relative_to(root) or request.get('task_id') != _relative(root, out):
        _reject('different_task')
    prepared, witnesses = _delivery(root, out, origin)
    if not isinstance(prepared, dict) or prepared.get('status') != 'prepared' or prepared.get('authorizes') != []:
        _reject('not_delivered_advice')
    query = prepared.get('query_result', {})
    if (query.get('schema') != 'planning-query.v1' or query.get('consumer') != 'vdd'
            or query.get('stage') != request.get('stage') or query.get('operation') != request.get('operation')
            or query.get('outcome') not in {'hit', 'no_match', 'degraded'}
            or query.get('diagnostic', {}).get('permission_checked') is not True
            or query.get('diagnostic', {}).get('closed') is not False):
        _reject('different_judgment_or_failed_origin')
    record = _file(root, request['record_path'])
    if record != out / 'execution-record.md':
        _reject('different_record')
    exact, episode_rows = [], []
    # Match the exact producer object, not latest success or a caller envelope.
    with record.open('rb') as stream:
        for raw_line in stream:
            prefix = adapter._RECORD_PREFIX.encode()
            if not raw_line.startswith(prefix) or not raw_line.endswith(b' -->\n'):
                continue
            row = json.loads(raw_line[len(prefix):-5])
            if row.get('episode_id') == query['episode_id']:
                episode_rows.append(row)
            if {k: v for k, v in row.items() if k != 'query'} == query:
                exact.append((raw_line, row))
    if len(exact) != 1 or exact[0][1].get('query') != request.get('query'):
        _reject('producer_record_binding')
    sources = {p: adapter._digest_file(_file(root, p))[0] for p in sorted(set(request['scope']))}
    if sources != query['diagnostic'].get('source_hashes'):
        _reject('scope_or_source_changed')
    references = query.get('source_references', [])
    for row in references:
        _file(root, row['path'])
    checked_refs = adapter._reference_metadata(root, {**request,
        'relevant_inputs': {'source_references': references}})
    intent = {'stage': request['stage'], 'operation': request['operation'], 'task': request['task_id'],
              'scope': sorted(sources), 'inputs': {'source_references': checked_refs} if checked_refs else {},
              'query': request['query'], 'consumer': 'vdd'}
    if (adapter._hash(adapter._wire(intent)) != query['diagnostic'].get('intent_hash')
            or adapter._hash(adapter._wire({'intent': intent, 'sources': sources})) != query['episode_id']):
        _reject('different_task_intent')
    if any(adapter._digest_file(_file(root, row['path']))[0] != row['sha256'] for row in query.get('read_set', [])):
        _reject('observed_source_changed')
    config = adapter._configuration(root, {'consumer': 'vdd'})
    paths = [_file(root, p) for p in adapter._CANONICAL]
    catalog, policies, projection = [_json(root, p) for p in paths]
    envelope = {'consumer': 'vdd', 'query': request['query'], 'policy_revision': policies['policy_revision']}
    policy = adapter.core._policy_for(envelope, policies)
    if not adapter.core.verify_current_publication(root, catalog_path=paths[0], policy_path=paths[1], projections_path=paths[2]):
        _reject('current_publication_invalid')
    if policy is None or not config['enabled']:
        _reject('current_permission_denied')
    eligible = adapter.core._projection_for(envelope, catalog, policies, projection)
    modules = {m['source_path']: m for m in catalog.get('modules', [])}
    candidates = [*query.get('candidates', []), *query.get('result', {}).get('candidates', [])]
    by_id = {m['module_id']: m for m in catalog.get('modules', [])}
    for row in candidates:
        module = by_id.get(row.get('module_id'))
        if (module is None or module['source_path'] != row.get('path')
                or (eligible is not None and module['module_id'] not in eligible)
                or not adapter.core._policy_allows(module, request['query'], policy)
                or module.get('source_sha256') != row.get('source_sha256')):
            _reject('current_permission_denied')
    for row in query.get('read_set', []):
        if row['path'] in sources:
            continue  # Explicit scope is reauthorized by the current public route.
        module = modules.get(row['path'])
        if (module is None or (eligible is not None and module['module_id'] not in eligible)
                or not adapter.core._policy_allows(module, request['query'], policy)):
            _reject('current_permission_denied')
    if type(policy.get('max_candidates')) is int:
        config['max_candidates'] = min(config['max_candidates'], policy['max_candidates'])
    if config != query['diagnostic'].get('effective_config'):
        _reject('current_configuration_changed')
    usage = query.get('budget_usage', {})
    if any(type(usage.get(k)) is not int or usage[k] < 0 for k in ('calls', 'candidates', 'output_bytes')):
        _reject('invalid_original_charge')
    # The actual producer row preserves cumulative charging, including its final
    # closed row. Reuse emits no advice bytes and writes no planning-query row.
    charge = len(adapter._wire(query))
    position = next(j for j, row in enumerate(episode_rows) if row == exact[0][1])
    prior = episode_rows[position - 1]['budget_usage']['output_bytes'] if position else 0
    if usage['output_bytes'] != prior + charge:
        _reject('original_charge_mismatch')
    closed = any(row.get('diagnostic', {}).get('closed') is True for row in episode_rows)
    reference = {'status': 'reference-only', 'authorizes': [], 'already_delivered': True,
            'original_outcome': query['outcome'], 'original_reason': query['reason_code'],
            'episode_id': query['episode_id'], 'episode_closed': closed,
            'observation_sha256': sc.sha256_value(query),
            'producer_record': {'path': _relative(root, record),
                'line_sha256': 'sha256:' + hashlib.sha256(exact[0][0]).hexdigest()},
            'native_delivery': witnesses,
            'boundary': 'Previously delivered observation reference only. Do not reload or redeliver its query JSON, candidates or excerpts. No query or episode is reopened; unknown/new material requires a blocked judgment. Normal native candidate/source gates remain mandatory.'}


    # Private consumer metadata is not worker context or a query delivery. The
    # existing decision writer rechecks actual final-candidate scope and records
    # accepted/rejected itself; no adoption decision is fabricated here.
    decisions = {'query_result': {
        'stage': query['stage'], 'episode_id': query['episode_id'], 'outcome': query['outcome'],
        'diagnostic': {'raw_status': query['diagnostic'].get('raw_status')},
        'read_set': [{key: row[key] for key in ('path', 'sha256', 'read_identity', 'origin')}
                     for row in query.get('read_set', [])]}}
    return reference, decisions


def reference(**kwargs):
    try:
        return _reference(**kwargs)
    except (KeyError, TypeError, AttributeError, adapter._Stop) as exc:
        _reject('invalid_origin_or_permission:' + type(exc).__name__)
