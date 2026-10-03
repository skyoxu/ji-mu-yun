from __future__ import annotations

import importlib

import pytest


@pytest.mark.cer_assertion("A-O-5A24A14515F4-frozen-historical-paths-unchanged")
def test_worker_delta_rejects_frozen_historical_path_rename() -> None:
    worker = importlib.import_module("worker_orchestrator")
    with pytest.raises(ValueError, match="write-set violation"):
        worker._validate_delta(
            ["historical/before.json", "historical/after.json"],
            allowed=["historical/after.json"],
            forbidden=[],
            label="red-author",
        )
