import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
PLAN = ROOT / "execution-plans/2026-08-18-toolchain-workflow-repair"


def test_authorization_successor_binds_current_control_closure():
    receipt = json.loads((PLAN / "implementation-authorization-receipt.successor.v1.json").read_text(encoding="utf-8"))
    required = {
        "implementation_contract", "command_registry", "authority_manifest",
        "knowledge_context_freeze", "skill_input_receipt", "skill_input_request",
        "plan_validation", "repair_closure", "bootstrap_preexisting_delta",
        "candidate_manifest", "validate_all", "terminal_validator",
        "immutable_predecessor",
    }
    assert required <= set(receipt)
    assert receipt["decision"]["owner"] == "maintainer"
    assert receipt["authorizes"] == ["implementation-authorized"]
