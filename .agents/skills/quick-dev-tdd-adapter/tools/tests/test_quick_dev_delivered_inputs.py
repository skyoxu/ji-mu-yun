"""ADR-0041: Quick Dev consumes its delivered contract, not BMAD review state."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

TOOLS=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(TOOLS))
from q1_planned_preflight import validate_planned_preflight
from test_ch456_q1_planned_preflight import _bundle, _workspace
from test_shared_execution import setup, descriptor, run, measured
from shared_execution import validate_use


def test_q1_does_not_require_upstream_review_or_run_upstream_process(tmp_path,monkeypatch):
    _workspace(tmp_path)
    def forbidden(*args,**kwargs):
        raise AssertionError('No BMAD generation/reviewer process allowed')
    monkeypatch.setattr(subprocess,'Popen',forbidden)
    result=validate_planned_preflight(workspace=tmp_path,bundle=_bundle(),slice_id='S1',timeout_seconds=10)
    assert result['status']=='planned-contract-valid'
    assert result['model_called'] is False and result['tests_executed'] is False
    assert not (tmp_path/'_bmad').exists() and not list(tmp_path.rglob('*review*'))


@pytest.mark.parametrize('defect,reason',[('missing','neither materialized nor declared planned'),('malformed','argv')])
def test_q1_keeps_actual_contract_checks(tmp_path,monkeypatch,defect,reason):
    _workspace(tmp_path);bundle=_bundle()
    monkeypatch.setattr(subprocess,'Popen',lambda *a,**k: pytest.fail('No external process allowed'))
    if defect=='missing': bundle['slices'][0]['planned_new_files']=[]
    else: bundle['agent_contexts'][0]['validation_commands']=[[]]
    with pytest.raises(ValueError,match=reason):
        validate_planned_preflight(workspace=tmp_path,bundle=bundle,slice_id='S1',timeout_seconds=10)


def test_reuse_binds_delivered_input_bytes_without_review_evidence(tmp_path,monkeypatch):
    semantic,bundle,_=setup(tmp_path)
    source=tmp_path/'_bmad-output/delivered/SPEC.md';source.parent.mkdir(parents=True)
    source.write_text('# Delivered input\nReturn the requested value.\n')
    # The delivered source is an explicit execution input; no upstream report,
    # BMAD installation, worker fixture or generation is part of this test.
    for item in bundle['slices']:
        item['execution_snapshot_paths'].append(source.relative_to(tmp_path).as_posix())
    semantic.write_text(json.dumps(bundle))
    calls=measured(monkeypatch)
    original_popen=subprocess.Popen
    def controlled(argv,*args,**kwargs):
        assert isinstance(argv,list)
        assert (argv[0]=='git' or str(TOOLS/'pytest_case_collector.py') in argv), argv
        return original_popen(argv,*args,**kwargs)
    monkeypatch.setattr(subprocess,'Popen',controlled)
    run(tmp_path,semantic,bundle,descriptor(bundle))
    target=descriptor(bundle,'S2','terminal','consumer2')
    receipt=run(tmp_path,semantic,bundle,target)
    assert len(calls)==1 and receipt['process_attempts']==0
    assert not list(tmp_path.rglob('*review*'))
    source.unlink()
    with pytest.raises(ValueError,match='reuse-dependency-content-changed:_bmad-output/delivered/SPEC.md'):
        validate_use(target,receipt)
