import json
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from idempotency_ledger import IdempotencyLedger


@pytest.fixture(scope="module")
def cases():
    return json.loads((Path(__file__).with_name("cases.json")).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("scenario", "failure_id"),
    [
        ("active_duplicate", "ACTIVE_CLAIM_DUPLICATE"),
        ("invalid_ttl", "INVALID_TTL_NO_RESERVATION"),
        ("missing_release", "RELEASE_NOT_FOUND"),
    ],
)
def test_idempotency_ledger_behaviors(cases, scenario, failure_id):
    ledger = IdempotencyLedger()

    if scenario == "active_duplicate":
        duplicate = cases["duplicate"]
        assert ledger.claim(**duplicate) == "accepted"
        result = ledger.claim(**duplicate)
        expected = "duplicate"
    elif scenario == "invalid_ttl":
        key = "invalid-ttl-key"
        result = (
            ledger.claim(key, now=5, ttl_seconds=cases["invalid_ttl"]),
            ledger.claim(key, now=5, ttl_seconds=10),
        )
        expected = ("invalid-ttl", "accepted")
    else:
        result = ledger.release(cases["missing_release"])
        expected = "not-found"

    print(f"FAILURE_ID:{failure_id}")
    assert result == expected
