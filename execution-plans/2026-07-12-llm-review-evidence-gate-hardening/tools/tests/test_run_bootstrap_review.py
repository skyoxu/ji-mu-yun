#!/usr/bin/env python3
"""Compatibility entry for the repository-owned Bootstrap Review tests."""

import importlib.util
from pathlib import Path


TEST_PATH = (
    Path(__file__).resolve().parents[3]
    / ".agents"
    / "skills"
    / "run-phase-bootstrap-review"
    / "tests"
    / "test_bootstrap_review.py"
)
SPEC = importlib.util.spec_from_file_location("bootstrap_review_skill_tests", TEST_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)

BootstrapReviewCliTests = MODULE.BootstrapReviewCliTests
