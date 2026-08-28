import hashlib
import json
from pathlib import Path
import pytest
from write_predecessor_judge_freeze import write


def _receipt(path: Path, valid: bool = True) -> None:
    value = {"schema_version":"process-receipt.v1","producer":"independent-judge","status":"pass","slice_id":"S3","run_id":"RUN-S3","receipt":{"judge_id":"independent-judge"}}
    body = dict(value)
    value["evidence_sha256"] = "sha256:" + hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest() if valid else "sha256:stale"
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")), encoding="utf-8")


def test_freeze_writer_binds_real_receipt(tmp_path: Path) -> None:
    receipt = tmp_path / "process-receipt.v1.json"; output = tmp_path / "predecessor-judge-freeze.v1.json"
    _receipt(receipt)
    result = write(receipt, output)
    assert result["receipt_sha256"].startswith("sha256:") and result["receipt_path"] == receipt.as_posix()


def test_freeze_writer_rejects_stale_receipt(tmp_path: Path) -> None:
    receipt = tmp_path / "process-receipt.v1.json"; _receipt(receipt, False)
    with pytest.raises(ValueError):
        write(receipt, tmp_path / "freeze.json")


def test_freeze_writer_rejects_non_run_or_sut_identity(tmp_path: Path) -> None:
    receipt = tmp_path / "process-receipt.v1.json"
    _receipt(receipt)
    value = json.loads(receipt.read_text(encoding="utf-8"))
    value["run_id"] = "local"
    value["receipt"]["judge_id"] = "sut"
    body = dict(value)
    value["evidence_sha256"] = "sha256:" + hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    receipt.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    with pytest.raises(ValueError):
        write(receipt, tmp_path / "freeze.json")
