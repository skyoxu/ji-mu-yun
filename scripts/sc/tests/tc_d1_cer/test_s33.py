"""S34 CER checks for append-only repair evidence."""
from __future__ import annotations

from pathlib import Path
import shutil
import sys
import uuid

import pytest


TOOLS = Path(__file__).resolve().parents[4] / ".agents" / "skills" / "quick-dev-tdd-adapter" / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from runtime_evidence import create_immutable  # noqa: E402


ASSERTION = "A-FR5-REPAIR-EVIDENCE-APPEND"
FAILURE = "F-REPAIR-EVIDENCE-NONAPPEND"


def _receipt(store: Path, sequence: int, payload: bytes) -> Path:
    """Write one repair receipt through the production immutable writer."""
    return create_immutable(store / f"receipt-{sequence:04d}.bin", payload)


def _assert_behavior(condition: bool, detail: object) -> None:
    if not condition:
        print(f"FAILURE_ID:{FAILURE}")
    assert condition, detail


@pytest.fixture
def repair_store() -> Path:
    store = Path(__file__).parent / f".s34-repair-{uuid.uuid4().hex}"
    store.mkdir()
    try:
        yield store
    finally:
        shutil.rmtree(store, ignore_errors=True)


@pytest.mark.cer_assertion(ASSERTION)
def test_repair_evidence_append_preserves_historical_prefix(repair_store: Path) -> None:
    store = repair_store
    historical = [b"prior-1\n", b"prior-2\n"]
    for sequence, payload in enumerate(historical):
        _receipt(store, sequence, payload)

    before = [path.read_bytes() for path in sorted(store.glob("receipt-*.bin"))]
    _receipt(store, len(historical), b"new-receipt\n")
    after_paths = sorted(store.glob("receipt-*.bin"))
    after = [path.read_bytes() for path in after_paths]

    _assert_behavior(
        after[: len(before)] == before
        and after[len(before) :] == [b"new-receipt\n"]
        and [path.name for path in after_paths]
        == ["receipt-0000.bin", "receipt-0001.bin", "receipt-0002.bin"],
        {"before": before, "after": after, "paths": [path.name for path in after_paths]},
    )


@pytest.mark.cer_assertion(ASSERTION)
@pytest.mark.parametrize("sequence", [0, 1])
def test_repair_evidence_rejects_historical_prefix_mutation(repair_store: Path, sequence: int) -> None:
    store = repair_store
    _receipt(store, 0, b"prior-1\n")
    _receipt(store, 1, b"prior-2\n")
    before = [path.read_bytes() for path in sorted(store.glob("receipt-*.bin"))]

    rejected = False
    try:
        _receipt(store, sequence, b"tampered\n")
    except ValueError:
        rejected = True

    remaining = sorted(store.glob("receipt-*.bin"))
    _assert_behavior(
        rejected
        and [path.read_bytes() for path in remaining] == before
        and [path.name for path in remaining] == ["receipt-0000.bin", "receipt-0001.bin"],
        {"sequence": sequence, "before": before, "remaining": [path.name for path in remaining]},
    )
