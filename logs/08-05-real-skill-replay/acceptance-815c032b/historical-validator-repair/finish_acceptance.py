"""Continue native Q8 through public deterministic Acceptance (ADR-0058).

The original projection request is preserved. This script only materializes
new inputs; lifecycle predicates and process evidence remain owner-produced.
"""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / 'acceptance-native-q8-r8'
OLD_REQUEST = ROOT / 'compact-vdd-projection-request.815c032b.v1.json'
REQUEST = ROOT / 'compact-vdd-projection-request.888ba9cc-native-q8-r8.v1.json'
CLI = '.agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py'
CANONICAL_CONTRACT = ROOT / '.agents/skills/run-refactor-implementation-acceptance/references/skill-input-contract.v1.json'
sys.path.insert(0, str(ROOT / 'scripts/python'))
sys.path.insert(0, str(ROOT / '.agents/skills/quick-dev-tdd-adapter/tools'))
from skill_input_selection import selection_identity
from runtime_evidence import load_json, create_json, create_immutable


def rel(path):
    return path.relative_to(ROOT).as_posix()


def digest(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def immutable(path, value):
    if path.exists():
        if load_json(path) != value:
            raise RuntimeError('Existing generated input differs: ' + str(path))
    else:
        create_json(path, value)


def command(label, args):
    evidence = EVIDENCE / label
    facts_path = evidence / 'process.json'
    argv = [sys.executable, '-B', *args]
    if facts_path.exists():
        facts = load_json(facts_path)
        if facts['argv'] != argv or facts['exit_code']:
            raise RuntimeError('Existing action requires explicit recovery: ' + label)
        print('REUSE ' + label, flush=True)
        return (evidence / 'stdout.bin').read_bytes()
    if evidence.exists():
        raise RuntimeError('Partial action: ' + label)
    evidence.mkdir(parents=True)
    print('START ' + label, flush=True)
    started = time.monotonic()
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=1200)
    create_immutable(evidence / 'stdout.bin', result.stdout)
    create_immutable(evidence / 'stderr.bin', result.stderr)
    create_json(facts_path, {'argv': argv, 'exit_code': result.returncode,
        'elapsed_seconds': time.monotonic() - started,
        'stdout_sha256': 'sha256:' + hashlib.sha256(result.stdout).hexdigest(),
        'stderr_sha256': 'sha256:' + hashlib.sha256(result.stderr).hexdigest(), 'authorizes': []})
    print(result.stdout.decode('utf-8', errors='replace')[-3500:], flush=True)
    if result.returncode:
        print(result.stderr.decode('utf-8', errors='replace')[-3500:], flush=True)
        raise RuntimeError('Failed public action: ' + label)
    return result.stdout


def main():
    q8 = HERE / 'owner-recovery-r8/Q8-historical-judge-r8'
    receipt = q8 / 'implementation-complete-result.v2.json'
    value = load_json(receipt)
    if value.get('status') != 'pass' or value.get('predicate') != 'implementation-complete':
        raise RuntimeError('Native Q8 has not passed')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip()
    if head != '888ba9cc898915e3f0dbbc1f1309d51956dc1c5b':
        raise RuntimeError('Candidate changed; inspect actual source impact before continuing')
    original = HERE / 'original-projection-request.815c032b.v1.json'
    if OLD_REQUEST.exists():
        if original.exists():
            raise RuntimeError('Original request archive already exists')
        # Recoverable move of the explicitly named assistant-generated input.
        OLD_REQUEST.rename(original)
    request = load_json(original)
    request['runId'] = 'acceptance-08-05-888ba9cc-native-q8-r8'
    request['currentQuickDev'].update(receipt={'path': rel(receipt), 'sha256': digest(receipt)},
        snapshotRoots=load_json(q8 / 'snapshot-roots.json'), sourceCommit=head)
    request['implementationReceiptPath'] = rel(receipt)
    request['implementationReceiptHash'] = digest(receipt)
    for descriptor in request['commands']:
        if descriptor['id'] == 'current-q8-read-only':
            descriptor['argv'] = [arg.replace(OLD_REQUEST.name, REQUEST.name) for arg in descriptor['argv']]
    immutable(REQUEST, request)
    target = ROOT / request['targetPlan']
    input_dir = target / 'acceptance-inputs' / request['runId']
    projection_result = EVIDENCE / 'projection-result.json'
    projected = json.loads(command('projection', [CLI, 'project-compact-vdd', '--repository-root', str(ROOT),
        '--request', rel(REQUEST), '--out', rel(projection_result)]))
    if projected.get('status') != 'ready':
        raise RuntimeError('Projection is not ready: ' + str(projected))
    bundle_path = ROOT / projected['bundle']
    run_request = ROOT / projected['runRequest']
    prepared = input_dir / 'prepared-run-input.v1.json'
    command('prepare-run', [CLI, 'prepare-run', '--input', rel(run_request), '--out', rel(prepared),
        '--knowledge-context', request['knowledgeContextPath'],
        '--prerequisite-bundle', bundle_path.relative_to(target).as_posix()])

    template = load_json(target / 'acceptance-inputs/acceptance-08-05-421c7188/skill-input-request.v2.json')
    template['plan_id'] = request['runId']
    template['policy_revision'] = 'acceptance-native-q8-r8-v1'
    template['storage'] = rel(input_dir / 'skill-input-v2/acceptance')
    for row in template['sources']:
        row['sha256'] = digest(ROOT / row['path'])
    authority = target / 'acceptance-inputs/acceptance-08-05-421c7188/skill-input-authority.v1.json'
    freeze_path = input_dir / 'skill-input-freeze.v2.json'
    selection = selection_identity(template['sources'], consumer=template['consumer'], policy_revision=template['policy_revision'])
    immutable(freeze_path, {'schema_version': 'skill-input-direct-source-freeze.v2',
        'sourceSelectionHash': selection['sourceSelectionHash'], 'authorizes': []})
    registry = input_dir / 'command-registry.v1.json'
    template['bindings'] = {name: {'path': rel(path), 'sha256': digest(path)}
        for name, path in [('contract', CANONICAL_CONTRACT), ('registry', registry),
                           ('authority', authority), ('knowledge_freeze', freeze_path)]}
    skill_request = input_dir / 'skill-input-request.v2.json'
    immutable(skill_request, template)
    result = json.loads(command('skill-input-prepare', ['scripts/python/skill_input_v2.py', 'prepare', '--request', rel(skill_request)]))
    if result.get('status') != 'ready':
        raise RuntimeError('Skill input not ready: ' + str(result))
    attempt = result['attempt_id']
    command('skill-input-consume', ['scripts/python/skill_input_v2.py', 'consume', '--plan-id', template['plan_id'],
        '--attempt-id', attempt, '--max-pages', '100'])
    command('skill-input-finish', ['scripts/python/skill_input_v2.py', 'finish', '--plan-id', template['plan_id'], '--attempt-id', attempt])
    pointer = ROOT / template['storage'] / 'current.v1.json'
    # The coordinator's contained transport refs require one exact-byte copy.
    # The adapter above still binds the canonical repository-owned contract.
    contract_copy = input_dir / 'skill-input-contract.v1.json'
    if not contract_copy.exists():
        create_immutable(contract_copy, CANONICAL_CONTRACT.read_bytes())
    if digest(contract_copy) != digest(CANONICAL_CONTRACT):
        raise RuntimeError('Contract transport bytes differ')
    coordinator = input_dir / 'coordinator-request.v3.json'
    immutable(coordinator, {'schemaVersion': 'jimuyun.acceptance-coordinator-request.v3',
        'targetPlan': request['targetPlan'], 'authorizes': [],
        **{key: {'path': path.relative_to(input_dir).as_posix(), 'sha256': digest(path)}
           for key, path in [('preparedRunInput', prepared), ('skillInputReceipt', pointer), ('skillInputContract', contract_copy)]}})
    final = input_dir / 'coordinator-result.v3.json'
    result = json.loads(command('coordinator', [CLI, 'run-coordinator', '--request', rel(coordinator), '--out', rel(final)]))
    print('TERMINAL ACCEPTANCE: ' + json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
