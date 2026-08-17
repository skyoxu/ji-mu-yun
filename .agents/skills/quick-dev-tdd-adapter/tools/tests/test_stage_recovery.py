import importlib.util
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_router_recognizes_a_current_red_handoff():
    router = _load("route_plan_directory")
    assert callable(router.current_red_handoff)
