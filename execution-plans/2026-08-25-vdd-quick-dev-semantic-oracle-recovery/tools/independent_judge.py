"""Independent receipt/observation relationship validator."""
from __future__ import annotations

from typing import Any


def validate_judge(receipt: dict[str, Any], observation: dict[str, Any]) -> tuple[bool, str]:
    required = {"executor_id", "judge_id", "descriptor_hash", "candidate_hash", "run_id", "exit_code", "actual_argv"}
    if not isinstance(receipt, dict) or not required.issubset(receipt):
        return False, "JUDGE-INDEPENDENCE-RED"
    if receipt["executor_id"] == receipt["judge_id"] or receipt["judge_id"] in {"sut", "candidate"}:
        return False, "JUDGE-INDEPENDENCE-RED"
    if not isinstance(observation, dict) or observation.get("run_id") != receipt["run_id"]:
        return False, "JUDGE-INDEPENDENCE-RED"
    assertions = observation.get("acceptance_assertions")
    if (not isinstance(assertions, dict) or not assertions
            or any(not isinstance(acceptance_id, str) or not acceptance_id
                   or not isinstance(assertion, str) or not assertion
                   for acceptance_id, assertion in assertions.items())):
        return False, "JUDGE-INDEPENDENCE-UNPROVEN"
    if (not isinstance(receipt.get("descriptor_hash"), str) or not receipt["descriptor_hash"].startswith("sha256:")
            or not isinstance(receipt.get("candidate_hash"), str) or not receipt["candidate_hash"].startswith("sha256:")):
        return False, "JUDGE-INDEPENDENCE-UNPROVEN"
    if receipt.get("actual_argv") != observation.get("descriptor_argv"):
        return False, "JUDGE-INDEPENDENCE-RED"
    if observation.get("descriptor_hash") != receipt.get("descriptor_hash"):
        return False, "JUDGE-INDEPENDENCE-UNPROVEN"
    if observation.get("candidate_hash") != receipt.get("candidate_hash"):
        return False, "JUDGE-INDEPENDENCE-UNPROVEN"
    if observation.get("executions", 0) < 1:
        return False, "JUDGE-INDEPENDENCE-UNPROVEN"
    if observation.get("expected_exit") == "zero" and receipt.get("exit_code") != 0:
        return False, "JUDGE-INDEPENDENCE-UNPROVEN"
    if observation.get("expected_exit") == "nonzero" and receipt.get("exit_code") == 0:
        return False, "JUDGE-INDEPENDENCE-UNPROVEN"
    if observation.get("executions", 0) < 1:
        return False, "JUDGE-INDEPENDENCE-UNPROVEN"
    expected = observation.get("expected_exit")
    if expected == "zero" and receipt.get("exit_code") != 0:
        return False, "JUDGE-INDEPENDENCE-UNPROVEN"
    if expected == "nonzero" and receipt.get("exit_code") == 0:
        return False, "JUDGE-INDEPENDENCE-UNPROVEN"
    if observation.get("expected_exit") == "nonzero" and (receipt.get("exit_code", 0) == 0 or observation.get("executions", 0) < 1):
        return False, "JUDGE-INDEPENDENCE-UNPROVEN"
    return True, ""
