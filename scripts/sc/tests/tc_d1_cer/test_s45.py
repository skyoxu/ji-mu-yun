from __future__ import annotations
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
ROUTER_PATH = ROOT / ".agents" / "skills" / "quick-dev-tdd-adapter" / "tools" / "current_router.py"


def _load_current_router():
    spec = importlib.util.spec_from_file_location("s45_current_router", ROUTER_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Unable to load current router from {ROUTER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assert_behavior(condition: bool, detail: object) -> None:
    if not condition:
        print("FAILURE_ID:FR12-DRIFT-RESULT-MUST-NOT-REMAIN-CURRENT")
    assert condition, detail


@pytest.mark.cer_assertion("FR12-UNEXPLAINED-INPUT-DRIFT-STALE-OR-CLOSED")
def test_changed_current_snapshot_invalidates_replay_observation() -> None:
    router = _load_current_router()
    bundle = {
        "plan_id": "PLAN-7B2637C400E8",
        "slices": [{"slice_id": "S45", "execution_snapshot_paths": ["fixtures/result-input.json"]}],
    }
    previous_snapshot = "sha256:" + "a" * 64
    current_snapshot = "sha256:" + "b" * 64
    result = router.recommendation(
        bundle=bundle,
        slice_id="S45",
        state={"state": "preflight-passed"},
        changed_paths=["fixtures/result-input.json"],
        change_kinds=["selector_fixture_target_case_source"],
        profile="standard",
        observation_index=[
            {
                "observation_id": "OBS-S45-REPLAY",
                "slice_id": "S45",
                "stage": "red",
                "current_snapshot_sha256": previous_snapshot,
            }
        ],
        current_snapshot_sha256=current_snapshot,
    )

    _assert_behavior(
        result["invalidated_observations"] == ["OBS-S45-REPLAY"]
        and result["reusable_observations"] == []
        and result["recommended_action"] == "run-red"
        and "red" in result["invalidated_stages"],
        result,
    )
