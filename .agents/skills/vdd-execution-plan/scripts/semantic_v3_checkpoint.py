"""ADR-0041: native V3 pause candidates, never plan-ready or execution proof.

Only the public compiler produces this content-bound candidate after V3A and
execution preflight. Resume rechecks V0/V2, worker gates, normalization and both
preflights; the saved result is not an instruction pointer or fixture import.
"""
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path

import semantic_compiler as sc

_current = None


def _rules():
    directory = Path(__file__).parent
    names = {'semantic_compiler.py', 'semantic_compiler_gate.py',
             'semantic_compiler_authority.py', 'semantic_v3_checkpoint.py',
             'semantic_feasibility_patch.py', 'semantic_worker_transport_patch.py',
             'semantic_worker_contract_patch.py', 'semantic_worker_relational_patch.py',
             'execution_contract.py',
             'execution_preflight.py', 'semantic_slice_cohesion_patch.py'}
    names.update(p.name for p in directory.glob('semantic_worker_v3*.py'))
    return {name: sc.sha256_bytes((directory / name).read_bytes()) for name in sorted(names)}


def _validate(payload, value, root):
    import semantic_compiler_gate as gate
    import semantic_worker_v3_domain_patch as domain
    import semantic_worker_v3_execution_contract_patch as execution
    findings = gate._worker_schema_findings('v3', value)
    findings += domain._domain_findings('v3', payload, value)
    findings += execution._findings(root, 'v3', payload, value, diagnostic_dir=None)
    if sc._v3_cache_requires_contract_refresh(value, root, payload):
        findings.append('v3-pause:current-contract-refresh-required')
    if findings:
        raise ValueError('V3 pause candidate invalid: ' + '; '.join(findings))


@contextmanager
def session(*, root, out_dir, enabled, resume):
    global _current
    if not enabled:
        yield
        return
    if _current is not None:
        raise ValueError('nested V3 pause session')
    previous = sc.invoke_worker
    context = {'root': Path(root), 'out_dir': Path(out_dir), 'resume': resume,
               'raw': None, 'reused': False, 'replay': False, 'identity': None}
    _current = context
    def worker(**kwargs):
        if kwargs['stage'] != 'v3' or context['identity'] is None:
            # A later V4-directed V3 correction must supersede this candidate,
            # never have its corrected answer hidden by in-memory replay.
            if kwargs['stage'].startswith('v3'):
                context.update(raw=None, replay=False)
            return previous(**kwargs)
        obligations = kwargs['payload'].get('obligations')
        if sc.sha256_value(obligations) != context['identity']['obligations_sha256']:
            return previous(**kwargs)
        if context['replay'] and context['raw'] is not None:
            value = deepcopy(context['raw'])
            _validate(kwargs['payload'], value, context['root'])
            return value
        value = previous(**kwargs)
        # Capture only a returned native result, never a pending response file.
        _validate(kwargs['payload'], value, context['root'])
        context['raw'] = deepcopy(value)
        return value
    sc.invoke_worker = worker
    try:
        yield
    finally:
        sc.invoke_worker = previous
        _current = None


def prepare(*, source_index, obligations, profile):
    if _current is None:
        return False
    context = _current
    identity = {'schema': 'vdd.v3-pause-candidate.v1',
                'repository_root': str(context['root'].resolve()),
                'output_directory': str(context['out_dir'].resolve()),
                'source_index_sha256': source_index['sha256'],
                'obligations_sha256': sc.sha256_value(list(obligations)),
                'profile': profile, 'rules': _rules()}
    context.update(identity=identity, raw=None, reused=False, replay=False)
    path = context['out_dir'] / '.compiler-work/v3-checkpoints' / (sc.sha256_value(identity)[7:] + '.json')
    output = context['out_dir'].absolute()
    if any(p.is_symlink() for p in (path, *path.parents) if p.is_relative_to(output)):
        raise ValueError('unsafe V3 pause candidate path')
    context['path'] = path
    if not context['resume'] or not path.exists():
        return False
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError('unsafe V3 pause candidate')
    record = json.loads(path.read_text(encoding='utf-8'))
    if (not isinstance(record, dict) or record.get('identity') != identity
            or record.get('authorizes') != []
            or record.get('completed_checks') != ['V3', 'V3A', 'V3-execution-preflight']
            or not isinstance(record.get('candidate'), dict)
            or sc.sha256_value(record['candidate']) != record.get('candidate_sha256')):
        raise ValueError('V3 pause candidate identity/integrity mismatch')
    _validate({'obligations': list(obligations)}, record['candidate'], context['root'])
    context.update(raw=record['candidate'], reused=True, replay=True)
    return True


def save():
    if _current is None or _current['raw'] is None:
        raise ValueError('no returned native V3 candidate to pause')
    context = _current
    record = {'identity': context['identity'], 'candidate': context['raw'],
              'candidate_sha256': sc.sha256_value(context['raw']),
              'completed_checks': ['V3', 'V3A', 'V3-execution-preflight'],
              'authorizes': []}
    path = context['path']
    # Content-addressed identity; never overwrite differing or corrupt history.
    if path.exists():
        if path.is_symlink() or json.loads(path.read_text(encoding='utf-8')) != record:
            raise ValueError('conflicting V3 pause candidate; history preserved')
    else:
        sc.atomic_json(path, record)
    return {'path': str(path), 'sha256': sc.sha256_bytes(path.read_bytes()),
            'candidate_sha256': record['candidate_sha256'], 'authorizes': []}
