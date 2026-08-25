from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "execution-plans/2026-08-24-phase-b-c-identity-isolation-workspace-recovery/tools/validate_all.py"
)
SPEC = spec_from_file_location("phase_b_validate_all", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_no_match_output_fails_even_when_process_exit_is_zero():
    output = "No test matches the given testcase filter FullyQualifiedName~Element"
    assert MODULE._test_output_failure(output, "") == "test-shard-no-tests-matched"


def test_passing_output_is_accepted():
    assert MODULE._test_output_failure("Passed! - Failed: 0, Passed: 1", "") is None
