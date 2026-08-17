import importlib.util
import json
from pathlib import Path
import tempfile


TOOLS = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_router_recognizes_a_current_red_handoff():
    router = _load("route_plan_directory")
    assert router.next_stage_action(["red"]) == "green"


def test_persisted_stage_router_requires_each_boundary():
    driver = _load("loop_plan_directory")
    with tempfile.TemporaryDirectory() as temp:
        run = Path(temp) / "RUN-001"
        observations = run / "observations"
        observations.mkdir(parents=True)
        (run / "stage-state.json").write_text(json.dumps({"stage": "red"}), encoding="utf-8")
        (observations / "red-observed.json").write_text("{}", encoding="utf-8")
        (run / "red-basis.v1.json").write_text("{}", encoding="utf-8")
        assert driver.route_staged_run(run) == "green"
        (run / "stage-state.json").write_text(json.dumps({"stage": "green"}), encoding="utf-8")
        (observations / "green-observed.json").write_text("{}", encoding="utf-8")
        assert driver.route_staged_run(run) == "refactor"
        (run / "stage-state.json").write_text(json.dumps({"stage": "refactor"}), encoding="utf-8")
        (observations / "refactor-observed.json").write_text("{}", encoding="utf-8")
        assert driver.route_staged_run(run) == "slice-terminal"
        (run / "slice-ready-result.json").write_text("{}", encoding="utf-8")
        assert driver.route_staged_run(run) is None
