"""ADR-0058: continue public read-only Q8 into deterministic Acceptance."""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
CLI = '.agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py'
CONTRACT = ROOT / '.agents/skills/run-refactor-implementation-acceptance/references/skill-input-contract.v1.json'
sys.path[:0] = [str(ROOT / 'scripts/python'), str(ROOT / '.agents/skills/quick-dev-tdd-adapter/tools')]
from skill_input_selection import selection_identity
from runtime_evidence import load_json, create_json, create_immutable


def rel(path):
    return path.relative_to(ROOT).as_posix()


def digest(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def immutable(path, value):
    if path.exists():
        if load_json(path) != value:
            raise RuntimeError('Preserved input differs: ' + str(path))
    else:
        create_json(path, value)


def command(evidence, label, args):
    directory = evidence / label
    facts_path = directory / 'process.json'
    argv = [sys.executable, '-B', *args]
    if facts_path.exists():
        facts = load_json(facts_path)
        if facts['argv'] != argv or facts['exit_code']:
            raise RuntimeError('Existing action requires explicit recovery: ' + label)
        print('REUSE ' + label, flush=True)
        return (directory / 'stdout.bin').read_bytes()
    if directory.exists():
        raise RuntimeError('Preserved partial action: ' + label)
    directory.mkdir(parents=True)
    print('START ' + label, flush=True)
    started = time.monotonic()
    try:
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=3600)
        stdout, stderr, code = result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired as exc:
        stdout, stderr, code = exc.stdout or b'', exc.stderr or b'', 124
    create_immutable(directory / 'stdout.bin', stdout)
    create_immutable(directory / 'stderr.bin', stderr)
    create_json(facts_path, {'argv': argv, 'exit_code': code,
        'elapsed_seconds': time.monotonic() - started, 'timeout_seconds': 3600,
        'stdout_sha256': digest(directory / 'stdout.bin'),
        'stderr_sha256': digest(directory / 'stderr.bin'), 'authorizes': []})
    print(stdout.decode('utf-8', errors='replace')[-3500:], flush=True)
    if code:
        print(stderr.decode('utf-8', errors='replace')[-3500:], flush=True)
        raise RuntimeError('Failed public action: ' + label)
    return stdout


def main():
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip()
    q8 = HERE / 'owner-recovery-r11-read-only-budget' / ('Q8-' + head[:8])
    receipt = q8 / 'implementation-complete-result.v2.json'
    value = load_json(receipt)
    if value.get('status') != 'pass' or value.get('predicate') != 'implementation-complete':
        raise RuntimeError('Native Q8 has not passed')
    evidence = HERE / ('acceptance-budget3-' + head[:8])
    request_path = ROOT / ('compact-vdd-projection-request.' + head[:8] + '-budget3.v1.json')
    request = load_json(ROOT / 'compact-vdd-projection-request.815c032b.v1.json')
    original_name = 'compact-vdd-projection-request.815c032b.v1.json'
    request['runId'] = 'acceptance-08-05-' + head[:8] + '-budget3'
    request['candidateRevision'] = head
    # Retain the original explicit candidate scope, adding every source delta
    # from its frozen candidate through the current approved repair.
    delta = subprocess.check_output(['git', 'diff', '--name-only',
        '888ba9cc898915e3f0dbbc1f1309d51956dc1c5b', head, '--',
        '.agents', 'scripts', 'docs', '.gitattributes'], cwd=ROOT).decode().splitlines()
    request['changedPaths'] = sorted(set(request['changedPaths']) | set(delta))
    request['affectedConsumerRefs'] = sorted(set(request['affectedConsumerRefs']) |
        {'.agents/skills/quick-dev-tdd-adapter', 'scripts/quick_dev/approved_budget_replay.py'})
    request['currentQuickDev'].update(receipt={'path': rel(receipt), 'sha256': digest(receipt)},
        snapshotRoots=load_json(q8 / 'snapshot-roots.json'), sourceCommit=head)
    request['implementationReceiptPath'] = rel(receipt)
    request['implementationReceiptHash'] = digest(receipt)
    for descriptor in request['commands']:
        descriptor['timeout_seconds'] = 900
        descriptor['argv'] = [arg.replace(original_name, request_path.name) for arg in descriptor['argv']]
    immutable(request_path, request)
    target = ROOT / request['targetPlan']
    input_dir = target / 'acceptance-inputs' / request['runId']
    projected = json.loads(command(evidence, 'projection', [CLI, 'project-compact-vdd',
        '--repository-root', str(ROOT), '--request', rel(request_path),
        '--out', rel(evidence / 'projection-result.json')]))
    if projected.get('status') != 'ready':
        raise RuntimeError('Projection is not ready: ' + str(projected))
    prepared = input_dir / 'prepared-run-input.v1.json'
    command(evidence, 'prepare-run', [CLI, 'prepare-run', '--input', projected['runRequest'],
        '--out', rel(prepared), '--knowledge-context', request['knowledgeContextPath'],
        '--prerequisite-bundle', (ROOT / projected['bundle']).relative_to(target).as_posix()])
    template = load_json(target / 'acceptance-inputs/acceptance-08-05-421c7188/skill-input-request.v2.json')
    template.update(plan_id=request['runId'], policy_revision='acceptance-budget3-v1',
        storage=rel(input_dir / 'skill-input-v2/acceptance'))
    for row in template['sources']:
        row['sha256'] = digest(ROOT / row['path'])
    selection = selection_identity(template['sources'], consumer=template['consumer'], policy_revision=template['policy_revision'])
    freeze_path = input_dir / 'skill-input-freeze.v2.json'
    immutable(freeze_path, {'schema_version': 'skill-input-direct-source-freeze.v2',
        'sourceSelectionHash': selection['sourceSelectionHash'], 'authorizes': []})
    authority = target / 'acceptance-inputs/acceptance-08-05-421c7188/skill-input-authority.v1.json'
    template['bindings'] = {name: {'path': rel(path), 'sha256': digest(path)} for name, path in
        [('contract', CONTRACT), ('registry', input_dir / 'command-registry.v1.json'),
         ('authority', authority), ('knowledge_freeze', freeze_path)]}
    skill_request = input_dir / 'skill-input-request.v2.json'
    immutable(skill_request, template)
    result = json.loads(command(evidence, 'skill-input-prepare', ['scripts/python/skill_input_v2.py',
        'prepare', '--request', rel(skill_request)]))
    if result.get('status') != 'ready':
        raise RuntimeError('Skill input is not ready: ' + str(result))
    attempt = result['attempt_id']
    command(evidence, 'skill-input-consume', ['scripts/python/skill_input_v2.py', 'consume',
        '--plan-id', template['plan_id'], '--attempt-id', attempt, '--max-pages', '100'])
    command(evidence, 'skill-input-finish', ['scripts/python/skill_input_v2.py', 'finish',
        '--plan-id', template['plan_id'], '--attempt-id', attempt])
    pointer = ROOT / template['storage'] / 'current.v1.json'
    contract_copy = input_dir / 'skill-input-contract.v1.json'
    create_immutable(contract_copy, CONTRACT.read_bytes())
    coordinator = input_dir / 'coordinator-request.v3.json'
    immutable(coordinator, {'schemaVersion': 'jimuyun.acceptance-coordinator-request.v3',
        'targetPlan': request['targetPlan'], 'authorizes': [],
        **{key: {'path': path.relative_to(input_dir).as_posix(), 'sha256': digest(path)} for key, path in
           [('preparedRunInput', prepared), ('skillInputReceipt', pointer), ('skillInputContract', contract_copy)]}})
    result = json.loads(command(evidence, 'coordinator', [CLI, 'run-coordinator',
        '--request', rel(coordinator), '--out', rel(input_dir / 'coordinator-result.v3.json')]))
    print('TERMINAL ACCEPTANCE: ' + json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
