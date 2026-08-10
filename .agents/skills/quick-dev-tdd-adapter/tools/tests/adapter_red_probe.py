from __future__ import annotations

import importlib.util
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("quick_dev_tdd_adapter", TOOLS / "adapter.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("adapter module is unavailable")
ADAPTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADAPTER)


def main() -> int:
    contract = {
        "backend": {"hidden_state": False},
        "command_registry": "schemas/command-registry.v1.json",
        "slices": [{"slice_id": "RMAP-S2", "allowed_changes": {"production": [], "tests": [], "documentation": []}}],
    }
    prepared = ADAPTER._prepare_core(contract, "RMAP-S2", {"contract_hash": "sha256:contract", "validator_hash": "sha256:validator"})
    result = ADAPTER.transition(prepared, "green", {"exit_code": 0, "changed_paths": []})
    rule_id = result.get("diagnostic", {}).get("rule_id")
    print(rule_id or "RMAP-ADAPTER-RED-PROBE-UNEXPECTED")
    return 1 if rule_id == "RMAP-TDD-RED-NOT-OBSERVED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
