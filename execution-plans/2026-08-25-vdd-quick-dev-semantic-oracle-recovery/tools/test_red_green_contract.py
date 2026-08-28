from pathlib import Path
import importlib.util


def test_plan_red_green_contract_is_machine_checked() -> None:
    path = Path(__file__).with_name("validate_red_green_contract.py")
    spec = importlib.util.spec_from_file_location("red_green_contract", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    ok, errors = module.validate(path.parent.parent)
    assert ok, errors
