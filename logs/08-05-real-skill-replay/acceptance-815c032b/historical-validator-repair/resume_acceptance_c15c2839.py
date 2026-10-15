"""ADR-0058/ADR-0060: consume the prepared input and continue Acceptance.

Preserves the successful projection, preparation and original helper failure.
Does not rerun tests or alter predecessor evidence.
"""
import json
import finish_acceptance_budget3 as runner


def main():
    root = runner.ROOT
    target = root / 'execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed'
    plan_id = 'acceptance-08-05-c15c2839-budget3'
    inputs = target / 'acceptance-inputs' / plan_id
    evidence = runner.HERE / 'acceptance-budget3-c15c2839/successor-r2'
    prepared = inputs / 'prepared-run-input.v1.json'
    request = runner.load_json(inputs / 'skill-input-request.v2.json')
    preparation = json.loads((evidence / 'skill-input-prepare/stdout.bin').read_bytes())
    if preparation['status'] != 'prepared':
        raise RuntimeError('Expected the native prepared state')
    attempt = preparation['attempt_id']
    consumed = runner.command(evidence, 'skill-input-consume', [
        'scripts/python/skill_input_v2.py', 'consume', '--plan-id', plan_id,
        '--attempt-id', attempt, '--max-pages', '100'])
    if json.loads(consumed)['status'] != 'complete':
        raise RuntimeError('Input delivery is incomplete')
    runner.command(evidence, 'skill-input-finish', [
        'scripts/python/skill_input_v2.py', 'finish', '--plan-id', plan_id,
        '--attempt-id', attempt])
    pointer = root / request['storage'] / 'current.v1.json'
    contract_copy = inputs / 'skill-input-contract.v1.json'
    if not contract_copy.exists():
        runner.create_immutable(contract_copy, runner.CONTRACT.read_bytes())
    elif contract_copy.read_bytes() != runner.CONTRACT.read_bytes():
        raise RuntimeError('Preserved contract differs')
    coordinator = inputs / 'coordinator-request.v3.json'
    runner.immutable(coordinator, {
        'schemaVersion': 'jimuyun.acceptance-coordinator-request.v3',
        'targetPlan': runner.rel(target), 'authorizes': [],
        **{key: {'path': path.relative_to(inputs).as_posix(), 'sha256': runner.digest(path)}
           for key, path in [('preparedRunInput', prepared),
                             ('skillInputReceipt', pointer),
                             ('skillInputContract', contract_copy)]}})
    result = json.loads(runner.command(evidence, 'coordinator', [
        runner.CLI, 'run-coordinator', '--request', runner.rel(coordinator),
        '--out', runner.rel(inputs / 'coordinator-result.v3.json')]))
    print('TERMINAL ACCEPTANCE: ' + json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
