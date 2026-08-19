from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
PYTHON_ROOT = ROOT / "scripts" / "python"
ACCEPTANCE_SCRIPTS = ROOT / ".agents/skills/run-refactor-implementation-acceptance/scripts"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))
if str(ACCEPTANCE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(ACCEPTANCE_SCRIPTS))


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


execution = load(
    "successor_execution_control",
    ROOT / ".agents/skills/run-refactor-implementation-acceptance/scripts/execution_control.py",
)
from skill_input_consumption import sha256_bytes
finalizer = load(
    "successor_deterministic_finalization",
    ROOT / ".agents/skills/run-refactor-implementation-acceptance/scripts/deterministic_finalization.py",
)


def test_canonical_json_identity_is_not_raw_bytes():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "artifact.json"
        path.write_text('{"b": 2, "a": 1}\n', encoding="utf-8")
        canonical = execution.artifact_identity_hash(path)
        raw = sha256_bytes(path.read_bytes())
        assert canonical != raw
        path.write_text('{"a":1,"b":2}', encoding="utf-8")
        assert execution.artifact_identity_hash(path) == canonical


def test_repository_artifact_rejects_stale_identity():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        path = root / "context.json"
        path.write_text('{"a": 1}\n', encoding="utf-8")
        try:
            execution._read_repository_artifact(root, "context.json", "sha256:" + "0" * 64)
        except execution.ControlError as error:
            assert "stale" in str(error)
        else:
            raise AssertionError("stale repository artifact was accepted")


def test_skill_input_custody_rejects_stale_and_mismatch():
    with tempfile.TemporaryDirectory() as directory:
        run = Path(directory)
        artifact = run / "skill-input.json"
        artifact.write_text('{"value": 1}\n', encoding="utf-8")
        state = {
            "skillInputBindingHash": "sha256:" + "1" * 64,
            "skillInputContextHash": "sha256:" + "0" * 64,
            "skillInputContextPath": "skill-input.json",
            "skillInputContextSourcePath": "source.json",
        }
        try:
            execution._verify_skill_input_custody(run, state)
        except execution.ControlError as error:
            assert "stale" in str(error)
        else:
            raise AssertionError("stale Skill-input custody was accepted")


def _finalizer_fixture(stdout: str):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        run = root / "run"
        run.mkdir()
        (run / "acceptance-events.jsonl").write_text("", encoding="utf-8")
        candidate = {"files": [], "status": "complete"}
        baseline = {"files": [], "status": "complete"}
        input_value = {
            "target": str(root),
            "baseline_content_manifest_path": "baseline.json",
            "candidate_content_manifest_path": "candidate.json",
            "affected_consumer_refs": [],
            "code_review_policy_hash": "sha256:" + "2" * 64,
        }
        prepared = {
            "schemaVersion": "acceptance-run-input.v1",
            "authorizes": [],
            "input": input_value,
            "inputHash": finalizer.canonical_hash(input_value),
            "candidateCustody": {"candidate": "same"},
        }
        state = {"runId": "acceptance-8-18-successor", "runInputHash": prepared["inputHash"], "contractHash": "sha256:" + "3" * 64}
        (run / "run-state.json").write_text("{}", encoding="utf-8")
        (root / "baseline.json").write_text("{}", encoding="utf-8")
        (root / "candidate.json").write_text("{}", encoding="utf-8")
        original = {
            "_load": finalizer._load,
            "validate_run_input": finalizer.validate_run_input,
            "validate_baseline_manifest": finalizer.validate_baseline_manifest,
            "validate_candidate_manifest": finalizer.validate_candidate_manifest,
            "verify_manifest_bytes": finalizer.verify_manifest_bytes,
            "_completed_receipts": finalizer._completed_receipts,
        }
        finalizer._load = lambda path: state if path.name == "run-state.json" else prepared if path.name == "prepared.json" else baseline
        finalizer.validate_run_input = lambda value: None
        finalizer.validate_baseline_manifest = lambda value: None
        finalizer.validate_candidate_manifest = lambda value, base: None
        finalizer.verify_manifest_bytes = lambda target, value, base, cand: prepared["candidateCustody"]
        finalizer._completed_receipts = lambda *args: [{
            "commandId": "terminal-full",
            "receipt": {"path": "terminal.json", "sha256": "sha256:" + "4" * 64},
            "receiptValue": {"processResult": {"stdout": stdout}},
        }]
        try:
            return finalizer.finalize_deterministic_run(root, run, run / "prepared.json", [], {"commands": []})
        finally:
            for name, value in original.items():
                setattr(finalizer, name, value)


def test_multiline_terminal_json_is_parsed():
    result = _finalizer_fixture(
        '{\n  "schema_version": "quick-dev-implementation-complete.v1",\n'
        '  "predicate": "implementation-complete",\n  "status": "pass",\n'
        '  "authorizes": ["implementation-complete"]\n}'
    )
    assert result["authorizes"] == ["acceptance-passed"]


def test_non_json_and_invalid_tail_are_rejected():
    for stdout in ("not json", '{"schema_version": "wrong"}\nnot json'):
        try:
            _finalizer_fixture(stdout)
        except finalizer.InputError as error:
            assert "machine-readable" in str(error) or "implementation-complete" in str(error)
        else:
            raise AssertionError("invalid terminal JSON was accepted")


if __name__ == "__main__":
    for name in sorted(globals()):
        if name.startswith("test_"):
            globals()[name]()
    print(json.dumps({"status": "passed", "tests": 6}, sort_keys=True))
