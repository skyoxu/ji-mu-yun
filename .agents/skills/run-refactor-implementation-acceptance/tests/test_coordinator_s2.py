from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def test_s2_recovery_projection_has_latest_successor_pointer(tmp_path: Path) -> None:
    import acceptance_cli
    from test_coordinator import _request
    source, output, _ = _request(tmp_path)
    result = acceptance_cli.run_coordinator(str(source), str(output))
    result = result
    assert result["recovery"]["successorReason"] == "same-binding-replay"
    assert result["recovery"]["latestSuccessorPointer"].startswith("sha256:")
