#!/usr/bin/env python3
"""Direct Skill-input v2 preparation, observation, publication and readback.

ADR-0060. This adapter has no lifecycle or Knowledge publication authority.
All consumers share this entry; legacy v1 remains an explicit compatibility API.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import uuid

try:
    from .skill_input_protocol import contained, digest, encoded, identity, read_json, immutable_json, atomic_json, name, check_hash
    from .skill_input_selection import verify_selection, READ_ROLES
    from .skill_input_transport import plan_transport, pages_for, continuation, validate_continuation
    from .skill_input_coverage import prove_ranges
    from .skill_input_generation import publish_receipt, read_generation
    from .skill_input_current import resolve_current, advance_current
    from .skill_input_retention import start_attempt, update_attempt, attempt_path, plan_retention, apply_retention, register_reference
    from .knowledge_gate_projection import project_knowledge_gates, observe_knowledge
    from .skill_input_consumption import redact_bytes
except ImportError:
    from skill_input_protocol import contained, digest, encoded, identity, read_json, immutable_json, atomic_json, name, check_hash
    from skill_input_selection import verify_selection, READ_ROLES
    from skill_input_transport import plan_transport, pages_for, continuation, validate_continuation
    from skill_input_coverage import prove_ranges
    from skill_input_generation import publish_receipt, read_generation
    from skill_input_current import resolve_current, advance_current
    from skill_input_retention import start_attempt, update_attempt, attempt_path, plan_retention, apply_retention, register_reference
    from knowledge_gate_projection import project_knowledge_gates, observe_knowledge
    from skill_input_consumption import redact_bytes

BINDINGS = {'contract', 'registry', 'authority', 'knowledge_freeze'}
MODULES = ('skill_input_protocol.py', 'skill_input_selection.py', 'skill_input_transport.py',
           'skill_input_coverage.py', 'skill_input_generation.py', 'skill_input_current.py',
           'skill_input_retention.py', 'knowledge_gate_projection.py', 'knowledge_context_validation.py', '_knowledge_locator_core.py', 'skill_input_v2.py', 'skill_input_consumption.py')


def validator_identity():
    parent = Path(__file__).parent
    return identity({p: digest((parent / p).read_bytes()) for p in MODULES})


def verify_bindings(repository_root, bindings):
    if not isinstance(bindings, dict) or set(bindings) != BINDINGS:
        raise ValueError('contract, registry, authority and knowledge_freeze bindings required')
    for key, ref in bindings.items():
        if not isinstance(ref, dict) or set(ref) != {'path', 'sha256'}:
            raise ValueError('invalid ' + key + ' binding')
        check_hash(ref['sha256'])
        path = contained(repository_root, ref['path'])
        if not path.is_file() or digest(path.read_bytes()) != ref['sha256']:
            raise ValueError(key + ' binding is stale or missing')
    return bindings


def source_bytes(repository_root, selection):
    result = {}
    for row in selection['sources']:
        if row['role'] not in READ_ROLES:
            continue
        raw = contained(repository_root, row['path']).read_bytes()
        if digest(raw) != row['sha256']:
            raise ValueError('source changed during read')
        safe, _sensitivity, redaction = redact_bytes(raw)
        if redaction == 'failed':
            raise ValueError('source redaction failed')
        result[row['path']] = safe
    return result


def _storage(repository_root, storage):
    if storage.startswith(('logs/', '.skill-input-work/')):
        raise ValueError('storage must not overlap runtime evidence or attempts')
    return contained(repository_root, storage)


def prepare(repository_root, request, *, allow_refresh=False):
    required = {'schema_version', 'plan_id', 'consumer', 'operation', 'policy_revision', 'storage', 'sources', 'bindings'}
    optional = {'page_bytes', 'max_snapshot_bytes', 'max_retries', 'changed_paths'}
    if not isinstance(request, dict) or not required <= set(request) or set(request) - required - optional or request['schema_version'] != 'skill-input-request.v2':
        raise ValueError('invalid v2 request')
    for field in ('plan_id', 'consumer', 'operation', 'policy_revision'):
        name(request[field])
    verify_bindings(repository_root, request['bindings'])
    contract = read_json(contained(repository_root, request['bindings']['contract']['path']))
    if contract.get('consumer') != request['consumer'] or request['operation'] not in contract.get('operations', {}):
        raise ValueError('consumer or operation is outside bound contract')
    selection = verify_selection(repository_root, request['sources'], consumer=request['consumer'], policy_revision=request['policy_revision'], allow_refresh=allow_refresh)
    store = _storage(repository_root, request['storage'])
    # Typed sources may never include the adapter output, regardless of filename.
    if any(p == request['storage'] or p.startswith(request['storage'] + '/') for p in selection['read_set']):
        raise ValueError('source selection overlaps output storage')
    previous = resolve_current(store)
    previous_receipt = read_generation(store, previous['generation_id'])['receipt'] if previous else None
    same = previous_receipt is None or previous_receipt['selection']['sourceSelectionHash'] == selection['sourceSelectionHash']
    authority_same = previous_receipt is None or previous_receipt['bindings']['authority'] == request['bindings']['authority']
    if not same:
        raise ValueError('selection-drift')
    if not authority_same:
        raise ValueError('authority-drift')
    knowledge = observe_knowledge(repository_root, contained(repository_root, request['bindings']['knowledge_freeze']['path']), selection_hash=selection['sourceSelectionHash'])
    gates = project_knowledge_gates(catalog_stale=knowledge['catalog_stale'], read_set_same=same,
        source_bytes_same=not selection['refreshed'] and not knowledge['source_refreshed'], authority_same=authority_same, changed_paths=request.get('changed_paths', []))
    if not gates['execution_allowed']:
        raise ValueError(gates['failure'] or gates['route'])
    raw = source_bytes(repository_root, selection)
    snapshot_limit = contract.get('max_snapshot_bytes', 8 * 1024 * 1024)
    page_limit = contract.get('max_snapshot_chunk_bytes', 32768)
    if len(raw) > contract.get('max_sources', 10000):
        raise ValueError('source count exceeds consumer contract')
    if request.get('max_snapshot_bytes', snapshot_limit) > snapshot_limit or request.get('page_bytes', page_limit) > page_limit:
        raise ValueError('requested budget exceeds consumer contract')
    transport = plan_transport(request.get('page_bytes', page_limit), request.get('max_snapshot_bytes', snapshot_limit),
                               content_hash=selection['sourceContentHash'], selection_hash=selection['sourceSelectionHash'], max_retries=request.get('max_retries', 2))
    pages = pages_for(raw, page_bytes=transport['page_bytes'], max_snapshot_bytes=transport['max_snapshot_bytes'])
    attempt_id = uuid.uuid4().hex
    start_attempt(repository_root, request['plan_id'], attempt_id)
    attempt = attempt_path(repository_root, request['plan_id'], attempt_id)
    prepared = {'schema_version': 'skill-input-prepared.v2', 'request': request, 'selection': selection,
                'transport': transport, 'pages': pages, 'previous_current': previous,
                'gates': gates, 'knowledge': knowledge, 'validator_hash': validator_identity(), 'authorizes': []}
    immutable_json(attempt / 'prepared.json', prepared)
    atomic_json(attempt / 'observed.json', {'prepared_hash': identity(prepared), 'pages': [],
                'continuation': continuation(transport, pages)})
    return {'status': 'prepared', 'plan_id': request['plan_id'], 'attempt_id': attempt_id, 'page_count': len(pages), 'authorizes': []}


def _load(repository_root, plan_id, attempt_id):
    attempt = attempt_path(repository_root, plan_id, attempt_id)
    prepared = read_json(contained(attempt, 'prepared.json'))
    request = prepared['request']
    if request['plan_id'] != plan_id or prepared['validator_hash'] != validator_identity():
        raise ValueError('prepared plan or validator identity changed')
    verify_bindings(repository_root, request['bindings'])
    selection = verify_selection(repository_root, prepared['selection']['sources'], consumer=request['consumer'], policy_revision=request['policy_revision'])
    if any(selection[k] != prepared['selection'][k] for k in ('sourceSelectionHash', 'sourceContentHash', 'read_set')):
        raise ValueError('prepared selection changed')
    if observe_knowledge(repository_root, contained(repository_root, request['bindings']['knowledge_freeze']['path']), selection_hash=selection['sourceSelectionHash']) != prepared['knowledge']:
        raise ValueError('Knowledge context changed during transport')
    raw = source_bytes(repository_root, selection)
    expected_pages = pages_for(raw, page_bytes=prepared['transport']['page_bytes'], max_snapshot_bytes=prepared['transport']['max_snapshot_bytes'])
    if expected_pages != prepared['pages']:
        raise ValueError('prepared transport changed')
    observed = read_json(contained(attempt, 'observed.json'))
    if observed['prepared_hash'] != identity(prepared):
        raise ValueError('observation binding mismatch')
    index = validate_continuation(observed['continuation'], prepared['transport'], prepared['pages'])
    if observed['pages'] != expected_pages[:index]:
        raise ValueError('observation prefix is incomplete or conflicting')
    return attempt, prepared, observed, raw, index


def consume(repository_root, plan_id, attempt_id, *, receiver=None, max_pages=None, expected_token=None):
    """Adapter invokes receiver with exact bytes and records only successful delivery.

    CLI writes each page to stdout. A Python caller may supply its actual model
    transport; raising OSError/TimeoutError persists a bounded retry on that page.
    """
    attempt, prepared, observed, raw, index = _load(repository_root, plan_id, attempt_id)
    if expected_token is not None and expected_token != observed['continuation']:
        raise ValueError('stale continuation token')
    if max_pages is not None and (type(max_pages) is not int or max_pages <= 0):
        raise ValueError('invalid page count')
    end = len(prepared['pages']) if max_pages is None else min(index + max_pages, len(prepared['pages']))
    for page_index in range(index, end):
        update_attempt(repository_root, plan_id, attempt_id)
        page = prepared['pages'][page_index]
        data = raw[page['source_path']][page['start_byte']:page['end_byte']]
        try:
            if receiver is not None:
                receiver(dict(page), data)
            else:
                print(json.dumps({'page': page, 'content': data.decode('utf-8')}, ensure_ascii=False), flush=True)
        except (OSError, TimeoutError):
            retry = observed['continuation']['retry_count'] + 1
            if retry > prepared['transport']['max_retries']:
                update_attempt(repository_root, plan_id, attempt_id, status='failed')
                raise ValueError('transport retry budget exhausted')
            observed['continuation'] = continuation(prepared['transport'], prepared['pages'], next_page=page_index, retry_count=retry)
            atomic_json(attempt / 'observed.json', observed)
            raise
        observed['pages'].append(page)
        observed['continuation'] = continuation(prepared['transport'], prepared['pages'], next_page=page_index + 1)
        atomic_json(attempt / 'observed.json', observed)
    return {'status': 'complete' if end == len(prepared['pages']) else 'partial', 'continuation': observed['continuation'], 'authorizes': []}


def finish(repository_root, plan_id, attempt_id):
    attempt, prepared, observed, raw, index = _load(repository_root, plan_id, attempt_id)
    coverage = prove_ranges(raw, observed['pages'], page_bytes=prepared['transport']['page_bytes'])
    request = prepared['request']
    context = {'schema_version': 'skill-input-context.v2', 'sources': [{'path': p, 'content': v.decode('utf-8')} for p, v in sorted(raw.items())], 'authorizes': []}
    receipt = {'schema_version': 'skill-input-receipt.v2', 'plan_id': plan_id,
               'consumer': request['consumer'], 'operation': request['operation'], 'policy_revision': request['policy_revision'],
               'selection': {k: v for k, v in prepared['selection'].items() if k != 'refreshed'},
               'bindings': request['bindings'], 'candidate_hash': prepared['selection']['sourceContentHash'],
               'validator_hash': prepared['validator_hash'], 'coverage': coverage,
               'transport': prepared['transport'], 'gates': prepared['gates'], 'knowledge': prepared['knowledge'],
               'context_hash': identity(context), 'ready': True, 'authorizes': []}
    store = _storage(repository_root, request['storage'])
    update_attempt(repository_root, plan_id, attempt_id)
    generation_id = publish_receipt(store, receipt, context)
    # Protect the generation by lease before the pointer changes.
    update_attempt(repository_root, plan_id, attempt_id, generation_ids=[generation_id])
    validate_generation(repository_root, store, generation_id, consumer=request['consumer'], operation=request['operation'], contract_path=contained(repository_root, request['bindings']['contract']['path']))
    pointer = advance_current(store, generation_id, expected_current=prepared['previous_current'], repository_root=repository_root, consumer=request['consumer'], operation=request['operation'], contract_path=contained(repository_root, request['bindings']['contract']['path']))
    update_attempt(repository_root, plan_id, attempt_id, status='succeeded', generation_ids=[generation_id])
    return {'status': 'ready', 'pointer': pointer, 'authorizes': []}


def validate_generation(repository_root, store, generation_id, *, consumer, operation, contract_path):
    payload = read_generation(store, generation_id)
    receipt = payload['receipt']
    if receipt['consumer'] != consumer or receipt['operation'] != operation or receipt['validator_hash'] != validator_identity():
        raise ValueError('generation consumer, operation or validator changed')
    verify_bindings(repository_root, receipt['bindings'])
    if contained(repository_root, receipt['bindings']['contract']['path']).resolve() != Path(contract_path).resolve():
        raise ValueError('generation contract path mismatch')
    verified = verify_selection(repository_root, receipt['selection']['sources'], consumer=consumer, policy_revision=receipt['policy_revision'])
    for key in ('sourceSelectionHash', 'sourceContentHash', 'read_set'):
        if verified[key] != receipt['selection'][key]:
            raise ValueError('generation source identity mismatch')
    knowledge = observe_knowledge(repository_root, contained(repository_root, receipt['bindings']['knowledge_freeze']['path']), selection_hash=verified['sourceSelectionHash'])
    if knowledge != receipt['knowledge']:
        raise ValueError('current Knowledge context changed')
    raw = source_bytes(repository_root, verified)
    expected_context = {'schema_version': 'skill-input-context.v2', 'sources': [{'path': p, 'content': v.decode('utf-8')} for p, v in sorted(raw.items())], 'authorizes': []}
    if payload['context'] != expected_context or receipt['candidate_hash'] != verified['sourceContentHash']:
        raise ValueError('generation content or candidate mismatch')
    transport = receipt['transport']
    pages = pages_for(raw, page_bytes=transport['page_bytes'], max_snapshot_bytes=transport['max_snapshot_bytes'])
    if prove_ranges(raw, pages, page_bytes=transport['page_bytes']) != receipt['coverage'] or not receipt['gates']['execution_allowed']:
        raise ValueError('generation coverage or gates invalid')
    return receipt


def require_current(repository_root, pointer_path, *, consumer, operation, contract_path):
    pointer_path = Path(pointer_path)
    if pointer_path.name != 'current.v1.json':
        raise ValueError('v2 consumer requires the canonical current pointer')
    pointer_path.resolve().relative_to(Path(repository_root).resolve())
    current = resolve_current(pointer_path.parent)
    if current is None:
        raise ValueError('current generation is missing')
    receipt = validate_generation(repository_root, pointer_path.parent, current['generation_id'], consumer=consumer, operation=operation, contract_path=contract_path)
    return {'status': 'ready', 'ready': True, 'context_artifact': pointer_path.parent / 'skill-input-generations' / current['generation_id'] / 'context.json',
            'context_artifact_hash': receipt['context_hash'], 'binding_hash': current['receipt_hash'], 'authorizes': []}


def main():
    # JSON Lines is a UTF-8 wire protocol, independent of the host locale.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='strict')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository-root', type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('prepare'); p.add_argument('--request', type=Path, required=True); p.add_argument('--allow-refresh', action='store_true')
    for command in ('consume', 'finish'):
        p = commands.add_parser(command); p.add_argument('--plan-id', required=True); p.add_argument('--attempt-id', required=True)
        if command == 'consume':
            p.add_argument('--max-pages', type=int); p.add_argument('--continuation', type=Path)
    p = commands.add_parser('heartbeat'); p.add_argument('--plan-id', required=True); p.add_argument('--attempt-id', required=True); p.add_argument('--lease-seconds', type=int, default=300)
    p = commands.add_parser('reference'); p.add_argument('--storage', required=True); p.add_argument('--reference-id', required=True); p.add_argument('--kind', choices=['lifecycle', 'authorization', 'terminal', 'acceptance'], required=True); p.add_argument('--artifact', required=True); p.add_argument('--generation-id', action='append', required=True)
    p = commands.add_parser('validate'); p.add_argument('--pointer', type=Path, required=True); p.add_argument('--consumer', required=True); p.add_argument('--operation', required=True); p.add_argument('--contract', type=Path, required=True)
    p = commands.add_parser('gc'); p.add_argument('--storage', required=True); p.add_argument('--plan-id', required=True); p.add_argument('--retention-seconds', type=int, default=86400)
    modes = p.add_mutually_exclusive_group(); modes.add_argument('--dry-run', action='store_true'); modes.add_argument('--apply', action='store_true')
    p.add_argument('--approval', type=Path)
    args = parser.parse_args()
    root = args.repository_root.resolve()
    try:
        if args.command == 'prepare':
            result = prepare(root, read_json(args.request), allow_refresh=args.allow_refresh)
        elif args.command == 'consume':
            result = consume(root, args.plan_id, args.attempt_id, max_pages=args.max_pages, expected_token=read_json(args.continuation) if args.continuation else None)
        elif args.command == 'finish':
            result = finish(root, args.plan_id, args.attempt_id)
        elif args.command == 'heartbeat':
            result = update_attempt(root, args.plan_id, args.attempt_id, lease_seconds=args.lease_seconds)
        elif args.command == 'reference':
            result = register_reference(_storage(root, args.storage), root, reference_id=args.reference_id, kind=args.kind, artifact_path=args.artifact, generation_ids=args.generation_id)
        elif args.command == 'validate':
            result = require_current(root, args.pointer, consumer=args.consumer, operation=args.operation, contract_path=args.contract)
        else:
            storage = _storage(root, args.storage)
            kwargs = dict(repository_root=root, plan_id=args.plan_id, retention_seconds=args.retention_seconds)
            result = apply_retention(storage, approval=read_json(args.approval) if args.approval else None, **kwargs) if args.apply else plan_retention(storage, **kwargs)
        print(json.dumps(result, default=str, sort_keys=True))
        return 0 if result.get('status') != 'approval-required' else 1
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'blocked', 'reason': str(exc), 'authorizes': []}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
