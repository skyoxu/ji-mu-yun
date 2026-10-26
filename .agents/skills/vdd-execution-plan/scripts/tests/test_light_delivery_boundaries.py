"""ADR-0041: characterize retained delivery guards without synthetic RED."""
from contextlib import redirect_stdout
import inspect
import io
import json
from pathlib import Path
import sys
import tempfile
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from scripts.vdd import compile_plan as cli
from execution_contract import ownerless_guard
from workflow_unit_budget import Budget, supervise


@pytest.mark.cer_assertion('ASSERT-LIGHT-9ECB9EABF5D9')
def test_light_d353d902f43c():
    plan = ROOT / 'execution-plans/2026-10-26-toolchain-light-optimizations-ready'
    bundle = json.loads((plan / 'semantic-plan-bundle.v1.json').read_text())
    guard = next(s for s in bundle['slices'] if s['slice_id'] == 'S1')
    obligations = [o for o in bundle['obligations'] if o['obligation_id'] in guard['obligation_ids']]
    failures = [f for f in bundle['failure_intents'] if f['failure_intent_id'] in guard['failure_intent_ids']]
    assert ownerless_guard(guard, obligations, failures)
    assert {f['failure_family'] for f in failures} == {'artifact-integrity'}
    assert len(bundle['obligations']) == len(bundle['acceptances']) == len(bundle['failure_intents']) == 24
    for item in bundle['slices']:
        assert set(item['production_owners']) <= set(item['allowed_write_paths'])
        assert not set(item['production_owners']) & set(item['execution_snapshot_paths'])
        assert all(not p.startswith(('PhaseA.Platform', 'runtime/phase-a')) for p in item['allowed_write_paths'])
        context = next(c for c in bundle['agent_contexts'] if c['slice_id'] == item['slice_id'])
        assert context['validation_commands'] and all(isinstance(a, list) and a for a in context['validation_commands'])
    budget = Budget()
    assert (budget.total, budget.idle) == (1800, 600)
    defaults = inspect.signature(supervise).parameters
    assert defaults['total'].default == 1800 and defaults['idle'].default == 600
    # Exercise the real public compiler's rejection path with a missing input.
    # The advisory query is an isolated dependency; it is not feature authority.
    from scripts.toolchain.knowledge_query import adapter
    with tempfile.TemporaryDirectory(dir=ROOT / 'logs', prefix='light-guard-') as name:
        temporary = Path(name)
        args = ['compile_plan.py', '--requirements', str(temporary / 'missing.md'), '--out-dir', str(temporary / 'out')]
        advisory = {'status': 'disabled', 'queried': False, 'authorizes': [], 'query_result': {'read_set': []}}
        original = (plan / 'semantic-plan-bundle.v1.json').read_bytes()
        with mock.patch.object(sys, 'argv', args), mock.patch.object(adapter, 'prepare_consumption', return_value=advisory), mock.patch.object(cli.semantic_compiler, 'invoke_worker') as worker, redirect_stdout(io.StringIO()):
            result = cli.main()
        assert result != 0 and worker.call_count == 0
        assert not (temporary / 'out/compiler-state.v1.json').exists()
        assert (plan / 'semantic-plan-bundle.v1.json').read_bytes() == original
