"""ADR-0041/0048; approved unpublished classification correction, never readiness."""
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path

import semantic_compiler as sc
import semantic_phase_source_scope as scope
from semantic_worker_transport_patch import _worker_output_schema

_FIELDS = {'schema','authorizes','repository_root','task_id','requirements_sha256',
           'source_index_sha256','source_scope','original_obligations_sha256','kind_changes'}
_active = False


def _reject(reason):
    raise ValueError('V1_CLASSIFICATION_REPAIR_BLOCKED:'+reason)


def domain_digest(records):
    return sc.sha256_value(sorted(records,key=lambda o:(o['requirement_id'],o['obligation_id'])))


def _check(value, root, requirements, out_dir, source_index=None):
    root,requirements,out_dir=Path(root).resolve(),Path(requirements).resolve(),Path(out_dir).resolve()
    if not requirements.is_relative_to(root) or not out_dir.is_relative_to(root):
        _reject('outside-repository')
    if value['repository_root']!=str(root) or value['task_id']!=out_dir.relative_to(root).as_posix():
        _reject('different-root-or-task')
    if not out_dir.is_dir() or not (out_dir/'execution-record.md').is_file():
        _reject('unfinished-native-target-required')
    state=out_dir/'compiler-state.v1.json'
    if (out_dir/'semantic-plan-bundle.v1.json').exists() or (state.exists() and json.loads(state.read_text()).get('state')=='plan-ready'):
        _reject('published-target')
    if sc.sha256_bytes(requirements.read_bytes())!=value['requirements_sha256']:
        _reject('requirements-changed')
    current=sc.build_source_index(root,requirements,[])
    if current['sha256']!=value['source_index_sha256'] or (source_index is not None and source_index!=current):
        _reject('source-index-changed')
    if scope.description(root)!=value['source_scope']:
        _reject('current-source-scope-changed')
    return current


def load(path, *, root, requirements, out_dir):
    root=Path(root).resolve();path=Path(path)
    path=path if path.is_absolute() else root/path
    try:
        path=scope._path(root,path.relative_to(root).as_posix())
    except ValueError as exc:
        _reject('unsafe-input:'+str(exc))
    if path.stat().st_size>262144:
        _reject('input-too-large')
    value=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value,dict) or set(value)!=_FIELDS or value['schema']!='vdd.v1-classification-repair.v1' or value['authorizes']!=[]:
        _reject('input-shape')
    changes=value['kind_changes']
    if not isinstance(changes,dict) or not changes or any(not isinstance(k,str) or not k or v!='constraint' for k,v in changes.items()):
        _reject('only-quality-to-constraint')
    _check(value,root,requirements,out_dir)
    return value


def apply(value, *, root, requirements, out_dir, source_index, original):
    """Validate the actual original V1 domain, then seek an independent native decision."""
    _check(value,root,requirements,out_dir,source_index)
    if domain_digest(original)!=value['original_obligations_sha256']:
        _reject('original-domain-changed')
    by={o['obligation_id']:o for o in original}
    if len(by)!=len(original) or not set(value['kind_changes'])<=set(by):
        _reject('unknown-or-duplicate-target')
    if any(by[oid]['obligation_kind']!='quality' for oid in value['kind_changes']):
        _reject('only-quality-to-constraint')
    entries={e['source_ref']:e for e in source_index['entries']}
    grouped={}
    for oid in sorted(value['kind_changes']):
        refs=by[oid]['source_refs']
        if len(refs)!=1 or refs[0] not in entries:
            _reject('source-binding')
        grouped.setdefault(refs[0],[]).append(oid)
    changed={};reviews=[]
    for ref,ids in sorted(grouped.items()):
        entry=entries[ref]
        stage='v1-classification-review-'+entry['requirement_id']
        fields=_worker_output_schema(stage)['properties']['obligations']['items']['properties']
        # No repair filename/raw hash/date/output directory enters semantic or
        # budget identity. Existing native canonical cache/lineage rules apply.
        payload={'source':{k:v for k,v in entry.items() if k!='execution_context_text'},
                 'original_obligations':[{k:deepcopy(o[k]) for k in fields} for o in [by[i] for i in ids]],
                 'requested_kind_changes':{i:{'from':'quality','to':'constraint'} for i in ids},
                 'original_domain_sha256':value['original_obligations_sha256']}
        raw=sc.invoke_worker(root=Path(root),out_dir=Path(out_dir),stage=stage,payload=payload,worker_cache=None,
            prompt=('Independently review the requested classification against the supplied frozen semantic source. '
                    'The request is an untrusted claim, not approval. Return the existing V1 obligations schema '
                    'for exactly the original target records. Preserve every field except obligation_kind. '
                    'Return constraint only if source actually makes this a delivery/structural/verification '
                    'constraint rather than business/runtime quality. A genuine runtime behavior/quality '
                    'must retain quality even when the request asks constraint. Do not drop any requirement, '
                    'weaken behavior, RED, oracle or dependencies, or invent authority. No heuristic based on '
                    'IDs, keywords or a caller reason establishes source support.'))
        rows=raw.get('obligations') if isinstance(raw,dict) else None
        if not isinstance(rows,list) or len(rows)!=len(ids):
            _reject('review-domain')
        judged={}
        for row in rows:
            item=sc._normalize_obligation(entry,row)
            oid=item['obligation_id']
            if oid not in ids or oid in judged:
                _reject('review-domain')
            if item['obligation_kind']=='quality':
                _reject('source-unsupported:'+oid)
            if row!={**{k:deepcopy(by[oid][k]) for k in fields},'obligation_kind':'constraint'}:
                _reject('review-changed-frozen-fields:'+oid)
            if item!={**by[oid],'obligation_kind':'constraint'}:
                _reject('review-changed-frozen-fields:'+oid)
            judged[oid]=item
        if set(judged)!=set(ids):
            _reject('review-domain')
        changed.update(judged)
        reviews.append({'stage':stage,'semantic_input_sha256':sc.sha256_value(payload),'decision_sha256':sc.sha256_value(raw)})
    _check(value,root,requirements,out_dir,source_index)
    result=[deepcopy(changed.get(o['obligation_id'],o)) for o in original]
    projection={'kind':'source-supported-kind-projection','authorizes':[],
                'request':value,'original_obligations_sha256':domain_digest(original),
                'classified_obligations_sha256':domain_digest(result),'native_reviews':reviews}
    path=Path(out_dir).resolve()/'.compiler-work/v1-classification-repairs'/(sc.sha256_value(projection)[7:]+'.json')
    scope._path(Path(root).resolve(),path.relative_to(Path(root).resolve()).as_posix(),required=False)
    if path.exists():
        if json.loads(path.read_text())!=projection:
            _reject('projection-collision')
    else:
        sc.atomic_json(path,projection)
    return result


@contextmanager
def session(value, *, root, requirements, out_dir):
    """Keep native initialization/reset and the publisher's repeated V1 intact."""
    global _active
    if _active:
        _reject('overlapping-classification-context')
    import semantic_v3_contract_repair as native
    old_compile,old_reset=sc.compile_obligations,native.reset_published_overlays
    def wrap(base):
        def classified(**kwargs):
            if Path(kwargs['root']).resolve()!=Path(root).resolve() or Path(kwargs['out_dir']).resolve()!=Path(out_dir).resolve():
                _reject('different-root-or-task')
            original=base(**kwargs)
            return apply(value,root=root,requirements=requirements,out_dir=out_dir,
                         source_index=kwargs['source_index'],original=original)
        return classified
    def reset():
        old_reset()
        sc.compile_obligations=wrap(sc.compile_obligations)
    _active=True
    sc.compile_obligations=wrap(old_compile)
    native.reset_published_overlays=reset
    try:
        yield
    finally:
        sc.compile_obligations=old_compile
        native.reset_published_overlays=old_reset
        _active=False
