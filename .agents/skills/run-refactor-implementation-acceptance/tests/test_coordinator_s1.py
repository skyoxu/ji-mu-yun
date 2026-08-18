from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def test_s1_route_contains_machine_projection_facts(tmp_path: Path) -> None:
    import acceptance_cli
    from test_coordinator import _request
    source, output, _ = _request(tmp_path)
    result = acceptance_cli.run_coordinator(str(source), str(output))
    assert result["routeProjection"]["sourceReadSetHash"].startswith("sha256:")
