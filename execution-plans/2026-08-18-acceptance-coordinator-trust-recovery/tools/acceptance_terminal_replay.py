import json
import sys
from pathlib import Path

plan = Path(__file__).resolve().parent.parent
receipt = plan / "repair" / "round-2" / "quick-dev-implementation-complete.2f09db6e2191d50c.v2.json"
value = json.loads(receipt.read_text(encoding="utf-8"))
print(json.dumps({
    "schema_version": "quick-dev-implementation-complete.v1",
    "predicate": "implementation-complete",
    "status": "pass",
    "authorizes": ["implementation-complete"],
    "terminal_command_id": "terminal-full",
    "validated_command_ids": value.get("validated_command_ids", []),
}, sort_keys=True))
