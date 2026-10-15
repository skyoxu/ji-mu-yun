"""ADR-0058/ADR-0060: renew input transport, preserving expired attempts."""
import json
import subprocess
import sys
import threading
import time
import finish_acceptance_budget3 as runner


def main():
    root = runner.ROOT
    target = root / 'execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed'
    plan_id = 'acceptance-08-05-c15c2839-budget3'
    inputs = target / 'acceptance-inputs' / plan_id
    evidence = runner.HERE / 'acceptance-budget3-c15c2839/successor-r3'
    request = runner.load_json(inputs / 'skill-input-request.v2.json')
    prepared = json.loads(runner.command(evidence, 'skill-input-prepare', [
        'scripts/python/skill_input_v2.py', 'prepare', '--request',
        runner.rel(inputs / 'skill-input-request.v2.json')]))
    if prepared['status'] != 'prepared':
        raise RuntimeError('Input preparation did not succeed')
    attempt = prepared['attempt_id']
    stopped = threading.Event()
    heartbeat_errors = []

    def heartbeat():
        index = 0
        while not stopped.is_set():
            argv = [sys.executable, '-B', 'scripts/python/skill_input_v2.py',
                    'heartbeat', '--plan-id', plan_id, '--attempt-id', attempt,
                    '--lease-seconds', '900']
            started = time.monotonic()
            process = subprocess.run(argv, cwd=root, capture_output=True, timeout=900)
            directory = evidence / 'heartbeat' / str(index)
            directory.mkdir(parents=True)
            runner.create_immutable(directory / 'stdout.bin', process.stdout)
            runner.create_immutable(directory / 'stderr.bin', process.stderr)
            runner.create_json(directory / 'process.json', {
                'argv': argv, 'exit_code': process.returncode,
                'elapsed_seconds': time.monotonic() - started,
                'timeout_seconds': 900, 'authorizes': []})
            if process.returncode:
                heartbeat_errors.append(process.stdout.decode('utf-8'))
                return
            index += 1
            if stopped.wait(60):
                return

    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        consumed = runner.command(evidence, 'skill-input-consume', [
            'scripts/python/skill_input_v2.py', 'consume', '--plan-id', plan_id,
            '--attempt-id', attempt, '--max-pages', '100'])
        if json.loads(consumed.splitlines()[-1])['status'] != 'complete':
            raise RuntimeError('Input delivery is incomplete')
        runner.command(evidence, 'skill-input-finish', [
            'scripts/python/skill_input_v2.py', 'finish', '--plan-id', plan_id,
            '--attempt-id', attempt])
    finally:
        stopped.set()
        thread.join(timeout=10)
    if heartbeat_errors:
        raise RuntimeError('Input heartbeat failed: ' + str(heartbeat_errors))
    pointer = root / request['storage'] / 'current.v1.json'
    contract = inputs / 'skill-input-contract.v1.json'
    if not contract.exists():
        runner.create_immutable(contract, runner.CONTRACT.read_bytes())
    elif contract.read_bytes() != runner.CONTRACT.read_bytes():
        raise RuntimeError('Preserved contract differs')
    coordinator = inputs / 'coordinator-request.v3.json'
    runner.immutable(coordinator, {
        'schemaVersion': 'jimuyun.acceptance-coordinator-request.v3',
        'targetPlan': runner.rel(target), 'authorizes': [],
        **{key: {'path': path.relative_to(inputs).as_posix(), 'sha256': runner.digest(path)}
           for key, path in [('preparedRunInput', inputs / 'prepared-run-input.v1.json'),
                             ('skillInputReceipt', pointer),
                             ('skillInputContract', contract)]}})
    result = json.loads(runner.command(evidence, 'coordinator', [
        runner.CLI, 'run-coordinator', '--request', runner.rel(coordinator),
        '--out', runner.rel(inputs / 'coordinator-result.v3.json')]))
    print('TERMINAL ACCEPTANCE: ' + json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
