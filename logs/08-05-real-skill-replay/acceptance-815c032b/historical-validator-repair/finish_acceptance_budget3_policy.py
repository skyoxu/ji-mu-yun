"""Materialize the maintainer-approved narrow policy projection (ADR-0058).

Only exact already-declared Toolchain paths are added. Every existing check,
domain rule, cross-domain dependency and authority reference remains intact.
The original repository policy and historical requests are never modified.
"""
import copy
import json
import sys
import finish_acceptance_budget3 as runner

sys.path.insert(0, str(runner.ROOT / '.agents/skills/run-refactor-implementation-acceptance/scripts'))
from acceptance_core import canonical_hash, validate_policy_pack

EXACT_PATHS = [
    '.gitattributes',
    'scripts/ci/verify_base_clean.ps1',
    'scripts/quick_dev/approved_budget_replay.py',
    'scripts/quick_dev/run_candidate_bound_metric.py',
    'scripts/quick_dev/tests/test_approved_budget_replay.py',
    'scripts/quick_dev/tests/test_public_budget_transfer.py',
    'scripts/vdd/probe_real_worker.py',
]
original_load = runner.load_json
original_request = runner.ROOT / 'compact-vdd-projection-request.815c032b.v1.json'
request = original_load(original_request)
policy = original_load(runner.ROOT / request['codeReviewPolicyPath'])
validate_policy_pack(policy)
projected = copy.deepcopy(policy)
projected['pathRules']['ownedPrefixes'] += EXACT_PATHS
projected['policyRevision'] = canonical_hash({key: value for key, value in projected.items() if key != 'policyRevision'})
validate_policy_pack(projected)
assert projected['checks'] == policy['checks']
assert projected['pathRules']['crossDomainPaths'] == policy['pathRules']['crossDomainPaths']
policy_path = runner.HERE / 'approved-budget3-policy/toolchain-code-review.v1.json'
runner.immutable(policy_path, projected)


def load_with_explicit_policy(path):
    value = json.loads(path.read_bytes()) if path.name == 'snapshot-roots.json' else original_load(path)
    if path == original_request:
        value['codeReviewPolicyPath'] = runner.rel(policy_path)
    return value


runner.load_json = load_with_explicit_policy
original_command = runner.command
runner.command = lambda evidence, label, args: original_command(evidence / 'successor-r2', label, args)
if __name__ == '__main__':
    runner.main()
