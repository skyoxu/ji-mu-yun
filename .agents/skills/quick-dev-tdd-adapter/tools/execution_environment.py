"""ADR-0041: one environment boundary for controlled Quick Dev pytest.

The call identifier belongs to the external executor, not the tested program.
Remove it from the child as well as its fingerprint; keep every other input.
"""
from workflow_unit_budget import execution_environment as _supervised_environment

ENVIRONMENT_SCHEMA = "quick-dev.pytest-environment.v2"


def execution_environment():
    environment = _supervised_environment()
    environment.pop("CODEX_TOOL_CALL_ID", None)
    return environment
