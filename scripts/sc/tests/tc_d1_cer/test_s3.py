from __future__ import annotations
import importlib.util
import sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[4]
VALIDATOR=ROOT/"scripts/python/validate_acceptance_execution_evidence.py"
FAILURE_ID="FI-E489B3A7974A-1"
def _validator_module():
    spec=importlib.util.spec_from_file_location("s3_validator", VALIDATOR); assert spec and spec.loader
    module=importlib.util.module_from_spec(spec); sys.modules[spec.name]=module; spec.loader.exec_module(module); return module
@pytest.mark.cer_assertion("A-E489B3A7974A-1")
def test_validator_rejects_verdict_without_real_execution_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    validator=_validator_module(); root=Path("C:/s3-bounded-fixture"); captured={}
    def load_json(path):
        return {"master":{"tasks":[{"id":3,"status":"in-progress"}]}} if path.name=="tasks.json" else ([{"taskmaster_id":3,"acceptance":["Assistant prose. Refs: scripts/sc/tests/tc_d1_cer/test_s3.py"]}] if path.name=="tasks_back.json" else [])
    monkeypatch.setattr(validator,"repo_root",lambda:root)
    monkeypatch.setattr(validator,"load_json",load_json)
    monkeypatch.setattr(validator,"load_sc_test_summary",lambda *_:{"run_id":"RUN-S3","steps":[{"name":"unit","artifacts_dir":str(root/"logs/unit")}]})
    monkeypatch.setattr(validator,"write_json",lambda _p,payload:captured.update(payload))
    real_exists = Path.exists
    monkeypatch.setattr(validator.Path, "exists", lambda p: False if p.is_relative_to(root) else real_exists(p))
    monkeypatch.setattr(sys,"argv",[str(VALIDATOR),"--task-id","3","--run-id","RUN-S3","--date","2099-01-01","--out",str(root/"out.json")])
    code=validator.main(); results=captured.get("results",[])
    rejected=code==1 and captured.get("status")=="fail" and captured.get("meta",{}).get("trx") is None and results and results[0].get("status")=="fail"
    if not rejected: print(f"FAILURE_ID:{FAILURE_ID}")
    assert rejected, captured
