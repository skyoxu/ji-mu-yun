import importlib.util
import json
from pathlib import Path
import sys
import tempfile


TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_staged_cutover_guard_is_available():
    driver = _load("loop_plan_directory")
    assert driver.staged_cutover_guard(
        Path.cwd(),
        Path("execution-plans/2026-08-17-quick-dev-tdd-stage-recovery"),
    ) is True
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / "repository"
        outside = Path(temp) / "outside"
        outside.mkdir()
        (outside / "implementation-contract.v1.json").write_text("{}", encoding="utf-8")
        assert driver.staged_cutover_guard(root, outside) is False


def test_8_17_dogfood_is_bound_to_staged_runner():
    plan = Path.cwd() / "execution-plans" / "2026-08-17-quick-dev-tdd-stage-recovery"
    registry = json.loads((plan / "command-registry.v1.json").read_text(encoding="utf-8"))
    command = next(item for item in registry["commands"] if item["id"] == "dogfood-8-17")
    assert command["argv"] == ["-3", "-B", "execution-plans/2026-08-17-quick-dev-tdd-stage-recovery/tools/dogfood_runner.py"]
