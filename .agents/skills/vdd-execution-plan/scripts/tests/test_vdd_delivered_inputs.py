"""ADR-0041: delivered inputs do not require upstream BMAD review evidence."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import semantic_compiler as sc


def delivered(root):
    (root / '.agents').mkdir()
    (root / 'AGENTS.md').write_text('# Fixture repository\n')
    folder = root / '_bmad-output/planning-artifacts'
    folder.mkdir(parents=True)
    source = folder / 'SPEC.md'
    source.write_text('# Delivered SPEC\n\n## FR-1\nReturn the requested value.\n', encoding='utf-8')
    companion = folder / 'architecture.md'
    companion.write_text('# Delivered architecture\n\n## FR-2\nKeep the service boundary.\n', encoding='utf-8')
    return source, companion


def no_process(*args, **kwargs):
    raise AssertionError('No upstream generator, reviewer, or model may be launched')


def test_public_vdd_entry_consumes_delivered_inputs_without_review_or_install(tmp_path, monkeypatch, capsys):
    source, companion = delivered(tmp_path)
    entry_path = SCRIPTS.parents[3] / 'scripts/vdd/compile_plan.py'
    spec = importlib.util.spec_from_file_location('delivered_vdd_cli', entry_path)
    entry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(entry)
    monkeypatch.setattr(subprocess, 'Popen', no_process)
    monkeypatch.setattr(sys, 'argv', ['compile_plan', '--requirements', str(source), '--companion', str(companion),
                                    '--out-dir', str(tmp_path/'not-published'), '--recommendation-only'])
    assert entry.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'recommendation-only'
    assert result['model_called'] is False and result['writes_performed'] is False
    assert not (tmp_path/'not-published').exists()
    assert not (tmp_path/'_bmad').exists()
    assert not list(tmp_path.rglob('*review*'))


@pytest.mark.parametrize('defect,reason', [('missing','unreadable'),('changed','stale-source-hash'),
                                          ('reference','source-ref'),('companion','unreadable')])
def test_actual_input_integrity_still_blocks(tmp_path,monkeypatch,defect,reason):
    source,companion=delivered(tmp_path)
    monkeypatch.setattr(subprocess,'Popen',no_process)
    index=sc.build_source_index(tmp_path,source,[companion])
    if defect=='missing': source.unlink()
    elif defect=='changed': source.write_text('Changed delivered content\n')
    elif defect=='reference': index['entries'][0]['source_ref']=''
    else: companion.unlink()
    result=sc.source_preflight(tmp_path,index)
    assert result['valid'] is False
    assert any(reason in finding for finding in result['findings'])


def test_malformed_or_unreadable_delivered_source_is_not_review_status(tmp_path,monkeypatch):
    source,_=delivered(tmp_path)
    monkeypatch.setattr(subprocess,'Popen',no_process)
    source.write_text('# No requirement anchors\n')
    with pytest.raises(ValueError,match='no canonical requirement anchors'):
        sc.build_source_index(tmp_path,source)
    source.write_bytes(b'\xff')
    with pytest.raises(UnicodeDecodeError): sc.build_source_index(tmp_path,source)
