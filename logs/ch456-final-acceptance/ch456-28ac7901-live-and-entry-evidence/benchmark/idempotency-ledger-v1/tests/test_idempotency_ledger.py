import importlib.util
import json
from pathlib import Path

import pytest


TEST_DIRECTORY = Path(__file__).resolve().parent
PRODUCTION_OWNER = TEST_DIRECTORY.parent / "src" / "idempotency_ledger.py"


def _load_production_ledger():
    spec = importlib.util.spec_from_file_location("idempotency_ledger", PRODUCTION_OWNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.IdempotencyLedger


def _assert_with_failure_id(actual, expected, failure_id):
    if actual != expected:
        print(f"FAILURE_ID:{failure_id}")
    assert actual == expected


@pytest.fixture
def cases():
    return json.loads((TEST_DIRECTORY / "cases.json").read_text(encoding="utf-8"))


@pytest.fixture
def ledger():
    return _load_production_ledger()()


@pytest.mark.parametrize(
    "scenario",
    ["active_claim", "invalid_ttl", "inactive_release"],
)
def test_fr_301_common_ledger_selector(ledger, cases, scenario):
    if scenario == "active_claim":
        duplicate_case = cases["duplicate"]
        ledger.claim(**duplicate_case)
        result = ledger.claim(
            duplicate_case["key"],
            duplicate_case["now"] + 1,
            duplicate_case["ttl_seconds"],
        )
        _assert_with_failure_id(result, "duplicate", "ACTIVE_CLAIM_ACCEPTED")
    elif scenario == "invalid_ttl":
        key = "invalid-ttl"
        result = ledger.claim(key, now=5, ttl_seconds=cases["invalid_ttl"])
        _assert_with_failure_id(result, "invalid-ttl", "INVALID_TTL_ACCEPTED")

        subsequent_claim = ledger.claim(key, now=5, ttl_seconds=10)
        _assert_with_failure_id(
            subsequent_claim,
            "accepted",
            "INVALID_TTL_ACCEPTED",
        )
    else:
        result = ledger.release(cases["missing_release"])
        _assert_with_failure_id(result, "not-found", "INACTIVE_RELEASE_SUCCEEDS")
