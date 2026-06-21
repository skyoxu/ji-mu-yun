#!/usr/bin/env python3
"""Compatibility aggregate for prototype workflow router tests."""
from __future__ import annotations

from scripts.python.tests.test_prototype_workflow_router_intake import *  # noqa: F401,F403
from scripts.python.tests.test_prototype_workflow_router_day4_implementation import *  # noqa: F401,F403
from scripts.python.tests.test_prototype_workflow_router_state_routing import *  # noqa: F401,F403
from scripts.python.tests.test_prototype_workflow_router_day4_validation import *  # noqa: F401,F403
from scripts.python.tests.test_prototype_workflow_router_packaging_completion import *  # noqa: F401,F403
from scripts.python.tests.test_prototype_workflow_router_game_type_enrichment import *  # noqa: F401,F403
from scripts.python.tests.test_prototype_workflow_router_confirmed_workflow import *  # noqa: F401,F403
from scripts.python.tests.test_prototype_workflow_router_dev_cli import *  # noqa: F401,F403


if __name__ == "__main__":
    import unittest

    unittest.main()
