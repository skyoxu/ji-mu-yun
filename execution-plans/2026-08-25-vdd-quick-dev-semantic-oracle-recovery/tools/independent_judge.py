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
    if not isinstance(observation.get("acceptance_assertions"), dict) or not observation["acceptance_assertions"]:
        return False, "JUDGE-INDEPENDENCE-UNPROVEN"
    if (not isinstance(receipt.get("descriptor_hash"), str) or not receipt["descriptor_hash"].startswith("sha256:")
            or not isinstance(receipt.get("candidate_hash"), str) or not receipt["candidate_hash"].startswith("sha256:")):
        return False, "JUDGE-INDEPENDENCE-UNPROVEN"
    if receipt.get("actual_argv") != observation.get("descriptor_argv"):
        return False, "JUDGE-INDEPENDENCE-RED"
    if observation.get("expected_exit") == "nonzero" and (receipt.get("exit_code", 0) == 0 or observation.get("executions", 0) < 1):
        return False, "JUDGE-INDEPENDENCE-UNPROVEN"
    return True, ""
