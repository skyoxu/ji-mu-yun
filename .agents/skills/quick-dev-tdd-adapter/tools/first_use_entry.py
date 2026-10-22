"""ADR-0041: explicit, deterministic Python entry preparation before behavioral RED.

Only missing planned production files can be created: Python callables return
None and JSON interfaces begin as empty objects. No model-authored body, feature implementation, import, test,
observation, or completion proof is generated. Existing Q2/Q4 gates stay intact.
"""
from __future__ import annotations

import fnmatch
import keyword
from pathlib import Path
import subprocess

from runtime_evidence import create_json, load_json, safe_relative, sha256_bytes, sha256_value

SCHEMA = 'quick-dev.first-use-contract.v1'
RECEIPT = 'quick-dev.first-use-entry.v1'


def _name(value):
    if not isinstance(value, str) or not value.isidentifier() or keyword.iskeyword(value) or value.startswith('__'):
        raise ValueError('first-use identifier invalid')
    return value


def _safe_path(root, raw):
    ref = safe_relative(raw)
    if ':' in ref or ref.startswith('.git/'):
        raise ValueError('first-use path is not production')
    path = root / ref
    for part in (path, *path.parents):
        if part == root:
            break
        if part.is_symlink():
            raise ValueError('first-use symlink path rejected')
    path.resolve().relative_to(root.resolve())
    return ref, path


def _render(exports):
    if not isinstance(exports, list) or not exports:
        raise ValueError('first-use exports required')
    names, blocks = set(), ['"""Unimplemented entry prepared by Quick Dev first-use (ADR-0041)."""\n']
    for export in exports:
        if not isinstance(export, dict) or set(export) != {'name', 'parameters', 'keyword_parameters'}:
            raise ValueError('first-use export shape invalid')
        name = _name(export['name'])
        if name in names:
            raise ValueError('first-use duplicate export')
        names.add(name)
        positional, named = export['parameters'], export['keyword_parameters']
        if not isinstance(positional, list) or not isinstance(named, list):
            raise ValueError('first-use parameter list invalid')
        parameters = [_name(v) for v in positional + named]
        if len(set(parameters)) != len(parameters):
            raise ValueError('first-use duplicate parameter')
        args = list(positional)
        if named:
            args += ['*', *(v + '=None' for v in named)]
        blocks.append(f"def {name}({', '.join(args)}):\n    return None\n")
    return ('\n\n'.join(blocks) + '\n').encode('utf-8')


def _outputs(workspace, bundle, slice_id, contract):
    if not isinstance(contract, dict) or set(contract) != {'schema', 'plan_sha256', 'slice_id', 'source_commit', 'entries'}:
        raise ValueError('first-use contract shape invalid')
    if contract['schema'] != SCHEMA or contract['plan_sha256'] != sha256_value(bundle) or contract['slice_id'] != slice_id:
        raise ValueError('first-use plan/slice binding mismatch')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=workspace, text=True).strip()
    if contract['source_commit'] != head:
        raise ValueError('first-use source commit mismatch')
    selected = next((s for s in bundle['slices'] if s['slice_id'] == slice_id), None)
    context = next((c for c in bundle['agent_contexts'] if c['slice_id'] == slice_id), None)
    if selected is None or context is None:
        raise ValueError('first-use slice/context missing')
    entries = contract['entries']
    if not isinstance(entries, list) or not entries:
        raise ValueError('first-use entries required')
    allowed = set(selected['production_owners']) & set(selected['allowed_write_paths']) & set(selected['planned_new_files'])
    snapshots = set(selected['execution_snapshot_paths'])
    forbidden = context.get('forbidden_paths', [])
    outputs = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {'path', 'exports'}:
            raise ValueError('first-use entry shape invalid')
        ref, path = _safe_path(workspace, entry['path'])
        if (ref.startswith('logs/') or ref not in allowed or ref in snapshots or not ref.endswith(('.py', '.json')) or '/tests/' in ref or ref.startswith('tests/')
                or any(fnmatch.fnmatchcase(ref, f) or ref == f or ref.startswith(f.rstrip('/') + '/') for f in forbidden)):
            raise ValueError('first-use owner outside declared new production boundary')
        if ref in outputs:
            raise ValueError('first-use duplicate path')
        if subprocess.run(['git', 'cat-file', '-e', head + ':' + ref], cwd=workspace, capture_output=True).returncode == 0:
            raise ValueError('first-use owner already exists in source commit')
        if ref.endswith('.json'):
            if entry['exports'] != []:
                raise ValueError('first-use JSON interface cannot declare behavior or data')
            content = b'{}\n'
        else:
            content = _render(entry['exports'])
        outputs[ref] = (path, content)
    return outputs


def prepare_entry(*, workspace, bundle, slice_id, contract, out):
    root = workspace.resolve()
    out_ref = out.relative_to(root).as_posix()
    _safe_path(root, out_ref)
    if not out_ref.startswith('logs/'):
        raise ValueError('first-use receipt must be under logs')
    if out.exists():
        result = validate_prepared_entry(workspace=root, bundle=bundle, slice_id=slice_id, receipt=load_json(out))
        if result['input'] != contract:
            raise ValueError('first-use receipt input conflict')
        return result
    outputs = _outputs(root, bundle, slice_id, contract)
    # Prevalidate every file before the first mutation. A partial filesystem
    # failure retains created bytes and never publishes a successful receipt.
    if any(path.exists() or path.is_symlink() for path, _ in outputs.values()):
        raise ValueError('first-use refuses existing production path')
    for path, content in outputs.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(content)
    result = {'schema': RECEIPT, 'status': 'entry-prepared', 'slice_id': slice_id,
              'plan_sha256': sha256_value(bundle), 'input': contract,
              'input_sha256': sha256_value(contract),
              'production_hashes': {ref: sha256_bytes(content) for ref, (_, content) in outputs.items()},
              'required_next_action': 'author-red', 'implementation_authorized': False,
              'tests_executed': False, 'authorizes': []}
    create_json(out, result)
    return result


def validate_prepared_entry(*, workspace, bundle, slice_id, receipt):
    if (receipt.get('schema') != RECEIPT or receipt.get('status') != 'entry-prepared'
            or receipt.get('authorizes') != [] or receipt.get('implementation_authorized') is not False
            or receipt.get('slice_id') != slice_id or receipt.get('plan_sha256') != sha256_value(bundle)
            or receipt.get('input_sha256') != sha256_value(receipt.get('input'))):
        raise ValueError('first-use receipt invalid')
    outputs = _outputs(workspace.resolve(), bundle, slice_id, receipt['input'])
    expected = {ref: sha256_bytes(content) for ref, (_, content) in outputs.items()}
    if receipt.get('production_hashes') != expected:
        raise ValueError('first-use generated contract hash mismatch')
    for ref, (path, content) in outputs.items():
        if not path.is_file() or path.read_bytes() != content:
            raise ValueError('first-use production changed before test authoring: ' + ref)
    return receipt
