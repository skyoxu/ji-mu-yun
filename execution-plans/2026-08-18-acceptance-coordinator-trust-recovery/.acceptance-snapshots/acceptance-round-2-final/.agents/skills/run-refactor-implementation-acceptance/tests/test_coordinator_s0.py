from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def test_s0_legacy_bundle_authority_is_not_a_current_input(tmp_path: Path) -> None:
    import acceptance_cli
    from test_coordinator import _legacy_request
    import pytest
    with pytest.raises(acceptance_cli.InputError, match="coordinator bundle is invalid"):
        acceptance_cli.run_coordinator(str(_legacy_request(tmp_path)), str(tmp_path / "result.json"))
