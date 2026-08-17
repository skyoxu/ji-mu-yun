import importlib.util
from pathlib import Path
import sys


TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_red_only_stage_runner_is_available():
    driver = _load("loop_plan_directory")
    basis = driver.build_red_basis(
        {"id": "red", "executable": "py", "argv": [], "cwd": ".", "timeout_seconds": 1, "shell": False},
        {"test_selector": "tests/test_stage.py", "expected_failure_ids": ["QDR-S0-EXIT"]},
        {"head": "head-sha"}, "validator-sha", "contract-sha",
    )
    assert set(basis) == {"failure_intent", "test_selector", "contract_hash", "validator_hash", "pre_implementation_candidate"}
    assert basis["failure_intent"]["command_id"] == "red"
