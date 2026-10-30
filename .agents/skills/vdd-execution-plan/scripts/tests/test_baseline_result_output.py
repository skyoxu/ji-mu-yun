"""ADR-0041: real public admission must deliver its explicitly requested result."""
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[5]


@pytest.mark.parametrize('stale', [False, True])
def test_public_admission_blocked_writes_current_result(tmp_path, stale):
    result = tmp_path / 'result.json'
    if stale:
        result.write_text('{"status":"plan-ready"}\n', encoding='utf-8')
    completed = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/vdd/compile_plan.py'),
        '--requirements', str(tmp_path / 'missing.md'), '--out-dir', str(tmp_path / 'plan'),
        '--admission-only', '--result-json', str(result)], cwd=ROOT, capture_output=True, text=True,
        timeout=30, shell=False)
    assert completed.returncode == 1, completed.stderr
    actual = json.loads(result.read_text(encoding='utf-8'))
    assert actual == json.loads(completed.stdout.splitlines()[-1])
    assert actual['status'] == 'repair-vdd' and actual['admission']['status'] == 'blocked'
    assert not (tmp_path / 'plan').exists()


def test_public_successful_admission_writes_non_authorizing_result(tmp_path):
    source = tmp_path / 'requirements.md'
    source.write_text('# FR-1: Value\nReturn the current value.\n', encoding='utf-8')
    result = tmp_path / 'result.json'
    completed = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/vdd/compile_plan.py'),
        '--requirements', str(source), '--out-dir', str(tmp_path / 'plan'),
        '--admission-only', '--result-json', str(result)], cwd=ROOT, capture_output=True, text=True,
        timeout=30, shell=False)
    assert completed.returncode == 0, completed.stderr
    actual = json.loads(result.read_text(encoding='utf-8'))
    assert actual == json.loads(completed.stdout.splitlines()[-1])
    assert actual['status'] == 'admission-only' and actual['authorizes'] == []
    assert not (tmp_path / 'plan').exists()


@pytest.mark.parametrize('style', ['equals', 'abbreviation', 'mixed-equals', 'mixed-abbreviation', 'duplicate'])
@pytest.mark.parametrize('stale', [False, True])
def test_candidate_channel_result_arguments_cannot_escape_owned_output(tmp_path, style, stale):
    """ADR-0041: exercise the exact public entry inside the real candidate channel."""
    ticket = json.loads(os.environ['JIMUYUN_REGRESSION_CHANNEL'])
    channel_root = (ROOT / ticket['context']).parent
    assert channel_root.name == 'regression'
    outside = channel_root.parent / f'owned-boundary-probe-{style}-{int(stale)}.json'
    assert not outside.is_relative_to(channel_root)
    sentinel = b'Preserved owned fixture sentinel\n'
    if stale:
        outside.write_bytes(sentinel)
    else:
        assert not outside.exists()
    copied = tmp_path / 'native-copy'
    entry = copied / 'scripts/vdd/compile_plan.py'
    entry.parent.mkdir(parents=True)
    entry.write_bytes((ROOT / 'scripts/vdd/compile_plan.py').read_bytes())
    shutil.copytree(ROOT / '.agents/skills/vdd-execution-plan',
        copied / '.agents/skills/vdd-execution-plan',
        ignore=shutil.ignore_patterns('__pycache__', 'tests'))
    inside = tmp_path / 'inside.json'
    argv = [sys.executable, '-B', str(entry), '--requirements', str(tmp_path / 'missing.md'),
            '--out-dir', str(tmp_path / 'plan'), '--admission-only']
    control = subprocess.run([*argv, '--result-json', str(inside)], cwd=ROOT,
                             capture_output=True, text=True, timeout=30, shell=False)
    assert control.returncode == 1, control.stderr
    assert json.loads(inside.read_text())['admission']['status'] == 'blocked'
    forms = {'equals': ['--result-json=' + str(outside)],
        'abbreviation': ['--result-j', str(outside)],
        'mixed-equals': ['--result-json', str(inside), '--result-json=' + str(outside)],
        'mixed-abbreviation': ['--result-json', str(inside), '--result-j', str(outside)],
        'duplicate': ['--result-json', str(inside), '--result-json', str(inside)]}
    result = subprocess.run([*argv, *forms[style]], cwd=ROOT,
                            capture_output=True, text=True, timeout=30, shell=False)
    assert result.returncode != 0
    assert 'SKILL_ADMISSION' in result.stdout
    assert outside.read_bytes() == sentinel if stale else not outside.exists()


@pytest.mark.parametrize('valid_identity', [False, True])
def test_repair_identity_precedes_query_without_rejecting_valid_input(tmp_path, monkeypatch, capsys, valid_identity):
    """ADR-0041: source mismatch is denied before any optional publication dependency."""
    from copy import deepcopy
    from scripts.vdd import compile_plan as cli
    from scripts.toolchain.knowledge_query import adapter
    from test_v3_test_path_input_repair import TestPathInputRepairTests
    case = TestPathInputRepairTests('test_single_contract_uses_same_early_gate')
    original_invoke = cli.semantic_compiler.invoke_worker
    original_alignment = cli.semantic_compiler.semantic_align
    case.setUp()
    try:
        req, companion = tmp_path / 'requirements.md', tmp_path / 'companion.md'
        req.write_text('| <a id="SM-T01"></a>T01 | constraint | retain | planning | companion.md | Preserve boundary. |\n', encoding='utf-8')
        companion.write_text('Complete normative boundary.\n', encoding='utf-8')
        index = cli.semantic_compiler.build_source_index(ROOT, req, [companion])
        correction = deepcopy(case.correction)
        import hashlib
        correction['requirements_sha256'] = 'sha256:' + hashlib.sha256(req.read_bytes()).hexdigest()
        correction['source_index_sha256'] = index['sha256'] if valid_identity else 'sha256:' + '0' * 64
        path = tmp_path / 'repair.json'
        path.write_text(json.dumps(correction), encoding='utf-8')
        calls = []
        def query_observed(*args, **kwargs):
            calls.append(True)
            raise RuntimeError('fixture-query-stage-observed')
        monkeypatch.setattr(adapter, 'prepare_consumption', query_observed)
        result_path = tmp_path / 'result.json'
        result_path.write_text('{"status":"plan-ready"}\n', encoding='utf-8')
        monkeypatch.setattr(sys, 'argv', ['compile_plan.py', '--requirements', str(req),
            '--companion', str(companion), '--out-dir', str(tmp_path / 'plan'),
            '--v3-contract-repair', str(path), '--result-json', str(result_path)])
        try:
            code = cli.main()
        except SystemExit as exc:
            code = exc.code
        captured = capsys.readouterr()
        assert code != 0
        result = json.loads(result_path.read_text(encoding='utf-8'))
        assert result['status'] == 'repair-vdd'
        assert result == json.loads(captured.out.splitlines()[-1])
        if valid_identity:
            assert calls == [True]
            assert 'fixture-query-stage-observed' in captured.out
        else:
            assert calls == []
            assert 'complete source-index identity mismatch' in captured.out + captured.err
        assert not (tmp_path / 'plan').exists()
    finally:
        case.doCleanups()
        cli.semantic_compiler.invoke_worker = original_invoke
        cli.semantic_compiler.semantic_align = original_alignment
