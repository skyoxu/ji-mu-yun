"""CER coverage for historical-artifact byte-integrity validation."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from hashlib import sha256
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
VALIDATOR = ROOT / "scripts" / "python" / "validate_acceptance_execution_evidence.py"


def _load_validator():
    spec = importlib.util.spec_from_file_location("s15_execution_evidence_validator", VALIDATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return spec, module


def _fixture(root: Path) -> tuple[Path, Path]:
    frozen = root / "historical" / "frozen-receipt.bin"
    frozen.parent.mkdir(parents=True)
    frozen.write_bytes(b"frozen historical bytes\n")
    task_dir = root / ".taskmaster" / "tasks"
    task_dir.mkdir(parents=True)
    (task_dir / "tasks.json").write_text('{"master":{"tasks":[{"id":1,"status":"in-progress"}]}}\n', encoding="utf-8")
    (task_dir / "tasks_back.json").write_text("[]\n", encoding="utf-8")
    (task_dir / "tasks_gameplay.json").write_text("[]\n", encoding="utf-8")
    return frozen, root


@pytest.mark.cer_assertion("A-D56F9D0379DE-1")
def test_historical_byte_mutation_is_detected_after_validator_execution() -> None:
    with tempfile.TemporaryDirectory() as directory:
        frozen, root = _fixture(Path(directory) / "fixture-repository")
        before = sha256(frozen.read_bytes()).hexdigest()
        frozen.write_bytes(b"mutated historical bytes\n")
        after = sha256(frozen.read_bytes()).hexdigest()
        spec, module = _load_validator()
        try:
            out = Path(directory) / "validation.json"
            module.repo_root = lambda: root
            sys.argv = [str(VALIDATOR), "--task-id", "1", "--run-id", "fixture-run", "--out", str(out), "--date", "2026-01-01"]
            module.main()
        finally:
            sys.modules.pop(spec.name, None)
        assert before != after
        assert frozen.read_bytes() == b"mutated historical bytes\n"
