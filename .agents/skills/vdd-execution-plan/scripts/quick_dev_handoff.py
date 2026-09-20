"""ADR-0041: execution-only repair of an already reviewed CER plan.

No semantic worker, implementation, execution receipt, or approval is created.
Only the public compiler CLI may invoke publish_repair to publish a successor.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path, PurePosixPath
import shlex


def _eligible(acceptance, obligations):
    bound = [obligations[oid] for oid in acceptance['obligation_ids']]
    return bool(bound) and all(o['obligation_kind'] in {'behavior', 'quality'}
                               and o['requirement_type'] != 'Governance' for o in bound)


def _inside(path, parent):
    return path == parent or path.startswith(parent.rstrip('/') + '/')


def handoff_findings(bundle):
    """Check actual Quick Dev write/selector roles, without observing behavior."""
    if 'behavior_routing' not in bundle:
        return []
    findings = []
    obligations = {o['obligation_id']: o for o in bundle['obligations']}
    acceptances = {a['acceptance_id']: a for a in bundle['acceptances']}
    failures = {f['failure_intent_id']: f for f in bundle['failure_intents']}
    contexts = {c['slice_id']: c for c in bundle['agent_contexts']}
    for item in bundle['slices']:
        sid = item['slice_id']
        context = contexts.get(sid, {})
        owners, snapshots = set(item['production_owners']), set(item['execution_snapshot_paths'])
        if any(_inside(a, b) or _inside(b, a) for a in owners for b in snapshots):
            findings.append(f'{sid}:production-frozen-by-execution-snapshot')
        commands = context.get('validation_commands', [])
        command = commands[0] if commands else []
        # The current CER adapter is single-process pytest. Other adapters need
        # their own explicit contract, not a file-extension fallback.
        offset = 2 if command[:2] == ['py', '-3'] else 1
        targets = command[offset + 2:] if command[offset:offset + 2] == ['-m', 'pytest'] else []
        paths = [v.split('::', 1)[0] for v in targets if v.endswith('.py') or '.py::' in v]
        authorable = set(item.get('planned_new_files', [])) | snapshots
        if not paths or any(p not in snapshots or p not in authorable or p in owners for p in paths):
            findings.append(f'{sid}:missing-authorable-pytest-entry')
        for p in paths:
            if any(_inside(p, f) for f in context.get('forbidden_paths', [])):
                findings.append(f'{sid}:test-entry-forbidden:{p}')
        for aid in item['acceptance_ids']:
            acceptance = acceptances[aid]
            if _eligible(acceptance, obligations) and not any(
                failures[fid]['failure_family'] == 'expected-red' for fid in acceptance['red_intent_ids']
            ):
                findings.append(f'{sid}:missing-behavior-red-route:{aid}')
    return findings


def _regression(command):
    """Retain test runners; CLI/negative-fixture invocations need bound oracles."""
    argv = shlex.split(command[0]) if len(command) == 1 else list(command)
    if argv[:2] == ['py', '-3']:
        argv = ['python', *argv[2:]]
    argv = [v for v in argv if v != '-B']
    argv = [v.replace('.agents/skills/vdd-execution-plan/tests',
                      '.agents/skills/vdd-execution-plan/scripts/tests') for v in argv]
    if argv[:3] == ['python', '-m', 'unittest']:
        if 'discover' in argv:
            root = argv[argv.index('-s') + 1]
            pattern = argv[argv.index('-p') + 1] if '-p' in argv else 'test*.py'
            argv = ['python', '-m', 'pytest', root if '*' in pattern else root + '/' + pattern]
        else:
            target = argv[3]
            if '/' not in target:
                target = target.replace('.', '/') + '.py'
            argv = ['python', '-m', 'pytest', target]
    if len(argv) == 2 and argv[0] == 'python' and Path(argv[1]).name.startswith('test_'):
        argv = ['python', '-m', 'pytest', argv[1]]
    if argv[:3] == ['python', '-m', 'pytest'] and not any('/validators' in v for v in argv):
        return argv, 'retained-regression'
    return None, 'bound-test-oracle-required'


def repair_bundle(bundle, test_root):
    import semantic_compiler as sc
    from semantic_behavior_contract import SCHEMA, project_intents, project_deferred
    root = PurePosixPath(test_root)
    if root.is_absolute() or '..' in root.parts or str(root) != test_root or not test_root.startswith('scripts/sc/tests/'):
        raise ValueError('handoff test root must be a normalized scripts/sc/tests child')
    result = deepcopy(bundle)
    obligations = {o['obligation_id']: o for o in result['obligations']}
    failures = {f['failure_intent_id']: f for f in result['failure_intents']}
    added = []
    for acceptance in result['acceptances']:
        if not _eligible(acceptance, obligations) or any(
            failures[fid]['failure_family'] == 'expected-red' for fid in acceptance['red_intent_ids']
        ):
            continue
        # Add a test-failure role. Never relabel the existing guard/diagnostic,
        # nor treat a subject's intended rejection as an expected test failure.
        raw = {
            'acceptance_ids': [acceptance['acceptance_id']], 'failure_family': 'expected-red',
            'failure_id': 'CER-' + acceptance['acceptance_id'] + '-BEHAVIOR',
            'expected_outcome': 'fail',
            'selector_intent': 'Exercise the bound Given/When against the real production entry. '
                'Only a failing assertion of the unchanged observable and expected outcome may emit this marker. '
                'Expected subject rejection is a passing test when the oracle requires rejection. '
                'Import, setup, process launch, timeout and infrastructure faults must never emit this marker. '
                'Observable: ' + acceptance['oracle']['observable'] + ' Expected: ' + acceptance['oracle']['expected'],
        }
        raw['failure_intent_id'] = sc._stable_failure_intent_id(raw)
        result['failure_intents'].append(raw)
        failures[raw['failure_intent_id']] = raw
        acceptance['red_intent_ids'] = sorted([*acceptance['red_intent_ids'], raw['failure_intent_id']])
        added.append(raw['failure_intent_id'])
    dispositions = []
    contexts = {c['slice_id']: c for c in result['agent_contexts']}
    for item in result['slices']:
        sid = item['slice_id']
        test = test_root + '/test_' + sid.lower() + '.py'
        context = contexts[sid]
        if any(_inside(test, p) for p in context.get('forbidden_paths', [])):
            raise ValueError(f'{sid}:planned-test-forbidden')
        item['execution_snapshot_paths'] = sorted({test, *(p for p in item['execution_snapshot_paths']
            if not any(_inside(p, owner) or _inside(owner, p) for owner in item['production_owners']))})
        item['planned_new_files'] = sorted({test, *item['planned_new_files']})
        item['allowed_write_paths'] = sorted({test, *item['allowed_write_paths']})
        related = [f for f in result['failure_intents'] if set(f['acceptance_ids']) & set(item['acceptance_ids'])]
        item['failure_intent_ids'] = sorted(f['failure_intent_id'] for f in related)
        selectors = sorted({f['selector_intent'] for f in related})
        item['proof']['selector_intents'] = selectors
        item['slice_input_hash'] = sc.sha256_value({k: v for k, v in item.items() if k != 'slice_input_hash'})
        commands = [['python', '-m', 'pytest', test, '-q']]
        for command in context['validation_commands']:
            normalized, disposition = _regression(command)
            dispositions.append({'slice_id': sid, 'original': command, 'disposition': disposition,
                                 'replacement': normalized or commands[0]})
            if normalized and normalized not in commands:
                commands.append(normalized)
            elif not normalized:
                context['contracts'].append('The dedicated assertion tests must cover the observable intent of '
                    + json.dumps(command, ensure_ascii=True) + ' using bounded fixtures, explicit arguments and '
                    'expected exit/verdict assertions. Help output, a schema document alone, or an unstarted '
                    'validator cannot prove the bound acceptance. Do not invoke live backends or mutate the real repository in a negative fixture.')
        context['validation_commands'] = commands
        context['allowed_paths'] = list(item['allowed_write_paths'])
        context['selector_intents'] = selectors
        context['contracts'].append('Each declared assertion needs a cer_assertion mapping and a meaningful '
            'independent oracle. Tests must invoke the real production entry. The plan is not a behavior '
            'observation. Keep governance/constraint failures non-authorizing; do not emit expected-red '
            'for them. Preserve all bound Given/When/Then and forbidden outcomes. No placeholder pass or synthetic RED.')
    result['pre_slice_coverage'] = sc.exact_cover(result['obligations'], result['acceptances'], result['failure_intents'])
    result['final_plan_coverage'] = sc.final_cover(result['pre_slice_coverage'], result['slices'])
    result['behavior_routing'] = {'schema': SCHEMA, 'intents': project_intents(result), 'deferred': project_deferred(result)}
    return result, {'added_expected_red_intents': added, 'command_dispositions': dispositions}


def repair_runtime_red_roles(bundle, failure_intent_ids):
    """Bind explicitly reviewed machine assertions, never infer human approval.

    Governance is a requirement category, not an execution outcome. An operator
    may select an existing intent after reviewing its machine oracle. Existing
    diagnostics remain intact; only real case-bound AssertionError can use the
    added role. No automatic conversion of governance/constraint intents occurs.
    """
    import semantic_compiler as sc
    from semantic_behavior_contract import SCHEMA, project_intents
    result = deepcopy(bundle)
    requested = set(failure_intent_ids)
    if not requested or len(requested) != len(failure_intent_ids):
        raise ValueError('runtime RED repair requires unique explicit failure intent IDs')
    index = {f['failure_intent_id']: f for f in result['failure_intents']}
    if not requested <= index.keys():
        raise ValueError('runtime RED repair references unknown failure intent')
    affected = set()
    additions = []
    for fid in sorted(requested):
        original = index[fid]
        if original['failure_family'] == 'expected-red' or len(original['acceptance_ids']) != 1:
            raise ValueError('runtime RED repair requires one non-RED Acceptance intent')
        aid = original['acceptance_ids'][0]
        acceptance = next(a for a in result['acceptances'] if a['acceptance_id'] == aid)
        selected = [item for item in result['slices'] if aid in item['acceptance_ids']]
        if len(selected) != 1 or acceptance.get('verification_lane') not in {'unit', 'integration', 'matrix', 'runtime'}:
            raise ValueError('runtime RED repair requires an executable slice oracle')
        item = selected[0]
        if not item['production_owners'] or not acceptance['assertion_ids'] or not acceptance['oracle']['observable']:
            raise ValueError('runtime RED repair lacks production/assertion/observable binding')
        if any(f['failure_family'] == 'expected-red' and aid in f['acceptance_ids'] for f in result['failure_intents']):
            raise ValueError('runtime RED role already exists for Acceptance')
        added = {**original, 'failure_family': 'expected-red',
            'selector_intent': original['selector_intent'] +
                ' Runtime test role: emit the existing failure ID only when a real assertion of this '
                'Acceptance oracle fails after invoking the production entry. A required subject rejection '
                'is a passing test. Human approval, Trust Approval, Consumer exceptions, setup/import '
                'errors, timeouts and harness binding errors cannot satisfy this role.'}
        added['failure_intent_id'] = sc._stable_failure_intent_id(added)
        result['failure_intents'].append(added)
        acceptance['red_intent_ids'] = sorted([*acceptance['red_intent_ids'], added['failure_intent_id']])
        item['failure_intent_ids'] = sorted([*item['failure_intent_ids'], added['failure_intent_id']])
        item['proof']['selector_intents'] = sorted([*item['proof']['selector_intents'], added['selector_intent']])
        item['slice_input_hash'] = sc.sha256_value({k: v for k, v in item.items() if k != 'slice_input_hash'})
        context = next(c for c in result['agent_contexts'] if c['slice_id'] == item['slice_id'])
        context['selector_intents'] = list(item['proof']['selector_intents'])
        context['contracts'].append('Explicit runtime RED role for ' + fid + ': only the bound executable '
            'assertion may emit ' + original['failure_id'] + '. The Governance requirement classification '
            'and all approval boundaries remain unchanged. This role is not an approval or observed RED.')
        affected.add(item['slice_id'])
        additions.append({'original_failure_intent_id': fid, 'runtime_failure_intent_id': added['failure_intent_id'],
                          'acceptance_id': aid, 'failure_id': original['failure_id']})
    result['pre_slice_coverage'] = sc.exact_cover(result['obligations'], result['acceptances'], result['failure_intents'])
    result['final_plan_coverage'] = sc.final_cover(result['pre_slice_coverage'], result['slices'])
    result['behavior_routing'] = {**result['behavior_routing'], 'schema': SCHEMA, 'intents': project_intents(result)}
    return result, {'runtime_red_role_bindings': additions, 'affected_slices': sorted(affected),
                    'unaffected_slices': [s['slice_id'] for s in result['slices'] if s['slice_id'] not in affected],
                    'command_dispositions': [], 'added_expected_red_intents': [a['runtime_failure_intent_id'] for a in additions]}


def semantic_projection(bundle):
    """Fields that this execution repair is not authorized to change."""
    return {
        'obligations': bundle['obligations'],
        'acceptances': [{k: v for k, v in a.items() if k != 'red_intent_ids'} for a in bundle['acceptances']],
        'slices': [{k: v for k, v in s.items() if k not in {
            'slice_input_hash', 'failure_intent_ids', 'proof', 'planned_new_files',
            'allowed_write_paths', 'execution_snapshot_paths'}} for s in bundle['slices']],
        'proof_assertions': [s['proof']['assertion_ids'] for s in bundle['slices']],
        'deferred': bundle['behavior_routing'].get('deferred', []),
    }


def publish_repair(*, root, requirements, predecessor, out_dir, test_root, runtime_red_intents=()):
    import semantic_compiler as sc
    from semantic_plan_contract import validate_semantic_bundle
    from semantic_chain_audit import audit_bundle
    root, predecessor, out_dir = root.resolve(), predecessor.resolve(), out_dir.resolve()
    for path in (predecessor, out_dir, requirements.resolve()):
        path.relative_to(root)
    if out_dir == predecessor or predecessor in out_dir.parents or (out_dir.exists() and any(out_dir.iterdir())):
        raise ValueError('handoff successor must be a distinct empty sibling scope')
    def read(name):
        return json.loads((predecessor / name).read_text(encoding='utf-8'))
    original = read('semantic-plan-bundle.v1.json')
    state = read('compiler-state.v1.json')
    pending = state.get('state') == 'semantic-validated-pending-handoff'
    if state.get('state') not in {'plan-ready', 'semantic-validated-pending-handoff'} or state.get('semantic_plan_sha256') != sc.sha256_value(original):
        raise ValueError('handoff predecessor is not a hash-bound reviewed semantic bundle')
    if pending:
        receipt = read('semantic-handoff-pending.v1.json')
        if (receipt.get('schema') != 'vdd.semantic-handoff-pending.v1' or receipt.get('authorizes') != []
                or receipt.get('semantic_plan_sha256') != state['semantic_plan_sha256']):
            raise ValueError('handoff pending predecessor receipt is invalid')
        origin = root / receipt.get('origin_out_dir', '')
        try:
            out_dir.relative_to(origin.parent)
        except ValueError:
            raise ValueError('handoff pending successor is outside its originating repair scope')
        if not origin.is_dir():
            raise ValueError('handoff pending predecessor origin is unavailable')
    else:
        # A published predecessor retains the established sibling-only rule.
        out_dir.relative_to(predecessor.parent)
    valid, errors = validate_semantic_bundle(original)
    if not valid or not audit_bundle(original)['valid']:
        raise ValueError('handoff predecessor contract invalid: ' + str(errors))
    source = read('source-index.v1.json')
    if source['sha256'] != sc.sha256_value(source['entries']):
        raise ValueError('handoff source index identity invalid')
    sources = set()
    source_rebindings = []
    source = deepcopy(source)
    for entry in source['entries']:
        path = root / entry['repository_relative_source_path']
        path.resolve().relative_to(root)
        sources.add(path.resolve())
        actual_hash = sc.sha256_bytes(path.read_bytes())
        if actual_hash != entry['source_sha256']:
            frozen = '\n'.join(e['source_text'] for e in source['entries']
                if e['repository_relative_source_path'] == entry['repository_relative_source_path'])
            # Rebind bytes only if the ENTIRE text is reproduced by the frozen
            # source entries. No discarded preamble, changed requirement, or
            # unreviewed execution context may pass this equivalence test.
            if path.read_text(encoding='utf-8').strip() != frozen.strip():
                raise ValueError('handoff source drift')
            source_rebindings.append({'source_ref': entry['source_ref'],
                'previous_sha256': entry['source_sha256'], 'current_sha256': actual_hash,
                'reason': 'entire-source-text-equals-frozen-entries'})
            entry['source_sha256'] = actual_hash
    if requirements.resolve() not in sources:
        raise ValueError('handoff requirements not in predecessor source identity')
    source['sha256'] = sc.sha256_value(source['entries'])
    alignment, recall = read('semantic-alignment.v1.json'), read('atomic-recall-alignment.v1.json')
    active = {o['obligation_id'] for o in original['obligations'] if o.get('status') == 'active'}
    if alignment.get('valid') is not True or recall.get('valid') is not True or set(recall['worker']['supported_obligation_ids']) != active:
        raise ValueError('handoff predecessor lacks complete independent semantic review')
    repaired, delta = (repair_runtime_red_roles(original, runtime_red_intents)
                       if runtime_red_intents else repair_bundle(original, test_root))
    repaired['plan_id'] = 'PLAN-' + sc.sha256_value({'source': source['sha256'], 'profile': original['profile']})[7:19].upper()
    if semantic_projection(original) != semantic_projection(repaired):
        raise ValueError('handoff repair changed semantic scope')
    if not all(f in repaired['failure_intents'] for f in original['failure_intents']):
        raise ValueError('handoff repair changed historical failure intent')
    context_by_aid = {aid: c for c in repaired['agent_contexts'] for aid in c['acceptance_ids']}
    checks = {
        'V0A': sc.source_preflight(root, source),
        'V2': sc.guard_obligations(source, repaired['obligations']),
        'V3A': sc.semantic_preflight(repaired['obligations'], repaired['acceptances'], repaired['failure_intents']),
        'V7': sc.feasibility(root, repaired['slices'], repaired['acceptances'], repaired['failure_intents'], context_by_aid),
        'semantic-chain': audit_bundle(repaired),
    }
    valid, errors = validate_semantic_bundle(repaired)
    checks['final-validation'] = {'valid': valid, 'findings': errors}
    errors = handoff_findings(repaired)
    checks['quick-dev-handoff'] = {'valid': not errors, 'findings': errors}
    if any(not value['valid'] for value in checks.values()):
        return {'status': 'repair-vdd', 'checks': checks}
    report = {
        'schema': 'vdd.quick-dev-handoff-repair.v1', 'authorizes': [],
        'predecessor': predecessor.relative_to(root).as_posix(),
        'predecessor_sha256': sc.sha256_value(original), 'semantic_plan_sha256': sc.sha256_value(repaired),
        'semantic_projection_sha256': sc.sha256_value(semantic_projection(repaired)),
        'source_byte_rebindings': source_rebindings,
        'reused_stages': ['V1', 'V4'], 'repartitioned': False, 'model_called': False,
        'predecessor_review_sha256': {name: sc.sha256_bytes((predecessor / name).read_bytes()) for name in
            ['source-index.v1.json', 'semantic-alignment.v1.json', 'atomic-recall-alignment.v1.json']},
        'checks': checks, **delta,
    }
    projections = {'obligations': 'obligations', 'acceptances': 'acceptances', 'failure-intents': 'failure_intents',
                   'pre-slice-coverage': 'pre_slice_coverage', 'slices': 'slices', 'final-plan-coverage': 'final_plan_coverage'}
    for name, key in projections.items():
        sc.atomic_json(out_dir / (name + '.v1.json'), repaired[key])
    for context in repaired['agent_contexts']:
        sc.atomic_json(out_dir / 'agent-context' / context['slice_id'] / 'agent-context.json', context)
    for name, value in [('source-index', source), ('semantic-alignment', alignment),
                        ('atomic-recall-alignment', recall), ('semantic-chain-audit', checks['semantic-chain']),
                        ('feasibility', checks['V7']), ('handoff-repair', report), ('semantic-plan-bundle', repaired)]:
        sc.atomic_json(out_dir / (name + '.v1.json'), value)
    sc.atomic_json(out_dir / 'compiler-state.v1.json', {**state,
        'plan_id': repaired['plan_id'],
        'state': 'plan-ready',
        'semantic_plan_sha256': sc.sha256_value(repaired),
        'execution_repair': 'handoff-repair.v1.json', 'reused_stages': ['V1', 'V4'],
        'completed_stages': ['V0', 'V0A', 'V2', 'V3A', 'V5', 'V6A', 'V7', 'final-validation', 'quick-dev-handoff']})
    return {'status': 'plan-ready', 'semantic_plan_sha256': sc.sha256_value(repaired),
            'slices': len(repaired['slices']), 'authorizes': [], 'model_called': False}
