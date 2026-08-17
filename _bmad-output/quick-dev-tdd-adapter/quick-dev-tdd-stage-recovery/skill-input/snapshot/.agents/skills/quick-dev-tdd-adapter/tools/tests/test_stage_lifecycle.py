import importlib.util
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_red_only_stage_runner_is_available():
    driver = _load("loop_plan_directory")
    assert callable(driver.run_red_only)
