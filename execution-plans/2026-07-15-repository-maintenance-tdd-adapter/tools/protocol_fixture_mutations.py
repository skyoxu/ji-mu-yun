from __future__ import annotations

import copy
from typing import Any


def apply_protocol_mutations(bundle: dict[str, Any], mutations: list[dict[str, Any]]) -> dict[str, Any]:
    result = copy.deepcopy(bundle)
    for mutation in mutations:
        parts = [part.replace("~1", "/").replace("~0", "~") for part in mutation["path"].strip("/").split("/")]
        current: Any = result
        for part in parts[:-1]:
            current = current[int(part)] if isinstance(current, list) else current[part]
        key = parts[-1]
        if mutation["op"] == "replace":
            if isinstance(current, list):
                current[int(key)] = mutation["value"]
            else:
                current[key] = mutation["value"]
        elif mutation["op"] == "remove":
            if isinstance(current, list):
                del current[int(key)]
            else:
                del current[key]
        elif mutation["op"] == "add":
            if isinstance(current, list):
                current.append(mutation["value"]) if key == "-" else current.insert(int(key), mutation["value"])
            else:
                current[key] = mutation["value"]
        else:
            raise ValueError(f"unsupported mutation op: {mutation['op']}")
    return result
