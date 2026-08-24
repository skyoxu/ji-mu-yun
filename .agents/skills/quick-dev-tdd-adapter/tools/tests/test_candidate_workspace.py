from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
MODULE_PATH = ROOT / ".agents/skills/quick-dev-tdd-adapter/tools/candidate_workspace.py"


def _load():
    spec = importlib.util.spec_from_file_location("candidate_workspace", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("candidate workspace module is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_lifecycle():
    path = ROOT / ".agents/skills/quick-dev-tdd-adapter/tools/run_slice_lifecycle.py"
    spec = importlib.util.spec_from_file_location("run_slice_lifecycle", path)
    if spec is None or spec.loader is None:
        raise AssertionError("lifecycle module is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_materialize_candidate_preserves_source_and_applies_overrides(tmp_path: Path):
    module = _load()
    source = tmp_path / "source"
    candidate = tmp_path / "candidate"
    (source / "plan").mkdir(parents=True)
    (source / "scripts").mkdir()
    (source / "plan" / "__pycache__").mkdir()
    (source / "plan" / "__pycache__" / "cached.pyc").write_bytes(b"cache")
    (source / "plan" / "receipt.json").write_text('{"status":"pass"}\n', encoding="utf-8")
    (source / "scripts" / "validator.py").write_text("print('ok')\n", encoding="utf-8")

    module.materialize(source, candidate, ["plan", "scripts"], remove=["plan/receipt.json"])

    assert not (candidate / "plan" / "receipt.json").exists()
    assert not (candidate / "plan" / "__pycache__").exists()
    assert (candidate / "scripts" / "validator.py").read_text(encoding="utf-8") == "print('ok')\n"
    assert (source / "plan" / "receipt.json").is_file()


def test_lifecycle_accepts_a_safe_candidate_cwd(tmp_path: Path):
    lifecycle = _load_lifecycle()
    descriptor = tmp_path / "command.json"
    descriptor.write_text(json.dumps({
            "id": "candidate",
            "executable": "py",
            "argv": ["-3", "-B", "validator.py"],
            "cwd": "candidate",
            "timeout_seconds": 10,
            "shell": False,
        }), encoding="utf-8")
    command = lifecycle._command(str(descriptor))
    assert command["cwd"] == "candidate"


def test_materialize_accepts_overlapping_explicit_paths(tmp_path: Path):
    module = _load()
    source = tmp_path / "source"
    candidate = tmp_path / "candidate"
    (source / "plan" / "tools").mkdir(parents=True)
    (source / "plan" / "implementation-contract.v1.json").write_text("{}\n", encoding="utf-8")
    (source / "plan" / "tools" / "validator.py").write_text("pass\n", encoding="utf-8")

    module.materialize(source, candidate, ["plan", "plan/tools"])

    assert (candidate / "plan" / "implementation-contract.v1.json").is_file()
    assert (candidate / "plan" / "tools" / "validator.py").is_file()


def test_materialize_rejects_generated_run_evidence(tmp_path: Path):
    module = _load()
    source = tmp_path / "source"
    candidate = tmp_path / "candidate"
    generated = source / "execution-plans" / "target" / "skill-input" / "receipt.json"
    generated.parent.mkdir(parents=True)
    generated.write_text("{}\n", encoding="utf-8")

    try:
        module.materialize(source, candidate, ["execution-plans/target/skill-input/receipt.json"])
    except ValueError as exc:
        assert "candidate content" in str(exc)
    else:
        raise AssertionError("generated evidence unexpectedly entered a candidate workspace")
