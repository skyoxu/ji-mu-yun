"""Content-addressed immutable receipt generations (ADR-0060)."""
from __future__ import annotations
import os
import shutil
import tempfile
from pathlib import Path
try:
    from .skill_input_protocol import contained, digest, encoded, identity, immutable_json, read_json, name
except ImportError:
    from skill_input_protocol import contained, digest, encoded, identity, immutable_json, read_json, name


def publish_generation(root, *, generation_id=None, content):
    """Compatibility content storage; this never creates or advances current."""
    if not isinstance(content, bytes):
        raise ValueError('content must be bytes')
    generation_id = generation_id or digest(content)[7:]
    name(generation_id)
    directory = contained(root, 'generations/' + generation_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = contained(directory, 'content.bin')
    try:
        with path.open('xb') as stream:
            stream.write(content)
    except FileExistsError:
        if path.read_bytes() != content:
            raise ValueError('immutable generation conflict')
    return directory


def publish_receipt(root, receipt, context):
    """Stage complete bytes, verify, rename; orphan generations are replayable."""
    payload = {'receipt': receipt, 'context': context}
    generation_id = identity(payload)[7:]
    parent = contained(root, 'skill-input-generations')
    parent.mkdir(parents=True, exist_ok=True)
    target = contained(parent, generation_id)
    if target.exists():
        if read_generation(root, generation_id) != payload:
            raise ValueError('immutable generation conflict')
        return generation_id
    temporary = Path(tempfile.mkdtemp(prefix='.staging-', dir=parent))
    try:
        immutable_json(temporary / 'receipt.json', receipt)
        immutable_json(temporary / 'context.json', context)
        # Verify the actual staged bytes before exposing the directory.
        actual = {'receipt': read_json(temporary / 'receipt.json'), 'context': read_json(temporary / 'context.json')}
        if identity(actual)[7:] != generation_id:
            raise ValueError('staged generation integrity failure')
        try:
            os.rename(temporary, target)
        except OSError:
            if not target.exists() or read_generation(root, generation_id) != payload:
                raise
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return generation_id


def read_generation(root, generation_id):
    name(generation_id)
    directory = contained(root, 'skill-input-generations/' + generation_id)
    if not directory.is_dir() or {p.name for p in directory.iterdir()} != {'receipt.json', 'context.json'}:
        raise ValueError('generation is incomplete')
    payload = {key: read_json(contained(directory, key + '.json')) for key in ('receipt', 'context')}
    if identity(payload)[7:] != generation_id:
        raise ValueError('generation integrity failure')
    receipt = payload['receipt']
    if not isinstance(receipt, dict) or receipt.get('schema_version') != 'skill-input-receipt.v2' or receipt.get('ready') is not True or receipt.get('authorizes') != []:
        raise ValueError('generation receipt is not ready')
    required = {'schema_version', 'plan_id', 'consumer', 'operation', 'policy_revision', 'selection', 'bindings', 'candidate_hash', 'candidate', 'inputs', 'storage', 'validator_hash', 'coverage', 'transport', 'gates', 'knowledge', 'context_hash', 'ready', 'authorizes'}
    if set(receipt) != required or receipt['coverage'].get('status') != 'complete' or receipt['gates'].get('execution_allowed') is not True:
        raise ValueError('generation receipt is incomplete')
    if receipt.get('context_hash') != identity(payload['context']):
        raise ValueError('context binding mismatch')
    return payload
