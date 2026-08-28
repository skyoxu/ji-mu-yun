from pathlib import Path
import importlib.util
import pytest


def test_terminal_rejects_missing_manifest() -> None:
    validator = Path(__file__).parent / "terminal_validator.py"
    spec = importlib.util.spec_from_file_location("terminal_validator", validator)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(ValueError, match="lineage"):
        module.write_manifest(Path(__file__).parent.parent, Path("missing-run"))
