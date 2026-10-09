"""Current native replay fixtures; historical Matrix inputs stay unchanged.

Accepted ADR-0058 owns the v3 execution and non-authorizing boundaries.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from scripts.sc import skill_replay_runtime as runtime


@pytest.fixture(scope="session")
def native_skill_replay_matrix():
    from scripts.sc import skill_package_replay as replay
    root = Path(__file__).resolve().parents[4]
    (root / "logs").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root / "logs", prefix="cer-native-matrix-") as directory:
        path = Path(directory) / "matrix.json"
        matrix = replay.runtime.prepare_matrix(root, replay.PRIMARY_TARGET, replay.PRIMARY_CAPABILITY,
                                               replay.runtime.TRUST_BASELINE, path.relative_to(root).as_posix())
        result = runtime.capture_process([sys.executable, "-X", "utf8", "-B", str(root / "scripts/sc/skill_package_replay.py"),
                                 "replay-matrix", "--matrix", path.relative_to(root).as_posix()],
                                root, timeout=150)
        assert result.returncode == 0, result.stdout + result.stderr
        yield matrix, json.loads(result.stdout)


@pytest.fixture
def native_matrix_rejection():
    """Execute a current v3 fault input through the real CLI, without mocks."""
    root = Path(__file__).resolve().parents[4]

    def run(matrix):
        with tempfile.TemporaryDirectory(dir=root / "logs", prefix="cer-matrix-fault-") as directory:
            path = Path(directory) / "matrix.json"
            path.write_text(json.dumps(matrix), encoding="utf-8", newline="\n")
            result = runtime.capture_process([sys.executable, "-X", "utf8", "-B", str(root / "scripts/sc/skill_package_replay.py"),
                                     "replay-matrix", "--matrix", path.relative_to(root).as_posix()],
                                    root, timeout=150)
            receipt = json.loads(result.stdout)
            assert receipt.get("authorizes") == []
            return result.returncode, receipt

    return run
