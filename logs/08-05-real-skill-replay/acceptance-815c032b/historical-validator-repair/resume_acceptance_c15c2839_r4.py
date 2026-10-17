"""ADR-0060: bind the exact contract path consumed by the coordinator.

Retains the previous request, generation and failure; uses identical contract
bytes and the existing source selection, authority and candidate.
"""
import copy
import json
import resume_acceptance_c15c2839_r3 as previous

runner = previous.runner
original_load = runner.load_json
original_command = runner.command
original_immutable = runner.immutable
target = runner.ROOT / 'execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed'
inputs = target / 'acceptance-inputs/acceptance-08-05-c15c2839-budget3'
old_request = inputs / 'skill-input-request.v2.json'
new_request = inputs / 'skill-input-request.r4.v2.json'
contract_copy = inputs / 'skill-input-contract.v1.json'
if contract_copy.read_bytes() != runner.CONTRACT.read_bytes():
    raise RuntimeError('Copied contract differs from canonical consumer contract')
request = copy.deepcopy(original_load(old_request))
request['bindings']['contract'] = {
    'path': runner.rel(contract_copy), 'sha256': runner.digest(contract_copy)}
original_immutable(new_request, request)


def load_current(path):
    return original_load(new_request if path == old_request else path)


def destination(path):
    if path.name == 'coordinator-request.v3.json':
        return path.with_name('coordinator-request.r4.v3.json')
    if path.name == 'coordinator-result.v3.json':
        return path.with_name('coordinator-result.r4.v3.json')
    return path


def command_current(evidence, label, args):
    evidence = evidence.with_name('successor-r4')
    rewritten = [runner.rel(new_request) if arg == runner.rel(old_request)
                 else runner.rel(destination(runner.ROOT / arg))
                 if arg.endswith(('coordinator-request.v3.json', 'coordinator-result.v3.json'))
                 else arg for arg in args]
    return original_command(evidence, label, rewritten)


runner.load_json = load_current
runner.immutable = lambda path, value: original_immutable(destination(path), value)
runner.command = command_current


if __name__ == '__main__':
    previous.main()
