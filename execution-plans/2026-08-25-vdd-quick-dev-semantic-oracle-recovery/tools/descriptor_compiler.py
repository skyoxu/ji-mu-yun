"""Descriptor owner for the Quick Dev boundary."""
from __future__ import annotations

import re
from typing import Any


def validate_descriptor(value: dict[str, Any]) -> tuple[bool, str]:
    required = {"target", "argv", "cwd", "timeout_seconds", "shell", "case_source_refs", "case_producer_ref"}
    if not isinstance(value, dict) or not required.issubset(value):
        return False, "QD-DESCRIPTOR-RED"
    if value.get("shell") is not False or not isinstance(value.get("argv"), list) or not value["argv"]:
        return False, "QD-DESCRIPTOR-RED"
    if not all(isinstance(item, str) and item for item in value["argv"]):
        return False, "QD-DESCRIPTOR-RED"
    if (not isinstance(value.get("case_source_refs"), list) or not value["case_source_refs"]
            or any(not isinstance(item, str) or not item.strip() for item in value["case_source_refs"])
            or not isinstance(value.get("case_producer_ref"), str) or not value["case_producer_ref"].strip()):
        return False, "QD-DESCRIPTOR-BINDING-INCOMPLETE"
    semantic_ref = value.get("semantic_artifact_ref")
    if (not isinstance(semantic_ref, dict)
            or set(semantic_ref) != {"path", "sha256", "producer", "slice_id", "run_id"}
            or semantic_ref.get("producer") != "vdd"
            or semantic_ref.get("slice_id") != "S1"
            or not all(isinstance(semantic_ref.get(key), str) and semantic_ref[key] for key in ("path", "sha256", "run_id"))):
        return False, "QD-DESCRIPTOR-BINDING-INCOMPLETE"
    if (not re.fullmatch(r"sha256:[0-9a-f]{64}", semantic_ref["sha256"])
            or not semantic_ref["run_id"].startswith("RUN-")
            or semantic_ref["path"].startswith(("/", "\\"))):
        return False, "QD-DESCRIPTOR-BINDING-INCOMPLETE"
    if not isinstance(value.get("timeout_seconds"), int) or value["timeout_seconds"] <= 0:
        return False, "QD-DESCRIPTOR-RED"
    return True, ""
