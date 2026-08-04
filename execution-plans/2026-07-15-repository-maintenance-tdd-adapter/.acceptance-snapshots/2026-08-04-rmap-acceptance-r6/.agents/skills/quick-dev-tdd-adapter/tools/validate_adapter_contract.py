from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_ACTIONS = {"prepare", "red", "green", "refactor", "finalize-candidate", "status", "resume"}


def validate(contract: dict[str, Any]) -> list[str]:
    """Validate only the adapter-facing, non-authoritative contract boundary."""
    errors: list[str] = []
    backend = contract.get("backend")
    if not isinstance(backend, dict) or backend.get("hidden_state") is not False:
        errors.append("RMAP-PREPARE-INVALID")
    protocol = contract.get("protocol_artifacts")
    if not isinstance(protocol, dict) or protocol.get("context_layout") != "context/<capsule-id>" or protocol.get("attempt_layout") != "attempts/<attempt-id>":
        errors.append("RMAP-CAPSULE-CONTEXT")
    actions = set(contract.get("adapter_actions", []))
    if actions and not REQUIRED_ACTIONS.issubset(actions):
        errors.append("RMAP-PREPARE-INVALID")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("contract", type=Path)
    args = parser.parse_args()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    errors = validate(contract)
    print(json.dumps({"ok": not errors, "errors": errors}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
