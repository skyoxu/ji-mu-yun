from __future__ import annotations

import os
import re

import pytest


_CHAPTER_NODE = re.compile(r"(?:^|[^a-z0-9])chapter[_-]?[2-7](?:[^a-z0-9]|$)", re.IGNORECASE)
_LEGACY_WORKFLOW_FILES = {
    "test_chapter3_task_generation.py",
    "test_chapter6_recovery_common.py",
    "test_chapter6_route.py",
    "test_chapter7_ui_wiring.py",
    "test_run_single_task_chapter6_lane.py",
}


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Keep repository-local workflow.md/Chapter 2-7 tests opt-in."""
    if os.environ.get("JIMUYUN_RUN_LEGACY_WORKFLOW_TESTS") == "1":
        return
    skip = pytest.mark.skip(
        reason="legacy workflow.md/Chapter 2-7 coverage is opt-in; set JIMUYUN_RUN_LEGACY_WORKFLOW_TESTS=1"
    )
    for item in items:
        path_name = getattr(item, "path", None)
        filename = path_name.name if path_name is not None else ""
        if filename in _LEGACY_WORKFLOW_FILES or _CHAPTER_NODE.search(item.nodeid):
            item.add_marker(skip)
