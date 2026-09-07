"""ADR-0041: critical mutation corpora have no tolerated leakage."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
METRICS = [
    ("vdd/evaluate_semantic_chain_mutations.py", "audit_bundle", "mapping"),
    ("vdd/evaluate_agent_context_mutations.py", "validate_semantic_bundle", "tuple"),
    ("quick_dev/evaluate_detached_mutations.py", "validate_detached_bundle", "tuple"),
]


def _load(relative):
    path = ROOT / "scripts" / relative
    spec = importlib.util.spec_from_file_location(path.stem + "_strict_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("relative,seam,shape", METRICS)
def test_each_real_corpus_passes_with_all_mutations_rejected(relative, seam, shape):
    result = _load(relative).evaluate()
    assert result["baseline_valid"] is True
    assert result["threshold_passed"] is True


@pytest.mark.parametrize("relative,seam,shape", METRICS)
def test_one_leaked_mutation_blocks_the_producer(relative, seam, shape, monkeypatch):
    module = _load(relative)
    original = getattr(module, seam)
    calls = 0

    def leak_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        result = original(*args, **kwargs)
        # Keep the real positive baseline; simulate one missed negative case.
        if calls == 2:
            return {**result, "valid": True} if shape == "mapping" else (True, [])
        return result

    monkeypatch.setattr(module, seam, leak_once)
    result = module.evaluate()
    assert result["baseline_valid"] is True
    assert result["threshold_passed"] is False
