"""ADR-0041: source-bound V1 replay, not a compiler program-counter restore.

Legacy caller-session results require the original native receipt and cache.
No response, timeout, log line or caller-authored state alone grants reuse.
All returned candidates still pass the normal current compiler validators.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Mapping

import semantic_compiler as sc
from semantic_worker_errors import WorkerTransportError

_legacy = None
_stats = {}
_PREFIX = ("You are a read-only semantic compiler worker. Do not modify files. "
           "Return JSON only. Do not invent requirements or runtime evidence.\n\n")
_ADVISORY = re.compile(r'(\nPlanning source observations \(advisory, not requirement authority\):\n)[^\n]*\n')


def configure(*, root: Path, out_dir: Path, session: Path | None):
    global _legacy, _stats
    _legacy = None
    _stats = {'source_content_replays': 0, 'legacy_v1_replays': 0}
    if session is None:
        return
    if session.is_symlink():
        raise ValueError('resume worker session must not be a symlink')
    session = session.resolve()
    root = root.resolve()
    if not out_dir.resolve().is_relative_to(root):
        raise ValueError('resume output scope must be inside repository')
    if not session.is_relative_to(root / 'logs') or session.is_symlink():
        raise ValueError('resume worker session must be an explicit repository logs directory')
    data = _read(session / 'session.json')
    if (data.get('schema') != 'jimuyun.host-session.v1' or data.get('authorizes') != []
            or not isinstance(data.get('repository_root'), str)
            or Path(data.get('repository_root', '')).resolve() != root):
        raise ValueError('resume worker session repository identity mismatch')
    requests = {}
    for path in sorted(session.glob('*/request.json')):
        request = _read(path)
        match = re.fullmatch(r'(v1-[A-Za-z0-9_.-]+)-[0-9a-f]{24}-last-message\.json',
                             Path(request.get('output_path', '')).name)
        if match:
            requests.setdefault(match[1], []).append((path, request))
    _legacy = (root, out_dir.resolve(), session, data['session_id'], requests)


def statistics():
    return dict(_stats)


def _read(path):
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('resume artifact missing, oversized or unsafe: ' + str(path))
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError('resume artifact must be an object: ' + str(path))
    return value


def _digest_request(value):
    return 'sha256:' + hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                               separators=(',', ':')).encode()).hexdigest()


def content_identity(stage, payload, prompt, role_contract):
    """V1 explicitly extracts only its frozen source, not advisory query facts."""
    source = payload.get('source')
    if not stage.startswith('v1-') or not isinstance(source, Mapping):
        return None
    required = ('source_ref', 'source_text', 'text_sha256', 'requirement_id')
    if any(not isinstance(source.get(k), str) or not source[k] for k in required):
        return None
    if sc.sha256_bytes(source['source_text'].encode()) != source['text_sha256']:
        raise WorkerTransportError(stage, 'artifact-integrity', 0, 'V1 source text hash mismatch')
    # File identity/position is rechecked by V0A. A sibling anchor changing bytes
    # or lines must not invalidate extraction of an identical frozen section.
    source = {k: v for k, v in source.items() if k not in ('source_sha256', 'line', 'source_order')}
    semantic = {k: v for k, v in payload.items() if k != 'planning_source_observations'}
    semantic['source'] = source
    prompt = _ADVISORY.sub(r'\1<current advisory; not extraction authority>\n', prompt)
    return {'schema': 'vdd.v1-source-replay.v1', 'stage': stage,
            'input': semantic, 'prompt': prompt, 'source_role_contract': role_contract}


def _path(out_dir, identity):
    return Path(out_dir) / '.compiler-cache' / 'source-replay' / (sc.sha256_value(identity)[7:] + '.json')


def save(*, out_dir, identity, value, origin):
    if identity is None:
        return
    path = _path(out_dir, identity)
    envelope = {'identity': identity, 'candidate': dict(value),
                'candidate_sha256': sc.sha256_value(value), 'origin': origin, 'authorizes': []}
    if path.exists():
        old = _read(path)
        if old['identity'] != identity or old['candidate_sha256'] != sc.sha256_value(value):
            raise WorkerTransportError(identity['stage'], 'artifact-integrity', 0, 'source replay candidate changed')
        return
    sc.atomic_json(path, envelope)


def lookup(*, root, out_dir, stage, payload, prompt, role_contract):
    identity = content_identity(stage, payload, prompt, role_contract)
    if identity is None:
        return None, identity
    path = _path(out_dir, identity)
    if path.exists():
        try:
            envelope = _read(path)
            value = envelope['candidate']
            if (envelope['identity'] != identity or not isinstance(value, dict)
                    or envelope['candidate_sha256'] != sc.sha256_value(value) or envelope.get('authorizes') != []):
                raise ValueError('source replay content binding mismatch')
        except (OSError, KeyError, ValueError) as exc:
            raise WorkerTransportError(stage, 'artifact-integrity', 0, str(exc)) from exc
        _stats['source_content_replays'] = _stats.get('source_content_replays', 0) + 1
        return value, identity
    if _legacy is None:
        return None, identity
    expected_root, expected_out, session, session_id, requests = _legacy
    if expected_root != Path(root).resolve() or expected_out != Path(out_dir).resolve():
        raise ValueError('resume cache scope mismatch')
    found = []
    # Explicit transcript inventory, never an adjacent-plan or latest-success scan.
    for request_path, request in requests.get(stage, []):
        output = Path(request.get('output_path', ''))
        if not re.fullmatch(re.escape(stage) + r'-[0-9a-f]{24}-last-message\.json', output.name):
            continue
        full = request.get('prompt', '')
        if not full.startswith(_PREFIX) or '\n\nINPUT:\n' not in full:
            continue
        prior_prompt, raw = full[len(_PREFIX):].rsplit('\n\nINPUT:\n', 1)
        if role_contract and not prior_prompt.endswith(role_contract):
            continue
        if role_contract:
            prior_prompt = prior_prompt[:-len(role_contract)]
        prior_payload = json.loads(raw)
        if content_identity(stage, prior_payload, prior_prompt, role_contract) != identity:
            continue
        call = request_path.parent
        if not (call / 'result.json').is_file() or not (call / 'response.json').is_file():
            continue  # An unconsumed answer is not an accepted native result.
        result, response = _read(call / 'result.json'), _read(call / 'response.json')
        if result.get('status') != 'returned':
            continue
        binding = _digest_request(request)
        cache_payload = {'source_role_contract': role_contract, 'prompt': prior_prompt, 'input': prior_payload}
        cache_path = expected_out / '.compiler-cache' / sc._worker_cache_key(stage, cache_payload)
        receipt_path = expected_out / '.compiler-work/worker-receipts' / (
            f"{stage}-{sc.sha256_value(prior_payload)[7:19]}-{sc.sha256_bytes(prior_prompt.encode())[7:19]}.json")
        try:
            value, receipt = _read(cache_path), _read(receipt_path)
            if (request.get('session_id') != session_id or request.get('request_id') != call.name
                    or not isinstance(request.get('repository_root'), str)
                    or Path(request.get('repository_root', '')).resolve() != expected_root
                    or output.resolve().parent != expected_out / '.compiler-work'
                    or request.get('mode') != 'read-only' or request.get('authorizes') != []
                    or request.get('schema') != 'jimuyun.host-request.v1'
                    or result.get('backend') != 'host-session'
                    or response.get('schema') != 'jimuyun.host-response.v1'
                    or any(x.get('request_sha256') != binding or x.get('request_id') != call.name
                           or x.get('authorizes') != [] for x in (result, response))
                    or response.get('session_id') != session_id
                    or sc._parse_json_output(response['output_text']) != value
                    or not output.is_file() or output.is_symlink()
                    or sc._parse_json_output(output.read_text(encoding='utf-8')) != value
                    or receipt.get('stage') != stage or receipt.get('schema_valid') is not True
                    or receipt.get('schema') != 'vdd.semantic-worker-receipt.v1'
                    or receipt.get('worker_authority') != 'read-only-semantic-candidate'
                    or receipt.get('schema_findings') != [] or receipt.get('authorizes') != []
                    or receipt.get('exit_status') not in ('ok', 'cache-reused')
                    or receipt.get('input_sha256') != sc.sha256_value(prior_payload)
                    or receipt.get('prompt_sha256') != sc.sha256_bytes(prior_prompt.encode())
                    or receipt.get('result_sha256') != sc.sha256_value(value)):
                raise ValueError('legacy source replay witness mismatch')
        except (OSError, KeyError, ValueError) as exc:
            raise WorkerTransportError(stage, 'artifact-integrity', 0, str(exc)) from exc
        found.append(value)
    if not found:
        return None, identity
    if any(value != found[0] for value in found[1:]):
        raise WorkerTransportError(stage, 'artifact-integrity', 0, 'ambiguous legacy source replay')
    # No cache/receipt is synthesized here. Current native validation owns replay.
    _stats['legacy_v1_replays'] = _stats.get('legacy_v1_replays', 0) + 1
    return found[0], identity
